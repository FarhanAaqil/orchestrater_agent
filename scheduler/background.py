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
            jobs = job_agent.scrape_internshala("machine-learning", limit=10)
            if jobs and "error" not in jobs[0]:
                add_notification(
                    f"🔍 Found {len(jobs)} new internships on Internshala", "jobs"
                )
            # Also search AI specifically
            ai_jobs = job_agent.scrape_internshala("artificial-intelligence", limit=10)
            if ai_jobs and "error" not in ai_jobs[0]:
                add_notification(
                    f"🔍 Found {len(ai_jobs)} AI internships", "jobs"
                )
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

    scheduler.start()
    add_notification("✅ Aaqil background scheduler started", "system")