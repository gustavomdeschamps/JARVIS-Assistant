"""Central configuration for JARVIS.

Every setting here can be overridden with an environment variable prefixed
``JARVIS_`` without touching this file — handy for running two profiles
(e.g. a fast tiny model on a laptop, a bigger one on a desktop), for CI,
or for tests. Env vars always win over the defaults below.

Example (PowerShell):
    $env:JARVIS_PRIMARY_MODEL = "llama3.2:3b"
    $env:JARVIS_LOG_LEVEL = "DEBUG"
    python main.py
"""

import os
from pathlib import Path


# ============================================================
# ENV HELPERS
# ============================================================

def _env(name, default):
    return os.environ.get(f"JARVIS_{name}", default)


def _env_str(name, default):
    return str(_env(name, default))


def _env_int(name, default):
    try:
        return int(_env(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(_env(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name, default):
    value = _env(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


# ============================================================
# PASTAS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = Path(_env_str("DATA_DIR", str(PROJECT_ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = DATA_DIR / "logs"

# Arquivos de estado persistente das skills / memória de longo prazo.
NOTES_FILE = DATA_DIR / "notes.json"
SCHEDULE_FILE = DATA_DIR / "schedule.json"
FACTS_FILE = DATA_DIR / "user_facts.json"
WEATHER_CACHE_FILE = DATA_DIR / "weather_cache.json"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"


# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = _env_str("LOG_LEVEL", "INFO")

LOG_TO_FILE = _env_bool("LOG_TO_FILE", True)


# ============================================================
# OLLAMA
# ============================================================

OLLAMA_HOST = _env_str("OLLAMA_HOST", "127.0.0.1")

OLLAMA_PORT = _env_int("OLLAMA_PORT", 11434)

OLLAMA_URL = _env_str(
    "OLLAMA_URL",
    f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat",
)

OLLAMA_TAGS_URL = _env_str(
    "OLLAMA_TAGS_URL",
    f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags",
)

OLLAMA_PULL_URL = _env_str(
    "OLLAMA_PULL_URL",
    f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/pull",
)

# Modelo menor e mais rápido — usado para roteamento de intenção.
PRIMARY_MODEL = _env_str("PRIMARY_MODEL", "qwen3:1.7b")

# Modelo de fallback caso o primário não esteja instalado no Ollama.
FALLBACK_MODEL = _env_str("FALLBACK_MODEL", "qwen2.5:3b")

# Mantém o modelo carregado na RAM (evita recarregar a cada frase).
OLLAMA_KEEP_ALIVE = _env_int("OLLAMA_KEEP_ALIVE", -1)

OLLAMA_TIMEOUT = _env_float("OLLAMA_TIMEOUT", 35)

# Quantas vezes tentar de novo uma chamada ao Ollama antes de desistir,
# e o tempo de espera inicial entre tentativas (dobra a cada tentativa).
BRAIN_MAX_RETRIES = _env_int("BRAIN_MAX_RETRIES", 2)

BRAIN_RETRY_BACKOFF_SECONDS = _env_float("BRAIN_RETRY_BACKOFF_SECONDS", 0.6)


# ============================================================
# IA / ROTEADOR
# ============================================================

ROUTER_CONTEXT_SIZE = _env_int("ROUTER_CONTEXT_SIZE", 4096)

ROUTER_MAX_TOKENS = _env_int("ROUTER_MAX_TOKENS", 220)

ROUTER_TEMPERATURE = _env_float("ROUTER_TEMPERATURE", 0.0)


# ============================================================
# CONVERSA / MEMÓRIA
# ============================================================

CONVERSATION_MEMORY_MESSAGES = _env_int("CONVERSATION_MEMORY_MESSAGES", 12)

CONVERSATION_ACTIVE_SECONDS = _env_float("CONVERSATION_ACTIVE_SECONDS", 35)

# Quando o histórico de curto prazo passa deste número de mensagens, as
# mensagens mais antigas são condensadas num resumo de uma linha em vez de
# simplesmente descartadas (ver core/memory.py).
MEMORY_SUMMARY_TRIGGER = _env_int("MEMORY_SUMMARY_TRIGGER", 20)

# Quantos fatos de longo prazo ("o usuário se chama Gustavo", "prefere
# Chrome", ...) manter sobre o usuário.
MAX_LONG_TERM_FACTS = _env_int("MAX_LONG_TERM_FACTS", 200)


# ============================================================
# CACHE
# ============================================================

APP_CACHE_HOURS = _env_float("APP_CACHE_HOURS", 6)

SYSTEM_CACHE_MINUTES = _env_float("SYSTEM_CACHE_MINUTES", 10)

WEATHER_CACHE_MINUTES = _env_float("WEATHER_CACHE_MINUTES", 20)


# ============================================================
# CONTEXTO
# ============================================================

MAX_APPS_IN_CONTEXT = _env_int("MAX_APPS_IN_CONTEXT", 70)

MAX_RESPONSE_CHARS = _env_int("MAX_RESPONSE_CHARS", 700)


# ============================================================
# SKILLS: TIMERS / LEMBRETES
# ============================================================

# Intervalo (segundos) em que a thread de agendador verifica se algum
# timer/lembrete venceu.
SCHEDULER_POLL_SECONDS = _env_float("SCHEDULER_POLL_SECONDS", 1.0)

MAX_ACTIVE_SCHEDULE_ITEMS = _env_int("MAX_ACTIVE_SCHEDULE_ITEMS", 50)


# ============================================================
# SEGURANÇA: AÇÕES DESTRUTIVAS
# ============================================================

# Palavra que o usuário precisa dizer/digitar para confirmar uma ação
# destrutiva (desligar, reiniciar o computador). Case-insensitive,
# sem acentuação (ver core/windows_controller.py normalize()).
CONFIRMATION_WORD = _env_str("CONFIRMATION_WORD", "confirmar")

CANCEL_WORD = _env_str("CANCEL_WORD", "cancelar")

# Quanto tempo (segundos) uma confirmação pendente continua válida antes
# de expirar automaticamente por segurança.
CONFIRMATION_TIMEOUT_SECONDS = _env_float("CONFIRMATION_TIMEOUT_SECONDS", 20)

# Ações que exigem confirmação explícita antes de executar.
DESTRUCTIVE_TARGETS = ("shutdown", "restart")
