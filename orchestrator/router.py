"""
router.py — Semantic router with confidence scoring, multi-agent routing,
and keyword-based fallback chain.

Upgrades over original:
- Structured JSON output with confidence score
- Multi-agent routing for compound tasks (e.g. "apply to Google" → [research, job, email])
- Keyword fallback if LLM parse fails
- Routing decisions logged to ChromaDB for debugging recurring misroutes
- Low-confidence requests escalated to clarification prompt
"""
from __future__ import annotations
from groq import Groq
from config import GROQ_API_KEY, MODEL, AGENTS
from memory.chroma_store import store_memory
from agents.agent_tools import extract_json_safe
from datetime import datetime
import json
import re

client = Groq(api_key=GROQ_API_KEY)

# ─── Keyword Fallback Map ─────────────────────────────────────────────────────
# Used when LLM routing fails or returns low confidence

KEYWORD_MAP = {
    "github": ["github", "repo", "readme", "commit", "repository", "code"],
    "linkedin": ["linkedin", "connection request", "recruiter message", "outreach"],
    "job": ["internship", "job search", "find jobs", "apply", "cover letter",
            "internshala", "wellfound", "job application", "scrape jobs"],
    "project_manager": ["task", "deadline", "project", "progress", "milestone",
                        "todo", "backlog", "sprint", "mark complete"],
    "career": ["resume", "skill", "certificate", "interview prep", "career",
               "skill gap", "tailor resume"],
    "growth": ["linkedin post", "twitter", "blog", "content", "hashnode",
               "devlog", "publish", "tweet", "post"],
    "research": ["paper", "research", "journal", "arxiv", "publication",
                 "manuscript", "write paper", "predatory"],
    "email": ["email", "draft email", "send email", "follow up", "outreach email",
              "recruiter email", "publisher email"],
    "briefing": ["morning", "briefing", "good morning", "status", "daily",
                 "news", "ai news", "github activity", "weekly review"],
}

# Compound task patterns → multiple agents
COMPOUND_PATTERNS = [
    {
        "keywords": ["apply pipeline", "apply to", "pipeline"],
        "agents": ["briefing", "career", "job", "email"],
        "task_type": "pipeline_apply"
    },
    {
        "keywords": ["publish pipeline", "content pipeline"],
        "agents": ["growth"],
        "task_type": "pipeline_publish"
    },
    {
        "keywords": ["research pipeline"],
        "agents": ["research", "email"],
        "task_type": "pipeline_research"
    },
]


def _keyword_fallback(user_input: str) -> dict:
    """Score agents by keyword match and return best match."""
    text = user_input.lower()
    scores = {}
    for agent, keywords in KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[agent] = score
    if scores:
        best = max(scores, key=scores.get)
        confidence = min(scores[best] / 3.0, 0.8)  # Cap at 0.8 — it's a fallback
        return {"agent": best, "agents": [best], "task": user_input,
                "confidence": confidence, "method": "keyword_fallback"}
    return {"agent": "briefing", "agents": ["briefing"], "task": user_input,
            "confidence": 0.2, "method": "default_fallback"}


def _check_compound(user_input: str) -> dict | None:
    """Detect compound pipeline tasks that need multiple agents."""
    text = user_input.lower()
    for pattern in COMPOUND_PATTERNS:
        if any(kw in text for kw in pattern["keywords"]):
            return {
                "agent": pattern["agents"][0],
                "agents": pattern["agents"],
                "task": user_input,
                "confidence": 0.95,
                "task_type": pattern["task_type"],
                "method": "compound_pattern"
            }
    return None


def route_task(user_input: str) -> dict:
    """
    Route a user request to the most appropriate agent(s).

    Returns:
        {
            "agent": str,          # primary agent name
            "agents": list[str],   # all agents for compound tasks
            "task": str,           # refined task description
            "confidence": float,   # 0.0 – 1.0
            "method": str          # "llm", "keyword_fallback", "compound_pattern"
        }
    """
    # 1. Check for compound pipeline tasks first
    compound = _check_compound(user_input)
    if compound:
        _log_routing(user_input, compound)
        return compound

    # 2. LLM-powered routing
    agent_list = "\n".join([f"- {k}: {v}" for k, v in AGENTS.items()])
    prompt = f"""You are a task router for a personal AI assistant system.
Given the user's request, determine which agent(s) should handle it.

Available agents:
{agent_list}

User request: {user_input}

Return ONLY valid JSON in this exact format:
{{
  "agent": "<primary_agent_name>",
  "agents": ["<agent1>", "<agent2>"],
  "task": "<refined, specific task description>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence why>"
}}

Rules:
- "agent" must be exactly one of the agent keys listed above
- "agents" lists all involved agents (usually just one)
- confidence > 0.8 means very clear intent
- confidence < 0.5 means ambiguous
- If genuinely unclear, use "briefing" agent with low confidence"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        result = extract_json_safe(raw)

        if result and "agent" in result and result["agent"] in AGENTS:
            # Ensure required fields exist
            result.setdefault("agents", [result["agent"]])
            result.setdefault("confidence", 0.75)
            result.setdefault("task", user_input)
            result["method"] = "llm"

            # Low confidence → still route but flag it
            if result["confidence"] < 0.4:
                result["needs_clarification"] = True

            _log_routing(user_input, result)
            return result

    except Exception as e:
        pass  # Fall through to keyword fallback

    # 3. Keyword-based fallback
    fallback = _keyword_fallback(user_input)
    _log_routing(user_input, fallback)
    return fallback


def _log_routing(user_input: str, result: dict):
    """Log routing decisions for debugging and improvement tracking."""
    try:
        log_id = f"route_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        store_memory(
            "router_log",
            log_id,
            json.dumps({
                "input": user_input[:200],
                "agent": result.get("agent"),
                "confidence": result.get("confidence"),
                "method": result.get("method")
            }),
            {
                "agent": result.get("agent", "unknown"),
                "confidence": str(result.get("confidence", 0)),
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception:
        pass  # Logging failures should never break routing