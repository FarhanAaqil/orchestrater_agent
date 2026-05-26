from github import Github
from agents.base_agent import BaseAgent
from config import GROQ_API_KEY, MODEL
import os
from dotenv import load_dotenv

load_dotenv()

class GitHubAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="github",
            system_prompt="""You are Aaqil's GitHub Agent. You help manage GitHub repos.
You generate professional READMEs, commit messages, and repo summaries.
Always be concise, technical, and professional."""
        )
        self.gh = Github(os.getenv("GITHUB_TOKEN"))
        self.user = self.gh.get_user()

    def get_repos(self):
        repos = self.user.get_repos()
        return [{"name": r.name, "description": r.description, "url": r.html_url, "language": r.language} for r in repos]

    def generate_readme(self, repo_name: str) -> str:
        try:
            repo = self.user.get_repo(repo_name)
            files = [f.path for f in repo.get_contents("")]
            task = f"""Generate a professional README.md for this GitHub repo:
Name: {repo.name}
Description: {repo.description}
Language: {repo.language}
Files: {files}
Stars: {repo.stargazers_count}

Include: Project title, description, features, tech stack, installation, usage, and author."""
            return self.run(task)
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_commit_message(self, changes: str) -> str:
        task = f"Generate a clean conventional commit message for these changes:\n{changes}"
        return self.run(task)

    def profile_summary(self) -> str:
        repos = self.get_repos()
        repo_list = "\n".join([f"- {r['name']} ({r['language']}): {r['description']}" for r in repos[:10]])
        task = f"""Summarize this GitHub profile for Farhan Aaqil:
Username: {self.user.login}
Public Repos: {self.user.public_repos}
Followers: {self.user.followers}
Repos:
{repo_list}

Give a professional summary and suggest improvements."""
        return self.run(task)

    def handle(self, task: str) -> str:
        t = task.lower()
        if "readme" in t:
            params = self.extract_intent(task, {
                "repo_name": "string, the GitHub repository name"
            })
            repo_name = params.get("repo_name")
            if not repo_name:
                # Fallback: try word-by-word
                words = task.split()
                stop_words = {"generate", "create", "make", "readme", "for", "the", "a", "my"}
                for word in words:
                    if word.lower() not in stop_words and len(word) > 2:
                        try:
                            return self.generate_readme(word)
                        except Exception:
                            continue
                return "Please specify a repo name. Example: 'generate readme for SheetSense'"
            return self.generate_readme(repo_name)

        elif "commit" in t:
            changes = task.replace("commit message for", "").replace("generate commit", "").strip()
            return self.generate_commit_message(changes)

        elif any(kw in t for kw in ["profile", "summary"]):
            return self.profile_summary()

        elif any(kw in t for kw in ["repos", "list", "my repos"]):
            repos = self.get_repos()
            return "\n".join([f"📁 {r['name']} — {r['language']} — {r['url']}" for r in repos])

        else:
            return self.run(task)