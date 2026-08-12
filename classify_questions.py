#!/usr/bin/env python3

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Load env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

QBANK_FILE = Path("GATE_PYQs/qbank.json")

def main():
    if not QBANK_FILE.exists():
        print("No qbank.json found. Please run the parser server first.")
        return

    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not configured in .env!")
        return

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.1-flash-lite")

    # Load questions
    with QBANK_FILE.open("r", encoding="utf-8") as f:
        qbank = json.load(f)

    # Filter questions missing topic or difficulty
    missing = [i for i, q in enumerate(qbank) if "topic" not in q or "difficulty" not in q]
    
    if not missing:
        print("All questions already classified!")
        return

    print(f"Found {len(missing)} questions to classify. Starting classification pipeline...")

    classified_count = 0
    for idx in missing:
        q = qbank[idx]
        q_subject = q.get("subject", "CS")
        q_type = q.get("type", "MCQ")
        q_marks = q.get("marks", 1)
        q_text = q.get("question_text", "")
        q_options = "\n".join(q.get("options", []))

        prompt = f"""
        Classify this GATE exam question into its syllabus topic and estimate its difficulty.
        
        Subject: {q_subject}
        Question Type: {q_type}
        Marks: {q_marks}
        Question Text:
        {q_text}
        
        Options:
        {q_options}
        
        Your classification MUST choose from one of the following topics based on the subject:
        
        If Subject is CS:
        - Engineering Mathematics
        - Discrete Mathematics
        - Digital Logic
        - Computer Organization and Architecture (COA)
        - Programming and Data Structures
        - Algorithms
        - Theory of Computation (TOC)
        - Compiler Design
        - Operating Systems (OS)
        - Databases (DBMS)
        - Computer Networks (CN)
        - General Aptitude
        
        If Subject is DA:
        - Linear Algebra
        - Calculus and Optimization
        - Probability and Statistics
        - Python Programming and Data Structures
        - Algorithms
        - Database Management and Warehousing
        - Machine Learning (ML)
        - Artificial Intelligence (AI)
        - General Aptitude
        
        Estimate difficulty as one of: "Easy", "Medium", "Hard".
        
        Output the response strictly in this JSON format:
        {{
          "topic": "Selected Topic name",
          "difficulty": "Easy/Medium/Hard"
        }}
        """

        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                }
            )
            result = json.loads(response.text)
            topic = result.get("topic")
            difficulty = result.get("difficulty")

            if topic and difficulty:
                q["topic"] = str(topic).strip()
                q["difficulty"] = str(difficulty).strip()
                classified_count += 1
                print(f"[{classified_count}/{len(missing)}] Classified {q['id']} as [{q['topic']}] ({q['difficulty']})")

                # Save periodically
                if classified_count % 10 == 0 or classified_count == len(missing):
                    with QBANK_FILE.open("w", encoding="utf-8") as f:
                        json.dump(qbank, f, indent=2)
            
            time.sleep(0.8)  # prevent rate limit
        except Exception as e:
            print(f"Error classifying {q['id']}: {e}")
            time.sleep(2.0)

    print(f"Classification complete! Classified {classified_count} questions.")

if __name__ == "__main__":
    main()
