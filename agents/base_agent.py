from groq import Groq
from config import GROQ_API_KEY, MODEL
from memory.chroma_store import store_memory, retrieve_memory

class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = Groq(api_key=GROQ_API_KEY)

    def recall(self, query: str):
        return retrieve_memory(self.name, query)

    def remember(self, doc_id: str, content: str, metadata: dict = {}):
        store_memory(self.name, doc_id, content, metadata)

    def run(self, task: str) -> str:
        memories = self.recall(task)
        memory_context = "\n".join(memories) if memories else "No previous memory."

        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Memory:\n{memory_context}\n\nTask:\n{task}"}
            ]
        )
        result = response.choices[0].message.content
        self.remember(f"{self.name}_{hash(task)}", result, {"task": task})
        return result