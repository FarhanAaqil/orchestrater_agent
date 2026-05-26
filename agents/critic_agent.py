from agents.base_agent import BaseAgent
from memory.chroma_store import store_memory, retrieve_memory
import json

CRITIQUE_STANDARDS = {
    "cover_letter": """Evaluate this cover letter:
1. Is it personalized or generic? (1-10)
2. Does it highlight specific achievements?
3. Is it the right length (150-250 words)?
4. Does it have a clear ask?
5. Overall quality score (1-10)
If score < 7, rewrite it. Return JSON:
{"score": X, "issues": [...], "rewritten": "...or null if good"}""",

    "research_paper": """Evaluate this research paper section:
1. Academic rigor (1-10)
2. Citation quality
3. Technical depth (1-10)
4. Writing clarity (1-10)
5. Overall score (1-10)
If score < 8, improve it. Return JSON:
{"score": X, "issues": [...], "improved": "...or null if good"}""",

    "linkedin_post": """Evaluate this LinkedIn post:
1. Hook strength (1-10)
2. Technical authenticity (1-10)
3. Engagement potential (1-10)
4. Hashtag relevance
5. Overall score (1-10)
If score < 7, rewrite it. Return JSON:
{"score": X, "issues": [...], "rewritten": "...or null if good"}""",

    "email": """Evaluate this professional email:
1. Subject line strength (1-10)
2. Personalization (1-10)
3. Clarity of ask (1-10)
4. Professional tone (1-10)
5. Overall score (1-10)
If score < 7, rewrite it. Return JSON:
{"score": X, "issues": [...], "rewritten": "...or null if good"}""",

    "job_match": """Evaluate this job match for Aaqil:
Profile: B.Tech AI/ML, LangChain, LLM Agents, Python, published researcher
Job: {content}
1. Skill match (1-10)
2. Growth potential (1-10)
3. Remote possibility
4. Overall fit (1-10)
Return JSON:
{"score": X, "apply": true/false, "reasons": [...]}"""
}

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="critic",
            system_prompt="""You are a silent quality critic agent.
You review outputs from other agents and improve them if needed.
Always return valid JSON. Never explain your process.
Be ruthlessly honest about quality."""
        )

    def critique(self, content_type: str, content: str) -> dict:
        """Silently critique and improve content. Returns improved version."""
        standard = CRITIQUE_STANDARDS.get(content_type, CRITIQUE_STANDARDS["email"])
        if "{content}" in standard:
            standard = standard.replace("{content}", content[:500])

        prompt = f"""{standard}

CONTENT TO EVALUATE:
{content}

Return ONLY valid JSON, nothing else."""

        try:
            raw = self.run(prompt)
            # Clean JSON
            raw = raw.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            result = json.loads(raw)

            # Store critique in memory
            store_memory(
                "critic",
                f"critique_{hash(content[:100])}",
                json.dumps(result),
                {"type": content_type, "score": result.get("score", 0)}
            )
            return result
        except Exception as e:
            return {"score": 8, "issues": [], "rewritten": None, "error": str(e)}

    def improve(self, content_type: str, content: str) -> str:
        """Main method — silently returns best version of content."""
        result = self.critique(content_type, content)
        score = result.get("score", 10)

        # Return improved version if score is low
        if score < 7:
            improved = result.get("rewritten") or result.get("improved")
            if improved:
                return improved

        return content  # Return original if already good

    def critique_job_match(self, job_title: str, company: str,
                            description: str) -> dict:
        content = f"Title: {job_title}\nCompany: {company}\nDescription: {description}"
        return self.critique("job_match", content)