"""
Briefing Agent — Daily morning briefing with real data.
Aggregates tasks, projects, jobs, news, and GitHub activity.
Uses DuckDuckGo as news fallback when RSS fails.
"""

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

    TOOLS = [
        {
            "name": "generate_briefing",
            "description": "Generate the full morning briefing with all stats, news, priorities. Use for 'morning briefing', 'good morning', 'daily briefing', 'generate briefing'.",
            "args": {}
        },
        {
            "name": "quick_status",
            "description": "Get a quick status snapshot of tasks, jobs, projects. Use for 'quick status', 'what's my status', 'summary'.",
            "args": {}
        },
        {
            "name": "get_ai_news",
            "description": "Get latest AI/ML news headlines. Use for 'ai news', 'ml news', 'what's happening in AI'.",
            "args": {}
        },
        {
            "name": "track_news_engagement",
            "description": "Track what news topics Aaqil reads to personalize future briefings. Use for 'I liked the article about X', 'track news'.",
            "args": {"topic": "str"}
        }
    ]

    def __init__(self):
        super().__init__(
            name="briefing",
            system_prompt="""You are Aaqil's Daily Briefing Agent — like J.A.R.V.I.S. giving Tony's morning update.
Every morning you give a crisp, motivating briefing about what matters today.
Be direct, actionable, and energizing. Like a smart personal assistant.
Format everything cleanly. Prioritize ruthlessly."""
        )

    def track_news_engagement(self, topic: str) -> str:
        self.remember(f"news_pref_{hash(topic)}", f"Aaqil is interested in news about: {topic}", {"type": "news_preference"})
        return f"✅ Noted your interest in '{topic}'. Future briefings will include more of this."

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
            except Exception:
                continue

        if len(news) < 3:
            try:
                prefs = self.recall("news preference interested topics")
                query = "AI ML LLM agents 2025"
                if prefs:
                    pref_str = " ".join([p.split(":")[-1].strip() for p in prefs])
                    query = f"AI ML {pref_str} 2025"
                
                from utils.web_search import search_news
                ddg_news = search_news(query, max_results=4)
                for n in ddg_news:
                    news.append({
                        "title": n.get("title", ""),
                        "summary": n.get("snippet", "")[:200],
                        "link": n.get("url", ""),
                        "source": "DuckDuckGo News"
                    })
            except Exception:
                pass

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
                repo = e.get("repo", {}).get("name", "").replace("FarhanAaqil/", "")
                if etype == "PushEvent":
                    commits = len(e.get("payload", {}).get("commits", []))
                    activity.append(f"Pushed {commits} commit(s) to {repo}")
                elif etype == "CreateEvent":
                    activity.append(f"Created {e['payload'].get('ref_type', '')} in {repo}")
            return "\n".join(activity) if activity else "No recent activity"
        except Exception:
            return "GitHub activity unavailable"

    def generate_briefing(self) -> str:
        now = datetime.now()
        day_name = now.strftime("%A")
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")

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

        briefing_data = f"""
Date: {day_name}, {date_str} | Time: {time_str}

TASKS:
- High priority: {len(high_tasks)} pending
- Top 3: {chr(10).join([f"  [{t['project_name']}] {t['title']}" for t in high_tasks[:3]])}

PROJECTS:
{chr(10).join([f"- {p['name']}: {p['progress']}% | Deadline: {p['deadline'] or 'None'}" for p in projects[:5]])}

JOBS:
- New matches: {len(jobs)}
- Total applied: {job_stats.get('applied', 0)}
- Interviews: {job_stats.get('interview', 0)}

RESEARCH:
- Active submissions: {len(active_papers)}
{chr(10).join([f"  - {p['title'][:50]}: {p['status']}" for p in active_papers])}

GOALS:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} ({g['period']})" for g in goals[:3]])}

EMAILS: {pending_emails} drafts pending

GITHUB:
{github}

AI/ML NEWS:
{chr(10).join([f"- {n['title']} ({n['source']})" for n in news[:4]])}
"""

        task = f"""Generate Aaqil's morning briefing from this data:
{briefing_data}

Format:
🌅 GOOD MORNING AAQIL — {day_name}, {date_str}

⚡ TODAY'S PRIORITY (top 3 tasks, ranked by impact)

📋 QUICK STATUS (jobs, projects, research in 3 bullet points)

🔥 AI/ML NEWS (top 2 headlines worth reading, with 1-line summary)

💡 ONE INSIGHT (one motivating or useful thought)

🎯 DAILY GOAL (one clear measurable thing to achieve today)

Under 300 words. Energizing. No fluff."""

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

    def get_ai_news(self) -> str:
        news = self._get_ai_news()
        if not news:
            return "❌ No AI/ML news available right now."
        result = "📰 **Latest AI/ML News:**\n\n"
        for n in news:
            result += f"• **{n['title']}**\n"
            result += f"  {n['source']} | {n['summary'][:150]}...\n"
            result += f"  🔗 {n['link']}\n\n"
        return result

    def handle(self, task: str) -> str:
        return self.think_and_act(task)