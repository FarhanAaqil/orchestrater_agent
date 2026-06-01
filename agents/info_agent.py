from agents.base_agent import BaseAgent
import json

class InfoAgent(BaseAgent):
    TOOLS = [
        {
            "name": "get_agent_details",
            "description": "Get detailed information about a specific agent, including its tools and system prompt.",
            "args": {"agent_name": "str"}
        },
        {
            "name": "list_all_agents",
            "description": "List all available agents in the system and a short summary of each.",
            "args": {}
        }
    ]

    def __init__(self):
        super().__init__(
            name="info",
            system_prompt="""You are the dedicated System Documentation & Help Agent (InfoAgent).
Your sole purpose is to explain how the other agents in the system work, what tools they have, and how the user can interact with them.
When asked about an agent, use the `get_agent_details` tool to read their actual code and provide accurate, helpful answers.
Always be extremely clear and format your outputs nicely with Markdown."""
        )

    def get_agent_details(self, agent_name: str) -> str:
        agent_name = agent_name.lower().replace(" ", "_")
        if agent_name not in self.AGENT_MAP:
            return f"❌ Agent '{agent_name}' not found in the system registry. Use list_all_agents to see available agents."
        
        target_agent = self.AGENT_MAP[agent_name]
        tools_str = json.dumps(target_agent.TOOLS, indent=2) if target_agent.TOOLS else "No specific tools defined (Raw LLM Agent)."
        sys_prompt = target_agent.system_prompt
        
        result = f"🔍 **Agent Profile: {agent_name.upper()}**\n\n"
        result += f"**System Prompt/Purpose:**\n```\n{sys_prompt}\n```\n\n"
        result += f"**Available Tools:**\n```json\n{tools_str}\n```\n\n"
        return result

    def list_all_agents(self) -> str:
        if not self.AGENT_MAP:
            return "❌ No agents found in registry."
            
        result = "📋 **Available System Agents:**\n\n"
        for name, agent in self.AGENT_MAP.items():
            tool_count = len(agent.TOOLS)
            result += f"- **{name}**: ({tool_count} tools)\n"
        
        result += "\n*Ask me for details on any specific agent!*"
        return result

    def handle(self, task: str) -> str:
        return self.think_and_act(task)
