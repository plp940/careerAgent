import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

USAJOBS_API_KEY = os.getenv("USAJOBS_API_KEY")
USAJOBS_USER_AGENT = os.getenv("USAJOBS_USER_AGENT", "www.468lakshmiprasanna@gmail.com")

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 120))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

import time


def run_with_retry(crew, max_retries=3, wait_seconds=15):
    """Retry crew.kickoff() on rate limit with a wait."""
    for attempt in range(max_retries):
        try:
            return crew.kickoff()
        except Exception as e:
            if "rate_limit" in str(e).lower() or "ratelimit" in str(e).lower():
                if attempt < max_retries - 1:
                    print(
                        f"[Rate Limit] Waiting {wait_seconds}s before retry {attempt+2}..."
                    )
                    time.sleep(wait_seconds)
                else:
                    raise
            else:
                raise


def get_llm(temperature=0.3):
    """
    Returns OpenRouter LLM. Falls back to Groq if OpenRouter quota is exceeded or not configured.
    """
    import litellm

    litellm.set_verbose = False

    # Try OpenRouter first
    if OPENROUTER_API_KEY:
        try:
            return LLM(
                model="openrouter/google/gemma-4-26b-a4b-it:free",
                api_key=OPENROUTER_API_KEY,
                temperature=temperature,
                timeout=LLM_TIMEOUT,
            )
        except Exception:
            pass

    # Fallback: Groq
    if GROQ_API_KEY:
        try:
            return LLM(
                model=LLM_MODEL,
                api_key=GROQ_API_KEY,
                temperature=temperature,
                timeout=LLM_TIMEOUT,
            )
        except Exception:
            pass

    # Return dummy LLM to prevent import crashes when keys are missing.
    # Actual invocation will fail downstream if keys are not supplied.
    return LLM(
        model="openrouter/google/gemma-4-26b-a4b-it:free",
        api_key="DUMMY_KEY_FOR_IMPORT_RESILIENCE",
        temperature=temperature,
        timeout=LLM_TIMEOUT
    )
