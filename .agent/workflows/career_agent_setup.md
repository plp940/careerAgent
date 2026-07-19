---
description: How to run, test and verify CareerAgent AI features
---

## CareerAgent Setup and Execution Walkthrough

This workflow helps you run and test the complete CareerAgent pipeline (from job crawling and scoring to browser automation and voice coaching).

### Prerequisites
1. Ensure Python 3.11+ is installed.
2. Install all required dependencies from the project root:
   ```bash
   pip install -r requirements.txt
   pip install playwright
   python -m playwright install chromium
   ```

3. Configure your API keys in the `.env` file under the project root:
   ```env
   GROQ_API_KEY=your_groq_key
   OPENROUTER_API_KEY=your_openrouter_key
   USAJOBS_API_KEY=your_usajobs_key
   ADZUNA_APP_ID=your_adzuna_id
   ADZUNA_APP_KEY=your_adzuna_key
   API_BASE_URL=http://localhost:8000
   ```

### Step 1: Run the Backend API
Run the FastAPI backend server (which powers the Voice Interview Coach):
// turbo
```bash
uvicorn interview_module.api:app --host 0.0.0.0 --port 8000
```
Verify the API is live by visiting [http://localhost:8000/interview](http://localhost:8000/interview).

### Step 2: Run the Streamlit Application
Start the main CareerAgent interface:
// turbo
```bash
streamlit run streamlit_app.py
```
This launches the application portal in your browser at [http://localhost:8501](http://localhost:8501).

### Step 3: Run the Test Suite
Verify the integrity of all features (RAG Candidate CRM, Playwright Auto-Apply analyzer, Cron Job crawler, and Vocal analytics):
```bash
python tests/test_features.py
```
Verify that all 6 tests pass successfully.
