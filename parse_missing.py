#!/usr/bin/env python3
import os
import csv
import json
import time
import base64
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import pdf2image
from PIL import Image
from pypdf import PdfReader
from database import SessionLocal, Question

# Load environment
load_dotenv()
DOWNLOAD_ROOT = Path("GATE_PYQs")
QBANK_FILE = DOWNLOAD_ROOT / "qbank.json"
ASSETS_DIR = DOWNLOAD_ROOT / "assets"
TEMP_DIR = DOWNLOAD_ROOT / "_tmp"

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_pdf_page_count(pdf_path: Path) -> int:
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        return 0

def crop_diagram(img_path: Path, bbox: list[int], dest_path: Path) -> bool:
    try:
        img = Image.open(img_path)
        w, h = img.size
        ymin, xmin, ymax, xmax = bbox
        left = max(0, int((xmin / 1000.0) * w) - 8)
        top = max(0, int((ymin / 1000.0) * h) - 8)
        right = min(w, int((xmax / 1000.0) * w) + 8)
        bottom = min(h, int((ymax / 1000.0) * h) + 8)
        if right > left and bottom > top:
            cropped = img.crop((left, top, right, bottom))
            cropped.save(dest_path, "PNG")
            return True
    except Exception as e:
        print(f"Error cropping diagram: {e}")
    return False

def parse_page_with_gemini(model, img_path: Path, prompt: str, schema: dict):
    try:
        img = Image.open(img_path)
        response = model.generate_content(
            [prompt, img],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return None

def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Load present papers in qbank.json
    present_papers = set()
    if QBANK_FILE.exists():
        try:
            with QBANK_FILE.open("r", encoding="utf-8") as f:
                qbank_data = json.load(f)
                for q in qbank_data:
                    present_papers.add((q["subject"], q["year"], q["session"]))
        except Exception as e:
            print(f"Error reading qbank.json: {e}")
            qbank_data = []
    else:
        qbank_data = []

    print(f"Loaded qbank.json. Found questions for {len(present_papers)} unique papers.")

    # 2. Read index and identify missing papers
    csv_path = DOWNLOAD_ROOT / "pyq_index.csv"
    if not csv_path.exists():
        print("Error: pyq_index.csv not found!")
        return

    missing_papers = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sub = row["subject"]
            year = int(row["year"])
            session = row["session"]
            if (sub, year, session) not in present_papers:
                # Check if file is corrupted
                pdf_path = DOWNLOAD_ROOT / row["paper_path"]
                p_count = get_pdf_page_count(pdf_path)
                if p_count == 0:
                    print(f"Skipping corrupted paper: {sub} {year} {session} ({pdf_path.name})")
                    continue
                row["total_pages"] = p_count
                missing_papers.append(row)

    print(f"\nIdentified {len(missing_papers)} missing papers to parse:")
    for p in missing_papers:
        print(f" - {p['subject']} {p['year']} {p['session']} ({p['total_pages']} pages)")

    if not missing_papers:
        print("All papers are already parsed and present in qbank.json!")
        return

    # Prompt and schema definitions
    prompt = """
    You are an expert exam digitizer. Extract all questions from the provided GATE exam page image.
    Rules:
    1. Translate all mathematical equations, variables, and formulas into LaTeX notation enclosed in `$...$` or `$$...$$`.
    2. Identify the question type: 'MCQ' (Multiple Choice), 'MSQ' (Multiple Select), or 'NAT' (Numerical Answer Type).
    3. Identify if the question has a diagram/figure. If yes, set 'has_diagram' to true and return the 'diagram_bbox' as [ymin, xmin, ymax, xmax] normalized from 0 to 1000 representing the region containing ONLY the diagram.
    4. Keep text formatting clean and readable using standard Markdown.
    5. Provide the 'correct_answer' by solving the question. For MCQ, return the correct option letter (e.g. 'A'). For MSQ, return the correct option letters separated by comma (e.g. 'A,C'). For NAT, return the exact numerical value (e.g. '10') or the acceptable range (e.g. '9.9 to 10.1').
    6. Output the response strictly as valid JSON matching the specified schema.
    """

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "question_number": {"type": "INTEGER"},
                        "type": {"type": "STRING", "enum": ["MCQ", "MSQ", "NAT"]},
                        "marks": {"type": "INTEGER"},
                        "question_text": {"type": "STRING"},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of options (e.g. ['A: ...', 'B: ...']). Empty array for NAT."
                        },
                        "has_diagram": {"type": "BOOLEAN"},
                        "diagram_bbox": {
                            "type": "ARRAY",
                            "items": {"type": "INTEGER"},
                            "description": "Bounding box [ymin, xmin, ymax, xmax] normalized to 1000. Empty if no diagram."
                        },
                        "correct_answer": {
                            "type": "STRING",
                            "description": "For MCQ, the correct option letter (e.g. 'A'). For MSQ, a comma-separated list of letters (e.g. 'A,C'). For NAT, the exact numerical answer or range as a string (e.g. '12' or '12.0 to 13.0')."
                        }
                    },
                    "required": ["question_number", "type", "marks", "question_text", "options", "has_diagram", "correct_answer"]
                }
            }
        },
        "required": ["questions"]
    }

    model = genai.GenerativeModel("gemini-3.1-flash-lite")

    # 3. Start parsing page-by-page
    for paper in missing_papers:
        sub = paper["subject"]
        year = int(paper["year"])
        session = paper["session"]
        pdf_path = DOWNLOAD_ROOT / paper["paper_path"]
        total_pages = paper["total_pages"]

        print(f"\n>>> Parsing {sub} {year} {session} (Total Pages: {total_pages})")
        
        for page_num in range(1, total_pages + 1):
            print(f"  Processing page {page_num}/{total_pages}...", end="", flush=True)
            
            temp_img_path = TEMP_DIR / f"temp_batch_page_{page_num}.png"
            
            # Convert to image
            try:
                images = pdf2image.convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=150)
                if not images:
                    print(" FAILED (Render returned empty)")
                    continue
                images[0].save(temp_img_path, "PNG")
            except Exception as e:
                print(f" FAILED (Rendering error: {e})")
                continue

            # Call Gemini
            result = parse_page_with_gemini(model, temp_img_path, prompt, schema)
            if not result or "questions" not in result:
                print(" FAILED (Gemini parsing failed)")
                if temp_img_path.exists():
                    temp_img_path.unlink()
                continue

            questions = result["questions"]
            print(f" Success! Extracted {len(questions)} questions.")

            # Process questions details
            db_session = SessionLocal()
            try:
                for q in questions:
                    q_num = q["question_number"]
                    q_id = f"{sub}_{year}_{session.replace(' ', '_')}_Q{q_num}"
                    q["id"] = q_id
                    q["subject"] = sub
                    q["year"] = year
                    q["session"] = session

                    # Crop diagram
                    diagram_base64 = ""
                    if q.get("has_diagram") and q.get("diagram_bbox"):
                        diagram_name = f"{q_id}_diagram.png"
                        dest_path = ASSETS_DIR / diagram_name
                        if crop_diagram(temp_img_path, q["diagram_bbox"], dest_path):
                            q["diagram_path"] = f"assets/{diagram_name}"
                            try:
                                with dest_path.open("rb") as img_f:
                                    diagram_base64 = base64.b64encode(img_f.read()).decode("utf-8")
                            except Exception:
                                pass
                        else:
                            q["diagram_path"] = ""
                    else:
                        q["diagram_path"] = ""

                    # 1. Update qbank_data (avoid duplicates)
                    exists = any(item["id"] == q_id for item in qbank_data)
                    if not exists:
                        qbank_data.append(q)

                    # 2. Insert into DB
                    db_q = Question(
                        id=q_id,
                        subject=sub,
                        topic=q.get("topic", "General Aptitude"),
                        difficulty=q.get("difficulty", "Medium"),
                        year=year,
                        session=session,
                        question_number=q_num,
                        type=q["type"],
                        marks=q["marks"],
                        question_text=q["question_text"],
                        options_json=json.dumps(q["options"]),
                        correct_answer=q["correct_answer"],
                        diagram_path=q["diagram_path"],
                        diagram_base64=diagram_base64
                    )
                    db_session.merge(db_q)

                db_session.commit()
            except Exception as db_e:
                db_session.rollback()
                print(f"    Database error: {db_e}")
            finally:
                db_session.close()

            # Clean up temp image
            if temp_img_path.exists():
                temp_img_path.unlink()

            # Save updated qbank.json immediately to preserve work
            try:
                with QBANK_FILE.open("w", encoding="utf-8") as f:
                    json.dump(qbank_data, f, indent=2)
            except Exception as e:
                print(f"Error saving qbank.json: {e}")

            # Sleep briefly to avoid hitting rate limits
            time.sleep(2.0)

    # Clean up temp folder
    try:
        Path.rmdir(TEMP_DIR)
    except Exception:
        pass

    print("\n=== BATCH DIGITIZATION OF MISSING PAPERS COMPLETED! ===")

if __name__ == "__main__":
    main()
