# AI Job Hunt Assistant - Project Report

## Project Overview

The **AI Job Hunt Assistant** is an intelligent multi-agent system built using Python and Streamlit. It automates and enhances the job application process by leveraging 5 specialized AI agents powered by CrewAI. The system searches for jobs across multiple sources (USAJobs, Adzuna, Remotive), scores resume-job matches, tailors application materials, and provides interview preparation.

---

## Architecture & Technology Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | Streamlit |
| **Multi-Agent Framework** | CrewAI |
| **LLM Providers** | Groq (primary), OpenRouter (fallback) |
| **LLM Models** | Llama 3.3 70B (Groq), Llama 3.1 70B (OpenRouter) |
| **Data Storage** | CSV files (applications tracking) |
| **Document Export** | DOCX format |
| **APIs Used** | USAJobs API, Adzuna API, Remotive API |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT UI (streamlit_app.py)                 │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  🔍 Job Search & Apply   │  │  📊 Applications Dashboard      │    │
│  │  - Resume input          │  │  - Application history           │    │
│  │  - Job search filters    │  │  - Match scores                  │    │
│  │  - Multi-source search   │  │  - Export to DOCX                │    │
│  └────────┬─────────────────┘  └──────────────────────────────────┘    │
└───────────┼───────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR (orchestrator.py)                  │
│                    Coordinates 5 Specialized AI Agents                  │
└──────┬─────────────┬─────────────┬─────────────┬─────────────┬──────-───┘
       │             │             │             │             │
       ▼             ▼             ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│  Agent 1 │  │  Agent 2 │  │  Agent 3 │  │  Agent 4 │  │   Agent 5    │
│  Scorer  │  │JD Analyst│  │Resume/CL │  │ ATS Res  │  │Interview     │
│          │  │          │  │  Writer  │  │ Builder  │  │   Coach      │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────┘
   scores       analyzes    tailors      optimizes    prepares
   resume       job desc    cover        for ATS      interview
   vs job                   letter       filters      questions
```

---

## Multi-Agent Workflow

### Pipeline Flow (run_pipeline function)

1. **Agent 1: Resume Scorer** (`agents/scorer_agent.py`)
   - **Role**: ATS Resume Scorer
   - **Goal**: Objectively score how well a resume matches a job description
   - **Output**: Match score (0-100), matched keywords, missing keywords, strengths, gaps, recommendation

2. **Agent 2: JD Analyst** (`agents/jd_analyst.py`)
   - **Role**: Job Description Analyst
   - **Goal**: Extract structured information from job postings (role summary, required skills, qualifications, responsibilities)
   - **Handles**: Clean API text AND messy HTML/raw text from LinkedIn, Naukri, etc.

3. **Agent 3: Resume & Cover Letter Writer** (`agents/resume_cl_agent.py`)
   - **Role**: Resume & Cover Letter Writer
   - **Goal**: Customize application materials to match job descriptions
   - **Output**: 
     - Tailored 3-5 sentence resume summary
     - Personalized cover letter
     - LinkedIn/email outreach message (under 150 words)

4. **Agent 4: ATS Resume Builder** (`agents/resume_cl_agent.py`)
   - **Role**: ATS Resume Architect
   - **Goal**: Build complete ATS-optimized resume by injecting missing keywords naturally
   - **Output**: Full Markdown resume with proper ATS formatting

5. **Agent 5: Interview Coach** (`agents/interview_agent.py`)
   - **Role**: Interview Coach
   - **Goal**: Generate targeted interview questions and model answers
   - **Output**: 
     - 5 behavioral questions with STAR-method answers
     - 5 technical questions with suggested answers
     - 3 role-specific quick tips

---

## Job Sources Integration

| Source | Type | API Key Required | Coverage |
|--------|------|------------------|----------|
| **USAJobs** | Government | Yes | US Federal Government jobs |
| **Adzuna** | Aggregator | Yes | Multi-country (US, UK, DE, IN, AE, etc.) |
| **Remotive** | Remote Tech | No | Worldwide remote tech jobs |

### Location Support
- **Multi-region**: USA, UK, Germany, Netherlands, France, Canada, Australia
- **Middle East**: Dubai, UAE
- **India**: Bangalore, Mumbai, Hyderabad, Chennai, Delhi, Pune
- **Remote**: Dedicated remote search via Remotive

---

## Data Tracking System

### Applications Log (`data/applications_log.csv`)

| Field | Description |
|-------|-------------|
| Job Title | Position applied for |
| Agency | Company or organization name |
| Source | Where job was found (USAJobs, Adzuna, Remotive) |
| Match Score | AI-generated match score (0-100) |
| Resume Summary | Tailored resume summary snippet |
| ATS Resume File | Path to generated ATS resume |
| Date Applied | Timestamp of application |

### Features
- **Duplicate Detection**: Prevents logging same job twice
- **CRUD Operations**: Create, read, update, delete applications
- **Export**: Convert applications to DOCX format

---

## Configuration & Environment

### Required Environment Variables (`.env` file)

```env
# USAJobs API
USAJOBS_API_KEY=your_usajobs_key
USAJOBS_USER_AGENT=your_email@example.com

# Adzuna API
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key

# LLM Providers (need at least one)
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional: Custom LLM settings
LLM_MODEL=groq/llama-3.3-70b-versatile
LLM_TIMEOUT=120
```

### LLM Fallback Strategy
1. **Primary**: Groq (Llama 3.3 70B) - fast, generous free tier
2. **Fallback**: OpenRouter (Llama 3.1 70B) - unlimited free tier
3. **Retry Logic**: Automatic retry on rate limits with 15s delay

---

## File Structure

```
job_agent/
│
├── streamlit_app.py          # Main Streamlit UI application
├── orchestrator.py           # Multi-agent pipeline coordinator
├── usajobs_api.py           # USAJobs API client
│
├── agents/                   # CrewAI Agent Definitions
│   ├── __init__.py
│   ├── jd_analyst.py        # Job description analyzer
│   ├── scorer_agent.py      # Resume scoring agent
│   ├── resume_cl_agent.py   # Resume/Cover letter writer
│   └── interview_agent.py   # Interview prep agent
│
├── utils/                    # Utility Modules
│   ├── __init__.py
│   ├── config.py            # Configuration & LLM setup
│   ├── job_sources.py       # Adzuna & Remotive APIs
│   ├── tracking.py          # Application tracking (CSV)
│   └── docx_export.py       # DOCX generation
│
├── data/                     # Data Storage
│   ├── applications_log.csv # Application history
│   ├── cover_letters/       # Generated cover letters
│   └── report.md            # JD analysis output
│
└── PROJECT_REPORT.md        # This document
```

---

## Key Features

### 1. Multi-Source Job Search
- Simultaneously search USAJobs, Adzuna, and Remotive
- Unified job result format across all sources
- Location-aware searching with country code mapping

### 2. AI-Powered Resume Analysis
- ATS-style scoring with keyword matching
- Gap identification (missing skills/keywords)
- Strength analysis based on job fit

### 3. Personalized Application Materials
- Tailored resume summaries for each job
- Custom cover letters addressing specific requirements
- Professional outreach messages for networking

### 4. ATS Optimization
- Full resume rebuild with keyword injection
- ATS-friendly Markdown formatting
- Action verb optimization

### 5. Interview Preparation
- Behavioral questions with STAR-method answers
- Technical questions based on job requirements
- Role-specific tips and strategies

### 6. Application Tracking
- CSV-based persistent storage
- Duplicate prevention
- Export to DOCX for offline use

---

## Usage Workflow

```
Step 1: Paste Resume
    ↓
Step 2: Enter Job Search Criteria (keyword + location)
    ↓
Step 3: Select Jobs from Search Results
    ↓
Step 4: AI Agents Process Selected Jobs
    ↓
Step 5: Review Generated Materials (Resume, Cover Letter, Interview Prep)
    ↓
Step 6: Application Automatically Logged
    ↓
Step 7: View & Manage Applications in Dashboard
```

---

## Technical Implementation Details

### Agent Configuration Pattern
Each agent follows a consistent pattern:
1. **Agent Definition**: Role, goal, backstory, LLM
2. **Task Creation**: Description with context injection, expected output format
3. **Crew Assembly**: Sequential process execution

### Error Handling
- Rate limit detection and automatic fallback
- Retry logic with exponential backoff
- Graceful degradation when APIs fail

### Output Parsing
- Structured format markers (e.g., `<<RESUME_SUMMARY>>`)
- Regex-based extraction for consistency
- Fallback parsers for handling model output variations

---

## Performance Considerations

| Aspect | Strategy |
|--------|----------|
| **API Limits** | Dual LLM provider with automatic fallback |
| **Timeouts** | 120s default for LLM calls |
| **Rate Limiting** | 5-second delays between agent executions |
| **Data Persistence** | CSV files (no database required) |
| **Memory** | Streaming results, minimal caching |

---

## Future Enhancements

### Potential Improvements
1. **Database Integration**: Replace CSV with SQLite/PostgreSQL
2. **Email Integration**: Direct application submission
3. **LinkedIn API**: Automated connection requests
4. **Scheduling**: Cron-based automated job searches
5. **More Sources**: Indeed, LinkedIn, AngelList integration
6. **Resume Templates**: Multiple ATS-friendly templates
7. **Analytics**: Application success rate tracking

---

## Dependencies

```
streamlit
pandas
requests
python-dotenv
crewai
litellm
python-docx
```

---

## Author & Date

- **Project**: AI Job Hunt Assistant
- **Built With**: Python, Streamlit, CrewAI
- **Date**: March 2025

---

*This report was generated to document the architecture, features, and implementation of the AI Job Hunt Assistant system.*
