import asyncio
import hashlib
import os
import queue
import threading
import time

os.environ[
    "PYGAME_HIDE_SUPPORT_PROMPT"
] = "1"


import edge_tts
import pygame
import pyttsx3

from config import DATA_DIR


class TextToSpeech:

    def __init__(
        self
    ):

        # =====================================================
        # VOZ
        # =====================================================

        self.voice_name = (
            "pt-BR-AntonioNeural"
        )


        self.rate = "+6%"

        self.pitch = "-7Hz"


        # =====================================================
        # CACHE
        # =====================================================

        self.cache_dir = (

            DATA_DIR
            /
            "tts_cache"
        )


        self.cache_dir.mkdir(

            parents=True,

            exist_ok=True
        )


        # =====================================================
        # FILA
        # =====================================================

        self.queue = queue.Queue()


        self.finished_event = (
            threading.Event()
        )


        self.finished_event.set()


        self.stop_event = (
            threading.Event()
        )


        # =====================================================
        # AUDIO
        # =====================================================

        self.pygame_available = False


        try:

            pygame.mixer.init(
                frequency=44100
            )


            self.pygame_available = True


        except Exception as error:

            print(
                f"[TTS] Mixer indisponível: {error}"
            )


        # =====================================================
        # THREAD
        # =====================================================

        threading.Thread(

            target=self._worker,

            daemon=True

        ).start()


        # =====================================================
        # PRÉ-CACHE
        # =====================================================

        threading.Thread(

            target=self._prewarm,

            daemon=True

        ).start()


    # =========================================================
    # SPEAKING
    # =========================================================

    @property
    def is_speaking(
        self
    ):

        return not (
            self.finished_event
            .is_set()
        )


    # =========================================================
    # CACHE PATH
    # =========================================================

    def _cache_path(
        self,
        text
    ):

        key = (

            f"{self.voice_name}|"
            f"{self.rate}|"
            f"{self.pitch}|"
            f"{text}"
        )


        digest = (
            hashlib
            .sha256(
                key.encode(
                    "utf-8"
                )
            )
            .hexdigest()
        )


        return (

            self.cache_dir

            /

            f"{digest}.mp3"
        )


    # =========================================================
    # GERAR
    # =========================================================

    def _ensure_audio(
        self,
        text
    ):

        path = (
            self._cache_path(
                text
            )
        )


        if (

            path.exists()

            and

            path.stat().st_size
            >
            700

        ):

            return path


        async def generate():

            speech = edge_tts.Communicate(

                text=text,

                voice=
                    self.voice_name,

                rate=
                    self.rate,

                pitch=
                    self.pitch
            )


            await speech.save(
                str(
                    path
                )
            )


        asyncio.run(
            generate()
        )


        return (

            path

            if path.exists()

            else None
        )


    # =========================================================
    # PREWARM
    # =========================================================

    def _prewarm(
        self
    ):

        for text in [

            "Sim?",

            "Pronto.",

            "Feito.",

            "Já abri.",

            "Pesquisando.",

            "Estou ouvindo."

        ]:

            try:

                self._ensure_audio(
                    text
                )


            except Exception:

                pass


    # =========================================================
    # SPEAK
    # =========================================================

    def speak(
        self,
        text,
        wait=False
    ):

        if not text:

            return


        done = (
            threading.Event()
        )


        self.finished_event.clear()


        self.queue.put(
            (
                str(
                    text
                ),

                done
            )
        )


        if wait:

            done.wait(
                timeout=45
            )


    # =========================================================
    # WAIT
    # =========================================================

    def wait_until_silent(
        self,
        timeout=45
    ):

        return (
            self.finished_event
            .wait(
                timeout=timeout
            )
        )


    # =========================================================
    # STOP
    # =========================================================

    def stop_current(
        self
    ):

        self.stop_event.set()


        try:

            pygame.mixer.music.stop()


        except Exception:

            pass


    # =========================================================
    # WORKER
    # =========================================================

    def _worker(
        self
    ):

        while True:

            item = self.queue.get()


            if item is None:

                break


            text, done = item


            self.stop_event.clear()


            print(
                f"[JARVIS] {text}"
            )


            success = False


            try:

                success = (
                    self._speak_edge(
                        text
                    )
                )


            except Exception as error:

                print(
                    f"[TTS] Edge TTS falhou: {error}"
                )


            if not success:

                try:

                    self._speak_windows(
                        text
                    )


                except Exception as error:

                    print(
                        f"[TTS] Voz local falhou: {error}"
                    )


            done.set()


            self.queue.task_done()


            if self.queue.empty():

                self.finished_event.set()


    # =========================================================
    # EDGE
    # =========================================================

    def _speak_edge(
        self,
        text
    ):

        if not self.pygame_available:

            return False


        path = (
            self._ensure_audio(
                text
            )
        )


        if path is None:

            return False


        pygame.mixer.music.load(
            str(
                path
            )
        )


        pygame.mixer.music.play()


        while pygame.mixer.music.get_busy():

            if self.stop_event.is_set():

                pygame.mixer.music.stop()

                break


            time.sleep(
                0.015
            )


        try:

            pygame.mixer.music.unload()


        except Exception:

            pass


        return True


    # =========================================================
    # WINDOWS FALLBACK
    # =========================================================

    def _speak_windows(
        self,
        text
    ):

        engine = pyttsx3.init()


        engine.setProperty(
            "rate",
            184
        )


        engine.setProperty(
            "volume",
            1.0
        )


        voices = (
            engine
            .getProperty(
                "voices"
            )
        )


        selected = None


        for voice in voices:

            info = (

                f"{voice.name} "
                f"{voice.id}"

            ).lower()


            if any(

                name in info

                for name in [

                    "antonio",

                    "antônio",

                    "daniel",

                    "ricardo",

                    "male"
                ]

            ):

                selected = voice

                break


        if selected is None:

            for voice in voices:

                info = (

                    f"{voice.name} "
                    f"{voice.id} "
                    f"{getattr(voice, 'languages', '')}"

                ).lower()


                if any(

                    value in info

                    for value in [

                        "portugu",

                        "brasil",

                        "brazil"
                    ]

                ):

                    selected = voice

                    break


        if selected is not None:

            engine.setProperty(

                "voice",

                selected.id
            )


        engine.say(
            text
        )


        engine.runAndWait()

        engine.stop()