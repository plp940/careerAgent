"""
Groq API wrapper using HTTP requests (no SDK required)
Loads .env automatically so GROQ_API_KEY is always available
"""

import os
import requests
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import pathlib

# Find .env whether it's in root or utils/
_root = pathlib.Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / "utils" / ".env")  # my project's actual location of .env


def _get_api_key():
    """Get API key fresh each call — never cached as None"""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not set. Add it to your .env file.")
    return key


def chat_completion(
    model: str,
    messages: list,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Call Groq chat completion API via HTTP"""
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def transcribe_audio(audio_file_path: str, model: str = "whisper-large-v3") -> str:
    """
    Transcribe audio using Groq Whisper API.
    Sends as audio/wav — more reliable than webm for Groq Whisper.
    """
    headers = {"Authorization": f"Bearer {_get_api_key()}"}

    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()

    # Determine content type from extension
    ext = os.path.splitext(audio_file_path)[1].lower()
    mime_map = {
        ".webm": "audio/webm",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
    }
    mime_type = mime_map.get(ext, "audio/webm")
    filename = f"audio{ext}"

    files = {"file": (filename, audio_bytes, mime_type)}
    data = {"model": model, "response_format": "text", "language": "en"}

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers=headers,
        files=files,
        data=data,
        timeout=60,
    )
    response.raise_for_status()

    # Groq returns plain text when response_format=text
    result = response.text.strip()
    return result if result else "[No speech detected]"


def text_to_speech(
    text: str, model: str = "playai-tts", voice: str = "Celeste-PlayAI"
) -> bytes:
    """Convert text to speech using Groq TTS API"""
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "voice": voice, "input": text}

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/speech",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def call_with_retry(func, max_retries=3, wait_seconds=5):
    """Retry API calls on rate limit or transient errors"""
    last_err = None
    for attempt in range(max_retries):
        try:
            return func()
        except requests.exceptions.HTTPError as e:
            last_err = e
            if attempt < max_retries - 1:
                code = e.response.status_code if e.response else 0
                if code == 429 or code >= 500:
                    print(
                        f"[Retry] HTTP {code}, waiting {wait_seconds}s... (attempt {attempt+1})"
                    )
                    time.sleep(wait_seconds)
                else:
                    raise
            else:
                raise
        except requests.exceptions.Timeout:
            last_err = Exception("Timeout")
            if attempt < max_retries - 1:
                print(f"[Retry] Timeout, retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
            else:
                raise
        except Exception:
            raise
    if last_err:
        raise last_err
