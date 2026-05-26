"""
master.py — Adaptive orchestrator with session memory and inter-agent messaging.

Upgrades over original:
- Session-level conversation context tracking
- Intent decomposition for complex multi-part requests
- Inter-agent collaboration via BaseAgent.consult()
- Smarter pipeline trigger detection using router confidence scores
- Clarification prompts when confidence is low instead of silent failure
- Comprehensive handle() that always returns meaningful output
"""
from __future__ import annotations
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
from datetime import datetime

# ─── Initialize All Agents ────────────────────────────────────────────────────

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

# ─── Session State ────────────────────────────────────────────────────────────

_session_context = []   # Tracks (agent, task, response) tuples for this session
MAX_SESSION_HISTORY = 20


def _update_session(agent: str, task: str, response: str):
    """Track session history for context-aware follow-ups."""
    _session_context.append({
        "agent": agent,
        "task": task,
        "response_preview": response[:200] if response else "",
        "timestamp": datetime.now().isoformat()
    })
    if len(_session_context) > MAX_SESSION_HISTORY:
        _session_context.pop(0)


def _get_session_context_str() -> str:
    """Format recent session context as a string for agents."""
    if not _session_context:
        return ""
    recent = _session_context[-3:]  # Last 3 interactions
    lines = []
    for s in recent:
        lines.append(f"[{s['agent']}] {s['task'][:80]} → {s['response_preview'][:100]}")
    return "\n".join(lines)


# ─── Conversational Handler ─────────────────────────────────────────────────────

# Patterns that indicate casual chat vs a task command
_GREETINGS = {
    "hi", "hello", "hey", "heyy", "heya", "yo", "sup", "wassup",
    "hi there", "hello there", "good evening", "good afternoon",
    "good night", "howdy", "hiya",
}

_CASUAL_PATTERNS = [
    # Feelings / state
    "how are you", "how r u", "how are u", "how's it going", "how is it going",
    "what's up", "whats up",
    # Identity / capability questions
    "what are you", "who are you", "what can you do", "what do you do",
    "how many agents", "how many agent", "what agents", "which agents",
    "tell me about yourself", "tell me about you", "what are your",
    "do you have", "can you", "are you able",
    "what is your", "what's your",
    # Acknowledgements
    "help me", "help", "thank you", "thanks", "thx", "ty",
    "ok", "okay", "k", "kk", "cool", "nice", "great", "awesome",
    "got it", "understood", "makes sense", "alright", "sure",
    "no worries", "no problem", "sounds good",
    # Farewells
    "bye", "goodbye", "see you", "cya", "later", "ttyl", "good night",
    # Questions about the system
    "what can i ask", "what should i ask", "what are your capabilities",
    "show me what you can do", "list your agents",
]

# Question-style openers that indicate conversational intent
_QUESTION_OPENERS = (
    "how many", "how do you", "how can you", "what is", "what are",
    "who are", "who is", "do you", "can you tell", "tell me",
    "are you", "is there",
)

# Words that indicate an actual task (prevents false positives)
_ACTION_WORDS = {
    "write", "generate", "find", "create", "show", "search", "send",
    "draft", "apply", "update", "add", "get", "make", "analyze",
    "publish", "check", "review", "improve", "build", "scrape",
    "tailor", "submit", "fetch"
}


def _is_casual_chat(u: str) -> bool:
    """Detect if input is casual conversation rather than a task."""
    stripped = u.strip().rstrip("!?.")
    words = u.split()
    word_count = len(words)

    # 1. Exact greeting match
    if stripped in _GREETINGS:
        return True

    # 2. Has no action words at all + short = conversational
    has_action = any(w in u for w in _ACTION_WORDS)
    if not has_action:
        # Short inputs without task verbs are almost always casual
        if word_count <= 8:
            # Check for casual pattern match
            if any(pattern in u for pattern in _CASUAL_PATTERNS):
                return True
            # Check for question opener
            if any(u.startswith(opener) for opener in _QUESTION_OPENERS):
                return True
        # Very short inputs with no action words
        if word_count <= 3:
            return True

    # 3. Even with action words, check exact casual patterns
    if any(pattern in u for pattern in _CASUAL_PATTERNS[:10]):  # Core patterns always win
        return True

    return False


def _handle_conversation(user_input: str) -> dict:
    """Handle casual chat with a warm, personality-driven response."""
    session_ctx = _get_session_context_str()
    now = datetime.now()
    hour = now.hour
    time_of_day = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    # Build agent capability summary for questions like "how many agents"
    agent_summary = (
        "You have 10 specialized agents: GitHub (repos/READMEs), LinkedIn (outreach/connections), "
        "Job (internship search), Project Manager (tasks/deadlines), Career (resume/skills/interview prep), "
        "Growth (blog/LinkedIn posts/Twitter threads), Research (papers/journals), "
        "Email (drafts/sends), Briefing (morning summary/news), and Critic (silent quality improver)."
    )

    prompt = f"""You are Aaqil's AI Chief of Staff — a smart, warm, and direct personal assistant.
You are talking to Aaqil (Farhan Aaqil, B.Tech AI/ML student).
Current time: {now.strftime('%I:%M %p')}, {now.strftime('%A %B %d')}

System info you know:
{agent_summary}

Recent session context:
{session_ctx if session_ctx else 'Fresh session.'}

Aaqil just said: "{user_input}"

CRITICAL RULES:
- DO NOT generate a morning briefing. DO NOT list tasks, projects, jobs, or papers.
- Respond ONLY to what Aaqil literally said.
- Keep it SHORT: 1-3 sentences maximum.
- Be warm and natural, like a smart assistant chatting.

If it's a greeting → greet back + mention 1 thing you can help with today.
If they ask how many agents / what you can do → answer directly from the system info above.
If they said thanks/ok → acknowledge briefly + ask if there's anything else.
If they said bye → say goodbye warmly."""

    response = briefing_agent.run_fresh(prompt, temperature=0.8)
    return {
        "agent": "orchestrator",
        "task": user_input,
        "response": response,
        "routed_to": "orchestrator",
        "confidence": 1.0
    }


# ─── Pipeline Detection ───────────────────────────────────────────────────────

def _try_pipeline(u: str, user_input: str) -> dict | None:
    """Detect and run pipeline commands. Returns result dict or None."""

    if "apply pipeline" in u or ("apply to" in u and "pipeline" in u):
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

    return None


# ─── Approval System ──────────────────────────────────────────────────────────

def _try_approval(u: str, user_input: str) -> dict | None:
    """Handle approval/reject commands. Returns result dict or None."""

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
        digits = ''.join(filter(str.isdigit, user_input))
        if digits:
            result = pipeline.approve(int(digits))
            return {"agent": "orchestrator", "task": user_input, "response": result}

    if u.startswith("reject "):
        digits = ''.join(filter(str.isdigit, user_input))
        if digits:
            result = pipeline.reject(int(digits))
            return {"agent": "orchestrator", "task": user_input, "response": result}

    return None


# ─── Main Handler ─────────────────────────────────────────────────────────────

def handle(user_input: str) -> dict:
    """
    Main entry point. Routes user input to the appropriate agent(s).

    Returns:
        {
            "agent": str,           # which agent handled it
            "task": str,            # the task sent to the agent
            "response": str,        # the agent's response
            "routed_to": str,       # routing destination
            "confidence": float,    # routing confidence (0-1)
        }
    """
    u = user_input.lower().strip()

    # Log to orchestrator memory
    store_memory(
        "orchestrator",
        f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        user_input,
        {"timestamp": datetime.now().isoformat()}
    )

    # 0. Casual conversation / greetings — handle BEFORE routing
    if _is_casual_chat(u):
        result = _handle_conversation(user_input)
        _update_session("orchestrator", user_input, result["response"])
        return result

    # 1. Check pipeline triggers
    pipeline_result = _try_pipeline(u, user_input)
    if pipeline_result:
        _update_session("pipeline", user_input, pipeline_result["response"])
        return {**pipeline_result, "routed_to": "pipeline", "confidence": 0.95}

    # 2. Check approval commands
    approval_result = _try_approval(u, user_input)
    if approval_result:
        _update_session("orchestrator", user_input, approval_result["response"])
        return {**approval_result, "routed_to": "orchestrator", "confidence": 1.0}

    # 3. Semantic routing
    routed = route_task(user_input)
    agent_name = routed.get("agent", "briefing")
    task = routed.get("task", user_input)
    confidence = routed.get("confidence", 0.5)
    needs_clarification = routed.get("needs_clarification", False)

    # 4. Inject session context into task for agents that benefit from it
    session_ctx = _get_session_context_str()
    if session_ctx and agent_name in {"career", "job", "research", "briefing"}:
        task = f"[Recent context]\n{session_ctx}\n\n[Current request]\n{task}"

    # 5. Clarification for very low-confidence routing
    if needs_clarification and confidence < 0.3:
        response = (
            f"🤔 I'm not sure which agent to use for: **\"{user_input}\"**\n\n"
            f"I routed to **{agent_name}** (confidence: {confidence:.0%}) but it might be wrong.\n\n"
            f"Available capabilities:\n"
            f"• **Job search**: 'find AI/ML internships'\n"
            f"• **Career**: 'tailor my resume for this JD' / 'interview prep for Google'\n"
            f"• **Research**: 'write paper for my project'\n"
            f"• **Growth**: 'generate LinkedIn post about my project'\n"
            f"• **Briefing**: 'good morning' / 'weekly review'\n"
            f"• **Email**: 'draft recruiter email to Sarah at OpenAI'\n"
            f"• **GitHub**: 'generate readme for my repo'\n\n"
            f"Trying **{agent_name}** agent anyway..."
        )
        # Still execute, just warn
        if agent_name in AGENT_MAP:
            agent_response = AGENT_MAP[agent_name].handle(task)
            full_response = response + "\n\n---\n\n" + agent_response
        else:
            full_response = response
        _update_session(agent_name, user_input, full_response)
        return {"agent": agent_name, "task": task, "response": full_response,
                "routed_to": agent_name, "confidence": confidence}

    # 6. Normal execution
    if agent_name in AGENT_MAP:
        agent = AGENT_MAP[agent_name]
        response = agent.handle(task)

        _update_session(agent_name, user_input, response)

        return {
            "agent": agent_name,
            "task": task,
            "response": response,
            "routed_to": agent_name,
            "confidence": confidence
        }

    # 7. True fallback — ask briefing agent for help
    response = briefing_agent.handle(
        f"The user said: '{user_input}'\nI couldn't figure out which agent to use. "
        f"Acknowledge this helpfully and suggest what they might try."
    )
    _update_session("orchestrator", user_input, response)
    return {
        "agent": "orchestrator",
        "response": response,
        "routed_to": "none",
        "confidence": 0.0
    }


def get_pipeline():
    return pipeline


def get_session_context() -> list:
    """Get the current session interaction history."""
    return _session_context.copy()


def reset_all_contexts():
    """Reset conversation history for all agents (start fresh session)."""
    for agent in AGENT_MAP.values():
        agent.reset_context()
    _session_context.clear()