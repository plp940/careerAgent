from crewai import Agent, Task, LLM
from utils.config import get_llm

llm = get_llm(temperature=0.3)


def get_resume_cl_agent():
    return Agent(
        role="Resume & Cover Letter Writer",
        goal="Customize application materials to match job descriptions",
        backstory=(
            "You're an expert in professional writing and tailoring resumes for job "
            "applications, especially in government and tech roles."
        ),
        llm=llm,
        verbose=True,
    )


def create_resume_cl_task(
    agent, job_summary, resume_text, missing_keywords="", user_bio="", agency_name=""
):
    missing_skills_instruction = ""
    if missing_keywords:
        missing_skills_instruction = f"""
        IMPORTANT: The following skills were identified as gaps:
        {missing_keywords}
        In the cover letter, naturally mention 1-2 as areas you are actively learning. Do NOT fabricate experience.
        """

    return Task(
        description=f"""
        Based on the job summary below, do THREE things:

        1. Tailor the candidate's resume summary.
        2. Generate a personalized cover letter.
        3. Write a short outreach message (under 150 words) the candidate could send to someone at {agency_name} via LinkedIn or email.

        {missing_skills_instruction}

        --- Job Summary ---
        {job_summary}

        --- Resume Text ---
        {resume_text}

        --- Candidate Bio ---
        {user_bio}

        Your output MUST follow this exact format:

        <<RESUME_SUMMARY>>
        [3-5 sentence tailored professional summary]

        <<COVER_LETTER>>
        [Full personalized cover letter]

        <<OUTREACH_MESSAGE>>
        [Short outreach message under 150 words, professional, for LinkedIn or email]
        """,
        agent=agent,
        expected_output="""
        <<RESUME_SUMMARY>>
        [Tailored 3-5 sentence resume summary]

        <<COVER_LETTER>>
        [Personalized cover letter]

        <<OUTREACH_MESSAGE>>
        [Short outreach message under 150 words]
        """,
        output_file="data/resume_agent_output.txt",
    )


# ── ATS Resume Builder ────────────────────────────────────────────────────────


def get_ats_resume_agent():
    return Agent(
        role="ATS Resume Architect",
        goal="Build a complete ATS-optimized resume by injecting missing keywords naturally into the candidate's existing experience",
        backstory=(
            "You are an elite resume writer and ATS optimization specialist. "
            "You take a candidate's real experience and rewrite their full resume "
            "to pass ATS filters for a specific job — injecting missing keywords "
            "naturally without fabricating any experience. Every bullet point "
            "starts with a strong action verb and is quantified where possible."
        ),
        llm=llm,
        verbose=False,
    )


def create_ats_resume_task(agent, job_summary, resume_text, missing_keywords=""):
    missing_section = ""
    if missing_keywords:
        missing_section = f"""
        MISSING KEYWORDS TO INJECT:
        {missing_keywords}
        Weave these naturally into experience bullets or the skills section.
        Do NOT invent jobs or projects. Only reframe existing experience using these terms.
        """

    return Task(
        description=f"""
        Build a complete ATS-optimized resume in Markdown format.

        Rules:
        - Use the candidate's REAL experience only — do not fabricate anything
        - Inject missing keywords naturally into existing bullet points or skills
        - Every experience bullet must start with a strong action verb
        - Quantify achievements wherever the original resume has numbers
        - Use standard ATS-friendly section headers exactly as shown below
        - Keep formatting clean — no tables, no columns, no graphics

        {missing_section}

        --- Original Resume ---
        {resume_text}

        --- Target Job Description ---
        {job_summary}

        Output the resume in this EXACT Markdown structure:

        # [Candidate Full Name]
        [Email] | [Phone] | [Location] | [LinkedIn] | [GitHub]

        ## Professional Summary
        [3-4 sentences tailored to the JD, incorporating matched and missing keywords]

        ## Skills
        **Programming:** [list]
        **ML/AI:** [list — inject missing ML keywords here if applicable]
        **Tools & Platforms:** [list]
        **Soft Skills:** [list]

        ## Experience

        ### [Job Title] | [Company] | [Start Date] – [End Date]
        - [Action verb] + [what you did] + [result/impact]
        - [bullet 2]
        - [bullet 3]

        ## Projects

        ### [Project Name] | [Tech Stack]
        - [what you built and the outcome]

        ## Education

        ### [Degree] | [University] | [Year]
        - CGPA: [x]/10

        ## Certifications & Achievements
        - [cert 1]
        - [cert 2]
        """,
        expected_output="A complete ATS-optimized resume in clean Markdown format.",
        agent=agent,
    )
