from crewai import Crew, Process, LLM
from agents.jd_analyst import get_jd_analyst_agent, create_jd_analysis_task
from agents.resume_cl_agent import get_resume_cl_agent, create_resume_cl_task
# from agents.messaging_agent import get_messaging_agent, create_messaging_task
from agents.scorer_agent import (
    get_scorer_agent,
    create_scoring_task,
    parse_score_output,
)
from agents.interview_agent import get_interview_agent, create_interview_task
from utils.tracking import log_application, save_cover_letter_file
import os
import time
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 600))


def extract_between_markers(text, start, end=None):
    try:
        start_idx = text.index(start) + len(start)
        end_idx = text.index(end, start_idx) if end else len(text)
        return text[start_idx:end_idx].strip()
    except ValueError:
        return "Not found"


def _openrouter_llm(temperature=0.3):
    """Build a fresh OpenRouter LLM object."""
    return LLM(
        model="openrouter/meta-llama/llama-3.1-70b-instruct:free",
        api_key=OPENROUTER_API_KEY,
        temperature=temperature,
        timeout=LLM_TIMEOUT,
    )


def _swap_crew_to_openrouter(crew):
    """
    Rebuild crew with every agent's LLM swapped to OpenRouter.
    Called at runtime when Groq daily limit is hit.
    """
    for agent in crew.agents:
        temp = 0.3
        try:
            temp = float(agent.llm.temperature) if agent.llm.temperature else 0.3
        except Exception:
            pass
        agent.llm = _openrouter_llm(temperature=temp)

    return Crew(
        agents=crew.agents,
        tasks=crew.tasks,
        process=Process.sequential,
        verbose=getattr(crew, "verbose", False),
    )


def run_with_retry(crew, max_retries=2, wait_seconds=15):
    for attempt in range(max_retries):
        try:
            return crew.kickoff()
        except Exception as e:
            err = str(e).lower()
            print(f"[DEBUG] Exception type: {type(e).__name__}")
            print(f"[DEBUG] Error string: {err[:300]}")
            print(f"[DEBUG] 'rate_limit' in err: {'rate_limit' in err}")
            print(f"[DEBUG] OPENROUTER_API_KEY set: {bool(OPENROUTER_API_KEY)}")

            if "rate_limit" in err or "ratelimit" in err:
                if OPENROUTER_API_KEY:
                    print("[Fallback] Switching to OpenRouter...")
                    crew = _swap_crew_to_openrouter(crew)
                    return crew.kickoff()
                else:
                    raise RuntimeError(
                        "Rate limit hit, no OPENROUTER_API_KEY set"
                    ) from e
            else:
                raise


def run_pipeline(job_data, resume_text, user_bio):
    job_summary = job_data["UserArea"]["Details"]["JobSummary"]
    agency_name = job_data.get("OrganizationName", "Unknown Agency")
    job_title = job_data.get("PositionTitle", "Unknown Position")
    source = job_data.get("_source", "🏛️ USAJobs")

    # ── Agent 1: Scorer ───────────────────────────────────────────────────────
    scorer_agent = get_scorer_agent()
    scoring_task = create_scoring_task(scorer_agent, job_summary, resume_text)
    score_crew = Crew(
        agents=[scorer_agent],
        tasks=[scoring_task],
        process=Process.sequential,
        verbose=False,
    )
    run_with_retry(score_crew)
    score_data = parse_score_output(str(scoring_task.output))
    missing_keywords_str = ", ".join(score_data.get("missing_keywords", []))

    time.sleep(5)

    # ── Agents 2-4: JD Analyst + Resume/CL + Outreach ────────────────────────
    jd_agent = get_jd_analyst_agent()
    resume_agent = get_resume_cl_agent()
    #message_agent = get_messaging_agent()

    jd_task = create_jd_analysis_task(jd_agent, job_summary)
    resume_task = create_resume_cl_task(
        resume_agent,
        job_summary,
        resume_text,
        missing_keywords_str,
        user_bio=user_bio,  # add this
        agency_name=agency_name,
    )
    #message_task = create_messaging_task(
     #   message_agent, job_summary, agency_name, user_bio)

    main_crew = Crew(
        agents=[jd_agent, resume_agent],
        tasks=[jd_task, resume_task],
        process=Process.sequential,
    )
    main_result = run_with_retry(main_crew)

    time.sleep(5)

    # ── Agent 5: Interview Prep ───────────────────────────────────────────────
    interview_agent = get_interview_agent()
    interview_task = create_interview_task(interview_agent, job_summary, resume_text)
    interview_crew = Crew(
        agents=[interview_agent],
        tasks=[interview_task],
        process=Process.sequential,
        verbose=False,
    )
    run_with_retry(interview_crew)

    # ── Extract outputs ───────────────────────────────────────────────────────
    resume_output = str(resume_task.output)
    resume_summary = extract_between_markers(resume_output, "<<RESUME_SUMMARY>>", "<<COVER_LETTER>>")
    cover_letter   = extract_between_markers(resume_output, "<<COVER_LETTER>>", "<<OUTREACH_MESSAGE>>")
    outreach_msg   = extract_between_markers(resume_output, "<<OUTREACH_MESSAGE>>")

    # ── Persist ───────────────────────────────────────────────────────────────
    log_application(
        job_title=job_title,
        agency=agency_name,
        resume_summary=resume_summary,
        match_score=score_data.get("match_score", 0),
        source=source,
    )
    save_cover_letter_file(job_title, cover_letter)

    return {
        "job_title": job_title,
        "agency_name": agency_name,
        "source": source,
        "score_data": score_data,
        "jd_analysis": str(jd_task.output),
        "resume_summary": resume_summary,
        "cover_letter": cover_letter,
        "outreach_message":  outreach_msg,
        "interview_prep": str(interview_task.output),
    }
