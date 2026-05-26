"""
critic_agent.py — Self-improving quality critic with adaptive thresholds.

Upgrades over original:
- Adaptive quality thresholds that tighten as average scores improve
- Learning from past critique scores via ChromaDB quality history
- Multi-pass improvement: if first rewrite still fails, does a targeted second pass
- critique_with_feedback() generates specific revision instructions
- Blog post critique standard added (was missing — pipeline used linkedin_post wrongly)
- All JSON parsing uses the robust extract_json_safe utility
"""
from __future__ import annotations
from agents.base_agent import BaseAgent
from memory.chroma_store import store_memory, get_quality_history
from agents.agent_tools import extract_json_safe
import json

# ─── Critique Standards ───────────────────────────────────────────────────────

CRITIQUE_STANDARDS = {
    "cover_letter": """Evaluate this cover letter for a tech internship:
1. Is it personalized or generic? (1-10)
2. Does it highlight specific achievements with numbers/impact?
3. Is it the right length (150-250 words)?
4. Does it have a clear, specific ask?
5. Is the tone professional but genuine (not robotic)?
6. Overall quality score (1-10)
If score < {threshold}, rewrite it completely. Return JSON:
{{"score": X, "issues": ["..."], "rewritten": "...or null if good", "feedback": "specific improvement note"}}""",

    "blog_post": """Evaluate this technical blog post:
1. Hook strength — does the intro grab attention? (1-10)
2. Technical depth — real code, real insights, not surface-level? (1-10)
3. Structure clarity (1-10)
4. SEO-friendliness — clear title, subheadings? (1-10)
5. Overall score (1-10)
If score < {threshold}, improve the intro and conclusion. Return JSON:
{{"score": X, "issues": ["..."], "rewritten": "...or null if good", "feedback": "..."}}""",

    "research_paper": """Evaluate this research paper section:
1. Academic rigor and formal language (1-10)
2. Citation quality and appropriate use (1-10)
3. Technical depth and specificity (1-10)
4. Writing clarity (1-10)
5. Logical flow and coherence (1-10)
6. Overall score (1-10)
If score < {threshold}, improve it. Return JSON:
{{"score": X, "issues": ["..."], "improved": "...or null if good", "feedback": "..."}}""",

    "linkedin_post": """Evaluate this LinkedIn post:
1. Hook strength — does line 1 stop the scroll? (1-10)
2. Technical authenticity — specific, not vague? (1-10)
3. Engagement potential — ends with question or insight? (1-10)
4. Appropriate length and formatting? (1-10)
5. Overall score (1-10)
If score < {threshold}, rewrite it. Return JSON:
{{"score": X, "issues": ["..."], "rewritten": "...or null if good", "feedback": "..."}}""",

    "email": """Evaluate this professional email:
1. Subject line strength (1-10)
2. Personalization and specificity (1-10)
3. Clarity of ask — is it obvious what you want? (1-10)
4. Professional but human tone (1-10)
5. Length appropriate (not too long)? (1-10)
6. Overall score (1-10)
If score < {threshold}, rewrite it. Return JSON:
{{"score": X, "issues": ["..."], "rewritten": "...or null if good", "feedback": "..."}}""",

    "job_match": """Evaluate this job opportunity for Aaqil:
Profile: B.Tech AI/ML, LangChain, LLM Agents, Python, published researcher, JPNCE 2027
Job: {content}
1. Skill match — how many required skills does Aaqil have? (1-10)
2. Growth potential — will this help his career? (1-10)
3. Is it remote-friendly? (yes/partial/no)
4. Overall fit score (1-10)
Return JSON:
{{"score": X, "apply": true/false, "reasons": ["..."], "priority": "high/medium/low"}}"""
}

# ─── Adaptive Threshold System ────────────────────────────────────────────────

DEFAULT_THRESHOLDS = {
    "cover_letter": 7,
    "blog_post": 7,
    "research_paper": 8,
    "linkedin_post": 7,
    "email": 7,
    "job_match": 6,
}

THRESHOLD_TIGHTENING_RATE = 0.1  # Raise bar by 0.1 per 5 good outputs


def _compute_adaptive_threshold(content_type: str, agent_name: str) -> float:
    """
    Compute an adaptive quality threshold based on past critique scores.
    As the agent produces higher-quality content, the bar tightens.
    """
    base = DEFAULT_THRESHOLDS.get(content_type, 7)
    history = get_quality_history(agent_name, content_type, n=10)
    if len(history) < 5:
        return base  # Not enough history yet
    avg = sum(history) / len(history)
    # If consistently producing > 8, tighten threshold
    if avg > 8.0:
        return min(base + THRESHOLD_TIGHTENING_RATE * (avg - 8.0) * 10, base + 1.5)
    return base


# ─── CriticAgent ──────────────────────────────────────────────────────────────

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="critic",
            system_prompt="""You are a silent quality critic agent.
You review outputs from other agents and improve them if needed.
Always return valid JSON. Never explain your process outside the JSON.
Be ruthlessly honest about quality. Score honestly — 8+ means genuinely excellent."""
        )

    def _get_standard(self, content_type: str, threshold: float, content: str = "") -> str:
        """Get the evaluation standard for a content type with threshold injected."""
        standard = CRITIQUE_STANDARDS.get(content_type, CRITIQUE_STANDARDS["email"])
        standard = standard.replace("{threshold}", str(int(threshold)))
        if "{content}" in standard:
            standard = standard.replace("{content}", content[:500])
        return standard

    def critique(self, content_type: str, content: str,
                 author_agent: str = "unknown") -> dict:
        """
        Critique and optionally improve content.
        Uses adaptive threshold based on past performance.
        Returns structured result dict.
        """
        threshold = _compute_adaptive_threshold(content_type, author_agent)
        standard = self._get_standard(content_type, threshold, content)

        prompt = f"""{standard}

CONTENT TO EVALUATE:
{content}

Return ONLY valid JSON, nothing else."""

        try:
            raw = self.run_fresh(prompt, temperature=0.2)
            result = self._extract_json_safe(raw)
            if not result:
                raise ValueError("JSON parse failed")

            # Store quality score for adaptive threshold tracking
            score = result.get("score", 0)
            try:
                from memory.chroma_store import store_reasoning_trace
                store_reasoning_trace(
                    f"critic_{content_type}",
                    f"critique of {content_type} by {author_agent}",
                    standard[:200],
                    json.dumps(result),
                    quality_score=score
                )
            except Exception:
                pass

            return result

        except Exception as e:
            return {
                "score": 7,
                "issues": [],
                "rewritten": None,
                "feedback": f"Critique unavailable: {str(e)}"
            }

    def improve(self, content_type: str, content: str,
                author_agent: str = "unknown") -> str:
        """
        Main method — returns the best version of content.
        Performs up to 2 passes if needed.
        """
        threshold = _compute_adaptive_threshold(content_type, author_agent)
        result = self.critique(content_type, content, author_agent)
        score = result.get("score", 10)

        # Pass 1: use rewritten version if score is low
        if score < threshold:
            improved = result.get("rewritten") or result.get("improved")
            if improved:
                # Pass 2: verify the rewrite is actually better
                result2 = self.critique(content_type, improved, author_agent)
                score2 = result2.get("score", 10)
                if score2 >= threshold:
                    return improved
                # If still below threshold, do a targeted improvement pass
                feedback = result.get("feedback", "")
                if feedback:
                    targeted = self._targeted_rewrite(content_type, improved, feedback)
                    if targeted:
                        return targeted
                return improved

        return content  # Already meets quality bar

    def _targeted_rewrite(self, content_type: str, content: str, feedback: str) -> str | None:
        """Targeted second-pass rewrite based on specific feedback."""
        prompt = f"""Rewrite this {content_type} addressing this specific issue: {feedback}

Original:
{content}

Return ONLY the rewritten content, no explanation."""
        try:
            return self.run_fresh(prompt, temperature=0.5)
        except Exception:
            return None

    def critique_with_feedback(self, content_type: str, content: str) -> str:
        """
        Return human-readable critique with specific, actionable feedback.
        Used when the user wants to see what's being improved.
        """
        result = self.critique(content_type, content)
        score = result.get("score", 0)
        issues = result.get("issues", [])
        feedback = result.get("feedback", "")

        emoji = "✅" if score >= 8 else "⚠️" if score >= 6 else "❌"
        out = f"{emoji} **Quality Score: {score}/10** (threshold: {DEFAULT_THRESHOLDS.get(content_type, 7)})\n\n"
        if issues:
            out += "**Issues Found:**\n"
            for issue in issues:
                out += f"  • {issue}\n"
        if feedback:
            out += f"\n**Key Improvement:** {feedback}\n"
        if score < 7 and (result.get("rewritten") or result.get("improved")):
            out += "\n✍️ *Content was automatically improved.*"
        return out

    def critique_job_match(self, job_title: str, company: str,
                            description: str) -> dict:
        """Evaluate if a job is worth applying to."""
        content = f"Title: {job_title}\nCompany: {company}\nDescription: {description}"
        return self.critique("job_match", content)