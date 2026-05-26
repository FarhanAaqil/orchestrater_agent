from groq import Groq
from config import GROQ_API_KEY, MODEL, AGENTS
import json

client = Groq(api_key=GROQ_API_KEY)

def route_task(user_input: str) -> str:
    agent_list = "\n".join([f"- {k}: {v}" for k, v in AGENTS.items()])

    prompt = f"""You are a router. Given the user's request, return ONLY a JSON like:
{{"agent": "agent_name", "task": "refined task description"}}

Available agents:
{agent_list}

User request: {user_input}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except:
        return {"agent": "unknown", "task": user_input}