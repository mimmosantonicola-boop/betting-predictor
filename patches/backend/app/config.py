import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from backend/app/)
_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")

# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")

# ── Local memory (replaces Zep Cloud) ────────────────────────────────────────
LOCAL_ZEP_DB_PATH = os.environ.get(
    "LOCAL_ZEP_DB_PATH",
    str(_root / "data" / "local_memory.db")
)

# ── File upload ───────────────────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {"pdf", "md", "txt"}
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# ── Simulation ────────────────────────────────────────────────────────────────
OASIS_MAX_ROUNDS = int(os.environ.get("OASIS_MAX_ROUNDS", "10"))
TWITTER_ACTIONS = [
    "like_post", "retweet_post", "create_post",
    "follow_user", "unfollow_user", "mute_user",
    "unmute_user", "create_comment",
]
REDDIT_ACTIONS = [
    "like_post", "dislike_post", "create_post",
    "follow_user", "unfollow_user", "create_comment",
]

# ── Report agent ──────────────────────────────────────────────────────────────
REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS", "30"))
REPORT_AGENT_REFLECTION_ROUNDS = int(os.environ.get("REPORT_AGENT_REFLECTION_ROUNDS", "2"))


def validate() -> list[str]:
    """Return list of configuration errors (empty = OK)."""
    errors = []
    if not LLM_API_KEY:
        errors.append(
            "LLM_API_KEY is missing. "
            "Get a free Groq key at https://console.groq.com and add it to .env"
        )
    return errors
 class Config:
      """Flask-compatible config class expected by MiroFish's app factory."""
      # LLM
      LLM_API_KEY = LLM_API_KEY
      LLM_BASE_URL = LLM_BASE_URL
      LLM_MODEL_NAME = LLM_MODEL_NAME

      # Local memory
      LOCAL_ZEP_DB_PATH = LOCAL_ZEP_DB_PATH

      # File upload
      MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
      ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS
      CHUNK_SIZE = CHUNK_SIZE
      CHUNK_OVERLAP = CHUNK_OVERLAP

      # Simulation
      OASIS_MAX_ROUNDS = OASIS_MAX_ROUNDS
      TWITTER_ACTIONS = TWITTER_ACTIONS
      REDDIT_ACTIONS = REDDIT_ACTIONS

      # Report agent
      REPORT_AGENT_MAX_TOOL_CALLS = REPORT_AGENT_MAX_TOOL_CALLS
      REPORT_AGENT_REFLECTION_ROUNDS = REPORT_AGENT_REFLECTION_ROUNDS
