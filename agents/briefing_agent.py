"""
briefing_agent.py — Proactive daily intelligence and momentum tracking.

Upgrades over original:
- Personalized insights from pattern analysis (coding streaks, application momentum)
- Priority prediction based on deadlines and past behavior
- weekly_review() for Sunday reflection reports
- Momentum tracking: streaks for coding, applications, research
- handle() uses intent extraction for natural language
"""
from __future__ import annotations
from agents.base_agent import BaseAgent
from database.tracker import (
    get_tasks, get_projects, get_all_jobs,
    get_papers, get_emails, get_goals, get_stats
)
from memory.chroma_store import retrieve_with_metadata, get_recent
import feedparser
import requests
from datetime import datetime, timedelta

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
            system_prompt="""You are Aaqil's Daily Intelligence Agent.
Every morning you give a crisp, motivating briefing about what matters today.
Be direct, actionable, and energizing. Like a smart personal chief of staff.
Format everything cleanly. Prioritize ruthlessly. Spot patterns and call them out.
If something has been pending for too long, say so diplomatically."""
        )

    # ─── Data Fetchers ────────────────────────────────────────────────────────

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
        return news[:6]

    def _get_github_activity(self) -> dict:
        """Fetch GitHub activity and return structured data for momentum tracking."""
        try:
            resp = requests.get(
                "https://api.github.com/users/FarhanAaqil/events/public",
                timeout=10
            )
            events = resp.json()[:10]
            activity = []
            commit_days = set()
            for e in events:
                etype = e.get("type", "")
                repo = e.get("repo", {}).get("name", "")
                created = e.get("created_at", "")[:10]
                if etype == "PushEvent":
                    commits = len(e.get("payload", {}).get("commits", []))
                    activity.append(f"Pushed {commits} commit(s) to {repo}")
                    commit_days.add(created)
                elif etype == "CreateEvent":
                    activity.append(f"Created {e['payload'].get('ref_type', '')} in {repo}")
                elif etype == "IssuesEvent":
                    activity.append(f"Issue {e['payload'].get('action', '')} in {repo}")

            # Calculate streak
            today = datetime.now().date()
            streak = 0
            for i in range(7):
                day = str(today - timedelta(days=i))
                if day in commit_days:
                    streak += 1
                elif i > 0:
                    break

            return {
                "activity": "\n".join(activity) if activity else "No recent activity",
                "commit_streak": streak,
                "last_commit_days_ago": (today - datetime.strptime(max(commit_days), "%Y-%m-%d").date()).days
                if commit_days else 999
            }
        except Exception:
            return {"activity": "GitHub activity unavailable", "commit_streak": 0,
                    "last_commit_days_ago": 0}

    def _get_momentum_insights(self) -> str:
        """Analyze patterns and generate personalized momentum insights."""
        stats = get_stats()
        tasks = get_tasks(status="todo")
        jobs = get_all_jobs()

        insights = []

        # Application momentum
        applied_today = len([j for j in jobs if j.get("applied_at", "")[:10] == datetime.now().strftime("%Y-%m-%d")])
        if applied_today == 0 and len([j for j in jobs if j["status"] == "found"]) > 3:
            insights.append("⚡ You have new job matches but haven't applied yet today")

        # High-priority task overdue
        high_tasks = [t for t in tasks if t["priority"] == "high"]
        old_high_tasks = [t for t in high_tasks
                          if t.get("deadline") and t["deadline"] < datetime.now().isoformat()]
        if old_high_tasks:
            insights.append(f"⏰ {len(old_high_tasks)} HIGH priority task(s) are overdue")

        # Application velocity
        total_applied = stats.get("applied", 0)
        interviews = stats.get("interview", 0)
        if total_applied > 5 and interviews == 0:
            insights.append("📊 Applied to many roles but 0 interviews — consider targeting different companies or refining your approach")
        elif total_applied > 0 and interviews > 0:
            rate = round(interviews / total_applied * 100)
            if rate > 20:
                insights.append(f"🔥 {rate}% interview rate — your applications are landing well!")

        return "\n".join(insights) if insights else ""

    # ─── Briefing Generators ──────────────────────────────────────────────────

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
        momentum = self._get_momentum_insights()

        high_tasks = [t for t in tasks if t["priority"] == "high"]
        active_papers = [p for p in papers if p["status"] in ["submitted", "revision", "review"]]

        # Streak messaging
        streak = github.get("commit_streak", 0)
        streak_msg = f"🔥 {streak}-day coding streak!" if streak >= 2 else \
                     ("⚠️ No commits today yet" if github.get("last_commit_days_ago", 0) >= 1 else "")

        briefing_data = f"""
Date: {day_name}, {date_str} | Time: {time_str}

TASKS:
- High priority: {len(high_tasks)} pending
- Top 3: {chr(10).join([f"  [{t['project_name']}] {t['title']}" for t in high_tasks[:3]])}

PROJECTS:
{chr(10).join([f"- {p['name']}: {p['progress']}% | Deadline: {p['deadline'] or 'None'}" for p in projects[:5]])}

JOBS:
- New matches not applied: {len(jobs)}
- Total applied: {job_stats.get('applied', 0)}
- Interviews: {job_stats.get('interview', 0)}

RESEARCH:
- Active submissions: {len(active_papers)}
{chr(10).join([f"  - {p['title'][:50]}: {p['status']}" for p in active_papers])}

GOALS:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} ({g['period']})" for g in goals[:3]])}

EMAILS PENDING: {len(emails)} drafts to send

GITHUB:
{github['activity']}
{streak_msg}

MOMENTUM ALERTS:
{momentum if momentum else "No alerts — you're on track!"}

AI/ML NEWS:
{chr(10).join([f"- {n['title']} ({n['source']})" for n in news[:4]])}
"""

        task = f"""Generate Aaqil's morning briefing from this data:
{briefing_data}

Format:
🌅 GOOD MORNING AAQIL — {day_name}, {date_str}

⚡ TODAY'S PRIORITY (top 3 things, ranked by urgency + impact)

📋 QUICK STATUS (jobs, projects, research — 3 bullets max)

🔥 AI/ML NEWS (top 2 headlines worth 2 minutes of reading)

💡 ONE INSIGHT (a pattern you noticed or a motivating truth)

🎯 DAILY GOAL (one specific, measurable thing to achieve today)

{f"🔥 MOMENTUM: {streak_msg}" if streak_msg else ""}

Keep it under 350 words. Energizing. Call out problems directly — don't sugarcoat."""

        return self.run(task)

    def quick_status(self) -> str:
        tasks = get_tasks(status="todo")
        jobs = get_stats()
        projects = get_projects(status="active")
        papers = get_papers()

        high = len([t for t in tasks if t["priority"] == "high"])
        submitted_papers = len([p for p in papers if p["status"] == "submitted"])
        github = self._get_github_activity()
        streak = github.get("commit_streak", 0)

        return f"""⚡ **Quick Status:**
📋 Tasks: {len(tasks)} pending ({high} high priority)
💼 Jobs applied: {jobs.get('applied', 0)} | Interviews: {jobs.get('interview', 0)}
📁 Active projects: {len(projects)}
📚 Papers submitted: {submitted_papers}
🔍 New job matches: {jobs.get('found', 0)}
{'🔥 Coding streak: ' + str(streak) + ' day(s)' if streak > 0 else '⚠️ No commits today'}"""

    def weekly_review(self) -> str:
        """Sunday reflection report — progress, patterns, next week focus."""
        tasks = get_tasks()
        done_tasks = [t for t in tasks if t.get("status") == "done"]
        jobs = get_stats()
        projects = get_projects(status="active")
        papers = get_papers()

        # Retrieve recent memory for patterns
        recent_traces = get_recent("briefing_traces", days=7, limit=5)

        data = f"""WEEK SUMMARY:
Tasks completed this week: {len(done_tasks)}
Jobs applied: {jobs.get('applied', 0)} total | Interviews: {jobs.get('interview', 0)}
Active projects: {len(projects)}
Research papers: {len(papers)}

Recent activity notes:
{chr(10).join([r['doc'][:100] for r in recent_traces]) if recent_traces else 'No traces found'}"""

        task = f"""Generate Aaqil's weekly reflection for the week ending {datetime.now().strftime('%B %d, %Y')}:

{data}

Format:
📊 WEEK IN REVIEW — {datetime.now().strftime('%B %d, %Y')}

✅ WINS (what went well)
⚠️ GAPS (what didn't happen)
📈 TREND (what pattern do you see)
🎯 NEXT WEEK FOCUS (top 3 priorities)
💬 ONE HONEST OBSERVATION (something Aaqil needs to hear)

Keep it honest and specific. Under 300 words."""
        return self.run(task)

    # ─── Handle ───────────────────────────────────────────────────────────────

    def handle(self, task: str) -> str:
        t = task.lower()

        if any(kw in t for kw in ["briefing", "morning", "good morning"]):
            return self.generate_briefing()
        elif any(kw in t for kw in ["quick status", "status", "how am i doing"]):
            return self.quick_status()
        elif any(kw in t for kw in ["weekly review", "week review", "sunday review"]):
            return self.weekly_review()
        elif any(kw in t for kw in ["news", "ai news"]):
            news = self._get_ai_news()
            result = "📰 **Latest AI/ML News:**\n\n"
            for n in news:
                result += f"• **{n['title']}**\n"
                result += f"  {n['source']} | {n['summary'][:150]}...\n"
                result += f"  🔗 {n['link']}\n\n"
            return result
        elif "github activity" in t or "coding streak" in t:
            gh = self._get_github_activity()
            streak = gh.get("commit_streak", 0)
            streak_str = f"🔥 Current coding streak: **{streak} day(s)**\n\n" if streak > 0 \
                         else "⚠️ No recent commits detected.\n\n"
            return f"🐙 **GitHub Activity:**\n\n{streak_str}{gh['activity']}"
        elif "momentum" in t or "patterns" in t or "insights" in t:
            insights = self._get_momentum_insights()
            return f"🎯 **Momentum Insights:**\n\n{insights or '✅ All good — no alerts!'}"
        else:
            return self.run(task)