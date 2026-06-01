import json
import re
from groq import Groq
from config import GROQ_API_KEY, MODEL, AGENTS

client = Groq(api_key=GROQ_API_KEY)

def route_task(user_input: str, context: list = None) -> dict:
    agent_list = "\n".join([f"- {k}: {v}" for k, v in AGENTS.items()])
    
    # Format context if available
    context_str = ""
    if context:
        context_str = "Recent conversation context:\n" + "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in context[-3:]]) + "\n\n"

    prompt = f"""You are a smart router for a multi-agent system.
Given the user's request, figure out the best agent to handle it.
Return a valid JSON object EXACTLY in this format:
{{"agent": "agent_name", "task": "refined task description"}}

Available agents:
{agent_list}

{context_str}User request: {user_input}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw = response.choices[0].message.content
        
        # Fallback markdown stripping just in case
        if "```" in raw:
            match = re.search(r"```(?:json)?(.*?)```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()

        return json.loads(raw)
    except Exception as e:
        print(f"[Router Error] {e}")
        return {"agent": "unknown", "task": user_input}