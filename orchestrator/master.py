from orchestrator.router import route_task
from orchestrator.pipeline import Pipeline
from memory.chroma_store import store_memory
from agents.github_agent import GitHubAgent
from agents.linkedin_agent import LinkedInAgent
from agents.job_agent import JobAgent
from agents.project_manager_agent import ProjectManagerAgent
from agents.career_agent import CareerAgent
from agents.growth_agent import GrowthAgent
from agents.research_agent import ResearchAgent
from agents.email_agent import EmailAgent
from agents.briefing_agent import BriefingAgent
from agents.critic_agent import CriticAgent
from scheduler.background import start_scheduler

# Init all agents
github_agent = GitHubAgent()
linkedin_agent = LinkedInAgent()
job_agent = JobAgent()
pm_agent = ProjectManagerAgent()
career_agent = CareerAgent()
growth_agent = GrowthAgent()
research_agent = ResearchAgent()
email_agent = EmailAgent()
briefing_agent = BriefingAgent()
critic_agent = CriticAgent()

AGENT_MAP = {
    "github": github_agent,
    "linkedin": linkedin_agent,
    "job": job_agent,
    "project_manager": pm_agent,
    "career": career_agent,
    "growth": growth_agent,
    "research": research_agent,
    "email": email_agent,
    "briefing": briefing_agent,
}

# Pipeline engine
pipeline = Pipeline(AGENT_MAP, critic_agent)

# Start background scheduler
start_scheduler(AGENT_MAP, pipeline)

def handle(user_input: str) -> dict:
    u = user_input.lower()
    store_memory("orchestrator", f"task_{hash(user_input)}",
                 user_input, {"timestamp": __import__("datetime").datetime.now().isoformat()})

    # Pipeline triggers
    if "apply pipeline" in u or "apply to" in u and "pipeline" in u:
        parts = user_input.split(",")
        company = parts[0].replace("apply pipeline", "").replace("apply to", "").strip()
        role = parts[1].strip() if len(parts) > 1 else "AI/ML Intern"
        jd = parts[2].strip() if len(parts) > 2 else ""
        email = parts[3].strip() if len(parts) > 3 else ""
        result = pipeline.run_apply_pipeline(company, role, jd, email)
        return {"agent": "pipeline", "task": user_input, "response": result}

    if "publish pipeline" in u or "content pipeline" in u:
        parts = user_input.split(",")
        project = parts[0].replace("publish pipeline", "").replace("content pipeline", "").strip()
        details = parts[1].strip() if len(parts) > 1 else ""
        result = pipeline.run_publish_pipeline(project, details)
        return {"agent": "pipeline", "task": user_input, "response": result}

    if "research pipeline" in u:
        parts = user_input.split(",")
        project = parts[0].replace("research pipeline", "").strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        journal = parts[2].strip() if len(parts) > 2 else ""
        result = pipeline.run_research_pipeline(project, description, journal)
        return {"agent": "pipeline", "task": user_input, "response": result}

    # Approval system
    if "show approvals" in u or "pending approvals" in u:
        approvals = pipeline.get_pending_approvals()
        if not approvals:
            return {"agent": "orchestrator", "task": user_input,
                    "response": "✅ No pending approvals."}
        result = f"📋 **{len(approvals)} Pending Approvals:**\n\n"
        for a in approvals:
            result += f"**[{a['id']}] {a['title']}**\n"
            result += f"Type: {a['type']} | {a['created_at'][:10]}\n"
            result += f"Preview: {a['content'][:200]}...\n"
            result += f"→ Type 'approve {a['id']}' or 'reject {a['id']}'\n\n"
        return {"agent": "orchestrator", "task": user_input, "response": result}

    if u.startswith("approve "):
        approval_id = int(''.join(filter(str.isdigit, user_input)))
        result = pipeline.approve(approval_id)
        return {"agent": "orchestrator", "task": user_input, "response": result}

    if u.startswith("reject "):
        approval_id = int(''.join(filter(str.isdigit, user_input)))
        result = pipeline.reject(approval_id)
        return {"agent": "orchestrator", "task": user_input, "response": result}

    # Normal routing
    routed = route_task(user_input)
    agent_name = routed.get("agent", "unknown")
    task = routed.get("task", user_input)

    if agent_name in AGENT_MAP:
        response = AGENT_MAP[agent_name].handle(task)
        return {"agent": agent_name, "task": task,
                "response": response, "routed_to": agent_name}

    return {
        "agent": "orchestrator",
        "response": "Aaqil here. Couldn't figure out which agent to use. Can you rephrase?",
        "routed_to": "none"
    }

def get_pipeline():
    return pipeline