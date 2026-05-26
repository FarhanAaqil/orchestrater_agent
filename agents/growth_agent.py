from agents.base_agent import BaseAgent
from database.tracker import add_content, get_content, update_content_status
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

AAQIL_BIO = """
Farhan Aaqil — Final year B.Tech AI/ML student at JPNCE Mahbubnagar.
Building LLM agents, LangChain pipelines, and AI systems.
Published researcher. Intern at Jala Academy.
GitHub: github.com/FarhanAaqil
"""

class GrowthAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="growth",
            system_prompt=f"""You are Aaqil's Growth and Content Agent.
You create viral, engaging tech content about Aaqil's projects and journey.
Aaqil's bio: {AAQIL_BIO}
Always write in first person as Aaqil. Be authentic, technical but accessible.
Avoid cringe hustle culture. Be real, share learnings, show the code."""
        )
        self.hashnode_token = os.getenv("HASHNODE_TOKEN")
        self.hashnode_pub_id = os.getenv("HASHNODE_PUBLICATION_ID")
        self.devto_key = os.getenv("DEVTO_API_KEY")

    # ─── Content Generators ───────────────────────────────────────────

    def generate_linkedin_post(self, project: str, achievement: str = "") -> str:
        task = f"""Write a LinkedIn post for Aaqil about:
Project/Topic: {project}
Achievement: {achievement if achievement else 'Building and learning'}

Format:
- Hook first line (no "Excited to share")
- 3-4 short paragraphs
- What you built, why, what you learned
- 1 key technical insight
- End with a question to spark engagement
- 5 relevant hashtags

No cringe. No "I'm thrilled". Be real and technical."""
        result = self.run(task)
        add_content(f"LinkedIn: {project}", result, "linkedin", project)
        return result

    def generate_twitter_thread(self, project: str, key_points: str = "") -> str:
        task = f"""Write a Twitter/X thread for Aaqil about:
Project: {project}
Key points: {key_points if key_points else 'How it was built and key learnings'}

Format:
- Tweet 1: Strong hook (under 280 chars)
- Tweets 2-7: One point each, technical, specific
- Tweet 8: Key learning
- Tweet 9: CTA — follow/GitHub link
- Number each tweet like "1/"

Be punchy. No fluff. Show actual code snippets or metrics where possible."""
        result = self.run(task)
        add_content(f"Twitter Thread: {project}", result, "twitter", project)
        return result

    def generate_blog_post(self, project: str, details: str = "") -> str:
        task = f"""Write a complete technical blog post for Aaqil about:
Project: {project}
Details: {details if details else 'Architecture, implementation, challenges, learnings'}

Structure:
# Title (catchy, SEO-friendly)

## Introduction (why this problem matters)

## The Problem
## The Architecture
## Implementation (with code snippets in Python)
## Challenges & How I Solved Them
## Results & Demo
## What I Learned
## What's Next

## About the Author
{AAQIL_BIO}

Write 800-1200 words. Include actual technical depth. Target: developers."""
        result = self.run(task)
        add_content(f"Blog: {project}", result, "hashnode", project)
        return result

    def generate_devlog(self, day: int, what_built: str, challenges: str = "") -> str:
        task = f"""Write a short devlog post for Aaqil:
Day: {day} of building
Built today: {what_built}
Challenges: {challenges if challenges else 'Various'}

Format: Short, raw, honest. 200-300 words.
What was planned vs what happened. One thing learned. Tomorrow's goal.
LinkedIn-ready but also works as a Hashnode devlog."""
        result = self.run(task)
        add_content(f"Devlog Day {day}", result, "linkedin", what_built)
        return result

    def generate_seo_tags(self, title: str, content: str) -> str:
        task = f"""Generate SEO metadata for this blog post:
Title: {title}
Content preview: {content[:300]}

Output:
- SEO Title (under 60 chars)
- Meta Description (under 160 chars)
- 10 relevant tags
- Suggested slug (URL-friendly)
Focus on AI/ML/Python developer audience."""
        return self.run(task)

    def content_calendar(self, weeks: int = 2) -> str:
        task = f"""Create a {weeks}-week content calendar for Aaqil:

His active projects: Aaqil (9-agent system), Self-Improving Code Agent,
SheetSense AI, IntelliGlove, InterviewPro, DiaPredict AI

Platforms: LinkedIn (3x/week), Twitter (2x/week), Hashnode blog (1x/week)

For each post include:
- Day and platform
- Topic/title
- Content type (devlog, tutorial, project showcase, insight)
- Key message

Make it realistic. Mix technical depth with personal journey."""
        return self.run(task)

    # ─── Publishers ───────────────────────────────────────────────────

    def publish_to_hashnode(self, title: str, content: str, tags: list = None) -> dict:
        if not self.hashnode_token or not self.hashnode_pub_id:
            return {"success": False, "error": "Hashnode token or publication ID missing in .env"}

        if tags is None:
            tags = ["python", "machinelearning", "ai", "llm", "programming"]

        query = """
mutation PublishPost($input: PublishPostInput!) {
  publishPost(input: $input) {
    post {
      id
      title
      url
    }
  }
}"""
        variables = {
            "input": {
                "title": title,
                "contentMarkdown": content,
                "publicationId": self.hashnode_pub_id,
                "tags": [{"slug": t, "name": t} for t in tags]
            }
        }

        try:
            response = requests.post(
                "https://gql.hashnode.com",
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": self.hashnode_token,
                    "Content-Type": "application/json"
                }
            )
            data = response.json()
            if "errors" in data:
                return {"success": False, "error": str(data["errors"])}
            post_url = data["data"]["publishPost"]["post"]["url"]
            return {"success": True, "url": post_url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_to_devto(self, title: str, content: str, tags: list = None) -> dict:
        if not self.devto_key:
            return {"success": False, "error": "DEVTO_API_KEY missing in .env"}

        if tags is None:
            tags = ["python", "machinelearning", "ai", "llm"]
    
        try:
            response = requests.post(
                "https://dev.to/api/articles",
                headers={
                    "api-key": self.devto_key,
                    "Content-Type": "application/json"
                },
                json={
                    "article": {
                        "title": title,
                        "body_markdown": content,
                        "published": True,
                        "tags": tags[:4]
                    }
                }
            )
            data = response.json()
            if "url" in data:
                return {"success": True, "url": data["url"]}
            return {"success": False, "error": str(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    # ─── Content Dashboard ────────────────────────────────────────────

    def content_dashboard(self) -> str:
        all_content = get_content()
        platforms = {}
        for c in all_content:
            platforms.setdefault(c["platform"], []).append(c)

        result = "📊 **Content Dashboard:**\n\n"
        result += f"Total pieces created: {len(all_content)}\n\n"

        platform_emoji = {
            "linkedin": "💼", "twitter": "🐦",
            "hashnode": "📝", "medium": "✍️"
        }

        for platform, posts in platforms.items():
            emoji = platform_emoji.get(platform, "📌")
            published = [p for p in posts if p["status"] == "published"]
            drafts = [p for p in posts if p["status"] == "draft"]
            result += f"{emoji} **{platform.capitalize()}:** {len(posts)} total | {len(published)} published | {len(drafts)} drafts\n"

        if all_content:
            result += "\n**Recent Content:**\n"
            for c in all_content[:5]:
                result += f"\n• [{c['platform'].upper()}] {c['title']}\n"
                result += f"  Status: {c['status']} | {c['created_at'][:10]}\n"
                if c["url"]: result += f"  🔗 {c['url']}\n"

        return result

    def handle(self, task: str) -> str:
        t = task.lower()

        if "linkedin post" in t:
            parts = task.replace("generate linkedin post", "").replace("linkedin post for", "").strip().split(",")
            project = parts[0].strip()
            achievement = parts[1].strip() if len(parts) > 1 else ""
            return self.generate_linkedin_post(project, achievement)

        elif "twitter thread" in t or "x thread" in t:
            parts = task.replace("generate twitter thread", "").replace("twitter thread for", "").strip().split(",")
            project = parts[0].strip()
            points = parts[1].strip() if len(parts) > 1 else ""
            return self.generate_twitter_thread(project, points)

        elif "blog post" in t or "hashnode" in t and "generate" in t:
            parts = task.replace("generate blog post", "").replace("blog post for", "").strip().split(",")
            project = parts[0].strip()
            details = parts[1].strip() if len(parts) > 1 else ""
            return self.generate_blog_post(project, details)

        elif "devlog" in t:
            parts = task.replace("generate devlog", "").replace("devlog", "").strip().split(",")
            day = int(''.join(filter(str.isdigit, parts[0]))) if parts[0] else 1
            built = parts[1].strip() if len(parts) > 1 else task
            challenges = parts[2].strip() if len(parts) > 2 else ""
            return self.generate_devlog(day, built, challenges)

        elif "content calendar" in t or "calendar" in t:
            weeks = 2
            nums = [int(s) for s in task.split() if s.isdigit()]
            if nums: weeks = nums[0]
            return self.content_calendar(weeks)

        elif "publish hashnode" in t:
            parts = task.replace("publish hashnode", "").strip().split(",")
            title = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            if not content:
                # Get latest draft
                drafts = get_content(platform="hashnode", status="draft")
                if drafts:
                    content = drafts[0]["content"]
                    title = drafts[0]["title"].replace("Blog: ", "")
            result = self.publish_to_hashnode(title, content)
            if result["success"]:
                return f"✅ Published to Hashnode!\n🔗 {result['url']}"
            return f"❌ Failed: {result['error']}"

        elif "publish devto" in t or "publish dev.to" in t or "publish dev" in t:
            parts = task.replace("publish devto", "").replace("publish dev", "").strip().split(",")
            title = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            if not content:
                drafts = get_content(platform="hashnode", status="draft")
                if drafts:
                    content = drafts[0]["content"]
                    title = drafts[0]["title"].replace("Blog: ", "")
            result = self.publish_to_devto(title, content)
            if result["success"]:
                return f"✅ Published to Dev.to!\n🔗 {result['url']}"
            return f"❌ Failed: {result['error']}"

        elif "seo" in t:
            parts = task.replace("generate seo", "").replace("seo for", "").strip().split(",")
            title = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            return self.generate_seo_tags(title, content)

        elif "content dashboard" in t or "my content" in t or "show content" in t:
            return self.content_dashboard()

        else:
            return self.run(task)