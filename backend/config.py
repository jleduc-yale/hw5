"""Model, API key, and cost limits for every agent on the team."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

BACKEND_DIR = Path(__file__).resolve().parent
HW_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"

# PORTKEY_API_KEY lives in the course-root .env (AI Foundations/.env). load_dotenv never overrides set values.
for folder in (BACKEND_DIR, HW_DIR, HW_DIR.parent):
    load_dotenv(folder / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# Every agent uses this one model through Portkey with PORTKEY_API_KEY. No other model or key is allowed.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_TIMEOUT_SECONDS = 90.0

# ---- Cost controls ---------------------------------------------------------
# Per-agent loop caps (each agent has its own loop and its own limits).
BOSS_LIMITS = UsageLimits(request_limit=20, tool_calls_limit=30, total_tokens_limit=150_000)
SPECIALIST_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=12, total_tokens_limit=50_000)
# gpt-6-luna is a reasoning model: it ignores temperature, so only output length is capped.
BOSS_SETTINGS = ModelSettings(max_tokens=4000)
SPECIALIST_SETTINGS = ModelSettings(max_tokens=2000)
OUTPUT_RETRIES = 2

# Team-wide caps across all agent loops in one run.
TEAM_TOKEN_BUDGET = 400_000
MAX_DELEGATIONS = 15
MAX_DELEGATION_DEPTH = 2  # boss (0) -> specialist (1) -> teammate consult (2); no deeper
APPROVAL_TIMEOUT_SECONDS = 900  # dashboard mode: how long an agent waits for a human decision on a payment


class ModelUnavailable(RuntimeError):
    pass


def build_model() -> OpenAIResponsesModel:
    """A fresh model instance for one agent: gpt-6-luna via Portkey, authenticated with PORTKEY_API_KEY.

    Uses the Responses API (/v1/responses): gpt-6-luna rejects function tools on
    /v1/chat/completions while reasoning is enabled.
    """
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise ModelUnavailable("PORTKEY_API_KEY is not set. Add it to the .env file in the course root.")
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL, timeout=MODEL_TIMEOUT_SECONDS)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()
