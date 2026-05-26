from agents.base_agent import BaseAgent
from database.tracker import add_email, mark_email_sent, get_emails
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

AAQIL_SIGNATURE = """
--
Farhan Aaqil
B.Tech AI/ML | JPNCE Mahbubnagar
GitHub: github.com/FarhanAaqil
LinkedIn: linkedin.com/in/farhan-aaqil-4730432bb
Phone: +91-6300825009
"""

class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="email",
            system_prompt=f"""You are Aaqil's Email Agent.
You draft and send professional emails for:
- Job/internship applications and follow-ups
- Research paper submissions to journals
- Recruiter outreach and networking
- Publisher communications
Always be professional, concise, and genuine.
Aaqil's signature: {AAQIL_SIGNATURE}"""
        )
        self.email = os.getenv("EMAIL_ADDRESS")
        self.password = os.getenv("EMAIL_APP_PASSWORD")

    def _send_email(self, to_email: str, subject: str, body: str) -> dict:
        if not self.email or not self.password:
            return {"success": False, "error": "Gmail credentials missing in .env"}
        try:
            msg = MIMEMultipart()
            msg["From"] = self.email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.email, self.password)
                server.send_message(msg)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def draft_recruiter_email(self, name: str, company: str,
                               role: str, email: str = "") -> str:
        task = f"""Draft a cold outreach email to a recruiter:
Recruiter: {name} at {company}
Role: {role}
From: Farhan Aaqil

Write a compelling, short email (150-200 words):
- Subject line
- Personal hook referencing {company}
- 2 sentences on Aaqil's strongest relevant experience
- Specific ask (30-min call or resume review)
- Professional closing
{AAQIL_SIGNATURE}"""
        result = self.run(task)
        subject = f"AI/ML Internship Opportunity — Farhan Aaqil"
        for line in result.split('\n'):
            if line.lower().startswith("subject:"):
                subject = line.replace("Subject:", "").replace("subject:", "").strip()
                break
        email_id = add_email(email, name, subject, result, "recruiter_outreach")
        return f"📧 Email drafted (ID: {email_id})\n\n{result}"

    def draft_application_email(self, company: str, role: str,
                                  jd_summary: str = "", email: str = "") -> str:
        task = f"""Draft a job application email:
Company: {company}
Role: {role}
JD: {jd_summary if jd_summary else 'AI/ML internship'}
From: Farhan Aaqil

Include:
- Strong subject line
- Opening that references {company} specifically
- 3 bullet points: most relevant project/skill for this role
- Link to GitHub and LinkedIn
- Professional close
{AAQIL_SIGNATURE}"""
        result = self.run(task)
        subject = f"Application for {role} — Farhan Aaqil"
        email_id = add_email(email, company, subject, result, "job_application")
        return f"📧 Application email drafted (ID: {email_id})\n\n{result}"

    def draft_follow_up(self, name: str, company: str,
                         context: str, days_ago: int = 7) -> str:
        task = f"""Draft a follow-up email:
To: {name} at {company}
Context: {context}
Sent {days_ago} days ago, no reply yet.

Write a short, polite follow-up (80-100 words):
- Reference the original email context
- Show continued genuine interest
- One new value-add (new project, achievement)
- Clear ask
{AAQIL_SIGNATURE}"""
        result = self.run(task)
        subject = f"Following up — {context[:40]}"
        email_id = add_email("", name, subject, result, "follow_up")
        return f"📧 Follow-up drafted (ID: {email_id})\n\n{result}"

    def draft_publisher_email(self, paper_title: str, journal: str,
                               editor_email: str = "") -> str:
        task = f"""Draft a manuscript submission email:
Paper: {paper_title}
Journal: {journal}
From: Farhan Aaqil, JPNCE Mahbubnagar, India
Previous pub: ML-based Diabetes Prediction (2025)

Formal academic submission email:
- Subject: Manuscript Submission — [Paper Title]
- State paper title and contribution
- Why it fits this journal
- Originality declaration
- Contact details
{AAQIL_SIGNATURE}"""
        result = self.run(task)
        subject = f"Manuscript Submission — {paper_title}"
        email_id = add_email(editor_email, f"Editor, {journal}", subject, result, "paper_submission")
        return f"📧 Submission email drafted (ID: {email_id})\n\n{result}"

    def send_email(self, email_id: int, to_email: str) -> str:
        emails = get_emails()
        email = next((e for e in emails if e["id"] == email_id), None)
        if not email:
            return "Email not found."
        result = self._send_email(to_email, email["subject"], email["body"])
        if result["success"]:
            mark_email_sent(email_id)
            return f"✅ Email sent successfully to {to_email}"
        return f"❌ Failed to send: {result['error']}"

    def email_dashboard(self) -> str:
        emails = get_emails()
        by_cat = {}
        for e in emails:
            by_cat.setdefault(e["category"], []).append(e)
        result = f"📬 **Email Dashboard ({len(emails)} total):**\n\n"
        cat_emoji = {
            "recruiter_outreach": "🤝",
            "job_application": "💼",
            "follow_up": "🔄",
            "paper_submission": "📚",
            "general": "📧"
        }
        for cat, cat_emails in by_cat.items():
            sent = len([e for e in cat_emails if e["status"] == "sent"])
            emoji = cat_emoji.get(cat, "📧")
            result += f"{emoji} {cat.replace('_', ' ').title()}: {len(cat_emails)} total | {sent} sent\n"
        result += "\n**Recent Emails:**\n"
        for e in emails[:5]:
            result += f"\n• [{e['status'].upper()}] {e['subject'][:50]}\n"
            result += f"  To: {e['to_name']} | {e['created_at'][:10]}\n"
        return result

    def handle(self, task: str) -> str:
        t = task.lower()

        if any(kw in t for kw in ["recruiter email", "outreach email"]):
            params = self.extract_intent(task, {
                "name": "string, the recruiter's name",
                "company": "string, the company name",
                "role": "string, the target role or internship",
                "email": "string or null, email address if mentioned"
            })
            name = params.get("name") or "Recruiter"
            company = params.get("company") or "the company"
            role = params.get("role") or "AI/ML Intern"
            email = params.get("email") or ""
            return self.draft_recruiter_email(name, company, role, email)

        elif "application email" in t:
            params = self.extract_intent(task, {
                "company": "string, the company name",
                "role": "string, the role to apply for",
                "description": "string or null, job description details",
                "email": "string or null, email address"
            })
            company = params.get("company") or "the company"
            role = params.get("role") or "AI/ML Intern"
            jd = params.get("description") or ""
            email = params.get("email") or ""
            return self.draft_application_email(company, role, jd, email)

        elif any(kw in t for kw in ["follow up email", "follow-up email"]):
            params = self.extract_intent(task, {
                "name": "string, the person's name",
                "company": "string, the company name",
                "context": "string, what the original email was about",
                "days_ago": "integer or null, how many days since the original email"
            })
            name = params.get("name") or "Recruiter"
            company = params.get("company") or "the company"
            context = params.get("context") or "my application"
            days = params.get("days_ago") or 7
            try:
                days = int(days)
            except (TypeError, ValueError):
                days = 7
            return self.draft_follow_up(name, company, context, days)

        elif any(kw in t for kw in ["publisher email", "journal email"]):
            params = self.extract_intent(task, {
                "paper": "string, the paper title",
                "journal": "string, the journal name",
                "email": "string or null, editor email address"
            })
            paper = params.get("paper") or "my paper"
            journal = params.get("journal") or "the journal"
            email = params.get("email") or ""
            return self.draft_publisher_email(paper, journal, email)

        elif "send email" in t:
            params = self.extract_intent(task, {
                "email_id": "integer, the email ID number",
                "to_email": "string, the recipient email address"
            })
            email_id = params.get("email_id")
            to_email = params.get("to_email") or ""
            if not email_id:
                digits = ''.join(filter(str.isdigit, task))
                email_id = int(digits) if digits else None
            if email_id:
                return self.send_email(int(email_id), to_email)
            return "Please specify an email ID. Example: 'send email 3 to recruiter@company.com'"

        elif any(kw in t for kw in ["email dashboard", "my emails", "show emails"]):
            return self.email_dashboard()

        else:
            return self.run(task)