import time

from core.audio import AudioCapture

from core.stt import SpeechToText

from core.tts import TextToSpeech


class VoiceEngine:

    def __init__(
        self
    ):

        self.audio = (
            AudioCapture()
        )


        self.stt = (
            SpeechToText()
        )


        self.tts = (
            TextToSpeech()
        )


    # =========================================================
    # MICROPHONE
    # =========================================================

    @property
    def microphone_available(
        self
    ):

        return bool(

            getattr(
                self.audio,
                "microphone_available",
                False
            )
        )


    @property
    def microphone_name(
        self
    ):

        return (

            getattr(
                self.audio,
                "device_name",
                None
            )

            or

            getattr(
                self.audio,
                "microphone_name",
                None
            )
        )


    # =========================================================
    # SPEAKING
    # =========================================================

    @property
    def speaking(
        self
    ):

        return (
            self.tts
            .is_speaking
        )


    # =========================================================
    # CALIBRATE
    # =========================================================

    def calibrate(
        self
    ):

        try:

            return (
                self.audio
                .calibrate(
                    seconds=1.0
                )
            )


        except TypeError:

            return (
                self.audio
                .calibrate()
            )


    # =========================================================
    # LISTEN
    # =========================================================

    def listen_once(
        self,
        max_wait=5.0,
        max_phrase=20.0
    ):

        if (

            not self.microphone_available

            or

            self.speaking

        ):

            return None


        try:

            audio = (
                self.audio
                .listen_phrase(

                    max_wait=max_wait,

                    max_phrase=max_phrase,

                    silence_duration=0.45
                )
            )


        except TypeError:

            audio = (
                self.audio
                .listen_phrase(

                    max_wait=max_wait,

                    max_phrase=max_phrase
                )
            )


        if audio is None:

            return None


        return (

            self.stt
            .transcribe(

                audio,

                self.audio.sample_rate
            )
        )


    # =========================================================
    # SPEAK
    # =========================================================

    def speak(
        self,
        text,
        wait=False
    ):

        self.tts.speak(
            text,
            wait=wait
        )


    # =========================================================
    # WAIT
    # =========================================================

    def wait_until_silent(
        self,
        timeout=45
    ):

        return (
            self.tts
            .wait_until_silent(
                timeout
            )
        )


    # =========================================================
    # PREPARE
    # =========================================================

    def prepare_for_listening(
        self
    ):

        self.wait_until_silent(
            45
        )


        time.sleep(
            0.10
        )


        if hasattr(
            self.audio,
            "flush"
        ):

            try:

                self.audio.flush()


            except Exception:

                pass


    # =========================================================
    # STOP SPEAK
    # =========================================================

    def stop_speaking(
        self
    ):

        self.tts.stop_current()


    # =========================================================
    # AUDIO LEVEL
    # =========================================================

    def audio_level(
        self
    ):

        if hasattr(
            self.audio,
            "get_level"
        ):

            try:

                return (
                    self.audio
                    .get_level()
                )


            except Exception:

                pass


        return (

            float(

                getattr(
                    self.audio,
                    "last_level",
                    0.0
                )
                or
                0.0
            ),

            float(

                getattr(
                    self.audio,
                    "last_peak",
                    0.0
                )
                or
                0.0
            )
        )


    # =========================================================
    # CLOSE
    # =========================================================

    def close(
        self
    ):

        if hasattr(
            self.audio,
            "close"
        ):

            try:

                self.audio.close()


            except Exception:

                pass