"""CommandSystem: turns a JarvisBrain decision into something that actually
happens, and into a sentence JARVIS can say back.

The flow for every user utterance is:

    text -> (confirmation check) -> brain.understand(text) -> route(action)
         -> perform side effect via a skill / WindowsController
         -> speak the result -> remember the turn

Two responsibilities live specifically in this module rather than in the
brain:

1. **Skill wiring.** Calculator, unit converter, notes, timers/reminders
   and weather are deterministic, testable, non-LLM pieces of logic. The
   brain only decides *that* the user wants a calculation; this module
   asks the calculator for the actual number.

2. **Destructive-action confirmation.** Shutting down or restarting the
   PC can lose unsaved work, so those two power actions are never
   executed on the first pass — JARVIS asks for an explicit spoken/typed
   confirmation word first. That check happens *before* the next
   utterance is even sent to the LLM, so it can never be talked around by
   a clever prompt, and it auto-expires after a short timeout so an old
   "sim" from an unrelated later sentence can't accidentally trigger it.
"""

import datetime
import os
import random
import time

from config import (
    CANCEL_WORD,
    CONFIRMATION_TIMEOUT_SECONDS,
    CONFIRMATION_WORD,
    DESTRUCTIVE_TARGETS,
    MAX_ACTIVE_SCHEDULE_ITEMS,
    NOTES_FILE,
    SCHEDULE_FILE,
    SCHEDULER_POLL_SECONDS,
    WEATHER_CACHE_FILE,
    WEATHER_CACHE_MINUTES,
)
from core.app_finder import AppFinder
from core.brain import JarvisBrain
from core.logger import get_logger
from core.skills import CalculatorSkill, ConverterSkill, NotesSkill, SchedulerSkill, WeatherSkill
from core.system_scanner import SystemScanner
from core.windows_controller import WindowsController

logger = get_logger(__name__)

_WEEKDAYS_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

_MONTHS_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

_ALL_WORD = ("todos", "todas", "tudo")
_LAST_WORD = ("ultima", "ultimo", "última", "último")


class CommandSystem:
    def __init__(self, voice, scanner=None, app_finder=None, brain=None):
        self.voice = voice

        self.scanner = scanner or SystemScanner()
        self.app_finder = app_finder or AppFinder()
        self.windows = WindowsController(self.app_finder)

        self.brain = brain or JarvisBrain(self.scanner, self.app_finder)

        # -----------------------------------------------------------
        # SKILLS
        # -----------------------------------------------------------

        self.calculator = CalculatorSkill()
        self.converter = ConverterSkill()
        self.notes = NotesSkill(NOTES_FILE)
        self.weather = WeatherSkill(WEATHER_CACHE_FILE, cache_minutes=WEATHER_CACHE_MINUTES)

        self.scheduler = SchedulerSkill(
            SCHEDULE_FILE,
            poll_seconds=SCHEDULER_POLL_SECONDS,
            max_active_items=MAX_ACTIVE_SCHEDULE_ITEMS,
        )
        self.scheduler.start(self._on_schedule_due)

        # -----------------------------------------------------------
        # STATE
        # -----------------------------------------------------------

        self.last_response = ""
        self.pending_confirmation = None

    # =========================================================
    # RESPONSE
    # =========================================================

    def respond(self, text):
        if text:
            self.voice.speak(text)

        return {"text": text, "exit": False}

    # =========================================================
    # SCHEDULER CALLBACK (runs on the background poller thread)
    # =========================================================

    def _on_schedule_due(self, item):
        if item.get("kind") == "timer":
            label = item.get("label") or ""
            suffix = f' "{label}"' if label else ""
            message = f"Seu temporizador{suffix} terminou."
        else:
            message = f"Lembrete: {item.get('label') or 'você pediu para eu te lembrar de algo.'}"

        logger.info("Item agendado venceu: %s", message)

        try:
            self.voice.speak(message)
        except Exception as error:
            logger.warning("Falha ao falar item agendado: %s", error)

    def shutdown(self):
        """Stop background work cleanly (called on app close)."""

        try:
            self.scheduler.stop()
        except Exception:
            pass

    # =========================================================
    # SYSTEM INFO (via SystemScanner — dados reais do notebook)
    # =========================================================

    def _system_info(self, target):
        target = str(target or "device").lower().strip()
        data = self.scanner.detailed_summary()

        if target in ["device", "notebook", "pc", "computer", "computador"]:
            maker = data.get("manufacturer") or ""
            model = data.get("model") or ""
            cpu = data.get("cpu", {}).get("name") or "processador não identificado"
            ram = data.get("ram_total_gb")
            gpu = ", ".join(data.get("gpus") or []) or "GPU não identificada"

            return (
                f"Este notebook é {maker} {model}. Tem {cpu}, "
                f"{ram} gigabytes de RAM e {gpu}."
            )

        if target in ["ram", "memoria", "memória"]:
            return (
                f"Você tem {data.get('ram_total_gb')} gigabytes de RAM "
                f"e o uso atual está em {data.get('ram_percent')} por cento."
            )

        if target in ["cpu", "processador"]:
            cpu = data.get("cpu", {})
            return (
                f"O processador é {cpu.get('name')}. "
                f"O uso atual está em {data.get('cpu_percent')} por cento."
            )

        if target in ["gpu", "video", "vídeo", "placa de video", "placa de vídeo"]:
            gpus = data.get("gpus") or []
            if not gpus:
                return "Não consegui identificar a GPU deste notebook."
            return "As GPUs identificadas são: " + ", ".join(gpus) + "."

        if target in ["battery", "bateria"]:
            percent = data.get("battery_percent")
            if percent is None:
                return "O Windows não forneceu informações de bateria."

            state = (
                "e está ligado na tomada"
                if data.get("battery_plugged")
                else "e está usando a bateria"
            )
            return f"A bateria está em {percent} por cento {state}."

        if target in ["disk", "disco", "ssd", "armazenamento", "espaco", "espaço"]:
            disks = data.get("disks") or []
            if not disks:
                return "Não consegui ler os discos do computador."

            parts = [
                f"{disk.get('mountpoint')} com {disk.get('free_gb')} gigabytes "
                f"livres de {disk.get('total_gb')}"
                for disk in disks[:3]
            ]
            return "Armazenamento: " + "; ".join(parts) + "."

        if target in ["os", "windows", "sistema"]:
            os_data = data.get("os", {})
            return (
                f"O sistema é {os_data.get('name')} {os_data.get('release')} "
                f"em arquitetura {os_data.get('architecture')}."
            )

        if target in ["apps", "aplicativos", "programas"]:
            names = self.app_finder.names(18)
            return (
                f"Eu tenho {len(self.app_finder.apps)} entradas de aplicativos "
                f"indexadas. Alguns deles são: {', '.join(names)}."
            )

        return "Não identifiquei qual informação do notebook você quer."

    # =========================================================
    # CONFIRMAÇÃO DE AÇÕES DESTRUTIVAS
    # =========================================================

    def _confirmation_pending_and_expired(self):
        return time.monotonic() > self.pending_confirmation.get("expires_at", 0)

    def _try_consume_confirmation(self, text):
        """If a destructive action is awaiting confirmation, handle `text`
        as the confirm/cancel answer instead of sending it to the LLM.

        Returns the final spoken response if it consumed the text, or
        ``None`` if there was nothing pending (or it expired) and normal
        routing through the brain should proceed.
        """

        if not self.pending_confirmation:
            return None

        if self._confirmation_pending_and_expired():
            self.pending_confirmation = None
            return None

        normalized = self.windows.normalize(text)

        if normalized == self.windows.normalize(CONFIRMATION_WORD):
            target = self.pending_confirmation["target"]
            self.pending_confirmation = None
            return self._perform_power_action(target, confirmed=True)

        if normalized == self.windows.normalize(CANCEL_WORD) or normalized in (
            "nao",
            "não",
            "cancela",
        ):
            self.pending_confirmation = None
            return "Tudo bem, cancelei."

        # Não foi nem confirmação nem cancelamento: descarta a pendência
        # por segurança e deixa o texto seguir o fluxo normal.
        self.pending_confirmation = None
        return None

    def _perform_power_action(self, target, confirmed=False):
        action_words = {
            "shutdown": ("desligar", "Desligando"),
            "restart": ("reiniciar", "Reiniciando"),
        }

        verb, gerund = action_words.get(target, ("executar", "Executando"))
        success = self.windows.power_action(target)

        if success:
            return f"{gerund} o computador agora."
        return f"Não consegui {verb} o computador."

    def _handle_system_power(self, target, reply):
        target = self.windows.normalize(target)

        if target not in self.windows.POWER_ACTIONS:
            return reply or "Não entendi qual ação de energia você quer."

        if target in DESTRUCTIVE_TARGETS:
            self.pending_confirmation = {
                "target": target,
                "expires_at": time.monotonic() + CONFIRMATION_TIMEOUT_SECONDS,
            }
            verb = "desligar" if target == "shutdown" else "reiniciar"
            return (
                f"Tem certeza que quer {verb} o computador? "
                f"Diga '{CONFIRMATION_WORD}' para confirmar "
                f"ou '{CANCEL_WORD}' para cancelar."
            )

        if target == "lock":
            success = self.windows.power_action(target)
            return reply or ("Tela bloqueada." if success else "Não consegui bloquear a tela.")

        if target == "sleep":
            success = self.windows.power_action(target)
            return reply or (
                "Suspendendo o computador." if success else "Não consegui suspender o computador."
            )

        return reply or "Não entendi qual ação de energia você quer."

    # =========================================================
    # DATA / HORA
    # =========================================================

    def _tell_time(self):
        now = datetime.datetime.now()
        return f"Agora são {now.strftime('%H:%M')}."

    def _tell_date(self):
        now = datetime.datetime.now()
        weekday = _WEEKDAYS_PT[now.weekday()]
        month = _MONTHS_PT[now.month - 1]
        return f"Hoje é {weekday}, {now.day} de {month} de {now.year}."

    # =========================================================
    # EXECUTE
    # =========================================================

    def execute(self, user_text):
        text = str(user_text or "").strip()

        if not text:
            return self.respond("")

        confirmation_response = self._try_consume_confirmation(text)
        if confirmation_response is not None:
            self.last_response = confirmation_response
            return self.respond(confirmation_response)

        decision = self.brain.understand(text)

        action = decision["action"]
        target = decision["target"]
        query = decision["query"]
        amount = decision["amount"]
        reply = decision["reply"]

        final = self._route(action, target, query, amount, reply)

        self.brain.remember(text, final)
        self.last_response = final

        return self.respond(final)

    # =========================================================
    # ROUTER
    # =========================================================

    def _route(self, action, target, query, amount, reply):
        handler = getattr(self, f"_action_{action}", None)

        if handler is None:
            return reply or "Entendi sua fala, mas não tenho uma ação segura para esse pedido."

        try:
            return handler(target, query, amount, reply)
        except Exception as error:
            logger.error("Ação '%s' falhou: %s", action, error)
            return reply or "Algo deu errado ao tentar fazer isso."

    # -----------------------------------------------------------
    # APLICATIVOS / JANELAS
    # -----------------------------------------------------------

    def _action_open_app(self, target, query, amount, reply):
        success = self.windows.open_app(target)
        if success:
            return reply or random.choice(["Pronto.", "Feito.", "Já abri."])
        return f"Não encontrei {target} neste notebook."

    def _action_close_app(self, target, query, amount, reply):
        success = self.windows.close_app(target)
        if success:
            return reply or "Fechado."
        return f"Não encontrei {target} em execução."

    def _action_open_site(self, target, query, amount, reply):
        if self.windows.open_site(target):
            return reply or "Pronto."

        self.windows.search_web(target)
        return f"Não achei um endereço direto para {target}, então pesquisei para você."

    def _action_open_folder(self, target, query, amount, reply):
        path = self.scanner.get_folder(target)

        if path:
            try:
                os.startfile(path)
                success = True
            except Exception:
                success = False
        else:
            success = self.windows.open_folder(target)

        if success:
            return reply or "Pronto."
        return f"Não encontrei a pasta {target}."

    def _action_open_settings(self, target, query, amount, reply):
        if self.windows.open_settings():
            return "Pronto."
        return "Não consegui abrir as configurações."

    def _action_search_web(self, target, query, amount, reply):
        success = self.windows.search_web(query or target)
        if success:
            return reply or "Pesquisando."
        return "Não identifiquei o que pesquisar."

    def _action_search_youtube(self, target, query, amount, reply):
        success = self.windows.search_youtube(query or target)
        if success:
            return reply or "Procurando no YouTube."
        return "Não identifiquei o que procurar."

    # -----------------------------------------------------------
    # VOLUME / MÍDIA
    # -----------------------------------------------------------

    def _action_volume_up(self, target, query, amount, reply):
        self.windows.volume_up(amount or 4)
        return reply or "Pronto."

    def _action_volume_down(self, target, query, amount, reply):
        self.windows.volume_down(amount or 4)
        return reply or "Pronto."

    def _action_volume_mute(self, target, query, amount, reply):
        self.windows.volume_mute()
        return reply or "Pronto."

    def _action_media_play_pause(self, target, query, amount, reply):
        self.windows.media_play_pause()
        return reply or "Pronto."

    def _action_media_next(self, target, query, amount, reply):
        self.windows.media_next()
        return reply or "Pronto."

    def _action_media_previous(self, target, query, amount, reply):
        self.windows.media_previous()
        return reply or "Pronto."

    # -----------------------------------------------------------
    # SISTEMA
    # -----------------------------------------------------------

    def _action_system_info(self, target, query, amount, reply):
        return self._system_info(target)

    def _action_system_power(self, target, query, amount, reply):
        return self._handle_system_power(target, reply)

    def _action_set_brightness(self, target, query, amount, reply):
        success = self.windows.set_brightness(amount)
        if success:
            return reply or f"Brilho ajustado para {amount} por cento."
        return "Não consegui ajustar o brilho da tela."

    def _action_take_screenshot(self, target, query, amount, reply):
        path = self.windows.take_screenshot()
        if path:
            return reply or "Print salvo."
        return "Não consegui capturar a tela."

    def _action_refresh_inventory(self, target, query, amount, reply):
        self.scanner.scan(force=True)
        total = self.app_finder.rebuild_index()
        return f"Atualizei o inventário do notebook e indexei {total} entradas de aplicativos."

    # -----------------------------------------------------------
    # CALCULADORA / CONVERSOR / CLIMA
    # -----------------------------------------------------------

    def _action_calculate(self, target, query, amount, reply):
        ok, result = self.calculator.evaluate(query or target)
        if ok:
            return f"O resultado é {result}."
        return result

    def _action_convert_units(self, target, query, amount, reply):
        ok, sentence = self.converter.describe(query or target)
        return sentence

    def _action_get_weather(self, target, query, amount, reply):
        ok, text = self.weather.get(target)
        return text

    # -----------------------------------------------------------
    # NOTAS
    # -----------------------------------------------------------

    def _action_add_note(self, target, query, amount, reply):
        text = (query or target).strip()
        if not text:
            return "O que você quer que eu anote?"

        self.notes.add(text)
        return reply or f"Anotado: {text}."

    def _action_list_notes(self, target, query, amount, reply):
        notes = self.notes.list(limit=amount or 5)
        if not notes:
            return "Você não tem nenhuma nota salva."

        items = "; ".join(f"{note['id']}: {note['text']}" for note in notes)
        return f"Suas notas mais recentes: {items}."

    def _action_delete_note(self, target, query, amount, reply):
        if self.windows.normalize(target) in _LAST_WORD:
            note = self.notes.delete_last()
            if note:
                return f"Apaguei a nota: {note['text']}."
            return "Você não tem notas para apagar."

        if amount:
            if self.notes.delete(amount):
                return "Nota apagada."
            return "Não encontrei essa nota."

        return "Diga o número da nota, ou 'a última', para eu apagar."

    # -----------------------------------------------------------
    # TIMERS
    # -----------------------------------------------------------

    def _action_set_timer(self, target, query, amount, reply):
        minutes = amount or 0
        if minutes <= 0:
            return "Por quantos minutos você quer o temporizador?"

        item, over_limit = self.scheduler.create_timer(minutes, label=query)
        if over_limit:
            return "Você já tem temporizadores demais ativos. Cancele algum antes."

        label_part = f' "{query}"' if query else ""
        return reply or f"Temporizador{label_part} de {minutes} minutos criado."

    def _action_list_timers(self, target, query, amount, reply):
        items = self.scheduler.list_active(kind="timer")
        if not items:
            return "Você não tem temporizadores ativos."

        parts = [
            f"{item['id']}: {self.scheduler.remaining_minutes(item)} minutos restantes"
            for item in items
        ]
        return "Temporizadores ativos: " + "; ".join(parts) + "."

    def _action_cancel_timer(self, target, query, amount, reply):
        if self.windows.normalize(target) in _ALL_WORD:
            count = self.scheduler.cancel_all(kind="timer")
            return f"Cancelei {count} temporizadores."

        if amount and self.scheduler.cancel(amount):
            return "Temporizador cancelado."

        return "Não encontrei esse temporizador. Diga o número, ou 'todos'."

    # -----------------------------------------------------------
    # LEMBRETES
    # -----------------------------------------------------------

    def _action_set_reminder(self, target, query, amount, reply):
        minutes = amount or 0
        text = (query or target).strip()

        if minutes <= 0:
            return "Em quantos minutos você quer o lembrete?"
        if not text:
            return "O que você quer que eu te lembre?"

        item, over_limit = self.scheduler.create_reminder(minutes, text)
        if over_limit:
            return "Você já tem lembretes demais pendentes. Cancele algum antes."

        return reply or f"Vou te lembrar em {minutes} minutos: {text}."

    def _action_list_reminders(self, target, query, amount, reply):
        items = self.scheduler.list_active(kind="reminder")
        if not items:
            return "Você não tem lembretes pendentes."

        parts = [
            f"{item['id']}: {item['label']} (em {self.scheduler.remaining_minutes(item)} minutos)"
            for item in items
        ]
        return "Lembretes pendentes: " + "; ".join(parts) + "."

    def _action_cancel_reminder(self, target, query, amount, reply):
        if self.windows.normalize(target) in _ALL_WORD:
            count = self.scheduler.cancel_all(kind="reminder")
            return f"Cancelei {count} lembretes."

        if amount and self.scheduler.cancel(amount):
            return "Lembrete cancelado."

        return "Não encontrei esse lembrete. Diga o número, ou 'todos'."

    # -----------------------------------------------------------
    # MEMÓRIA DE LONGO PRAZO
    # -----------------------------------------------------------

    def _action_remember_fact(self, target, query, amount, reply):
        key = target.strip()
        value = query.strip()

        if not key or not value:
            return "Preciso saber o que lembrar e sobre o quê."

        self.brain.long_term.remember(key, value)
        return reply or f"Vou lembrar que {key} é {value}."

    def _action_recall_fact(self, target, query, amount, reply):
        key = target.strip()
        value = self.brain.long_term.recall(key) if key else None

        if value:
            return f"{key}: {value}."
        return f"Não tenho nada guardado sobre {key or 'isso'}."

    def _action_forget_fact(self, target, query, amount, reply):
        if self.windows.normalize(target) in _ALL_WORD:
            self.brain.long_term.forget_all()
            return "Esqueci todos os fatos guardados sobre você."

        if self.brain.long_term.forget(target):
            return "Esqueci isso."
        return "Não tinha isso guardado."

    # -----------------------------------------------------------
    # DIVERSOS
    # -----------------------------------------------------------

    def _action_tell_time(self, target, query, amount, reply):
        return self._tell_time()

    def _action_tell_date(self, target, query, amount, reply):
        return self._tell_date()

    def _action_clear_memory(self, target, query, amount, reply):
        self.brain.clear_memory()
        return "Esqueci o histórico recente da nossa conversa."

    def _action_repeat_last(self, target, query, amount, reply):
        return self.last_response or "Ainda não disse nada para repetir."

    def _action_help(self, target, query, amount, reply):
        return reply or self.brain.describe_capabilities()

    def _action_chat(self, target, query, amount, reply):
        return reply or "Estou ouvindo."

    def _action_none(self, target, query, amount, reply):
        return reply or "Entendi sua fala, mas não tenho uma ação segura para esse pedido."
