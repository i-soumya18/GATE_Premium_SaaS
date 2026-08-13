#!/usr/bin/env python3
import os
import json
import time
import base64
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import pdf2image
from PIL import Image
from database import SessionLocal, Question

# Load environment
load_dotenv()
DOWNLOAD_ROOT = Path("GATE_PYQs")
QBANK_FILE = DOWNLOAD_ROOT / "qbank.json"
ASSETS_DIR = DOWNLOAD_ROOT / "assets"
TEMP_DIR = DOWNLOAD_ROOT / "_tmp"

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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

def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load qbank.json
    with QBANK_FILE.open("r", encoding="utf-8") as f:
        qbank_data = json.load(f)

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
    pdf_path = DOWNLOAD_ROOT / "CS/2021/GATE_CS_2021_Session_2.pdf"

    print(">>> Parsing Remaining Pages of CS 2021 Session 2 (Pages 6 to 35)")
    for page_num in range(6, 36):
        print(f"  Processing page {page_num}/35...", end="", flush=True)
        temp_img_path = TEMP_DIR / f"temp_s2_page_{page_num}.png"
        
        # Convert to image
        try:
            images = pdf2image.convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=150)
            if not images:
                print(" FAILED (empty render)")
                continue
            images[0].save(temp_img_path, "PNG")
        except Exception as e:
            print(f" FAILED (Rendering error: {e})")
            continue

        # Call Gemini
        try:
            img = Image.open(temp_img_path)
            response = model.generate_content(
                [prompt, img],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                }
            )
            result = json.loads(response.text)
        except Exception as e:
            print(f" FAILED (Gemini error: {e})")
            if temp_img_path.exists():
                temp_img_path.unlink()
            continue

        if not result or "questions" not in result:
            print(" FAILED (Invalid format)")
            if temp_img_path.exists():
                temp_img_path.unlink()
            continue

        questions = result["questions"]
        print(f" Success! Extracted {len(questions)} questions.")

        db_session = SessionLocal()
        try:
            for q in questions:
                q_num = q["question_number"]
                q_id = f"CS_2021_Session_2_Q{q_num}"
                q["id"] = q_id
                q["subject"] = "CS"
                q["year"] = 2021
                q["session"] = "Session 2"

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

                # Avoid duplicates
                exists = any(item["id"] == q_id for item in qbank_data)
                if not exists:
                    qbank_data.append(q)

                db_q = Question(
                    id=q_id,
                    subject="CS",
                    topic=q.get("topic", "General Aptitude"),
                    difficulty=q.get("difficulty", "Medium"),
                    year=2021,
                    session="Session 2",
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

        # Clean up
        if temp_img_path.exists():
            temp_img_path.unlink()

        # Save qbank.json
        with QBANK_FILE.open("w", encoding="utf-8") as f:
            json.dump(qbank_data, f, indent=2)

        time.sleep(2.0)

    try:
        Path.rmdir(TEMP_DIR)
    except Exception:
        pass
    print("=== FINISHED PARSING CS 2021 SESSION 2 ===")

if __name__ == "__main__":
    main()
