import os
from dotenv import load_dotenv

load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY is not set in .env")

FAST_MODEL = "llama-3.1-8b-instant"
SMART_MODEL = "llama-3.3-70b-versatile"
MODEL = FAST_MODEL

CHROMA_PATH = "./chroma_db"

# ─── Feature Flags ────────────────────────────────────────────────
# Set to False to skip the second self-reflection LLM call per response.
# Disabling halves API costs and latency significantly.
ENABLE_SELF_REFLECTION = os.getenv("ENABLE_SELF_REFLECTION", "true").lower() == "true"

# ─── Personal Details (from .env — never hardcode PII in source) ──
PERSONAL_NAME   = os.getenv("PERSONAL_NAME", "Farhan Aaqil")
PERSONAL_EMAIL  = os.getenv("EMAIL_ADDRESS", "fadurrani543@gmail.com")
AFFILIATION     = os.getenv("AFFILIATION", "Jayaprakash Narayan College of Engineering, Mahbubnagar, Telangana, India")
DEPARTMENT      = os.getenv("DEPARTMENT", "Artificial Intelligence and Machine Learning")

# ─── Model Selection ──────────────────────────────────────────────

def get_model(tier: str = "fast") -> str:
    """
    Centralised model resolver.
    tier: 'fast' (default) | 'smart' | 'selected' (honours UI override)
    """
    if tier == "selected":
        return os.getenv("SELECTED_SMART_MODEL", SMART_MODEL)
    if tier == "smart":
        return SMART_MODEL
    return FAST_MODEL

# ─── Agent Registry ───────────────────────────────────────────────
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