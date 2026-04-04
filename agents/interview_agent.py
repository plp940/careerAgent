from crewai import Agent, Task, LLM
#from utils.config import GROQ_API_KEY, LLM_MODEL, LLM_TIMEOUT
from utils.config import get_llm

#llm = LLM(model="groq/llama3-8b-8192", api_key=GROQ_API_KEY, temperature=0.4, timeout=LLM_TIMEOUT)
llm = get_llm(temperature=0.4)

def get_interview_agent():
    return Agent(
        role="Interview Coach",
        goal="Generate targeted interview questions and model answers based on the job and candidate's background",
        backstory=(
            "You are a senior technical interview coach with 15 years of experience "
            "preparing candidates for AI/ML, software engineering, and government tech roles. "
            "You generate realistic questions that actual hiring managers ask, and craft "
            "model answers using the STAR method grounded in the candidate's real experience."
        ),
        llm=llm,
        verbose=True,
    )


def create_interview_task(agent, job_summary, resume_text):
    return Task(
        description=f"""
        Based on the job description and candidate resume below, generate an interview preparation guide.

        Return EXACTLY this format:

        ## Behavioral Questions

        **Q1: [question]**
        💡 Suggested Answer: [STAR-method answer using candidate's actual resume experience]

        **Q2: [question]**
        💡 Suggested Answer: [STAR-method answer]

        **Q3: [question]**
        💡 Suggested Answer: [STAR-method answer]

        **Q4: [question]**
        💡 Suggested Answer: [STAR-method answer]

        **Q5: [question]**
        💡 Suggested Answer: [STAR-method answer]

        ## Technical Questions

        **Q6: [question specific to JD tech stack]**
        💡 Suggested Answer: [clear technical answer referencing candidate's projects where possible]

        **Q7: [question]**
        💡 Suggested Answer: [answer]

        **Q8: [question]**
        💡 Suggested Answer: [answer]

        **Q9: [question]**
        💡 Suggested Answer: [answer]

        **Q10: [question]**
        💡 Suggested Answer: [answer]

        ## Quick Tips for This Role
        • [tip 1 specific to this company/role type]
        • [tip 2]
        • [tip 3]

        --- Job Description ---
        {job_summary}

        --- Resume ---
        {resume_text}
        """,
        expected_output="10 interview questions with STAR-method answers split into behavioral and technical sections, plus 3 role-specific tips.",
        agent=agent,
    )
