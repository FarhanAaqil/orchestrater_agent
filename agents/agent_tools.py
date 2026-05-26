"""
agent_tools.py — Shared tool registry for all agents.

Provides composable, reusable tools that any agent can call without
importing other agents. This decouples agent logic and enables
dynamic tool use.
"""
from __future__ import annotations
from functools import wraps
from typing import Callable, Any
import json
import re

# ─── Tool Registry ────────────────────────────────────────────────────────────

_REGISTRY: dict[str, Callable] = {}


def tool(name: str = None, description: str = ""):
    """Decorator to register a function as a shared agent tool."""
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        _REGISTRY[tool_name] = fn
        fn._tool_name = tool_name
        fn._tool_description = description
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_tool(name: str) -> Callable | None:
    return _REGISTRY.get(name)


def list_tools() -> list[dict]:
    return [
        {"name": k, "description": getattr(v, "_tool_description", "")}
        for k, v in _REGISTRY.items()
    ]


# ─── Tools ────────────────────────────────────────────────────────────────────

@tool(name="web_search", description="Search the web for real-time information")
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Wraps the existing web_search utility."""
    try:
        from utils.web_search import search_web
        return search_web(query, max_results)
    except Exception as e:
        return [{"title": "Search unavailable", "snippet": str(e), "url": ""}]


@tool(name="arxiv_search", description="Search ArXiv for academic papers")
def arxiv_search(query: str, max_results: int = 8) -> list[dict]:
    """Wraps the ArXiv search utility."""
    try:
        from utils.web_search import search_arxiv
        return search_arxiv(query, max_results)
    except Exception as e:
        return [{"title": "ArXiv unavailable", "abstract": str(e), "url": ""}]


@tool(name="extract_intent", description="Use LLM to extract structured intent from free-form text")
def extract_intent(text: str, schema: dict, groq_client, model: str) -> dict:
    """
    Parse natural language into a structured dict using LLM.

    Args:
        text: The user's natural language input
        schema: Dict describing the expected output fields and their descriptions
        groq_client: An initialized Groq client
        model: The model name to use

    Returns:
        A dict matching the schema, or {} on failure
    """
    schema_desc = "\n".join([f'  "{k}": {v}' for k, v in schema.items()])
    prompt = f"""Extract information from this text and return ONLY valid JSON.

Text: "{text}"

Required JSON schema:
{{
{schema_desc}
}}

If a field cannot be determined, use null. Return ONLY the JSON object, nothing else."""

    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return {}


@tool(name="summarize_context", description="Summarize a long context into key points")
def summarize_context(context: str, focus: str, groq_client, model: str) -> str:
    """Summarize context, focusing on what's relevant to `focus`."""
    if len(context) < 200:
        return context
    prompt = f"""Summarize this in 3-5 bullet points, focusing on: {focus}

{context[:3000]}

Return only the bullet points."""
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return context[:500]


@tool(name="extract_json_safe", description="Safely extract JSON from LLM output that may have markdown fences")
def extract_json_safe(text: str) -> dict | None:
    """
    Robustly parse JSON from LLM output.
    Handles: raw JSON, ```json...```, ``` ... ```, leading/trailing text.
    """
    if not text:
        return None
    # Try raw first
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned.strip())
    except Exception:
        pass
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None
