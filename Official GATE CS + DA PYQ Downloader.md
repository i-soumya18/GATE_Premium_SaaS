```python
#!/usr/bin/env python3

"""
Download official GATE Computer Science (CS) and
Data Science & Artificial Intelligence (DA) previous-year
question papers.

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
DOWNLOAD_KEYS = False

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
# HELPERS
# ============================================================

def log(msg: str) -> None:
    print(f"[GATE] {msg}")


def safe_filename(name: str) -> str:
    """
    Make filenames safe for Linux/Windows/macOS.
    """
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


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
        log(f"Already exists: {output}")
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

    log(f"Saved: {output}")


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


def download_google_drive(url: str, output: Path) -> None:
    """
    Download a Google Drive file using gdown.
    """
    install_gdown()

    import gdown

    if output.exists() and output.stat().st_size > 0:
        log(f"Archive already exists: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)

    log(f"Downloading Google Drive archive")
    log(f"URL: {url}")

    result = gdown.download(
        url=url,
        output=str(output),
        quiet=False,
        fuzzy=True,
    )

    if not result:
        raise RuntimeError(
            "Google Drive download failed. "
            "Try opening the official GATE archive manually."
        )


def extract_cs_da_from_archive(
    archive_path: Path,
    output_root: Path,
) -> None:
    """
    Extract only CS/DA papers from the official bulk archive.
    """

    extract_dir = TEMP_DIR / "archive_extract"

    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    extract_dir.mkdir(parents=True, exist_ok=True)

    log("Extracting official archive...")
    
    with zipfile.ZipFile(archive_path, "r") as zf:
        members = zf.namelist()

        selected = []

        for member in members:
            lower = member.lower()

            # We only want PDFs
            if not lower.endswith(".pdf"):
                continue

            # Ignore answer keys unless explicitly requested
            if not DOWNLOAD_KEYS and (
                "answer" in lower
                or "key" in lower
            ):
                continue

            # CS detection
            is_cs = bool(
                re.search(
                    r"(^|[/_\-\s])cs([_\-\s./]|$)",
                    lower
                )
                or "computer science" in lower
                or "computer_science" in lower
            )

            # DA detection
            is_da = bool(
                re.search(
                    r"(^|[/_\-\s])da([_\-\s./]|$)",
                    lower
                )
                or "data science" in lower
                or "data_science" in lower
                or "artificial intelligence" in lower
            )

            if is_cs or is_da:
                selected.append(member)

        log(f"Found {len(selected)} candidate CS/DA files")

        for member in selected:
            zf.extract(member, extract_dir)

    # Move selected files into clean year folders
    for pdf in extract_dir.rglob("*.pdf"):
        name = pdf.name

        year_match = re.search(r"(20\d{2})", str(pdf))
        year = year_match.group(1) if year_match else "unknown"

        lower = name.lower()
        lower_path = str(pdf).lower()

        if (
            "data science" in lower
            or "data_science" in lower
            or re.search(r"(^|[_\-\s])da([_\-\s.]|$)", lower)
            or "artificial intelligence" in lower_path
        ):
            subject = "DA"
        else:
            subject = "CS"

        destination_dir = output_root / subject / year
        destination_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = destination_dir / safe_filename(name)

        if destination.exists():
            log(f"Already extracted: {destination}")
            continue

        shutil.copy2(pdf, destination)

        log(f"Saved: {destination}")


def find_official_bulk_link() -> str:
    """
    Find the official Google Drive bulk-download link
    from the GATE 2026 download page.
    """

    html = get_html(ARCHIVE_PAGE)

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()

        if (
            "bulk download" in text
            and "question papers" in text
        ):
            href = urljoin(
                ARCHIVE_PAGE,
                a["href"]
            )

            return href

    raise RuntimeError(
        "Could not find official GATE bulk download link."
    )


def find_2026_links() -> dict[str, list[tuple[str, str]]]:
    """
    Find official 2026 CS/DA question paper links.

    Returns:

        {
            "CS": [
                ("CS-1", "..."),
                ("CS-2", "...")
            ],
            "DA": [
                ("DA", "...")
            ]
        }
    """

    html = get_html(MASTER_2026_PAGE)

    soup = BeautifulSoup(html, "html.parser")

    results = {
        "CS": [],
        "DA": [],
    }

    # Walk through anchors and inspect surrounding text
    for a in soup.find_all("a", href=True):

        text = a.get_text(" ", strip=True)

        if not text:
            continue

        href = urljoin(
            MASTER_2026_PAGE,
            a["href"]
        )

        lower = text.lower()

        # Ignore answer-key links when DOWNLOAD_KEYS=False
        if not DOWNLOAD_KEYS:
            if (
                "key" in lower
                or "answer" in lower
            ):
                continue

        # CS-1
        if "cs-1" in lower:
            results["CS"].append(
                ("CS-1", href)
            )

        # CS-2
        elif "cs-2" in lower:
            results["CS"].append(
                ("CS-2", href)
            )

        # DA
        elif re.fullmatch(r"da", lower):
            results["DA"].append(
                ("DA", href)
            )

    return results


def download_2026_papers() -> None:
    """
    Download official GATE 2026 CS-1, CS-2 and DA papers.
    """

    links = find_2026_links()

    for subject, subject_links in links.items():

        if not subject_links:
            log(f"No 2026 links found for {subject}")
            continue

        for paper_name, url in subject_links:

            destination_dir = (
                DOWNLOAD_ROOT
                / subject
                / "2026"
            )

            destination_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            filename = (
                f"GATE_2026_{paper_name}.pdf"
            )

            destination = (
                destination_dir
                / filename
            )

            download_file(
                url,
                destination
            )


def create_readme() -> None:
    """
    Create a useful README explaining what was downloaded.
    """

    readme = DOWNLOAD_ROOT / "README.md"

    content = """
# GATE CS + DA Official PYQs

Downloaded from official GATE organizing institute websites.

## Subjects

### CS
Computer Science and Information Technology

Expected coverage:
- 2007–2026

### DA
Data Science and Artificial Intelligence

Expected coverage:
- 2024–2026

DA was introduced as a GATE paper in 2024.

## Structure

```text
GATE_PYQs/
├── CS/
│   ├── 2007/
│   ├── 2008/
│   ├── ...
│   ├── 2025/
│   └── 2026/
│
└── DA/
    ├── 2024/
    ├── 2025/
    └── 2026/
```

Only official question papers are intended to be stored here.

Answer keys are disabled by default.
Set DOWNLOAD_KEYS = True in the script to include them
when available.
"""

    readme.write_text(
        content.strip() + "\n",
        encoding="utf-8",
    )


def main() -> None:

    DOWNLOAD_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log("=======================================")
    log(" GATE CS + DA OFFICIAL PYQ DOWNLOADER")
    log("=======================================")

    # --------------------------------------------------------
    # STEP 1
    # Official 2007-2025 bulk archive
    # --------------------------------------------------------

    log("Finding official bulk archive...")

    bulk_url = find_official_bulk_link()

    log(f"Official bulk archive found:")
    log(bulk_url)

    archive_path = (
        TEMP_DIR
        / "gate_2007_2025_bulk.zip"
    )

    download_google_drive(
        bulk_url,
        archive_path
    )

    # --------------------------------------------------------
    # STEP 2
    # Extract CS + DA
    # --------------------------------------------------------

    extract_cs_da_from_archive(
        archive_path,
        DOWNLOAD_ROOT
    )

    # --------------------------------------------------------
    # STEP 3
    # Download 2026 papers
    # --------------------------------------------------------

    log("Downloading official GATE 2026 papers...")

    download_2026_papers()

    # --------------------------------------------------------
    # STEP 4
    # README
    # --------------------------------------------------------

    create_readme()

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    try:
        shutil.rmtree(TEMP_DIR)
    except OSError:
        pass

    log("")
    log("=======================================")
    log(" DONE")
    log("=======================================")
    log("")
    log(f"Papers are stored in: {DOWNLOAD_ROOT.resolve()}")
    log("")
    log("Expected structure:")
    log("  GATE_PYQs/")
    log("    CS/")
    log("      2007/")
    log("      ...")
    log("      2026/")
    log("    DA/")
    log("      2024/")
    log("      2025/")
    log("      2026/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
```

### Install

```bash
pip install requests beautifulsoup4 gdown
```

### Run

```bash
python download_gate_pyqs.py
```

You'll get:

```text
GATE_PYQs/
│
├── CS/
│   ├── 2007/
│   ├── 2008/
│   ├── 2009/
│   ├── ...
│   ├── 2024/
│   ├── 2025/
│   └── 2026/
│
└── DA/
    ├── 2024/
    ├── 2025/
    └── 2026/
```

The important thing is that this **doesn't hard-code random PDF URLs**. It discovers the official archive link from GATE's own download page and extracts only CS/DA, then separately pulls the official 2026 Master Question Papers. That makes it much less brittle when the organizing institute changes filenames or storage locations. The official GATE 2026 archive states that its bulk download covers **2007–2025**, and its 2026 Master Question Paper page lists **CS-1, CS-2 and DA**.

One useful improvement for your GATE system would be to make the script **automatically rename and organize every paper by year/session and generate a `pyq_index.csv`** so you can later feed it straight into your GATE preparation tracker or build topic-wise PYQ analysis on top of it.