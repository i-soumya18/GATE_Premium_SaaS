#!/usr/bin/env python3

"""
Download official GATE Computer Science (CS) and
Data Science & Artificial Intelligence (DA) previous-year
question papers, rename them cleanly by year/session,
and generate a pyq_index.csv index file.

Sources:
    GATE 2026 official archive:
        https://gate2026.iitg.ac.in/download.html

    GATE 2026 official Master Question Papers:
        https://gate2026.iitg.ac.in/QPs-answer-keys.html

Coverage:
    CS -> 2007 to 2026
    DA -> 2024 to 2026

The 2007-2025 archive is provided by the official GATE 2026 site.
The 2026 papers are fetched separately from the official 2026
Master Question Paper page.
"""

from __future__ import annotations

import re
import csv
import sys
import time
import zipfile
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

DOWNLOAD_ROOT = Path("GATE_PYQs")

ARCHIVE_PAGE = "https://gate2026.iitg.ac.in/download.html"

MASTER_2026_PAGE = "https://gate2026.iitg.ac.in/QPs-answer-keys.html"

REQUEST_TIMEOUT = 60

# Set True if you also want official answer keys
DOWNLOAD_KEYS = True

# Temporary directory
TEMP_DIR = DOWNLOAD_ROOT / "_tmp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


# ============================================================
# HELPERS & PARSING LOGIC
# ============================================================

def log(msg: str) -> None:
    print(f"[GATE] {msg}")


def get_html(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def download_file(url: str, output: Path) -> None:
    """
    Stream a file safely to disk.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and output.stat().st_size > 0:
        log(f"Already exists: {output.name}")
        return

    log(f"Downloading: {url}")

    with requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        stream=True,
    ) as response:
        response.raise_for_status()

        with output.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    log(f"Saved: {output.name}")


def install_gdown() -> None:
    """
    Install gdown automatically when needed.
    """
    try:
        import gdown  # noqa: F401
        return
    except ImportError:
        log("gdown not installed. Installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "gdown"]
        )


def find_official_bulk_link() -> str:
    """
    Find the official Google Drive bulk-download link
    from the GATE 2026 download page.
    """
    html = get_html(ARCHIVE_PAGE)
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        if "bulk download" in text and "question papers" in text:
            return urljoin(ARCHIVE_PAGE, a["href"])

    raise RuntimeError(
        "Could not find official GATE bulk download link."
    )


def download_cs_da_zips(bulk_url: str) -> dict[str, Path]:
    """
    Query the bulk folder URL, locate CS.zip and DA.zip, and download only those.
    """
    install_gdown()
    import gdown

    log("Querying official bulk archive Google Drive folder...")
    files = gdown.download_folder(bulk_url, skip_download=True, quiet=True)

    zip_paths = {}
    for item in files:
        name = item.path.lower()
        if name == "cs.zip":
            output_path = TEMP_DIR / "CS.zip"
            log(f"Downloading CS archive (ID: {item.id})...")
            gdown.download(id=item.id, output=str(output_path), quiet=False)
            zip_paths["CS"] = output_path
        elif name == "da.zip":
            output_path = TEMP_DIR / "DA.zip"
            log(f"Downloading DA archive (ID: {item.id})...")
            gdown.download(id=item.id, output=str(output_path), quiet=False)
            zip_paths["DA"] = output_path

    if not zip_paths:
        raise RuntimeError("Could not find CS.zip or DA.zip in the bulk folder.")

    return zip_paths


def parse_paper_details(filename: str, subject_hint: str | None = None) -> tuple[str, int, int | None]:
    """
    Extract (subject, year, session) from a filename.
    Returns:
        subject (str): 'CS' or 'DA'
        year (int): 4-digit year
        session (int | None): 1, 2, or None (if single session)
    """
    name = Path(filename).name.lower()
    
    # Extract year
    year_match = re.search(r"(20\d{2})", name)
    if year_match:
        year = int(year_match.group(1))
    else:
        year = 2026
        
    # Determine subject
    if subject_hint:
        subject = subject_hint.upper()
    else:
        if "da" in name or "data science" in name or "artificial intelligence" in name:
            subject = "DA"
        else:
            subject = "CS"
            
    # Determine session
    session = None
    name_without_year = name.replace(str(year), "")
    
    if subject == "CS":
        if any(x in name_without_year for x in ["cs1", "cs-1", "cs_1", "session1", "session_1", "forenoon", "cs 1"]):
            session = 1
        elif any(x in name_without_year for x in ["cs2", "cs-2", "cs_2", "session2", "session_2", "afternoon", "cs 2"]):
            session = 2
        elif re.search(r"cs\s*1", name_without_year) or re.search(r"cs\s*-\s*1", name_without_year):
            session = 1
        elif re.search(r"cs\s*2", name_without_year) or re.search(r"cs\s*-\s*2", name_without_year):
            session = 2
            
    return subject, year, session


# ============================================================
# ANSWER KEY DISCOVERY
# ============================================================

def parse_key_details(url: str, text: str) -> tuple[str, int, int | None] | None:
    """
    Parse an answer key link to determine (subject, year, session).
    """
    path = urlparse(url).path.lower()
    text_lower = text.lower()
    
    # Extract year
    year_match = re.search(r"(20\d{2})", path + text_lower)
    year = int(year_match.group(1)) if year_match else 2026
    
    # Subject
    if "da" in path or "data science" in text_lower or "artificial intelligence" in text_lower:
        subject = "DA"
    elif "cs" in path or "computer science" in text_lower:
        subject = "CS"
    else:
        return None
        
    # Session
    session = None
    cleaned = (path + "_" + text_lower).replace(str(year), "")
    if any(x in cleaned for x in ["cs1", "cs-1", "cs_1", "session1", "session_1", "forenoon"]):
        session = 1
    elif any(x in cleaned for x in ["cs2", "cs-2", "cs_2", "session2", "session_2", "afternoon"]):
        session = 2
        
    return subject, year, session


def find_all_answer_keys() -> dict[tuple[str, int, int | None], str]:
    """
    Scrape the download page and the 2026 page to find all available answer keys.
    """
    keys = {}
    
    # Page 1: Historical download page
    try:
        html = get_html(ARCHIVE_PAGE)
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf"):
                text = a.get_text(" ", strip=True)
                url = urljoin(ARCHIVE_PAGE, href)
                url_lower = url.lower()
                text_lower = text.lower()
                
                is_key = False
                if "key" in text_lower or "answer" in text_lower:
                    is_key = True
                elif any(k in url_lower for k in ["key", "keys", "ans", "answer"]):
                    is_key = True
                    
                if is_key:
                    details = parse_key_details(url, text)
                    if details:
                        keys[details] = url
    except Exception as e:
        log(f"Warning: Failed to scrape answer keys from {ARCHIVE_PAGE}: {e}")

    # Page 2: 2026 QPs and keys page
    try:
        html_2026 = get_html(MASTER_2026_PAGE)
        soup_2026 = BeautifulSoup(html_2026, "html.parser")
        for a in soup_2026.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf"):
                text = a.get_text(" ", strip=True)
                url = urljoin(MASTER_2026_PAGE, href)
                url_lower = url.lower()
                text_lower = text.lower()
                
                if "key" in text_lower or "answer" in text_lower or "key" in url_lower or "answer" in url_lower:
                    details = parse_key_details(url, text)
                    if details:
                        keys[details] = url
    except Exception as e:
        log(f"Warning: Failed to scrape answer keys from {MASTER_2026_PAGE}: {e}")

    return keys


# ============================================================
# 2026 PAPERS DISCOVERY
# ============================================================

def find_2026_links() -> list[tuple[str, str]]:
    """
    Find official 2026 CS-1, CS-2 and DA question paper links.
    Returns:
        List of (paper_name, url)
    """
    html = get_html(MASTER_2026_PAGE)
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if not text:
            continue
        href = urljoin(MASTER_2026_PAGE, a["href"])
        lower_text = text.lower()
        lower_href = href.lower()

        # Ignore answer key links in this step
        if "key" in lower_text or "answer" in lower_text or "key" in lower_href or "answer" in lower_href:
            continue

        if "computer science" in lower_text or "cs-1" in lower_text or "cs1.pdf" in lower_href:
            if "cs-1" in lower_text or "cs1.pdf" in lower_href:
                results.append(("CS-1", href))
            elif "cs-2" in lower_text or "cs2.pdf" in lower_href:
                results.append(("CS-2", href))
        elif "data science" in lower_text or "da.pdf" in lower_href:
            results.append(("DA", href))

    # Remove duplicates
    seen = set()
    unique_results = []
    for name, url in results:
        if url not in seen:
            seen.add(url)
            unique_results.append((name, url))
            
    return unique_results


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    log("=======================================")
    log(" GATE CS + DA OFFICIAL PYQ DOWNLOADER")
    log("=======================================")

    # Scrape answer key URLs if enabled
    answer_keys_map = {}
    if DOWNLOAD_KEYS:
        log("Scraping available answer key links from GATE site...")
        answer_keys_map = find_all_answer_keys()
        log(f"Discovered {len(answer_keys_map)} official CS/DA answer key links.")

    # --------------------------------------------------------
    # STEP 1: Download CS & DA Zip Archives (Historical papers)
    # --------------------------------------------------------
    log("Finding official bulk archive Google Drive folder...")
    bulk_url = find_official_bulk_link()
    log(f"Official bulk archive folder: {bulk_url}")

    zip_paths = download_cs_da_zips(bulk_url)

    # --------------------------------------------------------
    # STEP 2: Extract & Rename CS + DA Papers
    # --------------------------------------------------------
    records = []

    for subject, zip_path in zip_paths.items():
        extract_dir = TEMP_DIR / f"extract_{subject}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        log(f"Extracting {subject} papers from archive...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Only extract PDFs
            pdf_members = [m for m in zf.namelist() if m.lower().endswith(".pdf")]
            for member in pdf_members:
                zf.extract(member, extract_dir)

        # Process extracted PDFs
        for pdf in extract_dir.rglob("*.pdf"):
            sub, year, session = parse_paper_details(pdf.name, subject_hint=subject)
            
            dest_dir = DOWNLOAD_ROOT / sub / str(year)
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Determine standardized name
            session_str = f"Session_{session}" if session is not None else ""
            if session_str:
                dest_name = f"GATE_{sub}_{year}_{session_str}.pdf"
            else:
                dest_name = f"GATE_{sub}_{year}.pdf"

            dest_path = dest_dir / dest_name
            shutil.copy2(pdf, dest_path)
            log(f"Organized: {sub} {year} {session_str or 'Single'} -> {dest_path.relative_to(DOWNLOAD_ROOT)}")

            # Process Answer Key if requested
            key_rel_path = ""
            if DOWNLOAD_KEYS:
                key_url = answer_keys_map.get((sub, year, session))
                if not key_url and session is not None:
                    # Fallback to merged/year-level key if no session-specific key exists
                    key_url = answer_keys_map.get((sub, year, None))
                if key_url:
                    key_name = dest_name.replace(".pdf", "_Answer_Key.pdf")
                    key_dest_path = dest_dir / key_name
                    log(f"Downloading key for {sub} {year}...")
                    try:
                        download_file(key_url, key_dest_path)
                        key_rel_path = str(key_dest_path.relative_to(DOWNLOAD_ROOT))
                    except Exception as e:
                        log(f"Failed to download key {key_url}: {e}")

            records.append({
                "subject": sub,
                "year": year,
                "session": f"Session {session}" if session is not None else "Single Session",
                "paper_path": str(dest_path.relative_to(DOWNLOAD_ROOT)),
                "key_path": key_rel_path
            })

    # --------------------------------------------------------
    # STEP 3: Download & Organize 2026 Papers
    # --------------------------------------------------------
    log("Downloading official GATE 2026 papers...")
    links_2026 = find_2026_links()

    for paper_name, url in links_2026:
        sub, year, session = parse_paper_details(paper_name)
        
        dest_dir = DOWNLOAD_ROOT / sub / str(year)
        dest_dir.mkdir(parents=True, exist_ok=True)

        session_str = f"Session_{session}" if session is not None else ""
        if session_str:
            dest_name = f"GATE_{sub}_{year}_{session_str}.pdf"
        else:
            dest_name = f"GATE_{sub}_{year}.pdf"

        dest_path = dest_dir / dest_name
        download_file(url, dest_path)

        # Process Answer Key if requested
        key_rel_path = ""
        if DOWNLOAD_KEYS:
            key_url = answer_keys_map.get((sub, year, session))
            if not key_url and session is not None:
                # Fallback to merged/year-level key if no session-specific key exists
                key_url = answer_keys_map.get((sub, year, None))
            if key_url:
                key_name = dest_name.replace(".pdf", "_Answer_Key.pdf")
                key_dest_path = dest_dir / key_name
                try:
                    download_file(key_url, key_dest_path)
                    key_rel_path = str(key_dest_path.relative_to(DOWNLOAD_ROOT))
                except Exception as e:
                    log(f"Failed to download key {key_url}: {e}")

        records.append({
            "subject": sub,
            "year": year,
            "session": f"Session {session}" if session is not None else "Single Session",
            "paper_path": str(dest_path.relative_to(DOWNLOAD_ROOT)),
            "key_path": key_rel_path
        })

    # --------------------------------------------------------
    # STEP 4: Generate CSV Index & README
    # --------------------------------------------------------
    # Sort records cleanly: CS first, then DA, then by year, then session
    def sort_key(r):
        sess_num = 0
        if "Session 1" in r["session"]:
            sess_num = 1
        elif "Session 2" in r["session"]:
            sess_num = 2
        return (r["subject"], r["year"], sess_num)

    records.sort(key=sort_key)

    csv_path = DOWNLOAD_ROOT / "pyq_index.csv"
    log(f"Generating index file: {csv_path.name}")
    
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["subject", "year", "session", "paper_path", "key_path"])
        writer.writeheader()
        writer.writerows(records)

    # Generate README
    readme_path = DOWNLOAD_ROOT / "README.md"
    readme_content = f"""# GATE CS & DA Previous Year Question Papers (PYQs)

Organized and indexed collection of official GATE question papers and answer keys.

## Metadata Index
All files are indexed inside [pyq_index.csv](pyq_index.csv) with the following headers:
- `subject`: CS (Computer Science) or DA (Data Science & AI)
- `year`: Exam year
- `session`: Session name (Session 1, Session 2, or Single Session)
- `paper_path`: Path to the question paper PDF relative to this folder
- `key_path`: Path to the answer key PDF (if downloaded) relative to this folder

## Directory Structure
```text
GATE_PYQs/
├── pyq_index.csv
├── README.md
├── CS/
│   ├── 2007/
│   │   └── GATE_CS_2007.pdf
│   ├── ...
│   └── 2026/
│       ├── GATE_CS_2026_Session_1.pdf
│       └── GATE_CS_2026_Session_2.pdf
└── DA/
    ├── 2024/
    │   └── GATE_DA_2024.pdf
    ├── ...
    └── 2026/
        └── GATE_DA_2026.pdf
```
"""
    readme_path.write_text(readme_content.strip() + "\n", encoding="utf-8")

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------
    try:
        shutil.rmtree(TEMP_DIR)
    except OSError:
        pass

    log("")
    log("=======================================")
    log(" DOWNLOAD AND ORGANIZATION COMPLETED!")
    log("=======================================")
    log(f"Papers & index are stored in: {DOWNLOAD_ROOT.resolve()}")
    log(f"Total Papers Organized: {len(records)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
