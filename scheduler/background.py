from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database.tracker import get_all_jobs, get_tasks
from memory.chroma_store import store_memory
from utils.web_search import search_news
import streamlit as st
from datetime import datetime
import json

scheduler = BackgroundScheduler()
_agent_map = {}
_pipeline = None
_notifications = []

def set_agents(agent_map, pipeline):
    global _agent_map, _pipeline
    _agent_map = agent_map
    _pipeline = pipeline

def add_notification(message: str, type: str = "info"):
    _notifications.append({
        "message": message,
        "type": type,
        "time": datetime.now().strftime("%H:%M"),
        "read": False
    })
    # Keep last 50
    if len(_notifications) > 50:
        _notifications.pop(0)

def get_notifications() -> list:
    return _notifications

def mark_all_read():
    for n in _notifications:
        n["read"] = True

# ─── Scheduled Jobs ───────────────────────────────────────────────

def job_morning_briefing():
    try:
        briefing = _agent_map.get("briefing")
        if briefing:
            result = briefing.generate_briefing()
            store_memory("scheduler", f"briefing_{datetime.now().date()}", result)
            add_notification("🌅 Morning briefing ready", "briefing")
    except Exception as e:
        add_notification(f"⚠️ Briefing failed: {str(e)}", "error")

def job_daily_job_search():
    try:
        job_agent = _agent_map.get("job")
        if job_agent:
            result = job_agent.search_all("machine learning intern remote", limit=10)
            if "Found" in result or "Jobs Found" in result:
                add_notification(
                    "🔍 Daily job search complete — new matches found!", "jobs"
                )
            # Also search AI agents specifically
            ai_result = job_agent.search_all("LLM AI agent python intern", limit=8)
            if "Found" in ai_result or "Jobs Found" in ai_result:
                add_notification("🔍 New AI/LLM agent internships found", "jobs")
    except Exception as e:
        add_notification(f"⚠️ Job search failed: {str(e)}", "error")


def job_github_activity():
    try:
        github = _agent_map.get("github")
        if github:
            summary = github.profile_summary()
            store_memory("scheduler", f"github_{datetime.now().date()}", summary)
            add_notification("🐙 GitHub activity checked", "github")
    except Exception as e:
        add_notification(f"⚠️ GitHub check failed: {str(e)}", "error")

def job_ai_news():
    try:
        news = search_news("AI ML LLM agents research 2026", max_results=5)
        if news:
            headlines = "\n".join([f"- {n['title']}" for n in news[:3]])
            store_memory("scheduler", f"news_{datetime.now().date()}", headlines)
            add_notification("📰 AI/ML news updated", "news")
    except Exception as e:
        add_notification(f"⚠️ News fetch failed: {str(e)}", "error")

def job_weekly_reflection():
    try:
        career = _agent_map.get("career")
        pm = _agent_map.get("project_manager")
        if career and pm:
            report = pm.weekly_report()
            store_memory("scheduler", f"weekly_{datetime.now().date()}", report)
            add_notification("📊 Weekly reflection generated", "reflection")
    except Exception as e:
        add_notification(f"⚠️ Weekly reflection failed: {str(e)}", "error")

def job_high_priority_reminder():
    try:
        tasks = get_tasks(status="todo")
        high = [t for t in tasks if t["priority"] == "high"]
        if high:
            add_notification(
                f"🔴 You have {len(high)} high priority tasks pending", "reminder"
            )
    except Exception as e:
        pass

def job_memory_consolidation():
    """Consolidate and summarize old memories."""
    try:
        from memory.chroma_store import get_collection, store_memory
        from config import MODEL, GROQ_API_KEY
        from groq import Groq
        
        # Only consolidating agent short term summaries for now
        for agent in _agent_map.keys():
            col = get_collection(agent)
            count = col.count()
            if count > 20: # If getting cluttered
                client = Groq(api_key=GROQ_API_KEY)
                docs = col.get(limit=10, include=["documents"])
                if docs and docs["documents"]:
                    text = "\n".join(docs["documents"])
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "user", "content": f"Summarize these past learnings and interactions into 3-5 core principles/facts:\n{text}"}]
                    )
                    summary = resp.choices[0].message.content
                    store_memory(agent, f"consolidation_{datetime.now().date()}", summary, {"type": "consolidated"})
                    add_notification(f"🧹 Memory consolidated for {agent}", "system")
    except Exception as e:
        print(f"Memory consolidation failed: {e}")

# ─── Start Scheduler ──────────────────────────────────────────────

def start_scheduler(agent_map, pipeline):
    set_agents(agent_map, pipeline)

    if scheduler.running:
        return

    # 8 AM — Morning briefing
    scheduler.add_job(job_morning_briefing, CronTrigger(hour=8, minute=0),
                      id="morning_briefing", replace_existing=True)

    # 10 AM — Daily job search
    scheduler.add_job(job_daily_job_search, CronTrigger(hour=10, minute=0),
                      id="job_search", replace_existing=True)

    # 6 PM — GitHub activity check
    scheduler.add_job(job_github_activity, CronTrigger(hour=18, minute=0),
                      id="github_check", replace_existing=True)

    # Every 4 hours — AI news
    scheduler.add_job(job_ai_news, CronTrigger(hour="*/4"),
                      id="ai_news", replace_existing=True)

    # Sunday 9 PM — Weekly reflection
    scheduler.add_job(job_weekly_reflection,
                      CronTrigger(day_of_week="sun", hour=21, minute=0),
                      id="weekly_reflection", replace_existing=True)

    # 9 AM + 3 PM — High priority reminders
    scheduler.add_job(job_high_priority_reminder,
                      CronTrigger(hour="9,15", minute=0),
                      id="priority_reminder", replace_existing=True)

    # Sunday 2 AM — Memory Consolidation
    scheduler.add_job(job_memory_consolidation,
                      CronTrigger(day_of_week="sun", hour=2, minute=0),
                      id="memory_consolidation", replace_existing=True)

    scheduler.start()
    add_notification("✅ Aaqil background scheduler started", "system")