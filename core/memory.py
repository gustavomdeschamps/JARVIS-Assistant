"""Two kinds of memory JARVIS has: short-term conversation and long-term facts.

``ConversationMemory`` is the rolling window of the last few turns that
gets sent back to the LLM so it has conversational context ("e o segundo?"
referring to something said a moment ago). When the window grows past
``summary_trigger`` messages, the oldest ones are folded into a short
running summary instead of being silently forgotten — so very long
conversations don't lose the thread of what was discussed early on, while
the prompt sent to the (small, local) model stays bounded.

``LongTermMemory`` is a small persisted key/value store of facts about the
user ("o nome do usuário é Gustavo", "o usuário prefere o Chrome") that
survive across restarts of the app, backed by
:class:`core.persistence.JsonStore`.
"""

from collections import deque

from core.persistence import JsonStore

_MAX_SUMMARY_CHARS = 600


class ConversationMemory:
    def __init__(self, max_messages=10, summary_trigger=None):
        self.max_messages = max(2, int(max_messages))
        self.summary_trigger = int(summary_trigger or self.max_messages * 2)

        self._messages = deque()
        self._summary = ""

    # -----------------------------------------------------------
    # ADD
    # -----------------------------------------------------------

    def add_user(self, text):
        self._append("user", text)

    def add_assistant(self, text):
        self._append("assistant", text)

    def _append(self, role, text):
        if not text:
            return

        self._messages.append({"role": role, "content": str(text)})
        self._compact()

    def _compact(self):
        """Fold the oldest messages into ``self._summary`` once the window
        grows past ``summary_trigger``, then trim down to ``max_messages``.
        """

        if len(self._messages) <= self.summary_trigger:
            return

        overflow = len(self._messages) - self.max_messages

        for _ in range(max(0, overflow)):
            oldest = self._messages.popleft()
            self._fold_into_summary(oldest)

    def _fold_into_summary(self, message):
        role_label = "Usuário disse" if message["role"] == "user" else "Jarvis respondeu"
        snippet = message["content"].strip().replace("\n", " ")

        if len(snippet) > 80:
            snippet = snippet[:77] + "..."

        addition = f"{role_label}: {snippet}."

        combined = f"{self._summary} {addition}".strip() if self._summary else addition

        if len(combined) > _MAX_SUMMARY_CHARS:
            combined = combined[-_MAX_SUMMARY_CHARS:]
            # Avoid starting the summary mid-sentence.
            cut = combined.find(". ")
            if 0 <= cut < 200:
                combined = combined[cut + 2 :]

        self._summary = combined

    # -----------------------------------------------------------
    # READ
    # -----------------------------------------------------------

    def get_messages(self):
        return list(self._messages)

    def get_summary(self):
        return self._summary

    # -----------------------------------------------------------
    # CLEAR
    # -----------------------------------------------------------

    def clear(self):
        self._messages.clear()
        self._summary = ""


class LongTermMemory:
    """Persisted facts about the user, e.g. ``remember("nome", "Gustavo")``."""

    def __init__(self, path, max_facts=200):
        self.store = JsonStore(path, default={"facts": {}})
        self.max_facts = int(max_facts)

    def remember(self, key, value):
        key = str(key or "").strip().lower()
        value = str(value or "").strip()

        if not key or not value:
            return False

        def _mutate(data):
            facts = data.setdefault("facts", {})
            facts[key] = value

            if len(facts) > self.max_facts:
                # Drop the oldest-inserted fact (dicts keep insertion order).
                oldest_key = next(iter(facts))
                if oldest_key != key:
                    facts.pop(oldest_key, None)

            return data

        self.store.mutate(_mutate)
        return True

    def recall(self, key):
        key = str(key or "").strip().lower()
        return self.store.load().get("facts", {}).get(key)

    def recall_all(self):
        return dict(self.store.load().get("facts", {}))

    def forget(self, key):
        key = str(key or "").strip().lower()
        found = {"value": False}

        def _mutate(data):
            facts = data.setdefault("facts", {})
            if key in facts:
                del facts[key]
                found["value"] = True
            return data

        self.store.mutate(_mutate)
        return found["value"]

    def forget_all(self):
        def _mutate(data):
            data["facts"] = {}
            return data

        self.store.mutate(_mutate)

    def as_context_string(self, max_facts=20):
        facts = self.recall_all()
        if not facts:
            return ""

        items = list(facts.items())[-max_facts:]
        return "; ".join(f"{key}: {value}" for key, value in items)
