#!/usr/bin/env python3

import os
import csv
import json
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
import pdf2image
import google.generativeai as genai
import datetime
import jwt
from passlib.context import CryptContext
from database import SessionLocal, User, Question, Attempt, Response as DbResponse, SoloResponse, seed_questions
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DOWNLOAD_ROOT = Path("GATE_PYQs")
ASSETS_DIR = DOWNLOAD_ROOT / "assets"
QBANK_FILE = DOWNLOAD_ROOT / "qbank.json"
STATE_FILE = DOWNLOAD_ROOT / "parser_state.json"
TEMP_DIR = DOWNLOAD_ROOT / "_tmp"

# Password Hashing & JWT Settings
import hashlib

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + key.hex()

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False

SECRET_KEY = "GATE_CBT_SUPER_SECRET_KEY_FOR_SAAS"
ALGORITHM = "HS256"
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Create necessary directories
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Shared State
state = {
    "status": "idle",  # "idle", "running", "paused", "completed", "error"
    "running_cost": 0.0,
    "processed_pages": 0,
    "total_pages": 0,
    "budget_limit": 1.00,
    "extracted_count": 0,
    "diagrams_count": 0,
    "current_paper_index": 0,
    "current_page": 1
}

# Thread Safety & Communications
logs = []  # List of {"message": str, "level": str}
logs_lock = threading.RLock()
state_lock = threading.RLock()
stop_event = threading.Event()
worker_thread = None

# Global papers list
papers = []

def add_log(msg: str, level: str = "info"):
    with logs_lock:
        logs.append({"message": msg, "level": level})
    print(f"[GATE-LOG] [{level.upper()}] {msg}")

def set_status(new_status: str):
    with state_lock:
        state["status"] = new_status
    save_state()

def save_state():
    with state_lock:
        state_copy = state.copy()
    try:
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state_copy, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

def load_state_from_disk():
    global state
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                saved = json.load(f)
            with state_lock:
                for k, v in saved.items():
                    if k in state and k != "status":  # Preserve idle status on launch
                        state[k] = v
            print("Parser state successfully loaded from disk.")
        except Exception as e:
            print(f"Error loading state: {e}")

def get_pdf_page_count(pdf_path: Path) -> int:
    name = pdf_path.name
    # Fallbacks for known problematic/corrupted PDFs in the official archive
    if "GATE_CS_2011" in name:
        return 21
    elif "GATE_CS_2017_Session_1" in name:
        return 27
    elif "GATE_CS_2021_Session_2" in name:
        return 46

    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        return 35  # Generic safe average fallback

def load_papers_list():
    global papers, state
    papers = []
    csv_path = DOWNLOAD_ROOT / "pyq_index.csv"
    if not csv_path.exists():
        add_log("No pyq_index.csv found! Run download_gate_pyqs.py first.", "danger")
        return

    try:
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                papers.append(row)
        
        add_log(f"Successfully indexed {len(papers)} question papers.", "success")
        
        # Calculate total workload pages
        total_pages = 0
        for paper in papers:
            path = DOWNLOAD_ROOT / paper["paper_path"]
            p_count = get_pdf_page_count(path)
            paper["total_pages"] = p_count
            total_pages += p_count

        with state_lock:
            state["total_pages"] = total_pages
        save_state()
        add_log(f"Configured workload: {total_pages} total pages to digitise.", "info")
    except Exception as e:
        add_log(f"Error building paper workload index: {e}", "danger")

def crop_diagram(img_path: Path, bbox: list[int], dest_path: Path) -> bool:
    try:
        img = Image.open(img_path)
        w, h = img.size
        # Bbox is [ymin, xmin, ymax, xmax] normalized to 1000
        ymin, xmin, ymax, xmax = bbox
        
        left = int((xmin / 1000.0) * w)
        top = int((ymin / 1000.0) * h)
        right = int((xmax / 1000.0) * w)
        bottom = int((ymax / 1000.0) * h)
        
        # Clip to image boundaries with a tiny padding
        left = max(0, left - 8)
        top = max(0, top - 8)
        right = min(w, right + 8)
        bottom = min(h, bottom + 8)
        
        if right > left and bottom > top:
            cropped = img.crop((left, top, right, bottom))
            cropped.save(dest_path, "PNG")
            return True
    except Exception as e:
        print(f"Error cropping diagram: {e}")
    return False

def process_extracted_questions(paper: dict, questions: list, img_path: Path):
    global state
    qbank = []
    if QBANK_FILE.exists():
        try:
            with QBANK_FILE.open("r", encoding="utf-8") as f:
                qbank = json.load(f)
        except Exception:
            pass

    for q in questions:
        q_num = q["question_number"]
        sub = paper["subject"]
        year = paper["year"]
        session = paper["session"]
        
        q_id = f"{sub}_{year}_{session.replace(' ', '_')}_Q{q_num}"
        q["id"] = q_id
        q["subject"] = sub
        q["year"] = int(year)
        q["session"] = session

        # Crop diagram if visual bbox exists
        if q.get("has_diagram") and q.get("diagram_bbox"):
            diagram_name = f"{q_id}_diagram.png"
            dest_path = ASSETS_DIR / diagram_name
            if crop_diagram(img_path, q["diagram_bbox"], dest_path):
                q["diagram_path"] = f"assets/{diagram_name}"
                with state_lock:
                    state["diagrams_count"] += 1
            else:
                q["diagram_path"] = ""
        else:
            q["diagram_path"] = ""

        # Avoid duplicates in database
        exists = any(item["id"] == q_id for item in qbank)
        if not exists:
            qbank.append(q)

    # Save to JSON question bank
    try:
        with QBANK_FILE.open("w", encoding="utf-8") as f:
            json.dump(qbank, f, indent=2)
            
        # Save to SQL database dynamically
        db = SessionLocal()
        try:
            for q in questions:
                db_q = db.query(Question).filter(Question.id == q["id"]).first()
                if not db_q:
                    new_q = Question(
                        id=q["id"],
                        subject=q.get("subject", "CS"),
                        topic=q.get("topic", "General Aptitude"),
                        difficulty=q.get("difficulty", "Medium"),
                        year=q.get("year", 2007),
                        session=q.get("session", "Single Session"),
                        question_number=q.get("question_number", 1),
                        type=q.get("type", "MCQ"),
                        marks=q.get("marks", 1),
                        question_text=q["question_text"],
                        options_json=json.dumps(q.get("options", [])),
                        correct_answer=q.get("correct_answer", ""),
                        diagram_path=q.get("diagram_path", "")
                    )
                    db.add(new_q)
            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"Error seeding database dynamically: {db_err}")
        finally:
            db.close()
            
    except Exception as e:
        add_log(f"Error writing to database JSON bank: {e}", "danger")

def advance_page():
    global state, papers
    with state_lock:
        current_page = state["current_page"]
        current_paper_idx = state["current_paper_index"]
        
        paper = papers[current_paper_idx]
        total_pages_in_paper = paper["total_pages"]
        
        current_page += 1
        if current_page > total_pages_in_paper:
            current_page = 1
            current_paper_idx += 1
            
        if current_paper_idx >= len(papers):
            state["status"] = "completed"
            add_log("Digitisation completed successfully! The entire question bank is populated.", "success")
        else:
            state["current_page"] = current_page
            state["current_paper_index"] = current_paper_idx
            
        save_state()

def process_page(paper: dict, page_num: int):
    global state
    pdf_path = DOWNLOAD_ROOT / paper["paper_path"]
    
    # Handle unreadable corrupted PDFs gracefully by skipping
    if "GATE_CS_2011" in pdf_path.name or "GATE_CS_2017_Session_1" in pdf_path.name:
        add_log(f"Skipping page {page_num} of {pdf_path.name} (Official archive PDF is corrupted).", "warning")
        with state_lock:
            state["processed_pages"] += 1
        advance_page()
        return

    temp_img_path = TEMP_DIR / f"temp_page_{page_num}.png"
    
    # 1. Convert page to image
    try:
        images = pdf2image.convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=150)
        if not images:
            raise ValueError("Rendering failed")
        images[0].save(temp_img_path, "PNG")
    except Exception as e:
        add_log(f"Skipping page {page_num} of {pdf_path.name} (Rendering failed): {e}", "warning")
        with state_lock:
            state["processed_pages"] += 1
        advance_page()
        return

    # 2. Call Gemini 1.5 Flash API
    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
        
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

        img = Image.open(temp_img_path)
        response = model.generate_content(
            [prompt, img],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
        )
        
        # Calculate dynamic page costs from token feedback
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count
        candidates_tokens = usage.candidates_token_count
        
        page_cost = (prompt_tokens * 0.25 / 1_000_000) + (candidates_tokens * 0.75 / 1_000_000)
        
        result = json.loads(response.text)
        questions = result.get("questions", [])
        
        # Process and crop images
        process_extracted_questions(paper, questions, temp_img_path)
        
        # Update running tallies
        with state_lock:
            state["running_cost"] += page_cost
            state["processed_pages"] += 1
            state["extracted_count"] += len(questions)
            
        add_log(f"Digitised page {page_num} of {pdf_path.name}. Cost: ${page_cost:.4f}. Extracted {len(questions)} questions.", "success")
        
    except Exception as e:
        err_msg = str(e).lower()
        if "finish_reason" in err_msg or "reciting" in err_msg or "safety" in err_msg:
            add_log(f"Skipping page {page_num} of {pdf_path.name} (Gemini safety/recitation block).", "warning")
            with state_lock:
                state["processed_pages"] += 1
        else:
            add_log(f"Error parsing page {page_num} of {pdf_path.name} with Gemini: {e}", "danger")
            set_status("error")
        
    finally:
        # Cleanup temp PNG
        if temp_img_path.exists():
            try:
                temp_img_path.unlink()
            except OSError:
                pass
                
    advance_page()

def parser_worker_loop():
    global state, papers
    add_log("Background parser thread active.", "system")
    
    if not papers:
        load_papers_list()

    while not stop_event.is_set():
        with state_lock:
            status = state["status"]
            running_cost = state["running_cost"]
            budget_limit = state["budget_limit"]

        if status != "running":
            time.sleep(0.5)
            continue

        # 1. Budget Enforcer
        if running_cost >= budget_limit:
            set_status("paused")
            add_log(f"Extraction halted: cost (${running_cost:.3f}) reached or exceeded safety budget limit (${budget_limit:.2f}).", "warning")
            continue

        # 2. Extract indices
        with state_lock:
            idx = state["current_paper_index"]
            page_num = state["current_page"]

        if idx >= len(papers):
            set_status("completed")
            continue

        paper = papers[idx]
        
        # Call page processor
        process_page(paper, page_num)
        
        # Prevent API throttling & maintain stable page transitions
        time.sleep(2.0)

def backfill_answers_worker():
    if not QBANK_FILE.exists():
        return
    
    # Load qbank
    try:
        with QBANK_FILE.open("r", encoding="utf-8") as f:
            qbank = json.load(f)
    except Exception:
        return
        
    # Find questions without correct_answer
    missing_indices = [i for i, q in enumerate(qbank) if "correct_answer" not in q]
    if not missing_indices:
        return
        
    add_log(f"Found {len(missing_indices)} questions in qbank.json missing correct answers. Starting backfill worker...", "info")
    
    # Configure API key
    global GEMINI_API_KEY
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        add_log("Cannot backfill answers: GEMINI_API_KEY is not configured.", "warning")
        return
        
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    
    backfilled_count = 0
    for idx in missing_indices:
        if stop_event.is_set():
            break
            
        q = qbank[idx]
        
        q_text = q.get("question_text", "")
        q_options = "\n".join(q.get("options", []))
        q_type = q.get("type", "MCQ")
        
        prompt = f"""
        Solve this GATE exam question. Identify the correct answer.
        
        Question Type: {q_type}
        Question Text:
        {q_text}
        
        Options:
        {q_options}
        
        Output the response strictly in this JSON format:
        {{
          "correct_answer": "correct answer format"
        }}
        
        Rules for correct_answer:
        - For MCQ, return the correct option letter (e.g. 'A').
        - For MSQ, return the correct option letters separated by comma (e.g. 'A,C').
        - For NAT, return the exact numerical value (e.g. '10') or the acceptable range (e.g. '9.9 to 10.1').
        """
        
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                }
            )
            result = json.loads(response.text)
            ans = result.get("correct_answer")
            if ans:
                q["correct_answer"] = str(ans).strip()
                backfilled_count += 1
                
                # Periodically save to disk
                if backfilled_count % 5 == 0 or backfilled_count == len(missing_indices):
                    try:
                        with QBANK_FILE.open("w", encoding="utf-8") as f:
                            json.dump(qbank, f, indent=2)
                    except Exception:
                        pass
                        
            time.sleep(1.0)
        except Exception as e:
            print(f"Error backfilling answer for {q.get('id')}: {e}")
            time.sleep(2.0)
            
    add_log(f"Backfill complete. Successfully determined answers for {backfilled_count} questions.", "success")

# ============================================================
# FASTAPI SERVER CONFIG
# ============================================================

app = FastAPI(title="GATE PYQ Parser Server")

# Serve UI static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve diagram images
app.mount("/assets", StaticFiles(directory="GATE_PYQs/assets"), name="assets")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/api/status")
def get_status():
    global logs
    with state_lock:
        state_copy = state.copy()
    with logs_lock:
        new_logs = list(logs)
        logs.clear()  # Empty log buffer on read to prevent client duplicates

    all_questions = []
    if QBANK_FILE.exists():
        try:
            with QBANK_FILE.open("r", encoding="utf-8") as f:
                all_questions = json.load(f)
        except Exception:
            pass

    return {
        "state": state_copy,
        "new_logs": new_logs,
        "all_questions": all_questions
    }

@app.post("/api/start")
def start_parser():
    global GEMINI_API_KEY
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        add_log("Failed to start: GEMINI_API_KEY is not configured inside .env!", "danger")
        raise HTTPException(status_code=400, detail="API Key not configured")
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    with state_lock:
        status = state["status"]
    
    if status == "completed":
        raise HTTPException(status_code=400, detail="Extraction already completed. Reset state to restart.")
        
    set_status("running")
    add_log("Resuming question bank digitisation worker...", "system")
    return {"status": "ok"}

@app.post("/api/pause")
def pause_parser():
    set_status("paused")
    add_log("Pausing digitisation worker...", "system")
    return {"status": "ok"}

class LimitUpdate(BaseModel):
    limit: float

@app.post("/api/limit")
def update_limit(data: LimitUpdate):
    with state_lock:
        state["budget_limit"] = data.limit
    save_state()
    return {"status": "ok"}

@app.post("/api/reset")
def reset_parser():
    global state
    set_status("idle")
    
    with state_lock:
        state["running_cost"] = 0.0
        state["processed_pages"] = 0
        state["extracted_count"] = 0
        state["diagrams_count"] = 0
        state["current_paper_index"] = 0
        state["current_page"] = 1
    
    save_state()
    
    # Delete DB JSON file
    if QBANK_FILE.exists():
        try:
            QBANK_FILE.unlink()
        except OSError:
            pass
            
    # Clear diagrams folder
    for file in ASSETS_DIR.glob("*"):
        try:
            file.unlink()
        except OSError:
            pass
            
    add_log("Reset complete. Digitisation state and assets cleared.", "warning")
    return {"status": "ok"}

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class SolveRequest(BaseModel):
    user_answer: str

class QuestionResponse(BaseModel):
    id: str
    user_answer: Optional[str] = None
    time_spent: int

class ExamSubmission(BaseModel):
    subject: str
    year: int
    session: str
    total_time: int
    responses: list[QuestionResponse]

def parse_nat_correct_range(correct_str: str) -> Optional[tuple[float, float]]:
    correct_str = correct_str.strip().lower()
    cleaned = correct_str.replace("to", " ").replace(":", " ").replace("-", " ")
    parts = []
    for p in cleaned.split():
        try:
            parts.append(float(p))
        except ValueError:
            pass
    if len(parts) == 2:
        return min(parts), max(parts)
    elif len(parts) == 1:
        return parts[0], parts[0]
    
    try:
        val = float(correct_str)
        return val, val
    except ValueError:
        return None

# ============================================================
# USER AUTH ROUTES
# ============================================================

@app.post("/api/auth/register")
def register_user(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_pwd = hash_password(data.password)
    user = User(username=data.username, email=data.email, password_hash=hashed_pwd)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = jwt.encode(
        {"user_id": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"token": token, "username": user.username}

@app.post("/api/auth/login")
def login_user(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = jwt.encode(
        {"user_id": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"token": token, "username": user.username}

@app.get("/api/auth/me")
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "username": user.username, "email": user.email}

# ============================================================
# EXAM PRACTICE ENGINE ROUTES
# ============================================================

@app.get("/exam")
def get_exam_page():
    return FileResponse("static/exam.html")

@app.get("/api/exam/list-papers")
def list_papers(db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    if not questions:
        return []
        
    papers_map = {}
    for q in questions:
        key = (q.subject, q.year, q.session)
        if key not in papers_map:
            papers_map[key] = {
                "subject": q.subject,
                "year": q.year,
                "session": q.session,
                "total_questions": 0,
                "mcq_count": 0,
                "msq_count": 0,
                "nat_count": 0
            }
        p = papers_map[key]
        p["total_questions"] += 1
        if q.type == "MCQ":
            p["mcq_count"] += 1
        elif q.type == "MSQ":
            p["msq_count"] += 1
        elif q.type == "NAT":
            p["nat_count"] += 1
            
    result = list(papers_map.values())
    result.sort(key=lambda x: (x["subject"], -x["year"], x["session"]))
    return result

@app.get("/api/exam/get-paper")
def get_paper(subject: str, year: int, session: str, db: Session = Depends(get_db)):
    paper_questions = db.query(Question).filter(
        Question.subject == subject,
        Question.year == year,
        Question.session == session
    ).order_by(Question.question_number).all()
    
    result = []
    for q in paper_questions:
        options = []
        if q.options_json:
            try:
                options = json.loads(q.options_json)
            except Exception:
                pass
        result.append({
            "id": q.id,
            "subject": q.subject,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "year": q.year,
            "session": q.session,
            "question_number": q.question_number,
            "type": q.type,
            "marks": q.marks,
            "question_text": q.question_text,
            "options": options,
            "diagram_path": q.diagram_path
        })
    return result

@app.post("/api/exam/submit-test")
def submit_test(submission: ExamSubmission, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    q_ids = [r.id for r in submission.responses]
    questions = db.query(Question).filter(Question.id.in_(q_ids)).all()
    q_map = {q.id: q for q in questions}
    
    paper_qs = db.query(Question).filter(
        Question.subject == submission.subject,
        Question.year == submission.year,
        Question.session == submission.session
    ).all()
    total_marks_possible = sum(q.marks for q in paper_qs)
    
    marks_obtained = 0.0
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    
    db_responses = []
    
    for resp in submission.responses:
        q = q_map.get(resp.id)
        if not q:
            continue
            
        q_type = q.type
        q_marks = q.marks
        correct_ans = q.correct_answer
        user_ans = resp.user_answer
        
        status = "unanswered"
        score = 0.0
        is_correct = False
        
        if not user_ans or user_ans.strip() == "":
            status = "unanswered"
            score = 0.0
            unanswered_count += 1
        else:
            if q_type == "MCQ":
                if user_ans.strip().upper() == correct_ans.strip().upper():
                    status = "correct"
                    score = float(q_marks)
                    correct_count += 1
                    is_correct = True
                else:
                    status = "incorrect"
                    score = - (float(q_marks) / 3.0)
                    incorrect_count += 1
            elif q_type == "MSQ":
                user_set = {x.strip().upper() for x in user_ans.split(",") if x.strip()}
                correct_set = {x.strip().upper() for x in correct_ans.split(",") if x.strip()}
                if user_set == correct_set:
                    status = "correct"
                    score = float(q_marks)
                    correct_count += 1
                    is_correct = True
                else:
                    status = "incorrect"
                    score = 0.0
                    incorrect_count += 1
            elif q_type == "NAT":
                try:
                    user_val = float(user_ans.strip())
                    range_vals = parse_nat_correct_range(correct_ans)
                    if range_vals:
                        min_val, max_val = range_vals
                        if min_val <= user_val <= max_val:
                            status = "correct"
                            score = float(q_marks)
                            correct_count += 1
                            is_correct = True
                        else:
                            status = "incorrect"
                            score = 0.0
                            incorrect_count += 1
                    else:
                        if user_ans.strip() == correct_ans.strip():
                            status = "correct"
                            score = float(q_marks)
                            correct_count += 1
                            is_correct = True
                        else:
                            status = "incorrect"
                            score = 0.0
                            incorrect_count += 1
                except ValueError:
                    status = "incorrect"
                    score = 0.0
                    incorrect_count += 1
                    
        marks_obtained += score
        
        db_resp = DbResponse(
            question_id=resp.id,
            user_answer=user_ans or "",
            is_correct=is_correct,
            score=score,
            time_spent=resp.time_spent
        )
        db_responses.append(db_resp)
        
    attempt = Attempt(
        user_id=user_id,
        subject=submission.subject,
        year=submission.year,
        session=submission.session,
        total_time=submission.total_time,
        marks_obtained=round(marks_obtained, 3),
        total_marks_possible=total_marks_possible,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        unanswered_count=unanswered_count,
        responses=db_responses
    )
    
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    return {
        "timestamp": attempt.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "subject": attempt.subject,
        "year": attempt.year,
        "session": attempt.session,
        "total_time": attempt.total_time,
        "total_marks_possible": attempt.total_marks_possible,
        "marks_obtained": attempt.marks_obtained,
        "correct_count": attempt.correct_count,
        "incorrect_count": attempt.incorrect_count,
        "unanswered_count": attempt.unanswered_count,
        "responses": [
            {
                "id": r.question_id,
                "question_number": q_map[r.question_id].question_number,
                "user_answer": r.user_answer,
                "correct_answer": q_map[r.question_id].correct_answer,
                "status": "correct" if r.is_correct else ("unanswered" if not r.user_answer else "incorrect"),
                "score": r.score,
                "marks": q_map[r.question_id].marks,
                "type": q_map[r.question_id].type
            } for r in attempt.responses
        ]
    }

@app.get("/api/exam/history")
def get_exam_history(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).order_by(Attempt.timestamp.desc()).all()
    result = []
    for a in attempts:
        result.append({
            "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "subject": a.subject,
            "year": a.year,
            "session": a.session,
            "total_time": a.total_time,
            "total_marks_possible": a.total_marks_possible,
            "marks_obtained": a.marks_obtained,
            "correct_count": a.correct_count,
            "incorrect_count": a.incorrect_count,
            "unanswered_count": a.unanswered_count,
            "responses": [
                {
                    "id": r.question_id,
                    "question_number": r.question.question_number if r.question else 0,
                    "user_answer": r.user_answer,
                    "correct_answer": r.question.correct_answer if r.question else "",
                    "status": "correct" if r.is_correct else ("unanswered" if not r.user_answer else "incorrect"),
                    "score": r.score,
                    "marks": r.question.marks if r.question else 1,
                    "type": r.question.type if r.question else "MCQ"
                } for r in a.responses
            ]
        })
    return result

# ============================================================
# LEETCODE-STYLE DIRECTORY ROUTES
# ============================================================

@app.get("/api/questions")
def get_questions_list(
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    query = db.query(Question)
    if subject:
        query = query.filter(Question.subject == subject)
    if topic:
        query = query.filter(Question.topic == topic)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if search:
        query = query.filter(Question.question_text.like(f"%{search}%"))
        
    questions = query.order_by(Question.year.desc(), Question.question_number).all()
    
    # Solved statuses map
    solo_solved = db.query(SoloResponse.question_id, SoloResponse.is_correct).filter(SoloResponse.user_id == user_id).all()
    exam_solved = db.query(DbResponse.question_id, DbResponse.is_correct).join(Attempt).filter(Attempt.user_id == user_id).all()
    
    status_map = {}
    for q_id, is_corr in solo_solved + exam_solved:
        if is_corr:
            status_map[q_id] = "solved"
        elif status_map.get(q_id) != "solved":
            status_map[q_id] = "attempted"
            
    result = []
    for q in questions:
        q_status = status_map.get(q.id, "unattempted")
        if status and q_status != status:
            continue
            
        result.append({
            "id": q.id,
            "subject": q.subject,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "year": q.year,
            "session": q.session,
            "question_number": q.question_number,
            "type": q.type,
            "marks": q.marks,
            "question_text": q.question_text[:120] + "..." if len(q.question_text) > 120 else q.question_text,
            "status": q_status
        })
    return result

@app.get("/api/questions/{id}")
def get_question_detail(id: str, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    options = []
    if q.options_json:
        try:
            options = json.loads(q.options_json)
        except Exception:
            pass
            
    return {
        "id": q.id,
        "subject": q.subject,
        "topic": q.topic,
        "difficulty": q.difficulty,
        "year": q.year,
        "session": q.session,
        "question_number": q.question_number,
        "type": q.type,
        "marks": q.marks,
        "question_text": q.question_text,
        "options": options,
        "diagram_path": q.diagram_path
    }

@app.post("/api/questions/{id}/solve")
def solve_question(id: str, data: SolveRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    q_type = q.type
    correct_ans = q.correct_answer
    user_ans = data.user_answer
    
    is_correct = False
    if user_ans and user_ans.strip() != "":
        if q_type == "MCQ":
            is_correct = user_ans.strip().upper() == correct_ans.strip().upper()
        elif q_type == "MSQ":
            user_set = {x.strip().upper() for x in user_ans.split(",") if x.strip()}
            correct_set = {x.strip().upper() for x in correct_ans.split(",") if x.strip()}
            is_correct = user_set == correct_set
        elif q_type == "NAT":
            try:
                user_val = float(user_ans.strip())
                range_vals = parse_nat_correct_range(correct_ans)
                if range_vals:
                    min_val, max_val = range_vals
                    is_correct = min_val <= user_val <= max_val
                else:
                    is_correct = user_ans.strip() == correct_ans.strip()
            except ValueError:
                is_correct = False
                
    # Save solo response record
    solo = SoloResponse(
        user_id=user_id,
        question_id=q.id,
        user_answer=user_ans,
        is_correct=is_correct
    )
    db.add(solo)
    db.commit()
    
    return {
        "is_correct": is_correct,
        "correct_answer": correct_ans
    }

# ============================================================
# PERFORMANCE METRICS & SYLLABUS ANALYTICS
# ============================================================

@app.get("/api/analytics")
def get_user_analytics(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
    solo_solved = db.query(SoloResponse).filter(SoloResponse.user_id == user_id).all()
    
    total_exams = len(attempts)
    
    total_correct = sum(a.correct_count for a in attempts) + sum(1 for s in solo_solved if s.is_correct)
    total_incorrect = sum(a.incorrect_count for a in attempts) + sum(1 for s in solo_solved if not s.is_correct)
    
    exam_responses = db.query(DbResponse.is_correct, Question.topic).join(Question).join(Attempt).filter(Attempt.user_id == user_id).all()
    solo_responses = db.query(SoloResponse.is_correct, Question.topic).join(Question).filter(SoloResponse.user_id == user_id).all()
    
    all_resps = exam_responses + solo_responses
    
    topic_stats = {}
    for is_correct, topic in all_resps:
        if topic not in topic_stats:
            topic_stats[topic] = {"correct": 0, "total": 0}
        topic_stats[topic]["total"] += 1
        if is_correct:
            topic_stats[topic]["correct"] += 1
            
    mastery = []
    for topic, stats in topic_stats.items():
        accuracy = round((stats["correct"] / stats["total"]) * 100, 1)
        mastery.append({
            "topic": topic,
            "accuracy": accuracy,
            "total_solved": stats["correct"],
            "total_attempted": stats["total"]
        })
        
    mastery.sort(key=lambda x: -x["accuracy"])
    
    attempts_history = []
    for a in attempts:
        attempts_history.append({
            "date": a.timestamp.strftime("%Y-%m-%d"),
            "score": round((a.marks_obtained / a.total_marks_possible) * 100, 1) if a.total_marks_possible > 0 else 0
        })
    attempts_history.reverse()
    
    return {
        "total_exams_taken": total_exams,
        "total_correct": total_correct,
        "total_incorrect": total_incorrect,
        "mastery": mastery,
        "performance_trend": attempts_history
    }

@app.post("/api/exam/sync-db")
def sync_db(user_id: int = Depends(get_current_user_id)):
    seed_questions()
    return {"status": "success", "message": "Database sync triggered successfully"}

@app.on_event("startup")
def startup_event():
    global worker_thread
    load_state_from_disk()
    load_papers_list()
    
    # Create DB Tables and Seed initial Questions
    seed_questions()
    
    # Launch parser loop in daemon thread
    stop_event.clear()
    worker_thread = threading.Thread(target=parser_worker_loop, daemon=True)
    worker_thread.start()

    backfill_thread = threading.Thread(target=backfill_answers_worker, daemon=True)
    backfill_thread.start()

@app.on_event("shutdown")
def shutdown_event():
    stop_event.set()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8026)
