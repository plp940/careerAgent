from crewai import Agent, Task, LLM
#from utils.config import GROQ_API_KEY, LLM_MODEL, LLM_TIMEOUT
from utils.config import get_llm
#llm = LLM(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0.1, timeout=LLM_TIMEOUT)
llm = get_llm(temperature=0.1)

def get_scorer_agent():
    return Agent(
        role="ATS Resume Scorer",
        goal="Objectively score how well a resume matches a job description",
        backstory=(
            "You are a senior ATS specialist and technical recruiter with 15 years of "
            "experience screening resumes for AI, ML, software engineering, and government "
            "tech roles. You evaluate resumes with precision, identifying exact keyword "
            "matches, skill gaps, and giving actionable improvement advice."
        ),
        llm=llm,
        verbose=True,
    )


def create_scoring_task(agent, job_summary, resume_text):
    return Task(
        description=f"""
        Score the resume against the job description below.

        Return EXACTLY this format — no extra text, no preamble:

        MATCH_SCORE: [integer 0-100]
        MATCHED_KEYWORDS: [comma-separated keywords found in BOTH resume and JD]
        MISSING_KEYWORDS: [comma-separated important JD keywords ABSENT from resume]
        STRENGTHS:
        • [strength 1]
        • [strength 2]
        • [strength 3]
        GAPS:
        • [gap 1]
        • [gap 2]
        • [gap 3]
        RECOMMENDATION: [2 sentences: one on overall fit, one on what to improve]

        --- Job Description ---
        {job_summary}

        --- Resume ---
        {resume_text}
        """,
        expected_output="Structured score block with MATCH_SCORE, MATCHED_KEYWORDS, MISSING_KEYWORDS, STRENGTHS, GAPS, RECOMMENDATION.",
        agent=agent,
    )


def parse_score_output(raw: str) -> dict:
    """Parse scorer agent output into a clean dict. Handles minor formatting variations."""
    result = {
        "match_score": 0,
        "matched_keywords": [],
        "missing_keywords": [],
        "strengths": [],
        "gaps": [],
        "recommendation": "",
    }

    current_key = None

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("MATCH_SCORE:"):
            try:
                result["match_score"] = int(
                    line.split(":", 1)[1].strip().split("/")[0].strip()
                )
            except ValueError:
                result["match_score"] = 0

        elif line.startswith("MATCHED_KEYWORDS:"):
            val = line.split(":", 1)[1].strip()
            result["matched_keywords"] = [
                k.strip() for k in val.split(",") if k.strip()
            ]
            current_key = None

        elif line.startswith("MISSING_KEYWORDS:"):
            val = line.split(":", 1)[1].strip()
            result["missing_keywords"] = [
                k.strip() for k in val.split(",") if k.strip()
            ]
            current_key = None

        elif line.startswith("STRENGTHS:"):
            current_key = "strengths"
            val = line.split(":", 1)[1].strip()
            if val:
                result["strengths"].append(val)

        elif line.startswith("GAPS:"):
            current_key = "gaps"
            val = line.split(":", 1)[1].strip()
            if val:
                result["gaps"].append(val)

        elif line.startswith("RECOMMENDATION:"):
            current_key = "recommendation"
            result["recommendation"] = line.split(":", 1)[1].strip()

        elif current_key in ("strengths", "gaps") and line.startswith("•"):
            result[current_key].append(line[1:].strip())

        elif current_key == "recommendation":
            result["recommendation"] += " " + line

    return result
