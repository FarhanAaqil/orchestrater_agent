from agents.base_agent import BaseAgent
from database.tracker import (
    add_skill, get_skills, add_certificate, get_certificates,
    add_interview_prep, add_milestone, get_milestones,
    get_all_jobs, get_stats
)

AAQIL_RESUME = """
Name: Farhan Aaqil
Degree: B.Tech AI/ML — JPNCE Mahbubnagar (2027)
Email: fadurrani543@gmail.com | Phone: +91-6300825009
GitHub: github.com/FarhanAaqil | LinkedIn: linkedin.com/in/farhan-aaqil-4730432bb

EXPERIENCE:
- Python Full Stack Developer & AIML Intern — Jala Academy

SKILLS:
- Languages: Python, SQL
- AI/ML: LangChain, LLM Agents, Machine Learning, Deep Learning, NLP
- Tools: ChromaDB, FastAPI, Streamlit, Git, Playwright
- Data: Pandas, NumPy, Scikit-learn, Matplotlib

PROJECTS:
- Aaqil: 9-agent personal AI Chief of Staff system
- Self-Improving Code Agent: LLM agent with critique loop and vector memory
- SheetSense AI: AI-powered spreadsheet analysis
- IntelliGlove: Smart gesture recognition system
- InterviewPro: AI interview preparation platform
- DiaPredict AI: ML-based diabetes prediction (Published Research 2025)

CERTIFICATIONS:
- 4x Anthropic Certifications
- Apna College Full Stack Development
- NPTEL Database Management Systems
- 2x SkillUp Certifications

RESEARCH:
- Published Paper: ML-based Diabetes Prediction (2025)
"""

class CareerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="career",
            system_prompt=f"""You are Aaqil's Career Agent.
You help with resume tailoring, skill gap analysis, interview prep, and career tracking.
Here is Aaqil's full profile:
{AAQIL_RESUME}
Always give specific, actionable advice. Never be generic."""
        )
        self._seed_skills()
        self._seed_certificates()

    def _seed_skills(self):
        skills = [
            ("Python", "advanced", "Programming"),
            ("Machine Learning", "advanced", "AI/ML"),
            ("LangChain", "advanced", "AI/ML"),
            ("LLM Agents", "advanced", "AI/ML"),
            ("ChromaDB", "intermediate", "AI/ML"),
            ("FastAPI", "intermediate", "Backend"),
            ("Streamlit", "intermediate", "Frontend"),
            ("SQL", "intermediate", "Data"),
            ("Deep Learning", "intermediate", "AI/ML"),
            ("NLP", "intermediate", "AI/ML"),
            ("Pandas", "advanced", "Data"),
            ("NumPy", "advanced", "Data"),
            ("Scikit-learn", "intermediate", "AI/ML"),
            ("Git", "intermediate", "Tools"),
            ("Playwright", "intermediate", "Automation"),
            ("Docker", "beginner", "DevOps"),
        ]
        for name, level, category in skills:
            add_skill(name, level, category)

    def _seed_certificates(self):
        certs = [
            ("Anthropic Certification 1", "Anthropic", "completed", "", "AI/ML"),
            ("Anthropic Certification 2", "Anthropic", "completed", "", "AI/ML"),
            ("Anthropic Certification 3", "Anthropic", "completed", "", "AI/ML"),
            ("Anthropic Certification 4", "Anthropic", "completed", "", "AI/ML"),
            ("Full Stack Development", "Apna College", "completed", "", "Programming"),
            ("Database Management Systems", "NPTEL", "completed", "", "Data"),
            ("SkillUp Certification 1", "SkillUp", "completed", "", "AI/ML"),
            ("SkillUp Certification 2", "SkillUp", "completed", "", "AI/ML"),
        ]
        for title, provider, status, url, area in certs:
            add_certificate(title, provider, status, url, area)

    def tailor_resume(self, job_description: str) -> str:
        task = f"""Tailor Aaqil's resume for this job description:

JOB DESCRIPTION:
{job_description}

AAQIL'S RESUME:
{AAQIL_RESUME}

Output a tailored resume that:
1. Reorders skills to match JD keywords
2. Highlights the most relevant projects
3. Customizes the summary/objective
4. Adds any missing keywords naturally
Keep it ATS-friendly."""
        return self.run(task)

    def skill_gap_analysis(self, job_description: str) -> str:
        skills = get_skills()
        skill_names = [s["name"] for s in skills]
        task = f"""Analyze the skill gap between Aaqil's profile and this job:

JOB DESCRIPTION:
{job_description}

AAQIL'S CURRENT SKILLS:
{', '.join(skill_names)}

Output:
1. ✅ Skills Aaqil HAS that match
2. ❌ Skills MISSING (critical)
3. ⚠️ Skills to IMPROVE
4. 📚 Top 3 resources to fill gaps (free only)
5. Overall match score /10
6. Should he apply? Final verdict."""
        return self.run(task)

    def generate_interview_prep(self, company: str, role: str, jd: str = "") -> str:
        task = f"""Generate interview prep for Aaqil:
Company: {company}
Role: {role}
JD: {jd if jd else 'AI/ML internship'}

Generate:
1. 5 Technical questions (with ideal answers based on Aaqil's skills)
2. 3 Behavioral questions (with STAR-format answers)
3. 2 Questions Aaqil should ask the interviewer
4. Red flags to avoid
5. Key things to highlight from his profile

Be very specific to {company}'s culture and {role}."""
        result = self.run(task)
        add_interview_prep(company, role, result)
        return result

    def suggest_certificates(self) -> str:
        skills = get_skills()
        existing_certs = get_certificates()
        cert_names = [c["title"] for c in existing_certs]
        task = f"""Suggest free certifications for Aaqil to boost his career:

Current certifications: {', '.join(cert_names)}
Current skills: {', '.join([s['name'] for s in skills])}
Target: Remote paid AI/ML internships

Suggest 5 free certifications from:
- DeepLearning.AI (Coursera free audit)
- Google Cloud Skills Boost
- AWS Skill Builder  
- Hugging Face
- Fast.ai
- Microsoft Learn

For each: Name, Provider, Link, Why it matters for Aaqil."""
        return self.run(task)

    def career_dashboard(self) -> str:
        skills = get_skills()
        certs = get_certificates()
        milestones = get_milestones()
        job_stats = get_stats()
        applied = job_stats.get("applied", 0)
        interviews = job_stats.get("interview", 0)

        by_category = {}
        for s in skills:
            cat = s["category"] or "Other"
            by_category.setdefault(cat, []).append(f"{s['name']} ({s['level']})")

        result = "🎯 **Career Dashboard**\n\n"
        result += f"📜 Certifications: {len(certs)}\n"
        result += f"🛠️ Skills tracked: {len(skills)}\n"
        result += f"✅ Applications sent: {applied}\n"
        result += f"🎤 Interviews: {interviews}\n"
        result += f"🏆 Milestones: {len(milestones)}\n\n"

        result += "**Skills by Category:**\n"
        for cat, skill_list in by_category.items():
            result += f"\n*{cat}:*\n"
            result += ", ".join(skill_list) + "\n"

        if milestones:
            result += "\n**Recent Milestones:**\n"
            for m in milestones[:5]:
                result += f"🏆 {m['title']} — {m['date'][:10]}\n"

        return result

    def add_skill_command(self, task: str) -> str:
        parts = task.replace("add skill", "").strip().split(",")
        name = parts[0].strip()
        level = parts[1].strip() if len(parts) > 1 else "beginner"
        category = parts[2].strip() if len(parts) > 2 else ""
        add_skill(name, level, category)
        return f"✅ Skill added: **{name}** ({level})"

    def show_skills(self) -> str:
        skills = get_skills()
        if not skills:
            return "No skills tracked yet."
        level_emoji = {"advanced": "🔥", "intermediate": "⚡", "beginner": "🌱"}
        by_cat = {}
        for s in skills:
            cat = s["category"] or "Other"
            by_cat.setdefault(cat, []).append(s)
        result = "🛠️ **Skills:**\n\n"
        for cat, skill_list in by_cat.items():
            result += f"**{cat}:**\n"
            for s in skill_list:
                result += f"  {level_emoji.get(s['level'], '⚪')} {s['name']}\n"
            result += "\n"
        return result

    def show_certs(self) -> str:
        certs = get_certificates()
        if not certs:
            return "No certificates tracked."
        result = f"📜 **Certificates ({len(certs)}):**\n\n"
        for c in certs:
            result += f"✅ **{c['title']}** — {c['provider']}\n"
            result += f"   Area: {c['skill_area']} | {c['completed_at'][:10] if c['completed_at'] else 'N/A'}\n\n"
        return result

    def handle(self, task: str) -> str:
        t = task.lower()

        if "tailor resume" in t or "customize resume" in t:
            jd = task.replace("tailor resume for", "").replace("tailor resume", "").strip()
            return self.tailor_resume(jd)

        elif "skill gap" in t or "analyze job" in t:
            jd = task.replace("skill gap for", "").replace("skill gap", "").strip()
            return self.skill_gap_analysis(jd)

        elif "interview prep" in t or "prepare interview" in t:
            parts = task.replace("interview prep for", "").replace("prepare interview", "").strip().split(",")
            company = parts[0].strip() if len(parts) > 0 else "the company"
            role = parts[1].strip() if len(parts) > 1 else "AI/ML Intern"
            jd = parts[2].strip() if len(parts) > 2 else ""
            return self.generate_interview_prep(company, role, jd)

        elif "suggest cert" in t or "recommend cert" in t or "what cert" in t:
            return self.suggest_certificates()

        elif "add skill" in t:
            return self.add_skill_command(task)

        elif "add milestone" in t:
            parts = task.replace("add milestone", "").strip().split(",")
            title = parts[0].strip()
            category = parts[1].strip() if len(parts) > 1 else "general"
            notes = parts[2].strip() if len(parts) > 2 else ""
            add_milestone(title, category, notes)
            return f"🏆 Milestone added: **{title}**"

        elif "add certificate" in t or "add cert" in t:
            parts = task.replace("add certificate", "").replace("add cert", "").strip().split(",")
            title = parts[0].strip()
            provider = parts[1].strip() if len(parts) > 1 else "Unknown"
            area = parts[2].strip() if len(parts) > 2 else ""
            add_certificate(title, provider, "completed", "", area)
            return f"📜 Certificate added: **{title}** by {provider}"

        elif "show skills" in t or "my skills" in t:
            return self.show_skills()

        elif "show cert" in t or "my cert" in t or "certificates" in t:
            return self.show_certs()

        elif "dashboard" in t or "career stats" in t or "career summary" in t:
            return self.career_dashboard()

        else:
            return self.run(task)