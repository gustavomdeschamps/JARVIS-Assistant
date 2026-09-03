"""Weather lookup via wttr.in — free, no API key required.

If ``city`` is empty, wttr.in resolves location from the caller's IP,
which conveniently gives "the weather here" without needing an API key or
asking the user where they are.

Results are cached on disk for a few minutes (see
``config.WEATHER_CACHE_MINUTES``) so repeated "e agora, como está o
tempo?" questions during a conversation don't hammer the network, and so
the assistant still has something to say (a slightly stale answer) if the
network briefly hiccups right after a successful lookup.
"""

import datetime

import requests

from core.persistence import JsonStore

_BASE_URL = "https://wttr.in/{city}"


class WeatherSkill:
    def __init__(self, cache_path, cache_minutes=20, timeout=6, session=None):
        self.cache = JsonStore(cache_path, default={})
        self.cache_minutes = float(cache_minutes)
        self.timeout = float(timeout)
        self.session = session or requests.Session()

    # -----------------------------------------------------------
    # PUBLIC
    # -----------------------------------------------------------

    def get(self, city=""):
        """Returns ``(ok, text)`` — a ready-to-speak Portuguese sentence."""

        key = str(city or "").strip().lower() or "__local__"

        cached = self._read_cache(key)
        if cached is not None:
            return True, cached

        try:
            payload = self._fetch(city)
        except Exception:
            return False, (
                "Não consegui buscar a previsão do tempo agora. "
                "Verifique sua conexão com a internet."
            )

        text = self._format(payload, city)
        self._write_cache(key, text)
        return True, text

    # -----------------------------------------------------------
    # NETWORK
    # -----------------------------------------------------------

    def _fetch(self, city):
        url = _BASE_URL.format(city=requests.utils.quote(str(city or "")))
        response = self.session.get(
            url,
            params={"format": "j1", "lang": "pt"},
            timeout=self.timeout,
            headers={"User-Agent": "curl/8.0"},
        )
        response.raise_for_status()
        return response.json()

    def _format(self, payload, city):
        try:
            current = payload["current_condition"][0]
            temperature = current["temp_C"]
            feels_like = current["FeelsLikeC"]
            humidity = current["humidity"]
            description = (
                current.get("lang_pt", [{}])[0].get("value")
                or current["weatherDesc"][0]["value"]
            )
        except (KeyError, IndexError, TypeError):
            return "Não consegui interpretar a previsão do tempo agora."

        place = f" em {city}" if city else ""

        return (
            f"Agora{place} está {description.lower()}, "
            f"{temperature} graus, sensação térmica de {feels_like} graus "
            f"e umidade de {humidity} por cento."
        )

    # -----------------------------------------------------------
    # CACHE
    # -----------------------------------------------------------

    def _read_cache(self, key):
        entry = self.cache.load().get(key)
        if not entry:
            return None

        try:
            cached_at = datetime.datetime.fromisoformat(entry["cached_at"])
        except (KeyError, ValueError):
            return None

        age_minutes = (datetime.datetime.now() - cached_at).total_seconds() / 60.0
        if age_minutes > self.cache_minutes:
            return None

        return entry.get("text")

    def _write_cache(self, key, text):
        def _mutate(data):
            data[key] = {
                "text": text,
                "cached_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            return data

        self.cache.mutate(_mutate)
