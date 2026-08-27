from pathlib import Path


# ============================================================
# PASTAS
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent


DATA_DIR = (
    PROJECT_ROOT
    /
    "data"
)


DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# OLLAMA
# ============================================================

OLLAMA_URL = (
    "http://127.0.0.1:11434/api/chat"
)


OLLAMA_TAGS_URL = (
    "http://127.0.0.1:11434/api/tags"
)


# Modelo menor e mais rápido.
PRIMARY_MODEL = (
    "qwen3:1.7b"
)


# Modelo que você já possui.
FALLBACK_MODEL = (
    "qwen2.5:3b"
)


# Mantém o modelo na RAM.
OLLAMA_KEEP_ALIVE = -1


OLLAMA_TIMEOUT = 35


# ============================================================
# IA
# ============================================================

ROUTER_CONTEXT_SIZE = 2048

ROUTER_MAX_TOKENS = 180

ROUTER_TEMPERATURE = 0.0


# ============================================================
# CONVERSA
# ============================================================

CONVERSATION_MEMORY_MESSAGES = 8

CONVERSATION_ACTIVE_SECONDS = 35


# ============================================================
# CACHE
# ============================================================

APP_CACHE_HOURS = 6

SYSTEM_CACHE_MINUTES = 10


# ============================================================
# CONTEXTO
# ============================================================

MAX_APPS_IN_CONTEXT = 70

MAX_RESPONSE_CHARS = 700