"""
interview_module/pocketbase_client.py
Handles all PocketBase operations for interview persistence.
Falls back to in-memory storage if PocketBase is not configured.
"""

import os
import json
import requests
from typing import Optional, Dict, List
from dotenv import load_dotenv
import pathlib

_root = pathlib.Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / "utils" / ".env")

POCKETBASE_URL = os.getenv(
    "POCKETBASE_URL", "https://multi-agent-job-hunt-assistant.onrender.com"
)
POCKETBASE_EMAIL = os.getenv("POCKETBASE_EMAIL", "")
POCKETBASE_PASSWORD = os.getenv("POCKETBASE_PASSWORD", "")

_token_cache = {"token": None}


def is_configured() -> bool:
    """Check if PocketBase is configured and reachable."""
    try:
        r = requests.get(f"{POCKETBASE_URL}/api/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _get_token() -> Optional[str]:
    """Get or refresh admin auth token."""
    if _token_cache["token"]:
        return _token_cache["token"]
    if not POCKETBASE_EMAIL or not POCKETBASE_PASSWORD:
        return None
    try:
        r = requests.post(
            f"{POCKETBASE_URL}/api/admins/auth-with-password",
            json={"identity": POCKETBASE_EMAIL, "password": POCKETBASE_PASSWORD},
            timeout=5
        )
        if r.status_code == 200:
            _token_cache["token"] = r.json()["token"]
            return _token_cache["token"]
    except Exception as e:
        print(f"[PocketBase] Auth failed: {e}")
    return None


def _headers() -> Dict:
    token = _get_token()
    if token:
        return {"Authorization": token, "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


# ── Sessions ──────────────────────────────────────────────────────────────────

def save_session(session_id: str, session_data: Dict) -> bool:
    """Save or update a session in PocketBase."""
    if not is_configured():
        return False
    try:
        payload = {
            "session_id": session_id,
            "job_title": session_data.get("job_title", ""),
            "company": session_data.get("company", ""),
            "resume_text": session_data.get("resume_text", "")[:5000],  # Limit size
            "jd_text": session_data.get("jd_text", "")[:3000],
            "current_phase": session_data.get("current_phase", 1),
            "current_depth": session_data.get("current_depth", 0),
            "status": session_data.get("status", "active"),
            "resume_sections": json.dumps(session_data.get("resume_sections", {})),
            "projects_identified": json.dumps(session_data.get("projects_identified", [])),
        }

        # Check if exists
        r = requests.get(
            f"{POCKETBASE_URL}/api/collections/interview_sessions/records",
            params={"filter": f'session_id="{session_id}"'},
            headers=_headers(), timeout=5
        )
        items = r.json().get("items", []) if r.status_code == 200 else []

        if items:
            # Update
            record_id = items[0]["id"]
            r = requests.patch(
                f"{POCKETBASE_URL}/api/collections/interview_sessions/records/{record_id}",
                json=payload, headers=_headers(), timeout=5
            )
        else:
            # Create
            r = requests.post(
                f"{POCKETBASE_URL}/api/collections/interview_sessions/records",
                json=payload, headers=_headers(), timeout=5
            )

        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[PocketBase] save_session failed: {e}")
        return False


def load_session(session_id: str) -> Optional[Dict]:
    """Load a session from PocketBase by session_id."""
    if not is_configured():
        return None
    try:
        r = requests.get(
            f"{POCKETBASE_URL}/api/collections/interview_sessions/records",
            params={"filter": f'session_id="{session_id}"'},
            headers=_headers(), timeout=5
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                item = items[0]
                item["resume_sections"] = json.loads(item.get("resume_sections", "{}"))
                item["projects_identified"] = json.loads(item.get("projects_identified", "[]"))
                return item
    except Exception as e:
        print(f"[PocketBase] load_session failed: {e}")
    return None


def list_sessions(limit: int = 50) -> List[Dict]:
    """List recent sessions for dashboard."""
    if not is_configured():
        return []
    try:
        r = requests.get(
            f"{POCKETBASE_URL}/api/collections/interview_sessions/records",
            params={"sort": "-created", "perPage": limit},
            headers=_headers(), timeout=5
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception as e:
        print(f"[PocketBase] list_sessions failed: {e}")
    return []


# ── Turns ─────────────────────────────────────────────────────────────────────

def save_turn(session_id: str, turn: Dict) -> bool:
    """Save a single interview turn."""
    if not is_configured():
        return False
    try:
        payload = {
            "session_id": session_id,
            "phase": turn.get("phase", 1),
            "depth": turn.get("depth", 0),
            "question": turn.get("question", "")[:2000],
            "answer_transcript": turn.get("answer", turn.get("answer_transcript", ""))[:3000],
            "score": turn.get("score") or 0,
            "score_reason": turn.get("score_reason", "")[:500],
            "filler_words_count": turn.get("filler_count", 0),
            "hint_given": turn.get("hint_given", False),
        }
        r = requests.post(
            f"{POCKETBASE_URL}/api/collections/interview_turns/records",
            json=payload, headers=_headers(), timeout=5
        )
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[PocketBase] save_turn failed: {e}")
        return False


def load_turns(session_id: str) -> List[Dict]:
    """Load all turns for a session."""
    if not is_configured():
        return []
    try:
        r = requests.get(
            f"{POCKETBASE_URL}/api/collections/interview_turns/records",
            params={
                "filter": f'session_id="{session_id}"',
                "sort": "created",
                "perPage": 200
            },
            headers=_headers(), timeout=5
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception as e:
        print(f"[PocketBase] load_turns failed: {e}")
    return []


# ── Evaluations ───────────────────────────────────────────────────────────────

def save_evaluation(session_id: str, report: Dict) -> bool:
    """Save final evaluation report."""
    if not is_configured():
        return False
    try:
        payload = {
            "session_id": session_id,
            "overall_score": report.get("overall_score", 0),
            "phase_scores": json.dumps(report.get("phase_scores", {})),
            "strengths": json.dumps(report.get("strengths", [])),
            "gaps": json.dumps(report.get("gaps", [])),
            "improvement_tips": json.dumps(report.get("improvement_tips", [])),
            "overall_verdict": report.get("overall_verdict", "")[:1000],
            "report_json": json.dumps(report),
        }
        r = requests.post(
            f"{POCKETBASE_URL}/api/collections/interview_evaluations/records",
            json=payload, headers=_headers(), timeout=5
        )
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[PocketBase] save_evaluation failed: {e}")
        return False


def load_evaluation(session_id: str) -> Optional[Dict]:
    """Load evaluation report for a session."""
    if not is_configured():
        return None
    try:
        r = requests.get(
            f"{POCKETBASE_URL}/api/collections/interview_evaluations/records",
            params={"filter": f'session_id="{session_id}"'},
            headers=_headers(), timeout=5
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                item = items[0]
                item["report_json"] = json.loads(item.get("report_json", "{}"))
                return item["report_json"]
    except Exception as e:
        print(f"[PocketBase] load_evaluation failed: {e}")
    return None
