"""
job_agent.py — Intelligent job/internship agent.

Upgrades over original:
- FIXED: Dead code bug where `return jobs` prevented formatted output
- FIXED: Natural language handle() using extract_intent
- LLM-powered job scoring using full profile context (not just keyword counting)
- Deduplication before DB insert (prevents re-adding same URL)
- auto_apply_assessment(): after scraping, ranks and explains top 3 picks
- Wellfound scrape result now properly formatted (was working but could be improved)
"""
from __future__ import annotations
from agents.base_agent import BaseAgent
from database.tracker import insert_job, update_status, get_all_jobs, get_stats
import time
import random

AAQIL_PROFILE = """
Name: Farhan Aaqil
Degree: B.Tech AI/ML (Final Year, 2027) — JPNCE Mahbubnagar
Skills: Python, LangChain, LLM Agents, Machine Learning, Data Science, ChromaDB, FastAPI, Streamlit
Experience: Python Full Stack + AIML Intern at Jala Academy
Published Research: ML-based Diabetes Prediction (2025)
Projects: SheetSense AI, IntelliGlove, InterviewPro, DiaPredict AI, Aaqil (9-agent orchestrator)
Certifications: 4 Anthropic, Apna College Full Stack, NPTEL DBMS, 2 SkillUp
Target: Remote paid internships in Python, AI/ML, LLM Agents — NO pure web development
"""

FILTER_KEYWORDS = [
    "python", "ai", "ml", "machine learning", "llm", "nlp",
    "data science", "deep learning", "langchain", "agent", "artificial intelligence"
]

EXCLUDE_KEYWORDS = [
    "react only", "angular", "vue", "frontend only", "php", "ruby",
    "wordpress", "graphic design", "sales only", "marketing only"
]


class JobAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="job",
            system_prompt=f"""You are Aaqil's Job/Internship Agent.
You help find, filter, rank, and apply to internships.
Here is Aaqil's profile:
{AAQIL_PROFILE}
Always match jobs to this profile and generate highly tailored cover letters.
Be specific — mention exact projects and skills that match each role."""
        )
        self._seen_urls: set = set()  # Deduplication cache

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _human_delay(self, min_s=1.0, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def _is_relevant(self, title: str, description: str = "") -> bool:
        text = (title + " " + description).lower()
        has_keyword = any(k in text for k in FILTER_KEYWORDS)
        has_exclude = any(k in text for k in EXCLUDE_KEYWORDS)
        return has_keyword and not has_exclude

    def _score_job_keywords(self, title: str, description: str = "") -> int:
        """Fast keyword-based pre-score for filtering."""
        text = (title + " " + description).lower()
        score = 0
        weights = {
            "llm": 3, "langchain": 3, "agent": 3, "ai agent": 3,
            "nlp": 2, "machine learning": 2, "deep learning": 2,
            "python": 2, "data science": 2, "ml": 2,
            "intern": 1, "remote": 1, "paid": 1
        }
        for kw, w in weights.items():
            if kw in text:
                score += w
        return min(score, 10)

    def _score_job_llm(self, title: str, company: str, description: str) -> dict:
        """LLM-powered job evaluation using Aaqil's full profile."""
        prompt = f"""Evaluate this job for Aaqil and return ONLY valid JSON:

Job Title: {title}
Company: {company}
Description: {description[:800]}

Aaqil's Profile:
{AAQIL_PROFILE}

Return:
{{"match_score": 1-10, "apply": true/false, "strengths": ["what Aaqil has"], "gaps": ["what he lacks"], "priority": "high/medium/low", "reason": "one sentence"}}"""
        try:
            raw = self.run_fresh(prompt, temperature=0.2)
            result = self._extract_json_safe(raw)
            return result or {"match_score": self._score_job_keywords(title, description),
                              "apply": True, "priority": "medium"}
        except Exception:
            return {"match_score": self._score_job_keywords(title, description),
                    "apply": True, "priority": "medium"}

    def _is_duplicate(self, url: str) -> bool:
        """Check if this URL was already seen in this session."""
        if url in self._seen_urls:
            return True
        # Also check existing DB jobs
        existing = get_all_jobs()
        existing_urls = {j.get("url", "") for j in existing}
        if url in existing_urls:
            return True
        self._seen_urls.add(url)
        return False

    # ─── Scrapers ─────────────────────────────────────────────────────────────

    def scrape_internshala(self, keywords="machine-learning", limit=15) -> list:
        jobs = []
        url = f"https://internshala.com/internships/{keywords}-internship"

        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
        except ImportError:
            return [{"error": "Playwright not installed. Run: pip install playwright playwright-stealth"}]

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
                        if self._is_duplicate(link):
                            continue

                        score = self._score_job_keywords(title)
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
                    except Exception:
                        continue

            except Exception as e:
                return [{"error": str(e)}]
            finally:
                browser.close()

        return sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)

    def scrape_wellfound(self, keywords="machine learning", limit=10) -> list:
        jobs = []
        url = f"https://wellfound.com/jobs?q={keywords.replace(' ', '%20')}&remote=true"

        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
        except ImportError:
            return [{"error": "Playwright not installed"}]

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

                        title = title_el.inner_text().strip() if title_el else "N/A"
                        company = company_el.inner_text().strip() if company_el else "N/A"
                        link = "https://wellfound.com" + title_el.get_attribute("href") if title_el else "N/A"

                        if not self._is_relevant(title):
                            continue
                        if self._is_duplicate(link):
                            continue

                        score = self._score_job_keywords(title)
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
                    except Exception:
                        continue

            except Exception as e:
                return [{"error": str(e)}]
            finally:
                browser.close()

        return sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)

    # ─── Job Actions ──────────────────────────────────────────────────────────

    def generate_cover_letter(self, title: str, company: str,
                               description: str = "") -> str:
        task = f"""Write a tailored cover letter for Aaqil for this internship:
Role: {title}
Company: {company}
Description: {description if description else 'AI/ML internship'}

Profile:
{AAQIL_PROFILE}

Write 3 focused paragraphs:
1. Opening: mention something specific about {company} and why Aaqil is excited
2. Evidence: pick the 2 most relevant projects/skills for THIS specific role
3. Close: clear ask + mention published research as differentiator

Professional but genuine tone. Max 250 words."""
        return self.run(task)

    def auto_apply_assessment(self, jobs: list) -> str:
        """LLM-powered ranking of scraped jobs with apply recommendations."""
        if not jobs:
            return "No jobs to assess."
        job_list = "\n".join([
            f"{i+1}. {j['title']} at {j['company']} (Score: {j.get('match_score', 0)}/10) — {j.get('url', '')}"
            for i, j in enumerate(jobs[:10])
        ])
        prompt = f"""You are helping Aaqil decide which internships to prioritize.

Profile:
{AAQIL_PROFILE}

Found jobs:
{job_list}

Pick the TOP 3 to apply to immediately and explain why each is a strong match.
Format:
🥇 #1: [Title] at [Company]
   Why: [specific reason based on Aaqil's skills]
   Action: [what to emphasize in cover letter]

Do the same for #2 and #3."""
        return self.run(prompt)

    def get_dashboard(self) -> str:
        stats = get_stats()
        jobs = get_all_jobs()
        result = "📊 **Application Dashboard**\n\n"
        result += f"Total tracked: {len(jobs)}\n"
        for status, count in stats.items():
            emoji = {"found": "🔍", "applied": "✅", "rejected": "❌",
                     "interview": "🎯"}.get(status, "📌")
            result += f"{emoji} {status.capitalize()}: {count}\n"

        result += "\n🔥 **Top Matches (Not Applied Yet):**\n"
        top = [j for j in jobs if j["status"] == "found"][:5]
        for j in top:
            result += f"\n• **{j['title']}** at {j['company']}\n"
            result += f"  Score: {j['match_score']}/10 | {j['source']}\n"
            result += f"  🔗 {j['url']}\n"
        return result

    def _format_jobs(self, jobs: list, source: str) -> str:
        """Format scraped jobs into readable output."""
        if not jobs:
            return f"No relevant {source} jobs found."
        if isinstance(jobs[0], dict) and "error" in jobs[0]:
            return f"⚠️ Scraping error: {jobs[0].get('error', 'Unknown error')}"

        result = f"🔍 **Found {len(jobs)} relevant internships from {source}:**\n\n"
        for i, job in enumerate(jobs[:8], 1):
            result += f"{i}. **{job['title']}** at {job['company']}\n"
            result += f"   📍 {job.get('location', 'Remote')} | ⭐ Match: {job['match_score']}/10\n"
            result += f"   🔗 {job['url']}\n\n"

        # Add auto-assessment for top picks
        if len(jobs) >= 3:
            result += "\n---\n"
            result += self.auto_apply_assessment(jobs)

        return result

    # ─── Handle ───────────────────────────────────────────────────────────────

    def handle(self, task: str) -> str:
        t = task.lower()

        # Job search
        if any(kw in t for kw in ["internshala", "search", "find", "scrape"]) and \
           not "cover letter" in t and not "dashboard" in t:
            keywords = "machine-learning"
            if "python" in t:
                keywords = "python"
            elif "llm" in t or "langchain" in t:
                keywords = "artificial-intelligence"
            elif "data" in t:
                keywords = "data-science"

            if "wellfound" in t:
                jobs = self.scrape_wellfound(keywords.replace("-", " "))
                return self._format_jobs(jobs, "Wellfound")

            jobs = self.scrape_internshala(keywords)
            return self._format_jobs(jobs, "Internshala")

        elif "cover letter" in t:
            # Use LLM-powered intent extraction for natural language
            params = self.extract_intent(task, {
                "title": "string, the job title or role",
                "company": "string, the company name",
                "description": "string or null, any job description details mentioned"
            })
            title = params.get("title") or "AI/ML Intern"
            company = params.get("company") or "the company"
            desc = params.get("description") or ""
            return self.generate_cover_letter(title, company, desc)

        elif any(kw in t for kw in ["dashboard", "stats", "tracker"]):
            return self.get_dashboard()

        elif any(kw in t for kw in ["applied", "mark applied"]):
            parts = task.split(",")
            url = parts[-1].strip() if parts else ""
            if url:
                update_status(url, "applied")
                return f"✅ Marked as applied: {url}"
            return "Please provide the job URL to mark as applied."

        elif any(kw in t for kw in ["all jobs", "show jobs", "list jobs"]):
            jobs = get_all_jobs()
            if not jobs:
                return "No jobs tracked yet. Try: 'find AI ML internships on Internshala'"
            result = f"📋 All Tracked Jobs ({len(jobs)}):\n\n"
            for j in jobs[:10]:
                result += f"• **{j['title']}** — {j['company']} | {j['status'].upper()} | Score: {j['match_score']}/10\n"
            return result

        else:
            return self.run(task)