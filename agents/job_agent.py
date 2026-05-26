from agents.base_agent import BaseAgent
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from database.tracker import insert_job, update_status, get_all_jobs, get_stats
import time
import random

AAQIL_PROFILE = """
Name: Farhan Aaqil
Degree: B.Tech AI/ML (Final Year, 2027) — JPNCE Mahbubnagar
Skills: Python, LangChain, LLM Agents, Machine Learning, Data Science, ChromaDB, FastAPI, Streamlit
Experience: Python Full Stack + AIML Intern at Jala Academy
Published Research: ML-based Diabetes Prediction (2025)
Projects: SheetSense AI, IntelliGlove, InterviewPro, DiaPredict AI
Certifications: 4 Anthropic, Apna College Full Stack, NPTEL DBMS, 2 SkillUp
Target: Remote paid internships in Python, AI/ML, LLM Agents — NO web development
"""

FILTER_KEYWORDS = ["python", "ai", "ml", "machine learning", "llm", "nlp",
                   "data science", "deep learning", "langchain", "agent", "artificial intelligence"]

EXCLUDE_KEYWORDS = ["react", "angular", "vue", "frontend only", "php", "ruby",
                    "wordpress", "graphic design", "sales", "marketing only"]

class JobAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="job",
            system_prompt=f"""You are Aaqil's Job/Internship Agent.
You help find, filter, rank, and apply to internships.
Here is Aaqil's profile:
{AAQIL_PROFILE}
Always match jobs to this profile and generate tailored cover letters."""
        )

    def _human_delay(self, min=1.0, max=3.0):
        time.sleep(random.uniform(min, max))

    def _is_relevant(self, title: str, description: str = "") -> bool:
        text = (title + " " + description).lower()
        has_keyword = any(k in text for k in FILTER_KEYWORDS)
        has_exclude = any(k in text for k in EXCLUDE_KEYWORDS)
        return has_keyword and not has_exclude

    def _score_job(self, title: str, description: str = "") -> int:
        text = (title + " " + description).lower()
        score = 0
        high_value = ["llm", "langchain", "agent", "ai agent", "nlp", "machine learning"]
        medium_value = ["python", "data science", "ml", "deep learning"]
        low_value = ["intern", "remote", "paid"]
        for k in high_value:
            if k in text: score += 3
        for k in medium_value:
            if k in text: score += 2
        for k in low_value:
            if k in text: score += 1
        return min(score, 10)

    def scrape_internshala(self, keywords="machine-learning", limit=15) -> list:
        jobs = []
        url = f"https://internshala.com/internships/{keywords}-internship"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            stealth_sync(page)

            try:
                page.goto(url, timeout=30000)
                self._human_delay(2, 4)
                page.wait_for_selector(".internship_meta", timeout=15000)

                cards = page.query_selector_all(".internship-list-item-holder")

                for card in cards[:limit]:
                    try:
                        title_el = card.query_selector(".job-internship-name")
                        company_el = card.query_selector(".company-name")
                        location_el = card.query_selector(".locations span")
                        link_el = card.query_selector("a.view_detail_button")

                        title = title_el.inner_text().strip() if title_el else "N/A"
                        company = company_el.inner_text().strip() if company_el else "N/A"
                        location = location_el.inner_text().strip() if location_el else "Remote"
                        link = "https://internshala.com" + link_el.get_attribute("href") if link_el else "N/A"

                        if not self._is_relevant(title):
                            continue

                        score = self._score_job(title)
                        job = {
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": link,
                            "source": "Internshala",
                            "match_score": score
                        }
                        jobs.append(job)
                        insert_job(job)
                        self._human_delay(0.3, 0.7)
                    except:
                        continue

            except Exception as e:
                return [{"error": str(e)}]
            finally:
                browser.close()

        return sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)

    def scrape_wellfound(self, keywords="machine learning", limit=10) -> list:
        jobs = []
        url = f"https://wellfound.com/jobs?q={keywords.replace(' ', '%20')}&remote=true"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            stealth_sync(page)

            try:
                page.goto(url, timeout=30000)
                self._human_delay(3, 5)

                cards = page.query_selector_all("[data-test='StartupResult']")

                for card in cards[:limit]:
                    try:
                        title_el = card.query_selector("a[data-test='job-title']")
                        company_el = card.query_selector("a[data-test='startup-link']")
                        link_el = card.query_selector("a[data-test='job-title']")

                        title = title_el.inner_text().strip() if title_el else "N/A"
                        company = company_el.inner_text().strip() if company_el else "N/A"
                        link = "https://wellfound.com" + link_el.get_attribute("href") if link_el else "N/A"

                        if not self._is_relevant(title):
                            continue

                        score = self._score_job(title)
                        job = {
                            "title": title,
                            "company": company,
                            "location": "Remote",
                            "url": link,
                            "source": "Wellfound",
                            "match_score": score
                        }
                        jobs.append(job)
                        insert_job(job)
                    except:
                        continue

            except Exception as e:
                return [{"error": str(e)}]
            finally:
                browser.close()

        return sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)

    def generate_cover_letter(self, title: str, company: str, description: str = "") -> str:
        task = f"""Write a tailored cover letter for Aaqil for this internship:
Role: {title}
Company: {company}
Description: {description if description else 'AI/ML internship'}

Profile:
{AAQIL_PROFILE}

Write 3 short paragraphs. Professional but genuine tone. Highlight published paper and agent-building experience. End with enthusiasm."""
        return self.run(task)

    def get_dashboard(self) -> str:
        stats = get_stats()
        jobs = get_all_jobs()
        result = "📊 **Application Dashboard**\n\n"
        result += f"Total tracked: {len(jobs)}\n"
        for status, count in stats.items():
            emoji = {"found": "🔍", "applied": "✅", "rejected": "❌", "interview": "🎯"}.get(status, "📌")
            result += f"{emoji} {status.capitalize()}: {count}\n"

        result += "\n🔥 **Top Matches (Not Applied Yet):**\n"
        top = [j for j in jobs if j["status"] == "found"][:5]
        for j in top:
            result += f"\n• **{j['title']}** at {j['company']}\n"
            result += f"  Score: {j['match_score']}/10 | {j['source']}\n"
            result += f"  🔗 {j['url']}\n"
        return result

    def handle(self, task: str) -> str:
        task_lower = task.lower()

        if "internshala" in task_lower or "search" in task_lower or "find" in task_lower:
            keywords = "machine-learning"
            if "python" in task_lower: keywords = "python"
            if "llm" in task_lower or "langchain" in task_lower: keywords = "artificial-intelligence"
            if "data" in task_lower: keywords = "data-science"

            jobs = self.scrape_internshala(keywords)
            if not jobs:
                return "Scraping error: No jobs found or scraper returned empty results."
        
            if isinstance(jobs[0], dict) and "error" in jobs[0]:
                return f"Scraping error: {jobs[0].get('error', 'Unknown')}"
            
            return jobs

            result = f"🔍 Found {len(jobs)} relevant internships from Internshala:\n\n"
            for i, job in enumerate(jobs[:8], 1):
                result += f"{i}. **{job['title']}** at {job['company']}\n"
                result += f"   📍 {job['location']} | ⭐ Match: {job['match_score']}/10\n"
                result += f"   🔗 {job['url']}\n\n"
            return result

        elif "wellfound" in task_lower:
            jobs = self.scrape_wellfound()
            if not jobs or "error" in jobs[0]:
                return f"Scraping error: {jobs[0].get('error', 'Unknown')}"

            result = f"🔍 Found {len(jobs)} jobs from Wellfound:\n\n"
            for i, job in enumerate(jobs[:8], 1):
                result += f"{i}. **{job['title']}** at {job['company']}\n"
                result += f"   ⭐ Match: {job['match_score']}/10 | 🔗 {job['url']}\n\n"
            return result

        elif "cover letter" in task_lower:
            parts = task.replace("cover letter for", "").replace("generate", "").strip().split(",")
            title = parts[0].strip() if len(parts) > 0 else "AI/ML Intern"
            company = parts[1].strip() if len(parts) > 1 else "the company"
            desc = parts[2].strip() if len(parts) > 2 else ""
            cover = self.generate_cover_letter(title, company, desc)
            return cover

        elif "dashboard" in task_lower or "stats" in task_lower or "tracker" in task_lower:
            return self.get_dashboard()

        elif "applied" in task_lower or "mark" in task_lower:
            parts = task.split(",")
            url = parts[-1].strip() if parts else ""
            update_status(url, "applied")
            return f"✅ Marked as applied: {url}"

        elif "all jobs" in task_lower or "show jobs" in task_lower:
            jobs = get_all_jobs()
            if not jobs:
                return "No jobs tracked yet. Try searching first."
            result = f"📋 All Tracked Jobs ({len(jobs)}):\n\n"
            for j in jobs[:10]:
                result += f"• **{j['title']}** — {j['company']} | {j['status'].upper()} | Score: {j['match_score']}/10\n"
            return result

        else:
            return self.run(task)