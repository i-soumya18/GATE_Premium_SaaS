import os
import json
import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./gate_saas.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
    subject = Column(String, nullable=False) # e.g. "CS" or "DA"
    topic = Column(String, default="General Aptitude")
    difficulty = Column(String, default="Medium")
    year = Column(Integer, nullable=False)
    session = Column(String, nullable=False)
    question_number = Column(Integer, nullable=False)
    type = Column(String, nullable=False) # MCQ, MSQ, NAT
    marks = Column(Integer, default=1)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False) # JSON array of options
    correct_answer = Column(String, nullable=False)
    diagram_path = Column(String, default="")

    responses = relationship("Response", back_populates="question")
    solo_responses = relationship("SoloResponse", back_populates="question")

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(String, default="")
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0) # seconds

    attempt = relationship("Attempt", back_populates="responses")
    question = relationship("Question", back_populates="responses")

class SoloResponse(Base):
    __tablename__ = "solo_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="solo_responses")
    question = relationship("Question", back_populates="solo_responses")

# ============================================================
# SEEDER
# ============================================================

def seed_questions():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Question).count() > 0:
            print("Database questions already seeded.")
            return

        qbank_path = Path("GATE_PYQs/qbank.json")
        if not qbank_path.exists():
            print("Seeder: qbank.json not found. Skipping questions seed.")
            return

        with qbank_path.open("r", encoding="utf-8") as f:
            questions_data = json.load(f)

        print(f"Seeding {len(questions_data)} questions into database...")
        for q in questions_data:
            # Skip incomplete questions
            if not q.get("id") or not q.get("question_text"):
                continue

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
                diagram_path=q.get("diagram_path", "")
            )
            db.merge(db_q) # merge acts as insert-or-update

        db.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

# Create tables
Base.metadata.create_all(bind=engine)
