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
from agents.info_agent import InfoAgent
from scheduler.background import start_scheduler, scheduler
from orchestrator.health_monitor import health_monitor

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
info_agent = InfoAgent()

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

# Inject AGENT_MAP into BaseAgent for cross-agent consultation
from agents.base_agent import BaseAgent
BaseAgent.AGENT_MAP = AGENT_MAP

# Pipeline engine
pipeline = Pipeline(AGENT_MAP, critic_agent)

# Start background scheduler
if not scheduler.running:
    start_scheduler(AGENT_MAP, pipeline)

# Short term conversational memory per agent (Rolling window)
agent_short_term_memory = {agent: [] for agent in AGENT_MAP.keys()}
# For orchestrator-level routing/system messages
orchestrator_memory = []

def summarize_and_store_context(agent_name: str, context: list):
    """Summarize long context and store in ChromaDB."""
    text_to_summarize = "\n".join([f"{m['role']}: {m['content']}" for m in context])
    summary_prompt = f"Summarize the key points of this conversation thread concisely:\n\n{text_to_summarize}"
    try:
        from config import MODEL, GROQ_API_KEY
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.1
        )
        summary = resp.choices[0].message.content
        store_memory(agent_name, f"summary_{hash(summary)}", summary, {"type": "conversation_summary"})
    except Exception as e:
        print(f"Summarization failed for {agent_name}: {e}")

def handle(user_input: str, force_agent: str = None) -> dict:
    global agent_short_term_memory, orchestrator_memory
    u = user_input.lower()
    
    # Direct routing bypass
    if force_agent == "info":
        # We handle info agent memory separately or just keep it stateless
        response = info_agent.handle(user_input)
        return {"agent": "info", "task": user_input, "response": response, "routed_to": "info"}

    store_memory("orchestrator", f"task_{hash(user_input)}",
                 user_input, {"timestamp": __import__("datetime").datetime.now().isoformat()})
    
    orchestrator_memory.append({"role": "user", "content": user_input})
    if len(orchestrator_memory) > 10:
        orchestrator_memory = orchestrator_memory[-10:]

    # Pipeline triggers
    if ("apply pipeline" in u) or ("apply to" in u and "pipeline" in u):
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

    # Fast pre-router — bypass LLM for obvious commands
    FAST_ROUTES = {
        # briefing
        "morning briefing": "briefing", "generate briefing": "briefing",
        "good morning": "briefing", "daily briefing": "briefing",
        # job
        "job dashboard": "job", "show jobs": "job", "all jobs": "job",
        "find internship": "job", "search internshala": "job",
        # career
        "show skills": "career", "my skills": "career",
        "show cert": "career", "career dashboard": "career",
        "career stats": "career",
        # project manager
        "show all tasks": "project_manager", "show tasks": "project_manager",
        "add task": "project_manager", "show all projects": "project_manager",
        "show goals": "project_manager",
        # github
        "show github": "github", "github profile": "github",
        "generate readme": "github", "commit message": "github",
        # growth
        "content dashboard": "growth", "my content": "growth",
        "content calendar": "growth", "linkedin post": "growth",
        "twitter thread": "growth", "blog post": "growth",
        # research
        "research dashboard": "research", "show papers": "research",
        "my papers": "research", "write paper": "research",
        # email
        "show emails": "email", "draft email": "email",
    }
    for keyword, agent_name in FAST_ROUTES.items():
        if keyword in u and agent_name in AGENT_MAP:
            try:
                health_monitor.set_status(agent_name, "processing")
                
                # Context management
                mem = agent_short_term_memory[agent_name]
                mem.append({"role": "user", "content": user_input})
                
                AGENT_MAP[agent_name].current_context = mem
                response = AGENT_MAP[agent_name].handle(user_input)
                
                mem.append({"role": "assistant", "content": response})
                if len(mem) > 10:
                    summarize_and_store_context(agent_name, mem)
                    agent_short_term_memory[agent_name] = mem[-4:] # Keep last 4 for continuity
                    
                health_monitor.record_success(agent_name)
                return {"agent": agent_name, "task": user_input,
                        "response": response, "routed_to": agent_name}
            except Exception as e:
                health_monitor.record_failure(agent_name)
                return {"agent": agent_name, "task": user_input,
                        "response": f"Error executing task: {e}", "routed_to": agent_name}

    # Normal LLM routing (for ambiguous/complex inputs)
    routed = route_task(user_input, context=orchestrator_memory)
    agent_name = routed.get("agent", "unknown")
    task = routed.get("task", user_input)

    if agent_name in AGENT_MAP:
        try:
            health_monitor.set_status(agent_name, "processing")
            
            # Context management
            mem = agent_short_term_memory[agent_name]
            mem.append({"role": "user", "content": task})
            
            AGENT_MAP[agent_name].current_context = mem
            response = AGENT_MAP[agent_name].handle(task)
            
            mem.append({"role": "assistant", "content": response})
            if len(mem) > 10:
                summarize_and_store_context(agent_name, mem)
                agent_short_term_memory[agent_name] = mem[-4:] # Keep last 4 for continuity

            health_monitor.record_success(agent_name)
            return {"agent": agent_name, "task": task,
                    "response": response, "routed_to": agent_name}
        except Exception as e:
            health_monitor.record_failure(agent_name)
            return {"agent": agent_name, "task": task,
                    "response": f"Error executing task: {e}", "routed_to": agent_name}

    try:
        from config import MODEL, GROQ_API_KEY
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        system_prompt = "You are Aaqil AI, a highly capable Multi-Agent Orchestrator. You manage a team of specialized agents: github, linkedin, job, project manager, career, growth, research, email, and briefing. Respond to casual conversation, greetings, or questions about what you can do politely and conversationally."
        messages = [{"role": "system", "content": system_prompt}] + orchestrator_memory
        
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7
        )
        reply = resp.choices[0].message.content
        
        orchestrator_memory.append({"role": "assistant", "content": reply})
        
        return {
            "agent": "orchestrator",
            "task": user_input,
            "response": reply,
            "routed_to": "orchestrator"
        }
    except Exception as e:
        return {
            "agent": "orchestrator",
            "response": "Aaqil here. I'm having trouble connecting to my brain right now. Can you try again?",
            "routed_to": "none"
        }

def get_health_monitor():
    return health_monitor

def get_pipeline():
    return pipeline