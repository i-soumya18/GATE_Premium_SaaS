import os
import json
import datetime
import base64
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gate_saas.db")

# Use connect_args connect parameters only for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================================================
# MODELS
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    attempts = relationship("Attempt", back_populates="user")
    solo_responses = relationship("SoloResponse", back_populates="user")

class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, index=True) # e.g. "CS_2009_Single_Session_Q38"
    subject = Column(String, nullable=False, index=True) # e.g. "CS" or "DA"
    topic = Column(String, default="General Aptitude", index=True)
    difficulty = Column(String, default="Medium", index=True)
    year = Column(Integer, nullable=False, index=True)
    session = Column(String, nullable=False)
    question_number = Column(Integer, nullable=False)
    type = Column(String, nullable=False) # MCQ, MSQ, NAT
    marks = Column(Integer, default=1)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False) # JSON array of options
    correct_answer = Column(String, nullable=False)
    diagram_path = Column(String, default="")
    diagram_base64 = Column(Text, default="")


    responses = relationship("Response", back_populates="question")
    solo_responses = relationship("SoloResponse", back_populates="question")

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    session = Column(String, nullable=False) # e.g. Session 1 or "Custom Practice"
    total_time = Column(Integer, nullable=False) # seconds spent
    marks_obtained = Column(Float, nullable=False)
    total_marks_possible = Column(Integer, nullable=False)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="attempts")
    responses = relationship("Response", back_populates="attempt", cascade="all, delete-orphan")

class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False, index=True)
    user_answer = Column(String, default="")
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0) # seconds

    attempt = relationship("Attempt", back_populates="responses")
    question = relationship("Question", back_populates="responses")

class SoloResponse(Base):
    __tablename__ = "solo_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False, index=True)
    user_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="solo_responses")
    question = relationship("Question", back_populates="solo_responses")

class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False) # "CS" or "DA"
    topic = Column(String, nullable=False)
    subtopic = Column(String, default="")
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    type = Column(String, nullable=False) # e.g. "PDF", "Link", "GitHub Repo", "Book"
    description = Column(Text, default="")
    is_verified = Column(Boolean, default=True)

class VideoMaterial(Base):
    __tablename__ = "video_materials"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False) # "CS" or "DA"
    topic = Column(String, nullable=False)
    subtopic = Column(String, default="")
    title = Column(String, nullable=False)
    youtube_url = Column(String, nullable=False)
    video_id = Column(String, nullable=False)
    duration_mins = Column(Integer, default=0)
    channel_name = Column(String, default="")
    description = Column(Text, default="")

class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    material_type = Column(String, nullable=False) # "video" or "material"
    material_id = Column(Integer, nullable=False)
    completed = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False) # "CS" or "DA"
    topic = Column(String, nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)

class StudyLog(Base):
    __tablename__ = "study_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False) # "YYYY-MM-DD"
    minutes_spent = Column(Integer, default=0)

class CuratedSet(Base):
    __tablename__ = "curated_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    subject = Column(String, nullable=False) # "CS" or "DA"
    questions_csv = Column(String, nullable=False) # Comma-separated list of Question IDs

# ============================================================
# SEEDER
# ============================================================

def seed_questions():
    db = SessionLocal()
    try:
        qbank_path = Path("GATE_PYQs/qbank.json")
        if not qbank_path.exists():
            print("Seeder: qbank.json not found. Skipping questions seed.")
            return

        with qbank_path.open("r", encoding="utf-8") as f:
            questions_data = json.load(f)

        db_count = db.query(Question).count()
        if db_count == len(questions_data):
            print(f"Database questions already fully seeded ({db_count} questions).")
            return

        print(f"Seeding {len(questions_data)} questions into database (currently {db_count} in DB)...")
        for i, q in enumerate(questions_data):
            if not q.get("id") or not q.get("question_text"):
                continue

            diag_base64 = ""
            diag_path = q.get("diagram_path", "")
            if diag_path:
                local_path = Path("GATE_PYQs") / diag_path
                if local_path.exists():
                    try:
                        with local_path.open("rb") as img_f:
                            diag_base64 = base64.b64encode(img_f.read()).decode("utf-8")
                    except Exception as e:
                        print(f"Error encoding diagram {local_path}: {e}")

            db_q = Question(
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
                diagram_path=diag_path,
                diagram_base64=diag_base64
            )
            db.merge(db_q)

            if (i + 1) % 50 == 0 or (i + 1) == len(questions_data):
                db.commit()
                print(f"Seeding progress: {i + 1}/{len(questions_data)} questions committed.", flush=True)

        print("Database seeding completed successfully.", flush=True)
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

# Create tables
Base.metadata.create_all(bind=engine)
