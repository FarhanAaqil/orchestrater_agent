"""
base_agent.py — Intelligent, adaptive base class for all agents.

Upgrades over original:
- Multi-turn conversation history (10-turn window by default)
- UUID-based memory IDs (no hash collisions)
- Adaptive retry with exponential backoff
- Reasoning trace logging to ChromaDB
- Natural language intent extraction via extract_intent tool
- _extract_json_safe() for robust LLM JSON parsing
- reset_context() for session management
"""
from __future__ import annotations
from groq import Groq
from config import GROQ_API_KEY, MODEL
from memory.chroma_store import store_memory, retrieve_memory, store_reasoning_trace
from agents.agent_tools import extract_json_safe, extract_intent
import uuid
import time
import logging

logger = logging.getLogger(__name__)

MAX_HISTORY = 10          # Conversation turns kept per session
MAX_RETRIES = 3           # LLM call retries on failure
RETRY_BASE_DELAY = 1.0    # Seconds — doubles each retry


class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = Groq(api_key=GROQ_API_KEY)
        self.history: list[dict] = []   # Multi-turn conversation history
        self._session_id = str(uuid.uuid4())[:8]

    # ─── Memory ───────────────────────────────────────────────────────────────

    def recall(self, query: str, n: int = 3) -> list[str]:
        """Retrieve semantically relevant past memories."""
        return retrieve_memory(self.name, query, n)

    def remember(self, content: str, metadata: dict = {}):
        """Store content in agent memory with a unique UUID-based ID."""
        doc_id = f"{self.name}_{uuid.uuid4().hex}"
        meta = {"agent": self.name, **metadata}
        store_memory(self.name, doc_id, content, meta)

    # ─── Context ──────────────────────────────────────────────────────────────

    def reset_context(self):
        """Clear conversation history and start a new session."""
        self.history = []
        self._session_id = str(uuid.uuid4())[:8]

    def _trim_history(self):
        """Keep only the last MAX_HISTORY turns (2 messages per turn)."""
        max_msgs = MAX_HISTORY * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    # ─── LLM Calls ────────────────────────────────────────────────────────────

    def run(self, task: str, temperature: float = 0.7,
            use_history: bool = True) -> str:
        """
        Call the LLM with full conversation history and semantic memory.
        Retries up to MAX_RETRIES times with exponential backoff.
        Stores reasoning trace in ChromaDB for future learning.
        """
        # Build memory context
        memories = self.recall(task)
        memory_context = "\n".join(memories) if memories else "No previous memory."

        # Build message list
        messages = [{"role": "system", "content": self.system_prompt}]

        # Inject memory as a system-level context block
        if memories:
            messages.append({
                "role": "system",
                "content": f"[Relevant past context for this task]\n{memory_context}"
            })

        # Add conversation history (multi-turn)
        if use_history and self.history:
            self._trim_history()
            messages.extend(self.history)

        # Add the current user message
        messages.append({"role": "user", "content": task})

        # LLM call with retry
        result = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=temperature,
                )
                result = response.choices[0].message.content
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[{self.name}] LLM call failed (attempt {attempt+1}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"[{self.name}] All LLM retries exhausted: {e}")
                    result = f"⚠️ Agent {self.name} encountered an error. Please try again."

        # Update conversation history
        if use_history:
            self.history.append({"role": "user", "content": task})
            self.history.append({"role": "assistant", "content": result})
            self._trim_history()

        # Store in memory and reasoning trace
        self.remember(result, {"task": task[:200]})
        store_reasoning_trace(self.name, task, memory_context, result)

        return result

    def run_fresh(self, task: str, temperature: float = 0.4) -> str:
        """Run without conversation history — for one-shot structured tasks."""
        return self.run(task, temperature=temperature, use_history=False)

    # ─── Intent Extraction ────────────────────────────────────────────────────

    def extract_intent(self, task: str, schema: dict) -> dict:
        """
        Use LLM to extract structured intent from free-form natural language.

        Example:
            schema = {
                "company": "string, the company name",
                "role": "string, the job role",
                "email": "string or null, recruiter email if mentioned"
            }
        """
        return extract_intent(task, schema, self.client, MODEL)

    # ─── JSON Utilities ───────────────────────────────────────────────────────

    def _extract_json_safe(self, text: str) -> dict | None:
        """Robustly parse JSON from LLM output (handles markdown fences, prefix text)."""
        return extract_json_safe(text)

    # ─── Agent Consultation ───────────────────────────────────────────────────

    def consult(self, other_agent: "BaseAgent", question: str) -> str:
        """
        Ask another agent for input — enables inter-agent collaboration.
        The other agent runs the question without modifying its own history.
        """
        return other_agent.run_fresh(
            f"[Consulted by {self.name} agent]\n{question}",
            temperature=0.3
        )