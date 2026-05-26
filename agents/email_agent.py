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

        if "recruiter email" in t or "outreach email" in t:
            parts = task.replace("draft recruiter email to", "").replace("outreach email to", "").strip().split(",")
            name = parts[0].strip()
            company = parts[1].strip() if len(parts) > 1 else "the company"
            role = parts[2].strip() if len(parts) > 2 else "AI/ML Intern"
            email = parts[3].strip() if len(parts) > 3 else ""
            return self.draft_recruiter_email(name, company, role, email)

        elif "application email" in t:
            parts = task.replace("draft application email for", "").replace("application email for", "").strip().split(",")
            company = parts[0].strip()
            role = parts[1].strip() if len(parts) > 1 else "AI/ML Intern"
            jd = parts[2].strip() if len(parts) > 2 else ""
            email = parts[3].strip() if len(parts) > 3 else ""
            return self.draft_application_email(company, role, jd, email)

        elif "follow up email" in t or "follow-up email" in t:
            parts = task.replace("draft follow up email to", "").replace("follow-up email to", "").strip().split(",")
            name = parts[0].strip()
            company = parts[1].strip() if len(parts) > 1 else "the company"
            context = parts[2].strip() if len(parts) > 2 else "my application"
            days = int(''.join(filter(str.isdigit, parts[3]))) if len(parts) > 3 else 7
            return self.draft_follow_up(name, company, context, days)

        elif "publisher email" in t or "journal email" in t:
            parts = task.replace("draft publisher email for", "").replace("journal email for", "").strip().split(",")
            paper = parts[0].strip()
            journal = parts[1].strip() if len(parts) > 1 else "the journal"
            email = parts[2].strip() if len(parts) > 2 else ""
            return self.draft_publisher_email(paper, journal, email)

        elif "send email" in t:
            parts = task.replace("send email", "").strip().split(",")
            email_id = int(''.join(filter(str.isdigit, parts[0])))
            to_email = parts[1].strip() if len(parts) > 1 else ""
            return self.send_email(email_id, to_email)

        elif "email dashboard" in t or "my emails" in t or "show emails" in t:
            return self.email_dashboard()

        else:
            return self.run(task)