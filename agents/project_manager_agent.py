from agents.base_agent import BaseAgent
from database.tracker import (
    add_project, get_projects, update_project_progress,
    add_task, get_tasks, complete_task,
    add_goal, update_goal, get_goals
)
from datetime import datetime

class ProjectManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="project_manager",
            system_prompt="""You are Aaqil's Project Manager Agent.
You track projects, tasks, deadlines, and weekly goals.
Aaqil's current projects: Aaqil (9-agent AI system), Self-Improving Code Agent,
SheetSense AI, IntelliGlove, InterviewPro, DiaPredict AI.
Be concise, actionable, and priority-focused."""
        )

    def weekly_report(self) -> str:
        projects = get_projects()
        tasks = get_tasks()
        goals = get_goals()

        done_tasks = [t for t in tasks if t["status"] == "done"]
        todo_tasks = [t for t in tasks if t["status"] == "todo"]
        high_priority = [t for t in todo_tasks if t["priority"] == "high"]

        report_data = f"""
Projects: {len(projects)} total
Active: {len([p for p in projects if p['status'] == 'active'])}
Completed tasks this context: {len(done_tasks)}
Pending tasks: {len(todo_tasks)}
High priority pending: {len(high_priority)}

Projects:
{chr(10).join([f"- {p['name']}: {p['progress']}% | Deadline: {p['deadline'] or 'None'}" for p in projects])}

Goals:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} ({g['period']})" for g in goals])}

High Priority Tasks:
{chr(10).join([f"- [{t['project_name']}] {t['title']} | Due: {t['deadline'] or 'No deadline'}" for t in high_priority[:5]])}
"""
        task = f"Generate a professional weekly progress report from this data:\n{report_data}"
        return self.run(task)

    def plan_sprint(self, duration_days: int = 7) -> str:
        tasks = get_tasks(status="todo")
        projects = get_projects(status="active")

        task = f"""Plan a {duration_days}-day sprint for Aaqil:

Active Projects:
{chr(10).join([f"- {p['name']}: {p['progress']}% done" for p in projects])}

Pending Tasks:
{chr(10).join([f"- [{t['priority'].upper()}] [{t['project_name']}] {t['title']}" for t in tasks[:15]])}

Create a day-by-day plan prioritizing high-priority tasks. Be realistic about time."""
        return self.run(task)

    def suggest_next(self) -> str:
        tasks = get_tasks(status="todo")
        high = [t for t in tasks if t["priority"] == "high"]
        medium = [t for t in tasks if t["priority"] == "medium"]
        top = (high + medium)[:5]

        if not top:
            return "No pending tasks. Add some tasks first!"

        task = f"""What should Aaqil work on right now?
Top pending tasks:
{chr(10).join([f"- [{t['priority'].upper()}] [{t['project_name']}] {t['title']}" for t in top])}

Give a clear recommendation with reasoning. Max 3 sentences."""
        return self.run(task)

    def format_projects(self) -> str:
        projects = get_projects()
        if not projects:
            return "No projects tracked yet. Add one with: 'add project <name>'"
        result = "📁 **All Projects:**\n\n"
        for p in projects:
            bar = "█" * (p["progress"] // 10) + "░" * (10 - p["progress"] // 10)
            result += f"**{p['name']}**\n"
            result += f"  [{bar}] {p['progress']}%\n"
            result += f"  Status: {p['status']} | Deadline: {p['deadline'] or 'None'}\n"
            if p["github_url"]: result += f"  GitHub: {p['github_url']}\n"
            if p["deployed_url"]: result += f"  Live: {p['deployed_url']}\n"
            result += "\n"
        return result

    def format_tasks(self, project=None) -> str:
        tasks = get_tasks(project_name=project)
        if not tasks:
            return "No tasks found."
        todo = [t for t in tasks if t["status"] == "todo"]
        done = [t for t in tasks if t["status"] == "done"]

        result = f"📋 **Tasks** {'for ' + project if project else '(All)'}:\n\n"
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        if todo:
            result += "**Pending:**\n"
            for t in todo:
                emoji = priority_emoji.get(t["priority"], "⚪")
                result += f"{emoji} [{t['id']}] {t['title']}"
                result += f" | [{t['project_name']}]" if not project else ""
                result += f" | Due: {t['deadline']}" if t["deadline"] else ""
                result += "\n"

        if done:
            result += f"\n✅ **Done ({len(done)}):**\n"
            for t in done[:5]:
                result += f"  ✓ {t['title']}\n"
        return result

    def format_goals(self) -> str:
        goals = get_goals()
        if not goals:
            return "No goals set. Add one with: 'add goal <title>, <target>, <period>'"
        result = "🎯 **Goals:**\n\n"
        for g in goals:
            pct = int((g["current"] / g["target"]) * 100) if g["target"] > 0 else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            result += f"**{g['title']}**\n"
            result += f"  [{bar}] {g['current']}/{g['target']} ({pct}%) — {g['period']}\n\n"
        return result

    def handle(self, task: str) -> str:
        t = task.lower()

        # Add project
        if "add project" in t:
            parts = task.replace("add project", "").strip().split(",")
            name = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            deadline = parts[2].strip() if len(parts) > 2 else ""
            github = parts[3].strip() if len(parts) > 3 else ""
            deployed = parts[4].strip() if len(parts) > 4 else ""
            add_project(name, desc, deadline, github, deployed)
            return f"✅ Project **{name}** added!"

        # Update progress
        elif "update progress" in t or "set progress" in t:
            parts = task.split(",")
            name = parts[0].replace("update progress", "").replace("set progress", "").strip()
            progress = int(''.join(filter(str.isdigit, parts[1]))) if len(parts) > 1 else 0
            status = parts[2].strip() if len(parts) > 2 else None
            update_project_progress(name, progress, status)
            return f"✅ **{name}** updated to {progress}%"

        # Add task
        elif "add task" in t:
            parts = task.replace("add task", "").strip().split(",")
            project = parts[0].strip() if len(parts) > 0 else "General"
            title = parts[1].strip() if len(parts) > 1 else task
            priority = parts[2].strip() if len(parts) > 2 else "medium"
            deadline = parts[3].strip() if len(parts) > 3 else ""
            add_task(project, title, priority, deadline)
            return f"✅ Task added to **{project}**: {title}"

        # Complete task
        elif "complete task" in t or "done task" in t or "finish task" in t:
            task_id = int(''.join(filter(str.isdigit, task)))
            complete_task(task_id)
            return f"✅ Task {task_id} marked as done!"

        # Add goal
        elif "add goal" in t:
            parts = task.replace("add goal", "").strip().split(",")
            title = parts[0].strip()
            target = int(''.join(filter(str.isdigit, parts[1]))) if len(parts) > 1 else 10
            period = parts[2].strip() if len(parts) > 2 else "weekly"
            add_goal(title, target, period)
            return f"🎯 Goal added: **{title}** — {target} ({period})"

        # Update goal
        elif "update goal" in t:
            parts = task.split(",")
            goal_id = int(''.join(filter(str.isdigit, parts[0])))
            current = int(''.join(filter(str.isdigit, parts[1]))) if len(parts) > 1 else 0
            update_goal(goal_id, current)
            return f"✅ Goal {goal_id} updated!"

        # Show views
        elif "show projects" in t or "all projects" in t or "projects" in t:
            return self.format_projects()
        elif "show tasks" in t or "all tasks" in t or "tasks" in t:
            project = task.split("for")[-1].strip() if "for" in t else None
            return self.format_tasks(project)
        elif "goals" in t:
            return self.format_goals()
        elif "weekly report" in t or "report" in t:
            return self.weekly_report()
        elif "sprint" in t or "plan week" in t:
            days = 7
            nums = [int(s) for s in task.split() if s.isdigit()]
            if nums: days = nums[0]
            return self.plan_sprint(days)
        elif "what should" in t or "next task" in t or "what to do" in t:
            return self.suggest_next()

        else:
            return self.run(task)