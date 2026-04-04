import streamlit as st
import time
import os
import re
import datetime
import tempfile
import pandas as pd
import webbrowser
from orchestrator import run_pipeline
from usajobs_api import fetch_usajobs
from utils.job_sources import fetch_remotive, fetch_adzuna
from utils.tracking import load_applications, update_ats_resume_file, delete_application
from utils.config import ADZUNA_APP_ID, ADZUNA_APP_KEY

st.set_page_config(page_title="AI Job Hunt Assistant", layout="wide")

st.markdown("""
<div style="text-align:center; padding: 2rem 0">
    <h1 style="font-size:3.5rem">🤖 AI Job Hunt Assistant</h1>
    <p style="font-size:1.1rem; color:#888">
        5 AI agents · ATS resume generator · Voice interview practice
    </p>
</div>
""", unsafe_allow_html=True)

# col1, col2, col3 = st.columns(3)
# col1.metric("Agents Running", "5")
# col2.metric("Job Sources", "3")
# col3.metric("Applications Tracked", len(load_applications()))

# Initialize session state for page navigation
if "current_page" not in st.session_state:
    st.session_state.current_page = "🔍 Job Search & Apply"

# Sidebar navigation with session state
def set_page(page):
    st.session_state.current_page = page

page = st.sidebar.radio(
    "Navigate",
    ["🔍 Job Search & Apply", "📊 Applications Dashboard", "🎤 Interview Practice"],
    index=["🔍 Job Search & Apply", "📊 Applications Dashboard", "🎤 Interview Practice"].index(st.session_state.current_page)
)

# Update session state when radio changes
if page != st.session_state.current_page:
    st.session_state.current_page = page
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: Job Search & Apply
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Job Search & Apply":

    # st.title("🤖 AI Job Hunt Assistant")
    # st.markdown(   "5 AI agents — score your resume, tailor your cover letter, prep your interview, write outreach messages.")
    # st.markdown(
    #   "Paste your resume, search for jobs or paste any job description, and let the AIs do the work! Track all your applications in the dashboard."
    # )

    # ── Shared inputs ─────────────────────────────────────────────────────────
    resume_text = st.text_area("📄 Paste Your Resume *(mandatory)*", height=180)
    user_bio = st.text_area(
        "🙋 Short Bio (for outreach tone)",
        value="I'm a passionate AI/ML professional looking for impactful roles.",
    )

    st.markdown("---")

    # ── Mode A: Search Jobs ───────────────────────────────────────────────────
    # ── Unified Smart Input ─────────────────────────────────────────

    st.markdown("### 🎯 Find Jobs (Mode A)")

    col1, col2 = st.columns(2)

    with col1:
        keyword = st.text_input(
            "🔍 Search Jobs (Keyword)",
            placeholder="e.g. machine learning engineer",
        )

    with col2:
        location = st.text_input(
            "📍 Location (optional)",
            placeholder="e.g. Hyderabad / Remote",
        )

    st.markdown("#### ✨ Or analyze a specific job description directly (Mode B)")

    custom_title = st.text_input(
        "📋 Job Title (for direct analysis)",
        placeholder="e.g. Senior ML Engineer",
    )

    custom_company = st.text_input(
        "🏢 Company Name",
        placeholder="e.g. Google, Swiggy",
    )

    custom_jd = st.text_area(
        "Paste Job Description",
        height=150,
        placeholder="Paste JD from LinkedIn / Naukri / etc...",
    )

    # ── Smart Mode Detection ────────────────────────────────────────

    mode_b_active = bool(custom_jd.strip() and custom_title.strip())

    if mode_b_active:
        st.success("📋 Analyzing your pasted job description (Mode B)")
    else:
        st.info("🔍 Searching jobs based on your input (Mode A)")

    st.markdown("---")

    # ── EXECUTION LOGIC ─────────────────────────────────────────────

    if mode_b_active:
        if st.button("🚀 Run Agents Analysis", use_container_width=True):
            if not resume_text.strip():
                st.warning("Please paste your resume first.")
            else:
                job_data = {
                    "PositionTitle": custom_title.strip(),
                    "OrganizationName": custom_company.strip() or "Unknown Company",
                    "_source": "📋 Custom JD",
                    "UserArea": {"Details": {"JobSummary": custom_jd.strip()}},
                }

                with st.spinner("Running AI agents..."):
                    output = run_pipeline(job_data, resume_text, user_bio)

                st.session_state["pipeline_outputs"] = {
                    "custom": {
                        "output": output,
                        "title": custom_title,
                        "org": custom_company,
                        "jd": job_data,
                        "resume_text": resume_text,
                    }
                }

    else:
        if st.button("🔍 Find Jobs", use_container_width=True):
            if not keyword.strip():
                st.warning("Enter a keyword")
            else:
                with st.spinner("Searching jobs..."):
                    usajobs = fetch_usajobs(keyword, location, results_per_page=5)
                    remotive = fetch_remotive(keyword, limit=5)
                    adzuna = fetch_adzuna(
                        keyword,
                        location=location,
                        limit=5,
                        app_id=ADZUNA_APP_ID,
                        app_key=ADZUNA_APP_KEY,
                    )
                    jobs = usajobs + remotive + adzuna

                st.session_state["jobs"] = jobs
                st.success(f"Found {len(jobs)} jobs")

        # ── Job selection ─────────────────────────────────────────────────────
        if "jobs" in st.session_state:
            st.markdown("---")
            st.markdown("### 📋 Select Jobs to Apply For")

            selected_indexes = []
            for i, job in enumerate(st.session_state["jobs"]):
                jd = job["MatchedObjectDescriptor"]
                title = jd.get("PositionTitle", "Unknown Title")
                org = jd.get("OrganizationName", "Unknown Agency")
                loc_display = jd.get("PositionLocationDisplay", "")
                apply_url = jd.get("PositionURI", "")
                source = jd.get("_source", "🏛️ USAJobs")

                label = f"{source} **{title}** — {org}"
                if loc_display:
                    label += f" · 📍 {loc_display}"

                col_check, col_link = st.columns([6, 1])
                with col_check:
                    if st.checkbox(label, key=f"job_{i}"):
                        selected_indexes.append(i)
                with col_link:
                    if apply_url:
                        st.link_button("Apply 🔗", apply_url)

            st.markdown("---")
            if len(selected_indexes) > 2:
                st.warning("⚠️ Max 2 jobs at a time to avoid rate limits.")

            if st.button("⚡ Run AI Agents on Selected Jobs", use_container_width=True):
                if not selected_indexes:
                    st.warning("Select at least one job.")
                elif len(selected_indexes) > 2:
                    st.warning("⚠️ Please deselect some — max 2 at a time.")
                elif not resume_text.strip():
                    st.warning("Paste your resume first.")
                else:
                    if "pipeline_outputs" not in st.session_state:
                        st.session_state["pipeline_outputs"] = {}

                    for idx, i in enumerate(selected_indexes):
                        jd = st.session_state["jobs"][i]["MatchedObjectDescriptor"]
                        title = jd.get("PositionTitle", "Unknown")
                        org = jd.get("OrganizationName", "Unknown")

                        st.markdown(f"### 🤖 Processing: {title} at {org}")
                        progress_bar = st.progress(0, text="Initialising agents...")

                        try:
                            progress_bar.progress(10, text="🎯 Scoring resume match...")
                            with st.spinner("Running agents — 90–120 seconds..."):
                                output = run_pipeline(jd, resume_text, user_bio)
                            progress_bar.progress(100, text="✅ All agents completed!")

                            st.session_state["pipeline_outputs"][i] = {
                                "output": output,
                                "title": title,
                                "org": org,
                                "jd": jd,
                                "resume_text": resume_text,
                            }

                        except Exception as e:
                            st.error(f"Pipeline error: {str(e)}")
                            progress_bar.empty()
                            continue

                        if idx < len(selected_indexes) - 1:
                            with st.spinner("⏳ Cooling down 20s before next job..."):
                                time.sleep(20)

    # ── Render all stored outputs (both modes) ────────────────────────────────
    if "pipeline_outputs" in st.session_state and st.session_state["pipeline_outputs"]:
        for i, stored in st.session_state["pipeline_outputs"].items():
            output = stored["output"]
            title = stored["title"]
            org = stored["org"]
            jd = stored["jd"]
            res_text = stored["resume_text"]
            source = jd.get("_source", "🏛️ USAJobs")

            st.success(f"✅ Results for: {title} at {org}")
            st.markdown("---")

            tab_score, tab_jd, tab_resume, tab_interview = st.tabs(
                [
                    "🎯 Resume Score",
                    "📋 JD Analysis",
                    "📄 Resume, Cover Letter & Outreach",
                    "🎤 Interview Prep",
                ]
            )

            # ── Score tab ─────────────────────────────────────────────────────
            with tab_score:
                sd = output.get("score_data", {})
                score = sd.get("match_score", 0)
                st.markdown("#### 🎯 ATS Resume Match Score")
                if score >= 75:
                    st.success(f"### {score}/100 — Strong Match ✅")
                elif score >= 50:
                    st.warning(f"### {score}/100 — Moderate Match ⚠️")
                else:
                    st.error(f"### {score}/100 — Weak Match ❌")
                st.progress(score / 100)
                st.markdown("---")

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### ✅ Matched Keywords")
                    for kw in sd.get("matched_keywords", []):
                        st.markdown(f"- `{kw}`")
                with c2:
                    st.markdown("#### ❌ Missing Keywords")
                    missing = sd.get("missing_keywords", [])
                    for kw in missing:
                        st.markdown(f"- `{kw}`")
                    if missing:
                        st.info("💡 Added as learning goals in your cover letter.")

                st.markdown("---")
                c3, c4 = st.columns(2)
                with c3:
                    st.markdown("#### 💪 Strengths")
                    for s in sd.get("strengths", []):
                        st.markdown(f"- {s}")
                with c4:
                    st.markdown("#### 🔧 Gaps")
                    for g in sd.get("gaps", []):
                        st.markdown(f"- {g}")
                st.markdown("---")
                if sd.get("recommendation"):
                    st.markdown("#### 💬 Recruiter Recommendation")
                    st.info(sd["recommendation"])

            # ── JD tab ────────────────────────────────────────────────────────
            with tab_jd:
                st.markdown("#### 📋 Job Description Analysis")
                if source == "📋 Custom JD":
                    st.caption("Analysed from your pasted job description.")
                st.markdown(output.get("jd_analysis", "No analysis available."))

            # ── Resume tab ────────────────────────────────────────────────────
            with tab_resume:
                st.markdown("#### 📝 Tailored Resume Summary")
                st.markdown(output.get("resume_summary", "Not available."))
                st.markdown("---")

                region_label = (
                    "A4"
                    if any(x in source.lower() for x in ["/in", "/gb", "/de", "/ae"])
                    else "US Letter"
                )
                st.markdown("#### 🎯 ATS-Optimized Resume")
                st.caption(
                    f"Rewrites your full resume with missing keywords injected naturally. Page format: {region_label}"
                )

                ats_key = f"ats_resume_{i}"

                if st.button("⚡ Generate ATS Resume", key=f"ats_btn_{i}"):
                    with st.spinner("Building ATS resume — 30–60 seconds..."):
                        try:
                            from crewai import Crew, Process
                            from agents.resume_cl_agent import (
                                get_ats_resume_agent,
                                create_ats_resume_task,
                            )

                            ats_agent = get_ats_resume_agent()
                            missing_kw = ", ".join(
                                output.get("score_data", {}).get("missing_keywords", [])
                            )
                            job_summary_for_ats = (
                                jd.get("UserArea", {})
                                .get("Details", {})
                                .get("JobSummary", "")
                            )

                            ats_task = create_ats_resume_task(
                                ats_agent, job_summary_for_ats, res_text, missing_kw
                            )
                            ats_crew = Crew(
                                agents=[ats_agent],
                                tasks=[ats_task],
                                process=Process.sequential,
                                verbose=False,
                            )
                            ats_crew.kickoff()
                            ats_result = str(ats_task.output)

                            safe_title = re.sub(r'[\\/*?:"<>|]', "_", title[:30])
                            os.makedirs("data/ats_resumes", exist_ok=True)
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            ats_filepath = f"data/ats_resumes/{safe_title}_{ts}.md"
                            with open(ats_filepath, "w", encoding="utf-8") as f:
                                f.write(ats_result)

                            update_ats_resume_file(title, org, ats_filepath)

                            st.session_state[ats_key] = {
                                "content": ats_result,
                                "filepath": ats_filepath,
                                "source": source,
                            }
                            st.success("✅ ATS Resume generated!")

                        except Exception as e:
                            st.error(f"ATS Resume error: {str(e)}")

                if ats_key in st.session_state:
                    ats_data = st.session_state[ats_key]
                    st.markdown(ats_data["content"])

                    dl_col1, dl_col2 = st.columns(2)
                    with dl_col1:
                        st.download_button(
                            "📥 Download as Markdown",
                            data=ats_data["content"],
                            file_name=f"ats_resume_{title[:25].replace(' ','_')}.md",
                            mime="text/markdown",
                            key=f"dl_ats_md_{i}",
                        )
                    with dl_col2:
                        try:
                            from utils.docx_export import markdown_to_docx

                            tmp = tempfile.NamedTemporaryFile(
                                suffix=".docx", delete=False
                            )
                            tmp.close()
                            markdown_to_docx(
                                ats_data["content"],
                                tmp.name,
                                source=ats_data.get("source", ""),
                            )
                            with open(tmp.name, "rb") as f:
                                st.download_button(
                                    "📥 Download as Word (.docx)",
                                    data=f.read(),
                                    file_name=f"ats_resume_{title[:25].replace(' ','_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_ats_docx_{i}",
                                )
                            os.unlink(tmp.name)
                        except Exception as e:
                            st.caption(f"Word export error: {e}")

                st.markdown("---")
                st.markdown("#### 📄 Personalized Cover Letter")
                cover = output.get("cover_letter", "")
                st.markdown(cover)
                if cover and cover != "Not found":
                    st.download_button(
                        "📥 Download Cover Letter",
                        cover,
                        f"cover_letter_{title[:25].replace(' ','_')}.txt",
                        key=f"dl_cl_{i}",
                    )

                st.markdown("---")
                st.markdown("#### ✉️ Outreach Message")
                outreach = output.get("outreach_message", "")
                st.markdown(outreach)
                if outreach:
                    st.download_button(
                        "📥 Download Outreach",
                        outreach,
                        f"outreach_{title[:25].replace(' ','_')}.txt",
                        key=f"dl_out_{i}",
                    )

            # ── Interview tab ─────────────────────────────────────────────────
            with tab_interview:
                st.markdown("#### 🎤 Interview Preparation Guide")
                st.caption(
                    "10 STAR-method questions tailored to this role and your resume."
                )
                st.markdown("---")
                interview = output.get("interview_prep", "")
                if interview:
                    st.markdown(interview)
                    st.download_button(
                        "📥 Download Interview Prep",
                        interview,
                        f"interview_{title[:25].replace(' ','_')}.txt",
                        key=f"dl_int_{i}",
                    )
                else:
                    st.info("Interview prep not available.")

                # ── Live Interview Practice Button ─────────────────────────────────
                st.markdown("---")
                st.markdown("#### 🎤 Practice Live Interview")
                st.caption("Start a real-time voice interview with AI using this job.")

                # Store current job data for interview
                interview_key = f"interview_data_{i}"

                if st.button("🎤 Start Live Interview Practice", key=f"start_interview_{i}"):
                    # Store job data in session state for Interview Prep tab
                    st.session_state.interview_prefill = {
                        "job_title": title,
                        "company": org,
                        "resume_text": res_text,
                        "jd_text": jd.get("UserArea", {}).get("Details", {}).get("JobSummary", "")
                    }
                    # Redirect to Interview Practice tab
                    st.session_state.current_page = "🎤 Interview Practice"
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: Applications Dashboard
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Applications Dashboard":

    st.title("📊 Applications Dashboard")
    st.markdown("Track every job you've processed — scores, sources, and timeline.")

    if "dashboard_refresh" not in st.session_state:
        st.session_state["dashboard_refresh"] = 0

    apps = load_applications()

    if not apps:
        st.info(
            "No applications logged yet. Run the agents on a job to start tracking."
        )
        st.stop()

    df = pd.DataFrame(apps)

    if "Match Score" in df.columns:
        df["Match Score"] = (
            pd.to_numeric(df["Match Score"], errors="coerce").fillna(0).astype(int)
        )
    else:
        df["Match Score"] = 0

    total = len(df)
    avg_score = int(df["Match Score"].mean()) if total > 0 else 0
    unique_agencies = df["Agency"].nunique() if "Agency" in df.columns else 0
    sources = df["Source"].value_counts().to_dict() if "Source" in df.columns else {}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applied", total)
    col2.metric("Avg Match Score", f"{avg_score}/100")
    col3.metric("Unique Employers", unique_agencies)
    col4.metric("Sources Used", len(sources))

    st.markdown("---")

    # ── Applications table ────────────────────────────────────────────────────
    st.markdown("#### 📋 Recent Applications")
    table_cols = ["Job Title", "Agency", "Source", "Match Score", "Date Applied"]
    available = [c for c in table_cols if c in df.columns]
    st.dataframe(
        df[available].sort_values("Date Applied", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### 📄 Resume & Actions")

    for idx, row in df.sort_values("Date Applied", ascending=False).iterrows():
        job_title_row = row.get("Job Title", "Unknown")
        agency_row = row.get("Agency", "Unknown")
        date_row = str(row.get("Date Applied", ""))
        ats_file = str(row.get("ATS Resume File", ""))
        score_val = row.get("Match Score", 0)
        try:
            score_val = int(score_val)
        except Exception:
            score_val = 0

        col_title, col_score, col_resume, col_del = st.columns([4, 1, 1, 1])

        with col_title:
            st.markdown(f"**{job_title_row}** — {agency_row}")
        with col_score:
            if score_val >= 75:
                st.success(f"{score_val}/100")
            elif score_val >= 50:
                st.warning(f"{score_val}/100")
            else:
                st.error(f"{score_val}/100")
        with col_resume:
            if ats_file and os.path.exists(ats_file):
                with open(ats_file, "r", encoding="utf-8") as f:
                    content = f.read()
                st.download_button(
                    "📄 Resume",
                    data=content,
                    file_name=os.path.basename(ats_file),
                    mime="text/markdown",
                    key=f"dash_dl_{job_title_row[:10]}_{date_row[-5:]}",
                )
            else:
                st.caption("—")
        with col_del:
            if st.button(
                "🗑️",
                key=f"del_{job_title_row[:12]}_{agency_row[:8]}_{date_row[-5:]}",
                help=f"Remove {job_title_row}",
            ):
                delete_application(job_title_row, agency_row)
                st.rerun()

        st.divider()

    st.markdown("---")

    st.markdown("#### 🌐 Source Breakdown")
    if "Source" in df.columns:
        source_counts = df["Source"].value_counts()
        src_col1, src_col2 = st.columns([1, 2])
        with src_col1:
            for src, count in source_counts.items():
                st.metric(src, count)
        with src_col2:
            st.bar_chart(source_counts)

    st.markdown("---")

    st.markdown("#### 🎯 Score Distribution")
    strong = len(df[df["Match Score"] >= 75])
    moderate = len(df[(df["Match Score"] >= 50) & (df["Match Score"] < 75)])
    weak = len(df[df["Match Score"] < 50])
    d1, d2, d3 = st.columns(3)
    d1.metric("Strong Match (75+) ✅", strong)
    d2.metric("Moderate Match (50–74) ⚠️", moderate)
    d3.metric("Weak Match (<50) ❌", weak)

    st.markdown("---")
    st.download_button(
        "📥 Export Full Log as CSV",
        data=df.to_csv(index=False),
        file_name="applications_log_export.csv",
        mime="text/csv",
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: Interview Practice
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎤 Interview Practice":

    st.title("🎤 Interview Practice Agent")
    st.markdown(
        "Practice your interview skills with AI-powered feedback. Upload your resume and job description to start a live voice interview."
    )

    st.markdown("---")

    # ── Direct Input Mode ────────────────────────────────────────────────────
    # Check for prefill data from Job Search tab
    prefill = st.session_state.get("interview_prefill", {})

    st.markdown("### 📋 Enter Interview Details")

    col1, col2 = st.columns(2)
    with col1:
        interview_job_title = st.text_input(
            "Job Title",
            key="interview_job_title",
            value=prefill.get("job_title", ""),
            placeholder="e.g., Machine Learning Engineer"
        )
    with col2:
        interview_company = st.text_input(
            "Company",
            key="interview_company",
            value=prefill.get("company", ""),
            placeholder="e.g., Google"
        )

    st.markdown("#### 📄 Resume")
    interview_resume = st.text_area(
        "Paste your resume (or upload PDF below)",
        key="interview_resume",
        value=prefill.get("resume_text", ""),
        height=150
    )

    resume_file = st.file_uploader("Or upload PDF resume", type="pdf", key="interview_resume_pdf")

    if resume_file:
        import fitz

        pdf_bytes = resume_file.read()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        resume_text = "\n".join([page.get_text() for page in doc])
        doc.close()

        st.session_state["interview_resume_text"] = resume_text
        interview_resume = resume_text

    st.markdown("#### 📋 Job Description")
    interview_jd = st.text_area(
        "Paste the job description",
        key="interview_jd",
        value=prefill.get("jd_text", ""),
        height=150
    )

    st.markdown("---")

    # ── Start Interview Button ──────────────────────────────────────────────
    if st.button("🎤 Start Live Interview", use_container_width=True, type="primary"):
        if not interview_job_title or not interview_company:
            st.error("Please enter Job Title and Company.")
        elif not interview_resume:
            st.error("Please provide your resume (paste or upload PDF).")
        elif not interview_jd:
            st.error("Please provide the job description.")
        else:
            # Store session data in session state
            st.session_state["interview_session"] = {
                "job_title": interview_job_title,
                "company": interview_company,
                "resume_text": interview_resume,
                "jd_text": interview_jd
            }

            # Build interview URL with prefill data
            import requests as req

            response = req.post("http://localhost:8000/prefill_session", data={
                "job_title": interview_job_title,
                "company": interview_company,
                "resume_text": interview_resume,
                "jd_text": interview_jd,
            })
            data = response.json()
            interview_url = data["interview_url"]

            st.success("✅ Interview session ready!")
            st.markdown(f"[🎤 Click here to start the interview]({interview_url})")
            st.info("The interview will open in a new tab with your details pre-loaded.")

    # ── Or redirect from Job Search tab ─────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔄 Or Continue from Job Search")
    st.info(
        "You can also start an interview directly from the '🎤 Interview Prep' tab "
        "in the Job Search & Apply section after running AI agents on a job."
    )

    st.markdown("---")

    # ── Instructions ──────────────────────────────────────────────────────────
    with st.expander("📖 How it works"):
        st.markdown("""
        **Interview Phases:**
        1. **Background** - General questions about your experience
        2. **Primary Project Drill** - Deep dive into your most relevant project
        3. **Secondary Project Drill** - Discussion of another experience
        4. **Domain Questions** - Technical questions specific to the role
        5. **Behavioral Questions** - Standard behavioral and situational questions

        **Features:**
        - 🎤 Real-time voice interaction
        - 🤖 AI-powered question generation based on your resume & JD
        - 💡 Anxiety detection with optional break prompts
        - 📊 Detailed evaluation report with scores and improvement tips
        - ⭐ STAR-method interview guidance
        """)

    with st.expander("⚙️ System Requirements"):
        st.markdown("""
        - **Browser**: Chrome or Firefox recommended
        - **Microphone**: Required for voice input
        - **FastAPI Server**: Must be running on port 8000
        - **Groq API Key**: For LLM, STT, and TTS functionality
        """)

    st.markdown("---")
    st.caption("Powered by Groq LLM + Whisper + PlayAI TTS")
