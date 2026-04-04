"""
setup_pocketbase.py
Run once to create all required PocketBase collections.
Usage: python setup_pocketbase.py

Prerequisites:
1. PocketBase running at localhost:8090
2. POCKETBASE_EMAIL and POCKETBASE_PASSWORD set in .env
"""

import requests
import json
import os
import pathlib
from dotenv import load_dotenv

_root = pathlib.Path(__file__).parent
load_dotenv(_root / ".env")
load_dotenv(_root / "utils" / ".env")

PB_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
PB_EMAIL = os.getenv("POCKETBASE_EMAIL")
PB_PASSWORD = os.getenv("POCKETBASE_PASSWORD")


def get_token():
    r = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": PB_EMAIL, "password": PB_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["token"]


def create_collection(token, schema):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    r = requests.post(f"{PB_URL}/api/collections", json=schema, headers=headers)
    if r.status_code == 400 and "already exists" in r.text:
        print(f"  Collection '{schema['name']}' already exists — skipping")
        return True
    r.raise_for_status()
    print(f"  ✅ Created collection: {schema['name']}")
    return True


def main():
    print("Connecting to PocketBase...")
    token = get_token()
    print("✅ Authenticated\n")
    print("Creating collections...")

    collections = [
        {
            "name": "interview_sessions",
            "type": "base",
            "schema": [
                {"name": "session_id", "type": "text", "required": True},
                {"name": "job_title", "type": "text", "required": False},
                {"name": "company", "type": "text", "required": False},
                {"name": "resume_text", "type": "text", "required": False},
                {"name": "jd_text", "type": "text", "required": False},
                {"name": "resume_sections", "type": "json", "required": False},
                {"name": "projects_identified", "type": "json", "required": False},
                {"name": "current_phase", "type": "number", "required": False},
                {"name": "current_depth", "type": "number", "required": False},
                {"name": "status", "type": "text", "required": False},
            ],
        },
        {
            "name": "interview_turns",
            "type": "base",
            "schema": [
                {"name": "session_id", "type": "text", "required": True},
                {"name": "phase", "type": "number", "required": True},
                {"name": "depth", "type": "number", "required": False},
                {"name": "question", "type": "text", "required": False},
                {"name": "answer_transcript", "type": "text", "required": False},
                {"name": "score", "type": "number", "required": False},
                {"name": "score_reason", "type": "text", "required": False},
                {"name": "filler_words_count", "type": "number", "required": False},
                {"name": "hint_given", "type": "bool", "required": False},
            ],
        },
        {
            "name": "interview_evaluations",
            "type": "base",
            "schema": [
                {"name": "session_id", "type": "text", "required": True},
                {"name": "overall_score", "type": "number", "required": False},
                {"name": "phase_scores", "type": "json", "required": False},
                {"name": "strengths", "type": "json", "required": False},
                {"name": "gaps", "type": "json", "required": False},
                {"name": "improvement_tips", "type": "json", "required": False},
                {"name": "overall_verdict", "type": "text", "required": False},
                {"name": "report_json", "type": "json", "required": False},
            ],
        },
        # ── Job Applications (migrated from CSV) ──────────────────────────────
        {
            "name": "job_applications",
            "type": "base",
            "schema": [
                {"name": "job_title", "type": "text", "required": True},
                {"name": "agency", "type": "text", "required": True},
                {"name": "source", "type": "text", "required": False},
                {"name": "match_score", "type": "number", "required": False},
                {"name": "resume_summary", "type": "text", "required": False},
                {"name": "ats_resume_file", "type": "text", "required": False},
                {"name": "date_applied", "type": "text", "required": False},
            ],
        },
    ]

    for col in collections:
        create_collection(token, col)

    print("\n✅ All collections ready!")
    print(f"Admin UI: {PB_URL}/_/")


if __name__ == "__main__":
    main()
