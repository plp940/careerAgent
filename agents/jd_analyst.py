from crewai import Agent, Task, LLM
from utils.config import get_llm

llm = get_llm(temperature=0.2)


def get_jd_analyst_agent():
    return Agent(
        role="JD Analyst",
        goal="Extract clean, structured information from any job posting — whether from an API or pasted raw from LinkedIn, Naukri, or any job board",
        backstory=(
            "You're an expert in job market analysis covering government, tech, and global roles. "
            "You can parse messy job descriptions — stripping HTML artifacts, legal boilerplate, "
            "EEO statements, and irrelevant text — and extract only what matters: "
            "the role summary, required skills, and qualifications."
        ),
        llm=llm,
        verbose=True,
    )


def create_jd_analysis_task(agent, job_description):
    return Task(
        description=f"""
        Analyze the job posting below and extract the following.
        The input may be clean API text OR messy raw text pasted from LinkedIn, Naukri,
        Indeed, or a company careers page — it may contain HTML tags, EEO statements,
        legal disclaimers, or irrelevant boilerplate. Ignore all of that.
        Focus only on the actual job requirements.

        Extract:
        1. A concise summary of the role (2-3 sentences)
        2. Key technical skills required
        3. Qualifications and eligibility criteria
        4. Core responsibilities

        Job Posting:
        {job_description}
        """,
        expected_output="A structured markdown summary with sections: Role Summary, Required Skills, Qualifications, Responsibilities.",
        agent=agent,
        output_file="data/report.md",
    )
