from agents.base_agent import BaseAgent
from database.tracker import (
    get_tasks, get_projects, get_all_jobs,
    get_papers, get_emails, get_goals, get_stats
)
import feedparser
import requests
from datetime import datetime

AI_RSS_FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://bair.berkeley.edu/blog/feed.xml",
    "https://openai.com/blog/rss/",
    "https://blogs.microsoft.com/ai/feed/",
]

class BriefingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="briefing",
            system_prompt="""You are Aaqil's Daily Briefing Agent.
Every morning you give a crisp, motivating briefing about what matters today.
Be direct, actionable, and energizing. Like a smart personal assistant.
Format everything cleanly. Prioritize ruthlessly."""
        )

    def _get_ai_news(self) -> list:
        news = []
        for feed_url in AI_RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:2]:
                    news.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:200],
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", "Unknown")
                    })
            except:
                continue
        return news[:6]

    def _get_github_activity(self) -> str:
        try:
            resp = requests.get(
                "https://api.github.com/users/FarhanAaqil/events/public",
                timeout=10
            )
            events = resp.json()[:5]
            activity = []
            for e in events:
                etype = e.get("type", "")
                repo = e.get("repo", {}).get("name", "")
                if etype == "PushEvent":
                    commits = len(e.get("payload", {}).get("commits", []))
                    activity.append(f"Pushed {commits} commit(s) to {repo}")
                elif etype == "CreateEvent":
                    activity.append(f"Created {e['payload'].get('ref_type','')} in {repo}")
                elif etype == "IssuesEvent":
                    activity.append(f"Issue {e['payload'].get('action','')} in {repo}")
            return "\n".join(activity) if activity else "No recent activity"
        except:
            return "GitHub activity unavailable"

    def generate_briefing(self) -> str:
        now = datetime.now()
        day_name = now.strftime("%A")
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")

        # Gather all data
        tasks = get_tasks(status="todo")
        projects = get_projects(status="active")
        jobs = get_all_jobs(status="found")
        papers = get_papers()
        emails = get_emails(status="draft")
        goals = get_goals()
        job_stats = get_stats()
        news = self._get_ai_news()
        github = self._get_github_activity()

        high_tasks = [t for t in tasks if t["priority"] == "high"]
        active_papers = [p for p in papers if p["status"] in ["submitted", "revision", "review"]]
        pending_emails = len(emails)

        # Build briefing data for LLM
        briefing_data = f"""
Date: {day_name}, {date_str} | Time: {time_str}

TASKS:
- High priority: {len(high_tasks)} pending
- Top 3: {chr(10).join([f"  [{t['project_name']}] {t['title']}" for t in high_tasks[:3]])}

PROJECTS:
{chr(10).join([f"- {p['name']}: {p['progress']}% | Deadline: {p['deadline'] or 'None'}" for p in projects[:5]])}

JOBS:
- New matches found: {len(jobs)}
- Total applied: {job_stats.get('applied', 0)}
- Interviews: {job_stats.get('interview', 0)}

RESEARCH:
- Active submissions: {len(active_papers)}
{chr(10).join([f"  - {p['title'][:50]}: {p['status']}" for p in active_papers])}

GOALS:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} ({g['period']})" for g in goals[:3]])}

EMAILS:
- Drafts pending to send: {pending_emails}

GITHUB ACTIVITY:
{github}

AI/ML NEWS:
{chr(10).join([f"- {n['title']} ({n['source']})" for n in news[:4]])}
"""

        task = f"""Generate Aaqil's morning briefing from this data:
{briefing_data}

Format:
🌅 GOOD MORNING AAQIL — {day_name}, {date_str}

⚡ TODAY'S PRIORITY (top 3 things to do today, ranked)

📋 QUICK STATUS (jobs, projects, research in 3 bullet points)

🔥 AI/ML NEWS (top 2 headlines worth reading)

💡 ONE INSIGHT (one motivating or useful thought for the day)

🎯 DAILY GOAL (one clear measurable thing to achieve today)

Keep it under 300 words. Energizing. No fluff."""

        return self.run(task)

    def quick_status(self) -> str:
        tasks = get_tasks(status="todo")
        jobs = get_stats()
        projects = get_projects(status="active")
        papers = get_papers()

        high = len([t for t in tasks if t["priority"] == "high"])
        submitted_papers = len([p for p in papers if p["status"] == "submitted"])

        return f"""⚡ **Quick Status:**
📋 Tasks: {len(tasks)} pending ({high} high priority)
💼 Jobs applied: {jobs.get('applied', 0)} | Interviews: {jobs.get('interview', 0)}
📁 Active projects: {len(projects)}
📚 Papers submitted: {submitted_papers}
🔍 New job matches: {jobs.get('found', 0)}"""

    def handle(self, task: str) -> str:
        t = task.lower()

        if "briefing" in t or "morning" in t or "good morning" in t:
            return self.generate_briefing()
        elif "quick status" in t or "status" in t:
            return self.quick_status()
        elif "news" in t or "ai news" in t:
            news = self._get_ai_news()
            result = "📰 **Latest AI/ML News:**\n\n"
            for n in news:
                result += f"• **{n['title']}**\n"
                result += f"  {n['source']} | {n['summary'][:150]}...\n"
                result += f"  🔗 {n['link']}\n\n"
            return result
        elif "github activity" in t:
            return f"🐙 **GitHub Activity:**\n\n{self._get_github_activity()}"
        else:
            return self.run(task)