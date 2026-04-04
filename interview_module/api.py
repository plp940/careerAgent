"""
Interview Practice Agent - FastAPI Backend
With PocketBase persistence (gracefully falls back to in-memory if PB unavailable)
"""

import os
import json
import tempfile
import time
import uuid
import base64
import pathlib
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv


# Load .env from both possible locations
_root = pathlib.Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / "utils" / ".env")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles  # ← FIX 3: import added

from interview_module.engine import InterviewEngine, SessionState, InterviewPhase
from interview_module.groq_http import transcribe_audio, text_to_speech, call_with_retry
from interview_module import pocketbase_client as pb

app = FastAPI(title="Interview Practice Agent", version="2.1.0")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"[API] PROJECT_ROOT: {PROJECT_ROOT}")
print(
    f"[API] interview.html found: {os.path.exists(os.path.join(PROJECT_ROOT, 'interview.html'))}"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = InterviewEngine()

# In-memory cache — always used as primary fast store
# PocketBase is secondary persistent store
sessions_cache: dict = {}
prefill_cache: dict = {}


# ── Serve HTML ────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {"message": "Interview Practice Agent API v2.0"}


@app.get("/interview")
async def serve_interview():
    html_path = os.path.join(PROJECT_ROOT, "interview.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    raise HTTPException(
        status_code=404, detail=f"interview.html not found at {html_path}"
    )


# ── FIX 1: Add /interview.html alias route ────────────────────────────────────
@app.get("/interview.html")
async def serve_interview_html():
    html_path = os.path.join(PROJECT_ROOT, "interview.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    raise HTTPException(
        status_code=404, detail=f"interview.html not found at {html_path}"
    )


# ── Streamlit handoff ─────────────────────────────────────────────────────────
@app.post("/prefill_session")
async def prefill_session(
    job_title: str = Form(...),
    company: str = Form(...),
    resume_text: str = Form(""),
    jd_text: str = Form(""),
):
    """
    Called from Streamlit to pre-store session data.
    Returns a short token that interview.html uses to load the data.
    Avoids putting long resume text in URL params.
    """
    token = str(uuid.uuid4())[:8]
    prefill_cache[token] = {
        "job_title": job_title,
        "company": company,
        "resume_text": resume_text,
        "jd_text": jd_text,
    }
    return {
        "token": token,
        "interview_url": f"http://localhost:8000/interview.html?token={token}",  # ← FIX 2: .html added
    }


@app.get("/prefill/{token}")
async def get_prefill(token: str):
    """HTML page calls this to get pre-loaded data using token."""
    data = prefill_cache.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    return data


# ── Start session ─────────────────────────────────────────────────────────────


@app.post("/start_session")
async def start_session(
    job_title: str = Form(...),
    company: str = Form(...),
    resume_text: Optional[str] = Form(""),
    jd_text: str = Form(...),
    resume_pdf: Optional[UploadFile] = File(None),
    interview_prep_text: Optional[str] = Form(""),
):
    try:
        if not resume_text and not resume_pdf:
            raise HTTPException(status_code=422, detail="Provide resume text or PDF")

        if resume_pdf and resume_pdf.filename:
            try:
                import fitz

                pdf_content = await resume_pdf.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(pdf_content)
                    tmp_path = tmp.name
                doc = fitz.open(tmp_path)
                resume_text = "\n".join([page.get_text() for page in doc])
                doc.close()
                os.unlink(tmp_path)
            except ImportError:
                raise HTTPException(
                    status_code=500, detail="Install pymupdf: pip install pymupdf"
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"PDF error: {str(e)}")

        if not resume_text or len(resume_text.strip()) < 50:
            raise HTTPException(status_code=422, detail="Resume too short or empty")

        resume_sections = engine.parse_resume_sections(resume_text)
        session_id = str(uuid.uuid4())

        session = SessionState(
            session_id=session_id,
            job_title=job_title,
            company=company,
            resume_text=resume_text,
            resume_sections=resume_sections,
            jd_text=jd_text,
        )

        session.projects_identified = engine.identify_projects(session)
        print(f"[API] Projects found: {len(session.projects_identified)}")

        # Use pre-generated interview prep questions for domain phase if provided
        if interview_prep_text and interview_prep_text.strip():
            prep_questions = _parse_interview_prep_questions(interview_prep_text)
            if prep_questions:
                session.domain_questions_list = prep_questions
                print(
                    f"[API] Using {len(prep_questions)} questions from Interview Prep tab"
                )
            else:
                session.domain_questions_list = engine.generate_domain_questions(
                    session
                )
        else:
            session.domain_questions_list = engine.generate_domain_questions(session)

        # First question
        bg_questions = engine.generate_background_questions(session)
        first_question = bg_questions[0]

        # Store in memory
        sessions_cache[session_id] = session

        # Persist to PocketBase (non-blocking — don't fail if PB is down)
        pb.save_session(
            session_id,
            {
                "job_title": job_title,
                "company": company,
                "resume_text": resume_text,
                "jd_text": jd_text,
                "resume_sections": resume_sections,
                "projects_identified": session.projects_identified,
                "current_phase": session.current_phase.value,
                "current_depth": session.current_depth,
                "status": session.status,
            },
        )

        audio_b64 = _generate_tts(first_question)

        return {
            "session_id": session_id,
            "phase": session.current_phase.name,
            "depth": session.current_depth,
            "question": first_question,
            "audio": audio_b64,
            "status": "active",
            "projects_found": len(session.projects_identified),
            "pb_connected": pb.is_configured(),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Submit answer ─────────────────────────────────────────────────────────────


@app.post("/submit_answer")
async def submit_answer(
    session_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
):
    try:
        session = sessions_cache.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status == "completed":
            raise HTTPException(status_code=400, detail="Interview already completed")

        # ── STT ───────────────────────────────────────────────────────────────
        answer_transcript = transcript or ""
        tmp_path = None

        if audio and audio.filename and not transcript:
            audio_content = await audio.read()
            print(f"[STT] Audio: {len(audio_content)} bytes")

            if len(audio_content) < 500:
                answer_transcript = (
                    "[No audio — please speak clearly or type your answer]"
                )
            else:
                ext = ".webm"
                if audio.filename:
                    _, file_ext = os.path.splitext(audio.filename)
                    if file_ext:
                        ext = file_ext

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=ext, mode="wb"
                ) as tmp:
                    tmp.write(audio_content)
                    tmp_path = tmp.name

                try:
                    answer_transcript = call_with_retry(
                        lambda: transcribe_audio(tmp_path),
                        max_retries=2,
                        wait_seconds=3,
                    )
                    print(f"[STT] Result: {answer_transcript[:80]}")
                except Exception as e:
                    print(f"[STT] Failed: {e}")
                    answer_transcript = (
                        f"[STT failed: {str(e)[:60]}. Please type your answer.]"
                    )
                finally:
                    if tmp_path:
                        for _ in range(3):
                            try:
                                os.unlink(tmp_path)
                                break
                            except:
                                time.sleep(0.1)

        # ── Anxiety detection ─────────────────────────────────────────────────
        should_break, anxiety_signals = engine.detect_anxiety_signals(answer_transcript)

        if should_break:
            break_msg = (
                "Let's pause here. Take a deep breath. Continue when you're ready."
            )
            return JSONResponse(
                {
                    "session_id": session_id,
                    "phase": session.current_phase.name,
                    "depth": session.current_depth,
                    "question": break_msg,
                    "audio": _generate_tts(break_msg),
                    "answer_transcript": answer_transcript,
                    "is_break": True,
                    "anxiety_signals": anxiety_signals,
                    "status": session.status,
                }
            )

        # ── Score current question ────────────────────────────────────────────
        current_q = ""
        current_correct = ""
        # Find the last question that doesn't have an answer yet
        for turn in reversed(session.questions_asked):
            if not turn.get("answer") and not turn.get("answer_transcript"):
                current_q = turn.get("question", "")
                current_correct = turn.get("correct_answer", "")
                break

        score, score_reason = None, ""
        if session.current_phase not in [InterviewPhase.BACKGROUND] and current_q:
            score, score_reason = engine.score_answer(
                current_q,
                answer_transcript,
                session.current_phase,
                session.current_depth,
                correct_answer=current_correct,
            )

        # ── Record the answered turn ──────────────────────────────────────────
        answered_turn = {
            "phase": session.current_phase.value,
            "depth": session.current_depth,
            "question": current_q,
            "answer": answer_transcript,
            "score": score,
            "score_reason": score_reason,
            "filler_count": anxiety_signals["filler_count"],
            "hint_given": False,
        }
        # Replace the unanswered preview or append
        replaced = False
        for i, turn in enumerate(session.questions_asked):
            if (
                turn.get("question") == current_q
                and not turn.get("answer")
                and not turn.get("answer_transcript")
            ):
                session.questions_asked[i] = answered_turn
                replaced = True
                break
        if not replaced:
            session.questions_asked.append(answered_turn)

        # Save turn to PocketBase
        pb.save_turn(session_id, answered_turn)

        # ── Determine next action ─────────────────────────────────────────────
        next_phase, next_depth, hint = engine.determine_next_action(
            session, answer_transcript
        )
        session.current_phase = next_phase
        session.current_depth = next_depth

        # ── Generate next question ────────────────────────────────────────────
        next_question = ""
        correct_for_next = ""
        hint_given = False

        if next_phase == InterviewPhase.COMPLETED:
            next_question = "Thank you for your time. That concludes our interview. Your evaluation report is being generated."
            session.status = "completed"

        elif next_phase == InterviewPhase.BACKGROUND:
            bg_qs = engine.generate_background_questions(session)
            idx = min(session.background_index, len(bg_qs) - 1)
            next_question = bg_qs[idx]

        elif next_phase == InterviewPhase.PRIMARY_PROJECT_DRILL:
            if session.projects_identified:
                prev_qa = [
                    q
                    for q in session.questions_asked
                    if q.get("phase") == InterviewPhase.PRIMARY_PROJECT_DRILL.value
                    and q.get("answer")
                ]
                next_question, hint_given = engine.generate_socratic_drill_question(
                    session,
                    str(session.projects_identified[0]),
                    prev_qa,
                    next_depth,
                    session.primary_drill_stuck,
                )
                session.primary_drill_stuck = False
            else:
                session.current_phase = InterviewPhase.DOMAIN_QUESTIONS
                next_phase = InterviewPhase.DOMAIN_QUESTIONS
                dq = session.domain_questions_list
                if dq:
                    item = dq[0]
                    next_question = (
                        item["question"] if isinstance(item, dict) else str(item)
                    )
                    correct_for_next = (
                        item.get("correct_answer", "") if isinstance(item, dict) else ""
                    )

        elif next_phase == InterviewPhase.SECONDARY_PROJECT_DRILL:
            if len(session.projects_identified) > 1:
                prev_qa = [
                    q
                    for q in session.questions_asked
                    if q.get("phase") == InterviewPhase.SECONDARY_PROJECT_DRILL.value
                    and q.get("answer")
                ]
                next_question, hint_given = engine.generate_socratic_drill_question(
                    session,
                    str(session.projects_identified[1]),
                    prev_qa,
                    next_depth,
                    session.secondary_drill_stuck,
                )
                session.secondary_drill_stuck = False
            else:
                session.current_phase = InterviewPhase.DOMAIN_QUESTIONS
                next_phase = InterviewPhase.DOMAIN_QUESTIONS
                dq = session.domain_questions_list
                idx = session.domain_question_index
                if idx < len(dq):
                    item = dq[idx]
                    next_question = (
                        item["question"] if isinstance(item, dict) else str(item)
                    )
                    correct_for_next = (
                        item.get("correct_answer", "") if isinstance(item, dict) else ""
                    )

        elif next_phase == InterviewPhase.DOMAIN_QUESTIONS:
            dq = session.domain_questions_list
            idx = session.domain_question_index
            if idx < len(dq):
                item = dq[idx]
                next_question = (
                    item["question"] if isinstance(item, dict) else str(item)
                )
                correct_for_next = (
                    item.get("correct_answer", "") if isinstance(item, dict) else ""
                )
            else:
                next_question = (
                    "Tell me about the most important technical concept in your field."
                )

        elif next_phase == InterviewPhase.BEHAVIORAL:
            bq = engine.generate_behavioral_questions(session)
            idx = min(session.behavioral_index, len(bq) - 1)
            next_question = bq[idx]

        # Store next question preview (only if not completed)
        if next_phase != InterviewPhase.COMPLETED and next_question:
            session.questions_asked.append(
                {
                    "question": next_question,
                    "correct_answer": correct_for_next,
                    "phase": next_phase.value,
                    "depth": next_depth,
                    "answer": None,  # Marks as unanswered
                }
            )

        # Update PocketBase session state
        pb.save_session(
            session_id,
            {
                "job_title": session.job_title,
                "company": session.company,
                "resume_text": session.resume_text,
                "jd_text": session.jd_text,
                "resume_sections": session.resume_sections,
                "projects_identified": session.projects_identified,
                "current_phase": session.current_phase.value,
                "current_depth": session.current_depth,
                "status": session.status,
            },
        )

        sessions_cache[session_id] = session
        audio_b64 = _generate_tts(next_question) if next_question else None

        return JSONResponse(
            {
                "session_id": session_id,
                "phase": session.current_phase.name,
                "depth": session.current_depth,
                "question": next_question,
                "audio": audio_b64,
                "answer_transcript": answer_transcript,
                "score": score,
                "score_reason": score_reason,
                "is_break": False,
                "anxiety_signals": anxiety_signals,
                "status": session.status,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Report ────────────────────────────────────────────────────────────────────


@app.get("/get_report/{session_id}")
async def get_report(session_id: str):
    # Try PocketBase first (cached from previous run)
    cached_report = pb.load_evaluation(session_id)
    if cached_report:
        return cached_report

    session = sessions_cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    report = engine.generate_evaluation_report(session_id, session)

    # Save to PocketBase
    pb.save_evaluation(session_id, report)

    return report


@app.post("/resume_session/{session_id}")
async def resume_session(session_id: str):
    session = sessions_cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "active"
    sessions_cache[session_id] = session
    pb.save_session(
        session_id,
        {
            "status": "active",
            "job_title": session.job_title,
            "company": session.company,
            "resume_text": session.resume_text,
            "jd_text": session.jd_text,
            "resume_sections": session.resume_sections,
            "projects_identified": session.projects_identified,
            "current_phase": session.current_phase.value,
            "current_depth": session.current_depth,
        },
    )
    return {"status": "resumed", "session_id": session_id}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = sessions_cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "job_title": session.job_title,
        "company": session.company,
        "current_phase": session.current_phase.name,
        "current_depth": session.current_depth,
        "status": session.status,
        "questions_asked": len([q for q in session.questions_asked if q.get("answer")]),
        "projects_identified": len(session.projects_identified),
    }


@app.get("/past_sessions")
async def list_past_sessions():
    """List past interview sessions from PocketBase."""
    sessions = pb.list_sessions(limit=20)
    return {"sessions": sessions, "count": len(sessions)}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_tts(text: str) -> Optional[str]:
    if not text:
        return None
    try:
        audio_bytes = call_with_retry(
            lambda: text_to_speech(text), max_retries=2, wait_seconds=3
        )
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"[TTS] Failed: {e}")
        return None


def _parse_interview_prep_questions(prep_text: str) -> list:
    """
    Parse questions from Interview Prep agent output (markdown format).
    Extracts Q&A pairs from the Interview Prep tab output.
    """
    import re

    questions = []
    # Match **Q1: question** followed by 💡 Suggested Answer: answer
    pattern = (
        r"\*\*Q\d+:\s*(.+?)\*\*\s*\n💡 Suggested Answer:\s*(.+?)(?=\n\n|\*\*Q\d+:|##|$)"
    )
    matches = re.findall(pattern, prep_text, re.DOTALL)
    for q, a in matches:
        questions.append({"question": q.strip(), "correct_answer": a.strip()[:500]})
    if not questions:
        # Fallback: just extract numbered questions
        lines = prep_text.split("\n")
        for line in lines:
            if re.match(r"\*\*Q\d+:", line):
                q = re.sub(r"\*\*Q\d+:\s*|\*\*", "", line).strip()
                if q:
                    questions.append({"question": q, "correct_answer": ""})
    return questions[:6]


# ── FIX 3: Mount static files LAST (catches everything else) ──────────────────
# This serves interview.html and any JS/CSS assets at root level
app.mount("/", StaticFiles(directory=PROJECT_ROOT, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
