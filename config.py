import os
from dotenv import load_dotenv

load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FAST_MODEL = "llama-3.1-8b-instant"
SMART_MODEL = "llama-3.3-70b-versatile"
MODEL = FAST_MODEL
CHROMA_PATH = "./chroma_db"

AGENTS = {
    "github": "Handles GitHub repos, READMEs, commits",
    "linkedin": "Handles LinkedIn scraping and outreach",
    "job": "Handles job/internship search and apply",
    "project_manager": "Tracks tasks, deadlines, progress",
    "career": "Tracks skills, resume, interview prep",
    "growth": "Handles content posting and reach",
    "research": "Writes papers and finds publishers",
    "email": "Handles all outreach and follow-ups",
    "briefing": "Daily morning summary agent",
}