# Interview Practice Agent - Setup & Run Guide

## Overview
A real-time AI-powered voice interview system with 5 interview phases, anxiety detection, and detailed evaluation reports.

## Quick Start

### Step 1: Install Dependencies
```bash
# In your activated environment
pip install fastapi uvicorn pymupdf websockets

# Or use requirements.txt
pip install -r requirements.txt
```

### Step 2: Environment Variables
Ensure your `.env` file has:
```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url  # Optional - uses in-memory storage if not set
SUPABASE_KEY=your_supabase_key  # Optionaluus
```

### Step 3: Run the FastAPI Server
```bash
# From the project root directory
python -m uvicorn interview_module.api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### Step 4: Access the Interview
1. Open `interview.html` in a browser directly, OR
2. Use the Streamlit app: `streamlit run streamlit_app.py`
   - Navigate to "🎤 Interview Practice" tab
   - Fill in details and click "Start Live Interview"

## Architecture

```
Browser (interview.html) ←→ FastAPI (port 8000) ←→ Groq API
                                        ↓
                              In-Memory Session Store
                              (or Supabase for persistence)
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/start_session` | POST | Initialize interview session |
| `/submit_answer` | POST | Submit audio answer, get next question |
| `/get_report/{session_id}` | GET | Get final evaluation report |
| `/session/{session_id}` | GET | Get session state |
| `/resume_session/{session_id}` | POST | Resume after break |

## Interview Flow

1. **Phase 1 - Background**: General questions about experience (2-3 questions)
2. **Phase 2 - Primary Project Drill**: Socratic drilling on most relevant project (up to 5 depth levels)
3. **Phase 3 - Secondary Project Drill**: Deep dive into second experience
4. **Phase 4 - Domain Questions**: 4-6 technical questions specific to role
5. **Phase 5 - Behavioral**: Standard behavioral questions

## Features

### Voice Pipeline
- **Record**: Browser MediaRecorder → WebM audio
- **STT**: Groq Whisper Large v3
- **LLM**: Groq Llama 3.3 70B Versatile
- **TTS**: Groq PlayAI TTS (Celeste voice)

### Anxiety Detection
- Detects filler words: um, uh, like, you know, etc.
- Monitors pause duration
- Triggers break suggestion if 5+ fillers or 10+ second pause

### Scoring
- Technical depth score (1-10 per phase)
- Overall weighted score
- Detailed improvement tips in final report

## Troubleshooting

### Microphone Not Working
- Ensure browser has mic permissions
- Use Chrome or Firefox (Safari has limited support)
- Check that `http://localhost:8000` is allowed in browser permissions

### Groq API Errors
- Verify `GROQ_API_KEY` is set correctly
- Check Groq dashboard for rate limits
- The system has automatic retry with 3-second delays

### CORS Errors
- Ensure FastAPI is running with CORS enabled (default)
- Check browser console for blocked requests
- Try clearing browser cache

### Audio Not Playing
- Browser may block autoplay; click replay button
- Check browser audio permissions
- TTS errors return text-only mode automatically

## Running Both Systems

To run both Streamlit and FastAPI simultaneously:

**Terminal 1 - FastAPI:**
```bash
uvicorn interview_module.api:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Streamlit:**
```bash
streamlit run streamlit_app.py
```

Access Streamlit at `http://localhost:8501`

## File Structure

```
interview_module/
├── __init__.py          # Module init
├── engine.py            # Interview state machine, question generation
└── api.py               # FastAPI endpoints

interview.html           # Frontend UI
supabase_schema.sql      # Database schema (if using Supabase)
requirements.txt         # All dependencies
INTERVIEW_README.md      # This file
```

## Production Considerations

1. **Database**: Replace in-memory storage with Supabase
2. **Authentication**: Add user authentication
3. **Rate Limiting**: Implement per-user rate limits
4. **Audio Storage**: Store audio files in cloud storage
5. **SSL**: Use HTTPS in production
6. **CORS**: Restrict to specific origins

## Browser Compatibility

| Browser | Status | Notes |
|---------|--------|-------|
| Chrome  | ✅ Full | Recommended |
| Firefox | ✅ Full | |
| Edge    | ✅ Full | |
| Safari  | ⚠️ Limited | May need permissions workaround |
| Mobile  | ⚠️ Limited | iOS Safari has restrictions |

## Support

- Check browser console for JavaScript errors
- Review FastAPI logs for API errors
- Ensure Groq API key has sufficient quota

                                                                                                                                                                ┌───────────────────────┬─────────────┬──────────────────────────────────────────────────┐
  │         Phase         │   Status    │                  What Was Built                  │                                                                    
  ├───────────────────────┼─────────────┼──────────────────────────────────────────────────┤
  │ Phase 1: Foundation   │ ✅ Complete │ Supabase schema, dependencies, config updates    │                                                                      ├───────────────────────┼─────────────┼──────────────────────────────────────────────────┤                           │ Phase 2: Core System  │ ✅ Complete│ Interview engine, FastAPI backend, HTML frontend │                                                                      ├───────────────────────┼─────────────┼──────────────────────────────────────────────────┤                                                                    
  │ Phase 3: Intelligence │ ✅ Complete │ Streamlit integration, redirect button, 3rd tab  │
  ├───────────────────────┼─────────────┼──────────────────────────────────────────────────┤
  │ Phase 4: Polish       │ ✅ Complete │ Error handling, retry logic, documentation       │
  └───────────────────────┴─────────────┴──────────────────────────────────────────────────┘

  What Was Created

  New Files:
  1. interview_module/engine.py - 400+ lines with 5-phase state machine, Socratic drilling, anxiety detection
  2. interview_module/api.py - FastAPI backend with full voice pipeline
  3. interview.html - Complete frontend with voice recording, transcript, report viewer
  4. supabase_schema.sql - Database schema
  5. INTERVIEW_README.md - Setup and run instructions
  6. requirements.txt - Updated with all dependencies

  Modified Files:
  - utils/config.py - Added Supabase configuration
  - streamlit_app.py - Added Interview Practice tab + redirect button

  How to Run

  # Terminal 1 - Start FastAPI
  uvicorn interview_module.api:app --host 0.0.0.0 --port 8000

  # Terminal 2 - Start Streamlit
  streamlit run streamlit_app.py

  Then:
  1. Open Streamlit at http://localhost:8501
  2. Go to "🎤 Interview Practice" tab
  3. Enter job details, resume, JD
  4. Click "Start Live Interview"

  Or open interview.html directly in browser.

  All Tasks Status

  ✅ Task #1: Interview Engine Core
  ✅ Task #2: HTML Frontend
  ✅ Task #3: FastAPI Backend
  ✅ Task #4: Intelligence Features (Socratic drilling, anxiety detection)
  ✅ Task #5: Voice Loop & State Machine
  ✅ Task #6: Streamlit Integration
  ✅ Task #7: Report Generation & Polish
  ✅ Task #8: Foundation

    Chat-Style UI Redesign (interview.html)

  Completely redesigned the interview interface:
  - Chat bubbles: Messages appear as proper chat bubbles (AI on left, you on right)
  - Avatars: 🤖 for AI, 👤 for you
  - Typing indicator: Shows when AI is "typing"
  - Text input: Modern chat-style input with auto-resizing textarea
  - Send button: Arrow button to send typed messages
  - Recording: Red pulse animation on mic button when recording
  - Timestamps: Each message shows the time
  - Replay: Click 🔊 next to any AI message to hear it again
  - Responsive: Works on mobile devices
