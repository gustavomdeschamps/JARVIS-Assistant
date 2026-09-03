"""JARVIS skills package.

A "skill" is a small, self-contained, pure-Python capability that does not
depend on Qt, PySide6, audio hardware, or Windows-only APIs. Skills are
what let JARVIS do useful work (math, unit conversion, notes, timers,
reminders, weather, long-term memory of facts about the user) without
round-tripping every single one of those things through the local LLM.

Keeping them here, instead of inline inside ``core/commands.py``, means:

- Each one is independently unit-testable (see ``tests/``) on any OS,
  without a microphone, without Windows, without Ollama even running.
- ``core/commands.py`` stays a thin router: it asks the brain what the
  user wants, then delegates to the matching skill and turns the result
  into a spoken sentence.
- New capabilities can be added by dropping a new module here and wiring
  a couple of lines into ``JarvisBrain.ACTIONS`` + ``CommandSystem``,
  instead of growing one giant file forever.
"""

from core.skills.calculator import CalculatorSkill
from core.skills.converter import ConverterSkill
from core.skills.notes import NotesSkill
from core.skills.scheduler import SchedulerSkill
from core.skills.weather import WeatherSkill

__all__ = [
    "CalculatorSkill",
    "ConverterSkill",
    "NotesSkill",
    "SchedulerSkill",
    "WeatherSkill",
]
