# 🤖 CareerAgent AI (AI Job Hunt Assistant)

CareerAgent AI is a production-ready, autonomous multi-agent system that handles the entire job hunt lifecycle. It operates as an active, intelligent career companion: scouring global job boards, matches resume skills against postings, auto-filling application forms via AI browser automation, and coaching you through live, voice-driven mock interviews with raw anxiety telemetry.

---

## 🚀 Key Features

### 1. 🔍 Unified Multi-Source Sourcing
* Simultaneously searches **USAJobs**, **Adzuna**, and **Remotive** for target keywords and locations.
* Normalizes regions including remote work, US, UK, Canada, Australia, Germany, UAE (Dubai), and India (Bangalore, Hyderabad, Mumbai, Chennai, Pune).

### 2. ⚡ Autonomous Alert Crawler Daemon
* Configurable background daemon to monitor job markets without manual intervention.
* Automatically scores posting matches against your background profile.
* If the compatibility score exceeds your configured threshold (e.g. `75%+` fit), the coordinator triggers resume-tailoring and pushes a detailed alert notification directly to your configured **Slack Webhook URL**.

### 3. 📄 Resume Upload & Parse (PDF / DOCX)
* Integrates native file parsing using **PyMuPDF** (`fitz`) and **python-docx**.
* Simply upload a resume file in the dashboard to extract and populate experiences seamlessly.

### 4. 🧠 Candidate CRM & Resume RAG Oracle
* Synchronized vector retrieval store to answer profile queries in the dashboard sidebar (*e.g., "What Python projects match standard ML Engineer requirements?"*).
* Features fail-safe keyword (TF-IDF) indexing logic in environments without embedding API keys.

### 5. 🤖 Browser Auto-Apply Engine
* Uses **Playwright** browser automation to launch headed browser sessions.
* Analyzes HTML form snippets using a LLM analyzer to map field selectors to candidate profile details (names, email, portfolio links).
* Automatically uploads generated ATS resumes and keeps the browser session open on the final submit button container for your verification.

### 6. 📊 Speech & Analytics Interview Prep Coach
* Conduct mock interviews using live speech-to-text transcription.
* Evaluates answers using specialized socratic queries.
* Displays live reporting overlay including **Anxiety/Tension Gauges** (detects speech filler pace e.g., 'like', 'um', 'ah'), **Vocal Pace WPM Graphing**, and **Match/STAR Rating Meters**.

---

## 🛠️ Architecture & Technology Stack

| Component | Technology |
|---|---|
| **Dashboard Interface** | Streamlit |
| **Backend Orchestrator** | CrewAI |
| **API Clients & LLM Routing** | LiteLLM (Primary: OpenRouter, Fallback: Groq) |
| **Browser Automation Agent** | Playwright (headed mode execution) |
| **Parsing Engine** | PyMuPDF (`fitz`), python-docx |
| **RAG Retrieval** | TF-IDF / Keyword Alignment Fallback |
| **Persistent Storage** | SQLite / CSV (Applications log) |

---

## ⚙️ Configuration & Environment

Create a `.env` file in the root directory:

```env
# Sourcing API Credentials
USAJOBS_API_KEY=your_usajobs_key
USAJOBS_USER_AGENT=your_email@example.com
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key

# Unified LLM Credentials
OPENROUTER_API_KEY=your_openrouter_api_key
GROQ_API_KEY=your_groq_api_key

# Model Routing (Defaults to Gemma-4-26B for Free API & Llama-3.3 for Groq fallback)
LLM_MODEL=groq/llama-3.3-70b-versatile
LLM_TIMEOUT=120

# Slack Match Alert Hook
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T0000/B0000/XXXXXXXXXXXX
```

---

## 🛫 Running the Application

### 1. Install Dependencies
Make sure you have python 3.10+ installed:
```bash
pip install -r requirements.txt
playwright install
```

### 2. Start the Application
Run the Streamlit frontend app:
```bash
streamlit run streamlit_app.py
```

### 3. Run Automated Verification Tests
Verify all features (browser analyzer, anxiety triggers, RAG logic) via the mock validation suite:
```bash
python tests/test_features.py
```

---

## 📂 Project Structure

```
├── streamlit_app.py          # Streamlit UI dashboard
├── orchestrator.py           # CrewAI pipeline orchestrator
├── usajobs_api.py            # USAJobs endpoint client
│
├── agents/                   # CrewAI Agent Definitions
│   ├── jd_analyst.py         # Job description parser
│   ├── scorer_agent.py       # Compatibility match evaluator
│   └── resume_cl_agent.py    # Resume & cover letter builder
│
├── utils/                    # Utility Modules
│   ├── browser_apply.py      # Playwright form filler agent
│   ├── cron_agent.py         # Alert crawler scheduler daemon (w/ Slack hook)
│   ├── rag_manager.py        # Candidate CRM RAG retrieval Oracle
│   ├── job_sources.py        # Adzuna & Remotive crawler targets
│   ├── tracking.py           # Application history logging
│   └── config.py             # LLM setup & resilient fallbacks
│
├── tests/                    # Verification Suites
│   └── test_features.py      # Pipeline & system testing
```
