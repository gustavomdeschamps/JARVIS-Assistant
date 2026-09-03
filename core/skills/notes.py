"""Quick voice notes: "anote que preciso comprar leite", "minhas notas", ...

Persisted as JSON via :class:`core.persistence.JsonStore` so notes survive
restarts. Deliberately dumb and text-only — this is a scratchpad, not a
database.
"""

import datetime

from core.persistence import JsonStore


class NotesSkill:
    def __init__(self, path):
        self.store = JsonStore(path, default={"next_id": 1, "notes": []})

    # -----------------------------------------------------------
    # ADD
    # -----------------------------------------------------------

    def add(self, text):
        text = str(text or "").strip()
        if not text:
            return None

        def _mutate(data):
            note_id = data.get("next_id", 1)
            note = {
                "id": note_id,
                "text": text,
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            data.setdefault("notes", []).append(note)
            data["next_id"] = note_id + 1
            return data

        data = self.store.mutate(_mutate)
        return data["notes"][-1]

    # -----------------------------------------------------------
    # LIST
    # -----------------------------------------------------------

    def list(self, limit=None):
        notes = list(self.store.load().get("notes", []))
        notes.sort(key=lambda note: note.get("id", 0), reverse=True)

        if limit:
            notes = notes[:limit]

        return notes

    # -----------------------------------------------------------
    # DELETE
    # -----------------------------------------------------------

    def delete(self, note_id):
        note_id = int(note_id)
        removed = {"found": False}

        def _mutate(data):
            notes = data.get("notes", [])
            new_notes = [note for note in notes if note.get("id") != note_id]
            removed["found"] = len(new_notes) != len(notes)
            data["notes"] = new_notes
            return data

        self.store.mutate(_mutate)
        return removed["found"]

    def delete_last(self):
        notes = self.list(limit=1)
        if not notes:
            return None
        self.delete(notes[0]["id"])
        return notes[0]

    def clear(self):
        def _mutate(data):
            data["notes"] = []
            return data

        self.store.mutate(_mutate)

    def count(self):
        return len(self.store.load().get("notes", []))
