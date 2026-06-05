from datetime import datetime
from scheduler.background import add_notification
from database.tracker import (
    add_pipeline_approval,
    get_pending_approvals as db_get_pending_approvals,
    resolve_approval,
)


class Pipeline:
    """
    Multi-agent pipeline engine.

    Approvals are now persisted to SQLite so they survive app restarts.
    Callbacks are not persisted (they are transient send-actions); approval
    just marks the row as approved in the DB and triggers the callback if one
    was registered in the current session.
    """

    def __init__(self, agent_map, critic_agent):
        self.agent_map = agent_map
        self.critic_agent = critic_agent
        # In-memory callback registry keyed by DB approval ID
        self._callbacks: dict = {}

    # ─── Approval Helpers ─────────────────────────────────────────

    def _queue_approval(self, title: str, a_type: str, content: str, callback=None) -> str:
        approval_id = add_pipeline_approval(title, a_type, content)
        if callback:
            self._callbacks[approval_id] = callback
        return f"Queued for approval (ID: {approval_id}): {title}"

    def get_pending_approvals(self) -> list:
        """Return all pending approvals from the database."""
        return db_get_pending_approvals()

    def approve(self, approval_id: int) -> str:
        found = resolve_approval(approval_id, "approved")
        if not found:
            return f"❌ Approval ID {approval_id} not found."
        callback = self._callbacks.pop(approval_id, None)
        if callback:
            try:
                callback()
            except Exception as e:
                return f"✅ Approved ID {approval_id} (callback error: {e})"
        return f"✅ Approved ID {approval_id}"

    def reject(self, approval_id: int) -> str:
        found = resolve_approval(approval_id, "rejected")
        self._callbacks.pop(approval_id, None)
        if not found:
            return f"❌ Approval ID {approval_id} not found."
        return f"❌ Rejected ID {approval_id}"

    # ─── Pipelines ────────────────────────────────────────────────

    def run_apply_pipeline(self, company: str, role: str, jd: str, email: str) -> str:
        """
        Multi-agent job application pipeline:
        1. CareerAgent tailors resume to the JD
        2. JobAgent generates a cover letter
        3. CriticAgent reviews the cover letter
        4. Queues everything for human approval
        """
        steps = []

        # Pre-check: Skill Gap Analysis
        job_match = self.critic_agent.critique_job_match(role, company, jd)
        if job_match.get("score", 10) < 6:
            add_notification(
                f"Pipeline paused for {company}: Skill match too low ({job_match.get('score')}/10). Consider learning first.",
                "warning"
            )
            return (
                f"❌ Pipeline paused: Your skill match for {role} at {company} is too low "
                f"({job_match.get('score')}/10).\n\n"
                f"Reasons: {', '.join(job_match.get('reasons', []))}\n\n"
                "Recommendation: Focus on learning before applying."
            )

        add_notification(f"Starting apply pipeline for {company}", "system")

        # Step 1: Tailor resume
        career = self.agent_map.get("career")
        if career and jd:
            tailored_resume = career.tailor_resume(jd)
            steps.append(f"## Tailored Resume\n{tailored_resume}")
            add_notification(f"Step 1/2 complete: Tailored resume for {company}", "success")
        else:
            steps.append("## Tailored Resume\n*(No JD provided — using base resume)*")

        # Step 2: Generate cover letter
        job = self.agent_map.get("job")
        if job:
            cover_letter = job.generate_cover_letter(role, company, jd)
            # Step 3: Critic reviews the cover letter silently
            cover_letter = self.critic_agent.improve("cover_letter", cover_letter)
            steps.append(f"## Cover Letter\n{cover_letter}")
            add_notification(f"Step 2/2 complete: Cover letter ready for {company}", "success")

        full_content = (
            f"**Company:** {company}\n"
            f"**Role:** {role}\n"
            f"**Send To:** {email or 'N/A'}\n\n"
            + "\n\n---\n\n".join(steps)
        )
        return self._queue_approval(
            f"Application: {company} — {role}",
            "email",
            full_content
        )

    def run_publish_pipeline(self, project: str, details: str) -> str:
        """
        Multi-agent content publishing pipeline:
        1. GrowthAgent generates LinkedIn post + blog post
        2. CriticAgent reviews the LinkedIn post
        3. Queues for approval before any publishing
        """
        steps = []

        growth = self.agent_map.get("growth")
        if growth:
            linkedin = growth.generate_linkedin_post(project, details)
            # Critic reviews silently
            linkedin = self.critic_agent.improve("linkedin_post", linkedin)
            steps.append(f"## LinkedIn Post\n{linkedin}")

            blog = growth.generate_blog_post(project, details)
            steps.append(f"## Blog Post (Hashnode)\n{blog[:800]}...\n*(Full post saved to DB)*")

        full_content = (
            f"**Project:** {project}\n"
            f"**Details:** {details}\n\n"
            + "\n\n---\n\n".join(steps)
        )
        return self._queue_approval(
            f"Publish: {project}",
            "content",
            full_content
        )

    def run_research_pipeline(self, project: str, description: str, journal: str) -> str:
        """
        Multi-agent research pipeline:
        1. ResearchAgent writes a full paper
        2. ResearchAgent finds matching journals (DOAJ)
        3. ResearchAgent recommends top venues (LLM)
        4. Queues a summary for approval
        """
        research = self.agent_map.get("research")
        if research:
            add_notification(f"Starting research pipeline for: {project}", "system")
            paper_result = research.write_paper(project, description)
            paper_id = paper_result.get("paper_id")
            paper_title = paper_result.get("title", project)
            citations = paper_result.get("citations", 0)
            paper_content = paper_result.get("content", "")

            add_notification("Step 1/2 complete: Draft generated. Critic reviewing...", "success")

            # Critic improvement
            improved_content = self.critic_agent.improve("research_paper", paper_content[:2000])

            # Find journals
            journal_recs = research.recommend_journals(project, paper_id=paper_id)
            add_notification("Step 2/2 complete: Target journals found.", "success")

            full_content = (
                f"**Paper:** {paper_title}\n"
                f"**Target Journal:** {journal or 'TBD'}\n"
                f"**Citations Used:** {citations}\n"
                f"**DB Paper ID:** {paper_id}\n\n"
                f"## Journal Recommendations\n{journal_recs[:1000]}...\n\n"
                f"*(Full paper saved to database — ID: {paper_id})*"
            )
        else:
            full_content = (
                f"**Project:** {project}\n"
                f"**Description:** {description}\n"
                f"**Target Journal:** {journal}\n\n"
                "Research agent unavailable."
            )

        return self._queue_approval(
            f"Research: {project}",
            "paper",
            full_content
        )
