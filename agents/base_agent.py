import json
import re
import os
import logging
from groq import Groq
try:
    from groq import APITimeoutError, APIConnectionError
except ImportError:
    APITimeoutError = Exception
    APIConnectionError = Exception

from config import GROQ_API_KEY, MODEL, FAST_MODEL, SMART_MODEL, ENABLE_SELF_REFLECTION
from memory.chroma_store import store_memory, retrieve_memory

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Jarvis-style base agent. Each subclass:
    - Defines TOOLS (list of dicts describing what it can do)
    - Implements the methods listed in TOOLS
    - Calls `self.think_and_act(task)` from handle()
    """

    TOOLS: list = []  # Override in subclass
    AGENT_MAP: dict = {}  # Global registry injected by master

    def __init__(self, name: str, system_prompt: str, max_tokens: int = None):
        self.name = name
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.current_context = []
        self.client = Groq(api_key=GROQ_API_KEY)

    # ─── Memory ───────────────────────────────────────────────────────

    def recall(self, query: str) -> list:
        return retrieve_memory(self.name, query)

    def remember(self, doc_id: str, content: str, metadata: dict = None):
        store_memory(self.name, doc_id, content, metadata or {})

    def consult(self, target_agent: str, query: str) -> str:
        """Consult another agent for information."""
        if target_agent in self.AGENT_MAP:
            return self.AGENT_MAP[target_agent].run(f"[Consultation from {self.name}]: {query}")
        return f"Agent {target_agent} not found."

    # ─── Raw LLM Call ─────────────────────────────────────────────────

    def run(self, task: str, temperature: float = None) -> str:
        """Call the LLM with semantic memory + short-term context injected."""
        # Dynamic temperature
        if temperature is None:
            creative_keywords = ["write", "draft", "generate", "create", "brainstorm", "post", "blog"]
            if any(k in task.lower() for k in creative_keywords):
                temperature = 0.8
            else:
                temperature = 0.2

        memories = self.recall(task)
        memory_context = "\n".join(memories) if memories else ""

        sys_prompt = self.system_prompt + "\n\nAlways think step-by-step before answering. Enclose your reasoning in <thought>...</thought> tags.\nAfter your response, append a brief 'Proactive Suggestion:' for the logical next step."

        messages = [{
            "role": "system",
            "content": sys_prompt + (
                f"\n\nRelevant memory:\n{memory_context}" if memory_context else ""
            )
        }]

        for msg in self.current_context[-6:]:  # last 6 turns
            messages.append({"role": msg["role"], "content": msg["content"]})

        if not self.current_context or self.current_context[-1]["content"] != task:
            messages.append({"role": "user", "content": task})

        try:
            active_model = os.getenv("SELECTED_SMART_MODEL", SMART_MODEL)
            kwargs = dict(model=active_model, messages=messages, timeout=90, temperature=temperature)
            if self.max_tokens:
                kwargs["max_tokens"] = self.max_tokens
            response = self.client.chat.completions.create(**kwargs)
            result = response.choices[0].message.content
            
            # Remove thought tags from final output for cleaner UI
            final_result = re.sub(r'<thought>.*?</thought>', '', result, flags=re.DOTALL).strip()
            if not final_result:
                final_result = result
                
            # Self-reflection (Internal loop if score < 7)
            # Controlled by ENABLE_SELF_REFLECTION in config.py / .env
            if ENABLE_SELF_REFLECTION and self.name != "critic" and len(final_result) > 100:
                reflection_prompt = f"Rate this output from 1-10 on quality and accuracy:\n\n{final_result}\n\nReturn JSON: {{\"score\": X, \"issues\": [...], \"rewritten\": \"...improved version if < 7\"}}"
                try:
                    ref_resp = self.client.chat.completions.create(
                        model=FAST_MODEL,
                        messages=[{"role": "user", "content": reflection_prompt}],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )
                    ref_data = json.loads(ref_resp.choices[0].message.content)
                    if ref_data.get("score", 10) < 7 and ref_data.get("rewritten"):
                        final_result = ref_data["rewritten"] + "\n\n*(Self-corrected for better quality)*"
                except Exception:
                    pass  # Reflection is best-effort — never block the response

            self.remember(f"{self.name}_{abs(hash(task))}", final_result, {"task": task[:100]})
            return final_result
        except APITimeoutError:
            return f"⏱️ [{self.name}] Timed out after 90s. Try a simpler request."
        except APIConnectionError as e:
            return f"🔌 [{self.name}] Connection error: {e}"
        except Exception as e:
            return f"❌ [{self.name}] Error: {e}"

    # ─── Tool-Dispatch (Jarvis Brain) ─────────────────────────────────

    def think_and_act(self, task: str) -> str:
        """
        Core intelligence loop:
        1. Send task + tool list to LLM
        2. LLM returns JSON: {"tool": "method_name", "args": {...}}
        3. Dispatch to that method
        4. Return result

        If no tools match or LLM returns no tool, fall back to self.run(task).
        """
        if not self.TOOLS:
            return self.run(task)

        tool_descriptions = "\n".join([
            f'- {t["name"]}: {t["description"]} | args: {json.dumps(t.get("args", {}))}'
            for t in self.TOOLS
        ])

        dispatch_prompt = f"""You are the intelligence layer of {self.name} agent.
The user wants: "{task}"

Available tools:
{tool_descriptions}
- clarify_intent: Ask the user a clarifying question if the request is ambiguous or missing required information. | args: {{"question": "str"}}

Choose the BEST tool to handle this request.
Before deciding, think step-by-step about what the user is asking and what tool matches best.
Enclose your reasoning in <thought>...</thought> tags.
After thinking, return ONLY valid JSON:
{{"tool": "tool_name", "args": {{...fill args from user request...}}}}

If no tool fits, return: {{"tool": "run", "args": {{"task": "{task}"}}}}

Rules:
- Extract arguments from the user's request naturally
- If a required arg is clearly missing and cannot be defaulted safely, use `clarify_intent`.
- ONLY return JSON after your <thought> block."""

        try:
            response = self.client.chat.completions.create(
                model=FAST_MODEL,
                messages=[{"role": "user", "content": dispatch_prompt}],
                timeout=30,
                temperature=0.1  # low temp for deterministic routing
            )
            raw = response.choices[0].message.content.strip()
            
            # Extract JSON from output that might have <thought>
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "{" in raw:
                raw = raw[raw.find("{") : raw.rfind("}") + 1]
                
            decision = json.loads(raw)
            tool_name = decision.get("tool", "run")
            args = decision.get("args", {})
        except Exception:
            # Fallback to raw LLM if dispatch fails
            return self.run(task)

        # Dispatch
        if tool_name == "clarify_intent":
            return f"❓ [{self.name}]: {args.get('question', 'Could you clarify your request?')}"

        if tool_name == "run":
            return self.run(args.get("task", task))

        method = getattr(self, tool_name, None)
        if method is None:
            return self.run(task)

        try:
            res = method(**args)
            if not isinstance(res, str):
                try:
                    res = json.dumps(res, indent=2)
                except Exception:
                    res = str(res)
            return res
        except TypeError as e:
            logger.warning("[%s] Tool '%s' TypeError: %s — retrying with raw task.", self.name, tool_name, e)
            # Arg mismatch — try calling with just the task string
            try:
                res = method(task)
                if not isinstance(res, str):
                    try:
                        res = json.dumps(res, indent=2)
                    except Exception:
                        res = str(res)
                return res
            except Exception as inner_e:
                logger.error("[%s] Fallback call for '%s' failed: %s", self.name, tool_name, inner_e)
                return self.run(task)
        except Exception as e:
            logger.error("[%s] Tool '%s' raised: %s", self.name, tool_name, e, exc_info=True)
            return f"❌ [{self.name}] Tool `{tool_name}` failed: {e}"