"""
utils/tracking.py
Application tracking — PocketBase primary, CSV fallback.
"""

import csv
import os
import datetime
import re
import json
import requests
from typing import Optional
from dotenv import load_dotenv
import pathlib

_root = pathlib.Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / "utils" / ".env")

# ── Config ────────────────────────────────────────────────────────────────────

LOG_PATH = "data/applications_log.csv"

HEADERS = [
    "Job Title",
    "Agency",
    "Source",
    "Match Score",
    "Resume Summary",
    "ATS Resume File",
    "Date Applied",
]

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
POCKETBASE_EMAIL = os.getenv("POCKETBASE_EMAIL", "")
POCKETBASE_PASSWORD = os.getenv("POCKETBASE_PASSWORD", "")

_token_cache = {"token": None}


# ── PocketBase helpers ────────────────────────────────────────────────────────


def _pb_is_configured() -> bool:
    try:
        r = requests.get(f"{POCKETBASE_URL}/api/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _pb_get_token() -> Optional[str]:
    if _token_cache["token"]:
        return _token_cache["token"]
    if not POCKETBASE_EMAIL or not POCKETBASE_PASSWORD:
        return None
    try:
        r = requests.post(
            f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": POCKETBASE_EMAIL, "password": POCKETBASE_PASSWORD},
            timeout=5,
        )
        if r.status_code == 200:
            _token_cache["token"] = r.json()["token"]
            return _token_cache["token"]
    except Exception as e:
        print(f"[PocketBase] Auth failed: {e}")
    return None


def _pb_headers() -> dict:
    token = _pb_get_token()
    if token:
        return {"Authorization": token, "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


# ── Cover letter (unchanged — stays on disk) ──────────────────────────────────


def save_cover_letter_file(job_title, cover_letter, directory="data/cover_letters"):
    job_title = re.sub(r'[\\/*?:"<>|]', "_", job_title)
    os.makedirs(directory, exist_ok=True)
    filename = f"{job_title}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(cover_letter)


# ── Duplicate check ───────────────────────────────────────────────────────────


def is_duplicate(job_title: str, agency: str, filepath=LOG_PATH) -> bool:
    """Check for duplicates in PocketBase first, fall back to CSV."""
    if _pb_is_configured():
        try:
            filter_q = f'job_title="{job_title.strip()}" && agency="{agency.strip()}"'
            r = requests.get(
                f"{POCKETBASE_URL}/api/collections/job_applications/records",
                params={"filter": filter_q, "perPage": 1},
                headers=_pb_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                return len(r.json().get("items", [])) > 0
        except Exception as e:
            print(f"[Tracker] PB duplicate check failed: {e}")

    # CSV fallback
    if not os.path.exists(filepath):
        return False
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row.get("Job Title", "").strip().lower() == job_title.strip().lower()
                and row.get("Agency", "").strip().lower() == agency.strip().lower()
            ):
                return True
    return False


# ── Log application ───────────────────────────────────────────────────────────


def log_application(
    job_title,
    agency,
    resume_summary,
    match_score=0,
    source="USAJobs",
    ats_resume_file="",
    filepath=LOG_PATH,
) -> bool:
    """Log application. Tries PocketBase first, falls back to CSV."""
    if is_duplicate(job_title, agency, filepath):
        print(f"[Tracker] Duplicate skipped: {job_title} at {agency}")
        return False

    date_applied = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── PocketBase ────────────────────────────────────────────────────────────
    if _pb_is_configured():
        try:
            payload = {
                "job_title": job_title.strip(),
                "agency": agency.strip(),
                "source": source.strip(),
                "match_score": int(match_score),
                "resume_summary": resume_summary.strip()[:150],
                "ats_resume_file": ats_resume_file,
                "date_applied": date_applied,
            }
            r = requests.post(
                f"{POCKETBASE_URL}/api/collections/job_applications/records",
                json=payload,
                headers=_pb_headers(),
                timeout=5,
            )
            if r.status_code in [200, 201]:
                print(
                    f"[Tracker] PB logged: {job_title} at {agency} | Score: {match_score}"
                )
                return True
            else:
                print(f"[Tracker] PB log failed ({r.status_code}), falling back to CSV")
        except Exception as e:
            print(f"[Tracker] PB log error: {e}, falling back to CSV")

    # ── CSV fallback ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(HEADERS)
        writer.writerow(
            [
                job_title.strip(),
                agency.strip(),
                source.strip(),
                match_score,
                resume_summary.strip()[:150],
                ats_resume_file,
                date_applied,
            ]
        )
    print(f"[Tracker] CSV logged: {job_title} at {agency} | Score: {match_score}")
    return True


# ── Update ATS resume file ────────────────────────────────────────────────────


def update_ats_resume_file(job_title, agency, ats_filepath, filepath=LOG_PATH) -> bool:
    """Update the ATS resume path for an existing application."""
    if _pb_is_configured():
        try:
            filter_q = f'job_title="{job_title.strip()}" && agency="{agency.strip()}"'
            r = requests.get(
                f"{POCKETBASE_URL}/api/collections/job_applications/records",
                params={"filter": filter_q, "perPage": 1},
                headers=_pb_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    record_id = items[0]["id"]
                    r2 = requests.patch(
                        f"{POCKETBASE_URL}/api/collections/job_applications/records/{record_id}",
                        json={"ats_resume_file": ats_filepath},
                        headers=_pb_headers(),
                        timeout=5,
                    )
                    if r2.status_code == 200:
                        print(f"[Tracker] PB updated ATS resume for: {job_title}")
                        return True
        except Exception as e:
            print(f"[Tracker] PB update error: {e}, falling back to CSV")

    # CSV fallback
    if not os.path.exists(filepath):
        return False
    rows = []
    updated = False
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row.get("Job Title", "").strip().lower() == job_title.strip().lower()
                and row.get("Agency", "").strip().lower() == agency.strip().lower()
            ):
                row["ATS Resume File"] = ats_filepath
                updated = True
            if "ATS Resume File" not in row:
                row["ATS Resume File"] = ""
            rows.append(row)
    if updated:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[Tracker] CSV updated ATS resume for: {job_title}")
    return updated


# ── Delete application ────────────────────────────────────────────────────────


def delete_application(job_title, agency, filepath=LOG_PATH) -> bool:
    """Delete an application by job title + agency."""
    if _pb_is_configured():
        try:
            filter_q = f'job_title="{job_title.strip()}" && agency="{agency.strip()}"'
            r = requests.get(
                f"{POCKETBASE_URL}/api/collections/job_applications/records",
                params={"filter": filter_q, "perPage": 1},
                headers=_pb_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    record_id = items[0]["id"]
                    r2 = requests.delete(
                        f"{POCKETBASE_URL}/api/collections/job_applications/records/{record_id}",
                        headers=_pb_headers(),
                        timeout=5,
                    )
                    if r2.status_code == 204:
                        print(f"[Tracker] PB deleted: {job_title} at {agency}")
                        return True
        except Exception as e:
            print(f"[Tracker] PB delete error: {e}, falling back to CSV")

    # CSV fallback
    if not os.path.exists(filepath):
        return False
    rows = []
    deleted = False
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if (
                row.get("Job Title", "").strip().lower() == job_title.strip().lower()
                and row.get("Agency", "").strip().lower() == agency.strip().lower()
            ):
                deleted = True
                continue
            rows.append(row)
    if deleted:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[Tracker] CSV deleted: {job_title} at {agency}")
    return deleted


# ── Load applications ─────────────────────────────────────────────────────────


def load_applications(filepath=LOG_PATH) -> list:
    """Load all applications. PocketBase first, CSV fallback."""
    if _pb_is_configured():
        try:
            r = requests.get(
                f"{POCKETBASE_URL}/api/collections/job_applications/records",
                params={"sort": "-date_applied", "perPage": 500},
                headers=_pb_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                items = r.json().get("items", [])
                # Normalize keys to match original CSV header names
                # so the rest of your Streamlit dashboard code needs zero changes
                normalized = []
                for item in items:
                    normalized.append(
                        {
                            "Job Title": item.get("job_title", ""),
                            "Agency": item.get("agency", ""),
                            "Source": item.get("source", ""),
                            "Match Score": item.get("match_score", 0),
                            "Resume Summary": item.get("resume_summary", ""),
                            "ATS Resume File": item.get("ats_resume_file", ""),
                            "Date Applied": item.get("date_applied", ""),
                            "_pb_id": item.get("id", ""),  # bonus: PB record id
                        }
                    )
                return normalized
        except Exception as e:
            print(f"[Tracker] PB load error: {e}, falling back to CSV")

    # CSV fallback
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
