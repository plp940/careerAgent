"""
Interview Engine - Fixed version
- Proper ML-specific Socratic drilling
- Phase transitions based on actual question counts not guesses
- Rich evaluation report with LLM-generated feedback
"""

import re
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from interview_module.groq_http import chat_completion


class InterviewPhase(Enum):
    BACKGROUND = 1
    PRIMARY_PROJECT_DRILL = 2
    SECONDARY_PROJECT_DRILL = 3
    DOMAIN_QUESTIONS = 4
    BEHAVIORAL = 5
    COMPLETED = 6


@dataclass
class SessionState:
    session_id: str
    job_title: str
    company: str
    resume_text: str
    resume_sections: Dict
    jd_text: str
    current_phase: InterviewPhase = InterviewPhase.BACKGROUND
    current_depth: int = 0
    current_project_index: int = 0
    projects_identified: List[str] = field(default_factory=list)
    questions_asked: List[Dict] = field(default_factory=list)
    domain_questions_list: List[str] = field(default_factory=list)
    domain_question_index: int = 0
    behavioral_index: int = 0
    background_index: int = 0
    primary_drill_stuck: bool = False
    secondary_drill_stuck: bool = False
    status: str = "active"


@dataclass
class TurnResult:
    question: str
    answer_transcript: str
    next_phase: InterviewPhase
    next_depth: int
    score: Optional[int] = None
    filler_words_count: int = 0
    filler_words_detected: List[str] = field(default_factory=list)
    pause_seconds: int = 0
    hint_given: bool = False
    hint_text: Optional[str] = None
    is_break_triggered: bool = False


class InterviewEngine:
    MAX_DEPTH = 6
    BACKGROUND_QUESTIONS_COUNT = 2
    BEHAVIORAL_QUESTIONS_COUNT = 5
    DOMAIN_QUESTIONS_COUNT = 5
    FILLER_WORDS = [
        "um",
        "uh",
        "like",
        "you know",
        "sort of",
        "kind of",
        "basically",
        "actually",
        "literally",
        "right",
        "so yeah",
    ]

    def __init__(self):
        pass

    # ── Resume parsing ────────────────────────────────────────────────────────

    def parse_resume_sections(self, resume_text: str) -> Dict:
        """Extract structured sections from resume text using LLM for accuracy."""
        sections = {
            "summary": "",
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "raw": resume_text,
        }

        # LLM-based extraction for better accuracy
        try:
            prompt = f"""Extract sections from this resume. Return JSON with these keys:
"summary" (string), "education" (list of strings), "experience" (list of strings),
"projects" (list of strings - project names and brief descriptions), "skills" (list of strings).

For projects: include BOTH the projects section AND any projects mentioned in experience.
List each project as a separate entry with its name and what it does.

Resume:
{resume_text[:3000]}

Return ONLY valid JSON, no other text."""

            response = chat_completion(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
            )
            text = response["choices"][0]["message"]["content"].strip()
            # Extract JSON
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                sections.update({k: v for k, v in parsed.items() if k in sections})
        except Exception as e:
            print(f"[Engine] LLM resume parsing failed, using regex fallback: {e}")
            # Fallback to simple parsing
            sections = self._regex_parse_resume(resume_text)

        return sections

    def _regex_parse_resume(self, resume_text: str) -> Dict:
        """Simple regex fallback for resume parsing."""
        sections = {
            "summary": "",
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "raw": resume_text,
        }
        lines = resume_text.split("\n")
        current_section = None
        buffer = []
        section_keywords = {
            "summary": ["summary", "profile", "about", "objective"],
            "education": ["education", "academic", "degree"],
            "experience": ["experience", "work", "employment", "internship"],
            "projects": ["projects", "project", "portfolio"],
            "skills": ["skills", "technologies", "tech stack"],
        }
        for line in lines:
            line_lower = line.lower().strip()
            is_header = False
            for section, keywords in section_keywords.items():
                if any(k in line_lower for k in keywords) and len(line.strip()) < 30:
                    if current_section and buffer:
                        content = "\n".join(buffer)
                        if current_section in ["experience", "projects", "education"]:
                            sections[current_section].append(content)
                        else:
                            sections[current_section] = content
                    current_section = section
                    buffer = []
                    is_header = True
                    break
            if not is_header and current_section and line.strip():
                buffer.append(line)
        if current_section and buffer:
            content = "\n".join(buffer)
            if current_section in ["experience", "projects", "education"]:
                sections[current_section].append(content)
            else:
                sections[current_section] = content
        if not sections["projects"] and sections["experience"]:
            sections["projects"] = sections["experience"][:2]
        return sections

    def identify_projects(self, state: SessionState) -> List[str]:
        """Return top 2 projects for drilling."""
        projects = state.resume_sections.get("projects", [])
        experience = state.resume_sections.get("experience", [])
        all_items = [p for p in projects if p.strip()] + [
            e for e in experience if e.strip()
        ]
        return all_items[:2] if all_items else []

    # ── Anxiety detection ─────────────────────────────────────────────────────

    def detect_anxiety_signals(
        self, transcript: str, audio_duration: float = 0
    ) -> Tuple[bool, Dict]:
        transcript_lower = transcript.lower()
        signals = {
            "filler_words": [],
            "filler_count": 0,
            "pause_seconds": 0,
            "fast_speaking": False,
        }
        for filler in self.FILLER_WORDS:
            count = len(re.findall(r"\b" + re.escape(filler) + r"\b", transcript_lower))
            if count > 0:
                signals["filler_words"].append(filler)
                signals["filler_count"] += count
        words = transcript.split()
        expected_duration = len(words) * 0.4
        if audio_duration > expected_duration * 1.5:
            signals["pause_seconds"] = int(audio_duration - expected_duration)
        should_break = signals["filler_count"] >= 5 or signals["pause_seconds"] >= 10
        return should_break, signals

    # ── System prompt ─────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return """You are a professional technical interviewer.
STRICT RULES:
- Professional, concise, neutral, direct
- NEVER say: "great", "excellent", "amazing", "wonderful", "perfect", "incredible", "awesome"
- After candidate answers, ask the next question without praise
- Ask ONE question at a time
- Max 2 sentences per response
- Be direct: "Thank you. Next question: ..." or "Understood. Tell me about..."
- Do not give feedback during interview"""

    # ── Phase question generators ─────────────────────────────────────────────

    def generate_background_questions(self, state: SessionState) -> List[str]:
        questions = [
            "Could you walk me through your background and tell me about yourself?",
            "Tell me about your most recent experience and what you worked on.",
        ]
        if state.resume_sections.get("education"):
            questions.append(
                "How has your educational background prepared you for this role?"
            )
        return questions

    def generate_socratic_drill_question(
        self,
        state: SessionState,
        project_description: str,
        previous_qa: List[Dict],
        depth: int, 
        is_stuck: bool = False,
    ) -> Tuple[str, bool]:
        """
        Generate a Socratic ML-focused drill question.
        Returns (question, hint_given).
        """
        # Build conversation context
        qa_context = ""
        for qa in previous_qa[-4:]:
            answer_text = qa.get('answer', qa.get('answer_transcript', ''))
            if answer_text:
                qa_context += f"Q: {qa['question']}\nA: {answer_text[:300]}\n\n"

        hint_instruction = ""
        hint_given = False
        if is_stuck and depth > 1:
            hint_instruction = """
The candidate struggled with the last question. Give ONE subtle hint as part of your question.
Format: First acknowledge briefly, then give a nudge, then ask the question.
Example: "Think about the trade-offs between latency and accuracy here. Why might you choose X over Y?"
"""
            hint_given = True

        prompt = f"""{self._build_system_prompt()}

CONTEXT:
Job: {state.job_title} at {state.company}
JD Focus: {state.jd_text[:400]}

PROJECT BEING DISCUSSED:
{project_description[:600]}

CONVERSATION SO FAR:
{qa_context if qa_context else "This is the first question about this project."}

CURRENT DEPTH: {depth}/{self.MAX_DEPTH}
{hint_instruction}

DEPTH GUIDE FOR ML INTERVIEWS:
- Depth 0: "Tell me about this project and your specific role."
- Depth 1: "How does it work technically? Walk me through the architecture."
- Depth 2: Ask about specific ML choices — model selection, data pipeline, evaluation metrics
- Depth 3: Probe trade-offs — "Why X not Y? Why this loss function? Why this embedding model?"
- Depth 4: Deeper theory — "What are the limitations of this approach? What would fail at scale?"
- Depth 5: Edge cases — "How would you handle data drift? What if the labels were noisy?"
- Depth 6: Alternative approaches — "If you rebuilt this, what would you change and why?"

Generate ONE follow-up question. It must:
1. Reference something specific the candidate just said
2. Probe deeper into ML engineering knowledge
3. Be concise (one sentence)
4. Be appropriate for depth {depth}

Return ONLY the question, no preamble."""

        try:
            response = chat_completion(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=150,
            )
            question = (
                response["choices"][0]["message"]["content"]
                .strip()
                .strip('"')
                .strip("'")
            )
            return question, hint_given
        except Exception as e:
            print(f"[Engine] Drill question generation failed: {e}")
            fallbacks = [
                "Tell me about this project and your specific role in it.",
                "Walk me through the technical architecture you used.",
                "What were the key ML challenges you faced?",
                "Why did you choose this approach over alternatives?",
                "What were the limitations of your solution?",
                "How would you improve this if you rebuilt it today?",
                "What would break at 10x the current scale?",
            ]
            return fallbacks[min(depth, len(fallbacks) - 1)], False

    def generate_domain_questions(self, state: SessionState) -> List[str]:
        """Generate ML-specific domain questions based on resume and JD."""
        # Detect primary ML domain from resume
        skills_text = " ".join(state.resume_sections.get("skills", [])).lower()
        projects_text = " ".join(
            [str(p) for p in state.resume_sections.get("projects", [])]
        ).lower()
        combined = state.jd_text.lower()

        domain = "general machine learning"
        if any(
            kw in combined
            for kw in ["nlp", "language model", "bert", "transformers", "rag", "llm"]
        ):
            domain = "NLP and Large Language Models"
        elif any(
            kw in combined
            for kw in ["computer vision", "cnn", "yolo", "detection", "segmentation"]
        ):
            domain = "Computer Vision"
        elif any(kw in combined for kw in ["reinforcement", "rl", "policy", "reward"]):
            domain = "Reinforcement Learning"
        elif any(
            kw in combined
            for kw in ["mlops", "deployment", "kubernetes", "docker", "pipeline"]
        ):
            domain = "MLOps and Model Deployment"
        elif any(kw in combined for kw in ["figma", "wireframe", "ux", "ui", "design", "prototype", "user research"]):
            domain = "UI/UX Design"
        elif any(kw in combined for kw in ["sales", "revenue", "crm", "pipeline", "quota", "b2b", "saas sales"]):
            domain = "Sales and Business Development"
        elif any(kw in combined for kw in ["product", "roadmap", "stakeholder", "sprint", "agile", "product manager"]):
            domain = "Product Management"    

        prompt = f"""{self._build_system_prompt()}
        

Generate exactly 5 factual {domain} interview questions for a {state.job_title} candidate.
Primary domain detected: {domain}
JD highlights: {state.jd_text[:500]}

Questions must:
- Have factually correct, verifiable answers
- Cover different concepts (not all the same topic)
- Be specific, not vague
- Be answerable in 2-3 minutes
- Test actual ML engineering knowledge

For each question also provide the correct answer (for evaluation purposes).

Format EXACTLY:
Q1: [question]
A1: [correct answer]
Q2: [question]
A2: [correct answer]
...Q5/A5"""

        try:
            response = chat_completion(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            text = response["choices"][0]["message"]["content"]

            questions = re.findall(r"Q\d+:\s*(.+?)(?=A\d+:|$)", text, re.DOTALL)
            answers = re.findall(r"A\d+:\s*(.+?)(?=Q\d+:|$)", text, re.DOTALL)

            qa_pairs = []
            for q, a in zip(questions, answers):
                qa_pairs.append({"question": q.strip(), "correct_answer": a.strip()})

            return qa_pairs[:5] if qa_pairs else self._default_domain_questions()
        except Exception as e:
            print(f"[Engine] Domain question generation failed: {e}")
            return self._default_domain_questions(state.job_title)

    def _default_domain_questions(self, job_title: str = "") -> List[Dict]:
        """Role-aware fallback questions when LLM generation fails."""
        jt = job_title.lower()

        if any(w in jt for w in ["account", "finance", "receivable", "payable", "bookkeep"]):
            return [
                {"question": "What is the difference between accounts receivable and accounts payable?",
                "correct_answer": "AR = money owed TO the company by customers. AP = money the company OWES to vendors/suppliers."},
                {"question": "What is DSO (Days Sales Outstanding) and how do you calculate it?",
                "correct_answer": "DSO = (Accounts Receivable / Total Credit Sales) × Number of Days. Measures average days to collect payment."},
                {"question": "What is bank reconciliation and why is it important?",
                "correct_answer": "Comparing internal records with bank statement to find discrepancies. Ensures accuracy, detects fraud, prevents errors."},
                {"question": "What is the aging report in accounts receivable?",
                "correct_answer": "A report categorizing outstanding invoices by how long they've been unpaid: 0-30, 31-60, 61-90, 90+ days."},
                {"question": "What are common causes of payment disputes and how do you resolve them?",
                "correct_answer": "Invoice errors, duplicate payments, product issues. Resolution: documentation, communication, credit notes, escalation."},
            ]
        elif any(w in jt for w in ["software", "engineer", "developer", "backend", "frontend"]):
            return [
                {"question": "What is the difference between REST and GraphQL?",
                "correct_answer": "REST uses fixed endpoints, multiple requests for related data. GraphQL uses single endpoint, client specifies exact data needed."},
                {"question": "Explain SOLID principles.",
                "correct_answer": "Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion — OOP design principles."},
                {"question": "What is the difference between SQL and NoSQL databases?",
                "correct_answer": "SQL: structured, relational, ACID, fixed schema. NoSQL: flexible schema, horizontal scaling, eventual consistency."},
                {"question": "What is CI/CD and why is it important?",
                "correct_answer": "Continuous Integration/Delivery. Automates testing and deployment. Reduces integration issues, faster releases."},
                {"question": "Explain the concept of time complexity using Big O notation.",
                "correct_answer": "Describes how runtime grows with input size. O(1) constant, O(n) linear, O(log n) logarithmic, O(n²) quadratic."},
            ]
        else:
            # Generic professional fallback
            return [
                {"question": "How do you prioritize tasks when you have multiple deadlines?",
                "correct_answer": "Assess urgency vs importance (Eisenhower matrix), communicate with stakeholders, break tasks down, use time-blocking."},
                {"question": "Describe a situation where you had to learn something new quickly.",
                "correct_answer": "STAR method answer expected. Key: identify learning strategy, resources used, speed of application."},
                {"question": "How do you handle errors or mistakes in your work?",
                "correct_answer": "Acknowledge, fix immediately, document cause, implement prevention. Transparency with team/manager."},
                {"question": "What tools do you use for productivity and organization?",
                "correct_answer": "Project management tools (Jira, Trello), communication (Slack), documentation (Confluence, Notion), calendaring."},
                {"question": "How do you stay current with developments in your field?",
                "correct_answer": "Industry publications, courses, conferences, professional networks, hands-on projects."},
            ]

    def generate_behavioral_questions(self, state: SessionState) -> List[str]:
        return [
            "Where do you see yourself in five years, and how does this role fit into that vision?",
            "Tell me about a significant technical challenge you faced and how you resolved it.",
            "Describe a situation where you had to collaborate with a difficult team member. How did you handle it?",
            "How do you approach learning a new technology or framework that the team needs quickly?",
            "Do you have any questions for me about the role or the team?",
        ]

    # ── Scoring ───────────────────────────────────────────────────────────────

    def score_answer(
        self,
        question: str,
        answer: str,
        phase: InterviewPhase,
        depth: int = 0,
        correct_answer: str = "",
    ) -> Tuple[Optional[int], str]:
        if phase == InterviewPhase.BACKGROUND:
            return None, "No scoring for background phase"

        if phase == InterviewPhase.BEHAVIORAL:
            prompt = f"""Score this behavioral answer 1-10.
Question: {question}
Answer: {answer}

Criteria:
- Specificity (gave concrete example vs vague): 0-3 pts
- Evidence of problem-solving/teamwork: 0-3 pts  
- Clarity and structure (STAR method): 0-2 pts
- Relevance to question: 0-2 pts

Return ONLY:
SCORE: [number]
REASON: [one specific sentence explaining the score]"""
        elif phase == InterviewPhase.DOMAIN_QUESTIONS and correct_answer:
            prompt = f"""Score this technical answer against the correct answer. Scale 1-10.
Question: {question}
Correct Answer: {correct_answer}
Candidate Answer: {answer}

Criteria:
- Factual accuracy (are key concepts correct?): 0-5 pts
- Completeness (covered main points?): 0-3 pts
- Clarity of explanation: 0-2 pts

Return ONLY:
SCORE: [number]
REASON: [one specific sentence — what was correct, what was missing]"""
        else:
            # Socratic drill phases
            prompt = f"""Score this technical drill answer 1-10.
Job: Technical ML role
Depth level: {depth}/{self.MAX_DEPTH}
Question: {question}
Answer: {answer}

Criteria at depth {depth}:
- Technical accuracy of claims: 0-4 pts
- Depth of understanding shown: 0-3 pts
- Ability to reason about trade-offs: 0-2 pts  
- Used correct terminology: 0-1 pt

Return ONLY:
SCORE: [number]
REASON: [one specific sentence — what showed depth, what was shallow or missing]"""

        try:
            response = chat_completion(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=120,
            )
            text = response["choices"][0]["message"]["content"]
            score_match = re.search(r"SCORE:\s*(\d+)", text)
            reason_match = re.search(r"REASON:\s*(.+)", text, re.DOTALL)
            score = int(score_match.group(1)) if score_match else 5
            score = max(1, min(10, score))
            reason = (
                reason_match.group(1).strip() if reason_match else "Answer evaluated."
            )
            return score, reason
        except Exception as e:
            print(f"[Engine] Scoring failed: {e}")
            return 5, "Could not score — defaulted to 5"

    # ── Phase transitions ─────────────────────────────────────────────────────

    def check_if_stuck(self, answer: str) -> bool:
        """Detect if candidate is stuck — short answer, lots of fillers, or admits not knowing."""
        if not answer or len(answer.strip()) < 20:
            return True
        stuck_phrases = [
            "i don't know",
            "i'm not sure",
            "i haven't",
            "not familiar",
            "can't remember",
            "don't recall",
            "no idea",
            "i forget",
        ]
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in stuck_phrases):
            return True
        filler_count = sum(answer_lower.count(f) for f in self.FILLER_WORDS)
        if filler_count >= 4:
            return True
        return False

    def determine_next_action(
        self, state: SessionState, answer: str
    ) -> Tuple[InterviewPhase, int, Optional[str]]:
        """Determine next phase/depth. Returns (new_phase, new_depth, hint_text)."""
        hint = None
        new_phase = state.current_phase
        new_depth = state.current_depth
        is_stuck = self.check_if_stuck(answer)

        if state.current_phase == InterviewPhase.BACKGROUND:
            state.background_index += 1
            if state.background_index >= self.BACKGROUND_QUESTIONS_COUNT:
                new_phase = InterviewPhase.PRIMARY_PROJECT_DRILL
                new_depth = 0
            # else stay in background

        elif state.current_phase == InterviewPhase.PRIMARY_PROJECT_DRILL:
            if is_stuck and new_depth >= 2:
                # Candidate is stuck — give hint next turn, still increment depth
                state.primary_drill_stuck = True
                new_depth = min(state.current_depth + 1, self.MAX_DEPTH)
            elif new_depth >= self.MAX_DEPTH:
                new_phase = InterviewPhase.SECONDARY_PROJECT_DRILL
                new_depth = 0
            else:
                new_depth = state.current_depth + 1

        elif state.current_phase == InterviewPhase.SECONDARY_PROJECT_DRILL:
            if is_stuck and new_depth >= 2:
                state.secondary_drill_stuck = True
                new_depth = min(state.current_depth + 1, self.MAX_DEPTH)
            elif new_depth >= self.MAX_DEPTH:
                new_phase = InterviewPhase.DOMAIN_QUESTIONS
                new_depth = 0
            else:
                new_depth = state.current_depth + 1

        elif state.current_phase == InterviewPhase.DOMAIN_QUESTIONS:
            state.domain_question_index += 1
            if state.domain_question_index >= self.DOMAIN_QUESTIONS_COUNT:
                new_phase = InterviewPhase.BEHAVIORAL
                state.behavioral_index = 0

        elif state.current_phase == InterviewPhase.BEHAVIORAL:
            state.behavioral_index += 1
            if state.behavioral_index >= self.BEHAVIORAL_QUESTIONS_COUNT:
                new_phase = InterviewPhase.COMPLETED

        return new_phase, new_depth, hint

    # ── Report generation ─────────────────────────────────────────────────────

    def generate_evaluation_report(self, session_id: str, state: SessionState) -> Dict:
        """Generate rich LLM-written evaluation report with phase-wise feedback."""
        turns = state.questions_asked

        # Group turns by phase
        phase_turns = {i: [] for i in range(1, 7)}
        for turn in turns:
            phase_val = turn.get("phase", 1)
            if isinstance(phase_val, int) and 1 <= phase_val <= 6:
                phase_turns[phase_val].append(turn)

        # Calculate numeric scores per phase
        phase_scores = {}
        for phase_val, phase_turns_list in phase_turns.items():
            scores = [t["score"] for t in phase_turns_list if t.get("score")]
            if scores:
                phase_scores[InterviewPhase(phase_val).name] = round(
                    sum(scores) / len(scores), 1
                )

        # Depth metrics for socratic phases
        primary_turns = phase_turns.get(InterviewPhase.PRIMARY_PROJECT_DRILL.value, [])
        secondary_turns = phase_turns.get(
            InterviewPhase.SECONDARY_PROJECT_DRILL.value, []
        )
        max_primary_depth = max((t.get("depth", 0) for t in primary_turns), default=0)
        max_secondary_depth = max(
            (t.get("depth", 0) for t in secondary_turns), default=0
        )

        # Domain accuracy
        domain_turns = phase_turns.get(InterviewPhase.DOMAIN_QUESTIONS.value, [])
        domain_scores = [t["score"] for t in domain_turns if t.get("score")]
        domain_correct = sum(1 for s in domain_scores if s >= 7)

        # Build full transcript for LLM report generation
        transcript_summary = ""
        for turn in turns[:20]:  # Limit to avoid token overflow
            phase_name = (
                InterviewPhase(turn.get("phase", 1)).name
                if turn.get("phase")
                else "UNKNOWN"
            )
            transcript_summary += f"[{phase_name} D{turn.get('depth', 0)}]\n"
            transcript_summary += f"Q: {turn.get('question', '')[:200]}\n"
            transcript_summary += f"A: {turn.get('answer' or '')[:300]}\n"
            if turn.get("score"):
                transcript_summary += (
                    f"Score: {turn['score']}/10 — {turn.get('score_reason', '')}\n"
                )
            transcript_summary += "\n"

        # Generate LLM-written report
        report_prompt = f"""You are evaluating a {state.job_title} interview at {state.company}.

INTERVIEW TRANSCRIPT:
{transcript_summary}

NUMERIC SCORES:
{json.dumps(phase_scores, indent=2)}

Socratic Depth Reached:
- Primary Project: {max_primary_depth}/{self.MAX_DEPTH} levels
- Secondary Project: {max_secondary_depth}/{self.MAX_DEPTH} levels

Domain Q Accuracy: {domain_correct}/{len(domain_scores)} correct

Write a structured evaluation report. Be specific — reference actual answers from the transcript.

Format EXACTLY:

PHASE_1_SUMMARY: [2 sentences on background/communication quality]

PHASE_2_ANALYSIS: [3 sentences: what depth was reached, what they knew well, where they got stuck]
PHASE_2_SOCRATIC_SCORE: [X/10 — how deep they went in the Russian doll drill]

PHASE_3_ANALYSIS: [3 sentences: similar to phase 2]
PHASE_3_SOCRATIC_SCORE: [X/10]

PHASE_4_ANALYSIS: [2 sentences: factual accuracy, which questions they got right/wrong]
PHASE_4_ACCURACY: [{domain_correct}/{len(domain_scores) if domain_scores else 5} correct]

PHASE_5_ANALYSIS: [2 sentences: are they visionary, grounded, team player?]

STRENGTHS:
- [specific strength 1 with example from interview]
- [specific strength 2]
- [specific strength 3]

GAPS:
- [specific gap 1 with what was missed]
- [specific gap 2]
- [specific gap 3]

IMPROVEMENT_TIPS:
- [actionable tip 1]
- [actionable tip 2]
- [actionable tip 3]
- [actionable tip 4]

OVERALL_VERDICT: [3 sentences: overall fit for {state.job_title}, readiness level, one key recommendation]"""

        try:
            response = chat_completion(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": report_prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            report_text = response["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Engine] Report generation failed: {e}")
            report_text = "Report generation failed. Please try again."

        # Parse the report text
        def extract_field(text, field_name):
            match = re.search(
                rf"{re.escape(field_name)}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL
            )
            return match.group(1).strip() if match else ""

        def extract_list(text, field_name):
            match = re.search(rf"{re.escape(field_name)}:\s*\n((?:- .+\n?)+)", text)
            if match:
                items = re.findall(r"- (.+)", match.group(1))
                return [item.strip() for item in items]
            return []

        # Calculate weighted overall score
        weights = {
            "PRIMARY_PROJECT_DRILL": 0.25,
            "SECONDARY_PROJECT_DRILL": 0.20,
            "DOMAIN_QUESTIONS": 0.30,
            "BEHAVIORAL": 0.15,
            "BACKGROUND": 0.10,
        }
        overall = 0
        weight_used = 0
        for phase_name, weight in weights.items():
            if phase_name in phase_scores:
                overall += phase_scores[phase_name] * weight
                weight_used += weight
        if weight_used > 0:
            overall = round(overall / weight_used, 1)
        else:
            overall = 0

        return {
            "session_id": session_id,
            "job_title": state.job_title,
            "company": state.company,
            "overall_score": overall,
            "phase_scores": phase_scores,
            "socratic_depth": {
                "primary": f"{max_primary_depth}/{self.MAX_DEPTH}",
                "secondary": f"{max_secondary_depth}/{self.MAX_DEPTH}",
            },
            "domain_accuracy": f"{domain_correct}/{len(domain_scores) if domain_scores else 0}",
            "phase_1_summary": extract_field(report_text, "PHASE_1_SUMMARY"),
            "phase_2_analysis": extract_field(report_text, "PHASE_2_ANALYSIS"),
            "phase_2_socratic_score": extract_field(
                report_text, "PHASE_2_SOCRATIC_SCORE"
            ),
            "phase_3_analysis": extract_field(report_text, "PHASE_3_ANALYSIS"),
            "phase_3_socratic_score": extract_field(
                report_text, "PHASE_3_SOCRATIC_SCORE"
            ),
            "phase_4_analysis": extract_field(report_text, "PHASE_4_ANALYSIS"),
            "phase_5_analysis": extract_field(report_text, "PHASE_5_ANALYSIS"),
            "strengths": extract_list(report_text, "STRENGTHS"),
            "gaps": extract_list(report_text, "GAPS"),
            "improvement_tips": extract_list(report_text, "IMPROVEMENT_TIPS"),
            "overall_verdict": extract_field(report_text, "OVERALL_VERDICT"),
            "total_questions": len(turns),
            "generated_at": datetime.now().isoformat(),
        }
