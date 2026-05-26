from memory.chroma_store import store_memory
from database.tracker import add_email, add_content
import json
from datetime import datetime

class Pipeline:
    def __init__(self, agent_map: dict, critic):
        self.agents = agent_map
        self.critic = critic
        self.pending_approvals = []

    def _log(self, pipeline_name: str, step: str, result: str):
        store_memory(
            "pipelines",
            f"{pipeline_name}_{hash(step)}_{datetime.now().isoformat()}",
            result,
            {"pipeline": pipeline_name, "step": step}
        )

    def queue_approval(self, item_type: str, title: str,
                       content: str, action: str, metadata: dict = {}):
        """Queue something for user approval before executing"""
        self.pending_approvals.append({
            "id": len(self.pending_approvals) + 1,
            "type": item_type,
            "title": title,
            "content": content,
            "action": action,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        })

    def get_pending_approvals(self) -> list:
        return [a for a in self.pending_approvals if a["status"] == "pending"]

    def approve(self, approval_id: int) -> str:
        for item in self.pending_approvals:
            if item["id"] == approval_id:
                item["status"] = "approved"
                return self._execute_approved(item)
        return "Approval not found."

    def reject(self, approval_id: int) -> str:
        for item in self.pending_approvals:
            if item["id"] == approval_id:
                item["status"] = "rejected"
                return f"❌ Rejected: {item['title']}"
        return "Approval not found."

    def _execute_approved(self, item: dict) -> str:
        action = item["action"]
        content = item["content"]
        meta = item["metadata"]

        if action == "send_email":
            email_agent = self.agents.get("email")
            if email_agent:
                result = email_agent._send_email(
                    meta.get("to_email", ""),
                    meta.get("subject", ""),
                    content
                )
                return f"✅ Email sent!" if result["success"] else f"❌ {result['error']}"

        elif action == "publish_hashnode":
            growth_agent = self.agents.get("growth")
            if growth_agent:
                result = growth_agent.publish_to_hashnode(
                    meta.get("title", ""), content
                )
                return f"✅ Published! {result.get('url','')}" if result["success"] else f"❌ {result['error']}"

        elif action == "publish_devto":
            growth_agent = self.agents.get("growth")
            if growth_agent:
                result = growth_agent.publish_to_devto(
                    meta.get("title", ""), content
                )
                return f"✅ Published! {result.get('url','')}" if result["success"] else f"❌ {result['error']}"

        return f"✅ Action '{action}' executed."

    # ─── Pipelines ────────────────────────────────────────────────

    def run_apply_pipeline(self, company: str, role: str,
                            jd: str = "", recruiter_email: str = "") -> str:
        """Research → Resume → Cover Letter → Email → Queue for approval"""
        results = []

        # Step 1: Research company
        web = self.agents.get("briefing")
        from utils.web_search import search_web
        company_info = search_web(f"{company} company AI ML culture tech stack", 3)
        company_context = "\n".join([f"- {r['title']}: {r['snippet']}" for r in company_info])
        self._log("apply", "research", company_context)
        results.append(f"🔍 Researched {company}")

        # Step 2: Skill gap analysis
        career = self.agents.get("career")
        if career and jd:
            gap = career.skill_gap_analysis(jd)
            self._log("apply", "skill_gap", gap)
            results.append("🎯 Skill gap analyzed")

        # Step 3: Generate cover letter
        job = self.agents.get("job")
        if job:
            cover = job.generate_cover_letter(role, company,
                f"{jd}\n\nCompany context:\n{company_context}")
            # Critic silently improves it
            cover = self.critic.improve("cover_letter", cover)
            self._log("apply", "cover_letter", cover)
            results.append("✍️ Cover letter written + critiqued")

        # Step 4: Draft application email
        email_agent = self.agents.get("email")
        if email_agent:
            email_body = email_agent.draft_application_email(company, role, jd)
            email_body = self.critic.improve("email", email_body)
            self._log("apply", "email", email_body)

            # Queue for approval — don't send automatically
            self.queue_approval(
                "email",
                f"Application Email → {company} ({role})",
                email_body,
                "send_email",
                {"to_email": recruiter_email, "subject": f"Application for {role} — Farhan Aaqil"}
            )
            results.append("📧 Application email drafted → waiting for your approval")

        return "\n".join(results) + \
               f"\n\n✅ Pipeline complete. Check **Approvals** tab to review and send."

    def run_publish_pipeline(self, project: str, details: str = "") -> str:
        """Generate all content → queue everything for approval"""
        results = []
        growth = self.agents.get("growth")
        if not growth:
            return "Growth agent not available."

        # Generate blog
        blog = growth.generate_blog_post(project, details)
        blog = self.critic.improve("linkedin_post", blog)
        self.queue_approval(
            "blog", f"Blog Post: {project}", blog,
            "publish_hashnode", {"title": f"Building {project}"}
        )
        results.append("📝 Blog post ready → pending approval")

        # Generate LinkedIn post
        post = growth.generate_linkedin_post(project, details)
        post = self.critic.improve("linkedin_post", post)
        self.queue_approval(
            "linkedin_post", f"LinkedIn Post: {project}",
            post, "linkedin_post", {}
        )
        results.append("💼 LinkedIn post ready → pending approval")

        # Generate Twitter thread
        thread = growth.generate_twitter_thread(project)
        self.queue_approval(
            "twitter_thread", f"Twitter Thread: {project}",
            thread, "twitter_thread", {}
        )
        results.append("🐦 Twitter thread ready → pending approval")

        return "\n".join(results) + \
               "\n\n✅ All content drafted. Check **Approvals** tab to review each piece."

    def run_research_pipeline(self, project: str,
                               description: str, target_journal: str = "") -> str:
        """Write paper → find journals → draft submission → queue for approval"""
        results = []
        research = self.agents.get("research")
        if not research:
            return "Research agent not available."

        # Write paper
        paper = research.write_paper(project, description)
        results.append(f"📄 Paper written (ID: {paper['paper_id']})")

        # Find journals
        journals = research.recommend_journals(project, paper["paper_id"])
        results.append("📚 Journals identified")

        # Draft submission email
        email_agent = self.agents.get("email")
        if email_agent and target_journal:
            sub_email = email_agent.draft_publisher_email(
                paper["title"], target_journal
            )
            sub_email = self.critic.improve("email", sub_email)
            self.queue_approval(
                "submission_email",
                f"Submission Email → {target_journal}",
                sub_email, "send_email",
                {"to_email": "", "subject": f"Manuscript Submission — {paper['title']}"}
            )
            results.append("📧 Submission email drafted → pending approval")

        return "\n".join(results) + \
               "\n\n✅ Research pipeline complete. Check **Approvals** tab."