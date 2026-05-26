from agents.base_agent import BaseAgent
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import time
import random
import json
import os
from dotenv import load_dotenv

load_dotenv()

class LinkedInAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="linkedin",
            system_prompt="""You are Aaqil's LinkedIn Agent. You help with:
- Drafting professional connection request messages
- Writing outreach messages to recruiters
- Analyzing job descriptions
- Writing follow-up messages
Keep all messages professional, concise, and personalized.
Aaqil is a final-year AI/ML student targeting remote paid internships in Python, AI agents, and ML."""
        )
        self.email = os.getenv("LINKEDIN_EMAIL")
        self.password = os.getenv("LINKEDIN_PASSWORD")

    def _human_delay(self, min=1.0, max=3.0):
        time.sleep(random.uniform(min, max))

    def scrape_jobs(self, keywords="AI ML intern", location="India", limit=10) -> list:
        jobs = []
        url = f"https://www.linkedin.com/jobs/search/?keywords={keywords.replace(' ', '%20')}&location={location}&f_JT=I&f_WT=2"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            stealth(page)

            try:
                page.goto(url, timeout=30000)
                self._human_delay(2, 4)
                page.wait_for_selector(".jobs-search__results-list", timeout=15000)

                job_cards = page.query_selector_all(".jobs-search__results-list li")

                for card in job_cards[:limit]:
                    try:
                        title = card.query_selector("h3")
                        company = card.query_selector("h4")
                        location_el = card.query_selector(".job-search-card__location")
                        link = card.query_selector("a")

                        jobs.append({
                            "title": title.inner_text().strip() if title else "N/A",
                            "company": company.inner_text().strip() if company else "N/A",
                            "location": location_el.inner_text().strip() if location_el else "N/A",
                            "url": link.get_attribute("href") if link else "N/A"
                        })
                        self._human_delay(0.3, 0.8)
                    except:
                        continue

            except Exception as e:
                jobs = [{"error": str(e)}]
            finally:
                browser.close()

        return jobs

    def draft_connection_request(self, name: str, role: str, company: str) -> str:
        task = f"""Draft a LinkedIn connection request message for:
Name: {name}
Role: {role}
Company: {company}

Keep it under 300 characters. Be genuine, mention AI/ML interest. Don't be salesy."""
        return self.run(task)

    def draft_outreach(self, name: str, role: str, company: str, job_title: str = "") -> str:
        task = f"""Draft a LinkedIn outreach message to a recruiter:
Recruiter: {name} — {role} at {company}
Target Role: {job_title if job_title else 'AI/ML Intern or Python Developer Intern'}

Write a short, professional cold message. Mention Aaqil's ML background, published paper, and LangChain/LLM agent experience. Max 3 short paragraphs."""
        return self.run(task)

    def analyze_job(self, job_description: str) -> str:
        task = f"""Analyze this job description for Aaqil:
{job_description}

Output:
1. Match score (out of 10) for Aaqil's profile
2. Key required skills Aaqil has
3. Key required skills Aaqil is missing
4. Should he apply? Why?
5. Customization tips for resume/cover letter"""
        return self.run(task)

    def draft_follow_up(self, name: str, company: str, days_ago: int) -> str:
        task = f"""Draft a LinkedIn follow-up message:
Recruiter: {name} at {company}
Applied {days_ago} days ago, no response yet.

Keep it polite, short, show continued interest. Don't be desperate."""
        return self.run(task)

    def handle(self, task: str) -> str:
        task_lower = task.lower()

        if "scrape" in task_lower or "search jobs" in task_lower or "find jobs" in task_lower or "find internships" in task_lower:
            keywords = "AI ML Python intern"
            if "python" in task_lower:
                keywords = "Python developer intern"
            elif "llm" in task_lower or "langchain" in task_lower:
                keywords = "LLM AI agent intern"

            jobs = self.scrape_jobs(keywords=keywords)
            if not jobs or "error" in jobs[0]:
                return f"Scraping error: {jobs[0].get('error', 'Unknown')}"

            result = f"Found {len(jobs)} jobs:\n\n"
            for i, job in enumerate(jobs, 1):
                result += f"{i}. **{job['title']}** at {job['company']}\n"
                result += f"   📍 {job['location']}\n"
                result += f"   🔗 {job['url']}\n\n"
            return result

        elif "connection" in task_lower:
            parts = task.replace("draft connection", "").replace("for", "").strip().split(",")
            name = parts[0].strip() if len(parts) > 0 else "the person"
            role = parts[1].strip() if len(parts) > 1 else "professional"
            company = parts[2].strip() if len(parts) > 2 else "their company"
            return self.draft_connection_request(name, role, company)

        elif "outreach" in task_lower or "recruiter" in task_lower:
            parts = task.replace("draft outreach", "").replace("message to", "").strip().split(",")
            name = parts[0].strip() if len(parts) > 0 else "Recruiter"
            role = parts[1].strip() if len(parts) > 1 else "HR Manager"
            company = parts[2].strip() if len(parts) > 2 else "the company"
            job_title = parts[3].strip() if len(parts) > 3 else ""
            return self.draft_outreach(name, role, company, job_title)

        elif "analyze" in task_lower or "job description" in task_lower:
            jd = task.replace("analyze", "").replace("job description", "").strip()
            return self.analyze_job(jd)

        elif "follow up" in task_lower or "followup" in task_lower:
            parts = task.split(",")
            name = parts[0].replace("follow up", "").strip() if len(parts) > 0 else "Recruiter"
            company = parts[1].strip() if len(parts) > 1 else "the company"
            days = int(parts[2].strip()) if len(parts) > 2 else 7
            return self.draft_follow_up(name, company, days)

        else:
            return self.run(task)