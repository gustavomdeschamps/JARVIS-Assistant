import queue
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd


class AudioCapture:

    def __init__(self):

        # =====================================================
        # MICROFONE
        # =====================================================

        self.device_index = None
        self.device_name = None

        self.microphone_available = False

        # =====================================================
        # ÁUDIO
        # =====================================================

        self.sample_rate = 48000

        self.channels = 1

        # 20 ms costuma deixar a detecção bastante responsiva.
        self.block_ms = 20

        self.block_size = 960

        # =====================================================
        # DETECÇÃO DE VOZ
        # =====================================================

        self.noise_floor = 0.001

        self.threshold = 0.0025

        self.minimum_threshold = 0.0018

        self.maximum_threshold = 0.080

        # =====================================================
        # ESTADO
        # =====================================================

        self.calibrated = False

        self.last_level = 0.0

        self.last_peak = 0.0

        # =====================================================
        # BUFFER CONTÍNUO
        # =====================================================

        self.audio_queue = queue.Queue(
            maxsize=600
        )

        self.lock = threading.Lock()

        self.stream = None

        self.running = False

        # =====================================================
        # INICIAR
        # =====================================================

        if self.detect_microphone():

            self.start_stream()


    # =========================================================
    # RMS
    # =========================================================

    def calculate_rms(
        self,
        audio
    ):

        if audio is None:

            return 0.0


        audio = np.asarray(
            audio,
            dtype=np.float32
        )


        if audio.size == 0:

            return 0.0


        value = np.sqrt(
            np.mean(
                np.square(
                    audio
                )
            )
            +
            1e-12
        )


        return float(
            value
        )


    # =========================================================
    # PEAK
    # =========================================================

    def calculate_peak(
        self,
        audio
    ):

        if audio is None:

            return 0.0


        audio = np.asarray(
            audio,
            dtype=np.float32
        )


        if audio.size == 0:

            return 0.0


        return float(
            np.max(
                np.abs(
                    audio
                )
            )
        )


    # =========================================================
    # MICROFONE
    # =========================================================

    def detect_microphone(
        self
    ):

        print()
        print("=" * 70)
        print("JARVIS AUDIO ENGINE - WINDOWS 11")
        print("=" * 70)


        try:

            devices = sd.query_devices()


        except Exception as error:

            print(
                "[AUDIO] Erro ao consultar dispositivos:"
            )

            print(
                error
            )

            return False


        input_devices = []


        for index, device in enumerate(
            devices
        ):

            max_inputs = int(
                device[
                    "max_input_channels"
                ]
            )


            if max_inputs <= 0:

                continue


            name = str(
                device[
                    "name"
                ]
            )


            print(
                f"[{index}] {name}"
            )


            score = 0

            lower = name.lower()


            preferred_words = [
                "microphone",
                "microfone",
                "mic",
                "array",
                "realtek",
                "headset",
                "intel",
                "input"
            ]


            for word in preferred_words:

                if word in lower:

                    score += 10


            input_devices.append(
                (
                    score,
                    index,
                    device
                )
            )


        if not input_devices:

            print()
            print(
                "[AUDIO] Nenhum microfone encontrado."
            )

            return False


        # =====================================================
        # MICROFONE PADRÃO PRIMEIRO
        # =====================================================

        indexes = []


        try:

            default_index = (
                sd.default.device[0]
            )


            if (
                isinstance(
                    default_index,
                    int
                )
                and
                default_index >= 0
            ):

                indexes.append(
                    default_index
                )


        except Exception:

            pass


        # =====================================================
        # OUTROS POR PRIORIDADE
        # =====================================================

        input_devices.sort(
            key=lambda item: item[0],
            reverse=True
        )


        for _, index, _ in input_devices:

            if index not in indexes:

                indexes.append(
                    index
                )


        # =====================================================
        # TESTAR
        # =====================================================

        for index in indexes:

            try:

                device = sd.query_devices(
                    index
                )


                if int(
                    device[
                        "max_input_channels"
                    ]
                ) <= 0:

                    continue


                sample_rate = int(
                    device[
                        "default_samplerate"
                    ]
                )


                recording = sd.rec(

                    int(
                        sample_rate
                        *
                        0.08
                    ),

                    samplerate=sample_rate,

                    channels=1,

                    dtype="float32",

                    device=index
                )


                sd.wait()


                self.device_index = index

                self.device_name = str(
                    device[
                        "name"
                    ]
                )


                self.sample_rate = (
                    sample_rate
                )


                self.block_size = max(

                    128,

                    int(
                        self.sample_rate
                        *
                        self.block_ms
                        /
                        1000
                    )
                )


                self.microphone_available = True


                print()
                print(
                    "[AUDIO] MICROFONE SELECIONADO"
                )

                print(
                    f"[AUDIO] Nome: {self.device_name}"
                )

                print(
                    f"[AUDIO] Índice: {self.device_index}"
                )

                print(
                    f"[AUDIO] Sample rate: {self.sample_rate}"
                )

                print(
                    f"[AUDIO] Block size: {self.block_size}"
                )

                print("=" * 70)
                print()


                return True


            except Exception as error:

                print(
                    f"[AUDIO] Dispositivo {index} rejeitado."
                )


        self.microphone_available = False

        return False


    # =========================================================
    # CALLBACK
    # =========================================================

    def audio_callback(
        self,
        indata,
        frames,
        time_info,
        status
    ):

        if status:

            # Não encerra o Jarvis por pequenos overruns.
            pass


        try:

            mono = np.asarray(

                indata[
                    :,
                    0
                ],

                dtype=np.float32

            ).copy()


            level = self.calculate_rms(
                mono
            )


            peak = self.calculate_peak(
                mono
            )


            with self.lock:

                self.last_level = level

                self.last_peak = peak


            try:

                self.audio_queue.put_nowait(
                    mono
                )


            except queue.Full:

                try:

                    self.audio_queue.get_nowait()

                except queue.Empty:

                    pass


                try:

                    self.audio_queue.put_nowait(
                        mono
                    )

                except queue.Full:

                    pass


        except Exception:

            pass


    # =========================================================
    # ABRIR STREAM
    # =========================================================

    def start_stream(
        self
    ):

        if not self.microphone_available:

            return False


        if self.running:

            return True


        try:

            self.stream = sd.InputStream(

                device=self.device_index,

                samplerate=self.sample_rate,

                channels=1,

                dtype="float32",

                blocksize=self.block_size,

                latency="low",

                callback=self.audio_callback
            )


            self.stream.start()


            self.running = True


            print(
                "[AUDIO] Stream contínuo iniciado."
            )


            return True


        except Exception as first_error:

            print(
                "[AUDIO] Latência baixa indisponível."
            )

            print(
                "[AUDIO] Tentando modo automático..."
            )


            try:

                self.stream = sd.InputStream(

                    device=self.device_index,

                    samplerate=self.sample_rate,

                    channels=1,

                    dtype="float32",

                    blocksize=0,

                    callback=self.audio_callback
                )


                self.stream.start()


                self.running = True


                print(
                    "[AUDIO] Stream contínuo iniciado em modo automático."
                )


                return True


            except Exception as second_error:

                print(
                    "[AUDIO] Não consegui abrir o stream:"
                )

                print(
                    second_error
                )


                self.running = False

                return False


    # =========================================================
    # LIMPAR BUFFER
    # =========================================================

    def flush(
        self
    ):

        while True:

            try:

                self.audio_queue.get_nowait()

            except queue.Empty:

                break


    # =========================================================
    # PEGAR BLOCO
    # =========================================================

    def get_block(
        self,
        timeout=0.25
    ):

        try:

            return self.audio_queue.get(
                timeout=timeout
            )


        except queue.Empty:

            return None


    # =========================================================
    # CALIBRAÇÃO
    # =========================================================

    def calibrate(
        self,
        seconds=1.0
    ):

        if not self.microphone_available:

            return False


        print()
        print(
            "[AUDIO] Calibrando sensibilidade..."
        )

        print(
            "[AUDIO] Fique em silêncio por 1 segundo."
        )


        self.flush()


        levels = []


        start = time.monotonic()


        while (
            time.monotonic()
            -
            start
            <
            seconds
        ):

            block = self.get_block(
                timeout=0.30
            )


            if block is None:

                continue


            level = self.calculate_rms(
                block
            )


            levels.append(
                level
            )


        if not levels:

            print(
                "[AUDIO] Calibração falhou."
            )

            return False


        # Mediana é melhor do que média porque ignora
        # pequenos ruídos repentinos.
        median_noise = float(
            np.median(
                np.asarray(
                    levels,
                    dtype=np.float32
                )
            )
        )


        self.noise_floor = max(

            median_noise,

            0.0003
        )


        self.threshold = min(

            max(

                self.noise_floor
                *
                2.2,

                self.minimum_threshold
            ),

            self.maximum_threshold
        )


        self.calibrated = True


        print(
            f"[AUDIO] Ruído: {self.noise_floor:.6f}"
        )

        print(
            f"[AUDIO] Sensibilidade: {self.threshold:.6f}"
        )

        print(
            "[AUDIO] Calibrado."
        )

        print()


        self.flush()


        return True


    # =========================================================
    # ESCUTAR FRASE
    # =========================================================

    def listen_phrase(
        self,
        max_wait=6.0,
        max_phrase=20.0,
        silence_duration=0.45
    ):

        if not self.microphone_available:

            return None


        if not self.running:

            if not self.start_stream():

                return None


        if not self.calibrated:

            self.calibrate()


        # =====================================================
        # PRÉ-BUFFER
        # =====================================================

        # Guarda aproximadamente 350 ms antes da detecção.
        # Isso impede "abre" virar "bre", por exemplo.

        pre_roll_blocks = max(

            8,

            int(
                350
                /
                max(
                    self.block_ms,
                    1
                )
            )
        )


        pre_roll = deque(
            maxlen=pre_roll_blocks
        )


        recorded = []


        speech_started = False

        speech_started_at = None

        last_voice_at = None


        consecutive_voice = 0


        wait_started = time.monotonic()


        print(
            "[AUDIO] Escutando..."
        )


        while True:

            now = time.monotonic()


            # =================================================
            # NINGUÉM FALOU
            # =================================================

            if (
                not speech_started
                and
                now - wait_started
                >
                max_wait
            ):

                return None


            # =================================================
            # FRASE MUITO LONGA
            # =================================================

            if (
                speech_started
                and
                speech_started_at is not None
                and
                now - speech_started_at
                >
                max_phrase
            ):

                print(
                    "[AUDIO] Limite máximo de frase."
                )

                break


            block = self.get_block(
                timeout=0.25
            )


            if block is None:

                continue


            level = self.calculate_rms(
                block
            )


            peak = self.calculate_peak(
                block
            )


            with self.lock:

                self.last_level = level

                self.last_peak = peak


            # =================================================
            # ADAPTAÇÃO AO AMBIENTE
            # =================================================

            if (
                not speech_started
                and
                level
                <
                self.threshold
            ):

                self.noise_floor = (

                    self.noise_floor
                    *
                    0.985

                    +

                    level
                    *
                    0.015
                )


                new_threshold = (

                    self.noise_floor
                    *
                    2.2
                )


                self.threshold = min(

                    max(

                        new_threshold,

                        self.minimum_threshold
                    ),

                    self.maximum_threshold
                )


            # =================================================
            # DETECTOR DE INÍCIO
            # =================================================

            if not speech_started:

                pre_roll.append(
                    block
                )


                rms_voice = (
                    level
                    >
                    self.threshold
                )


                peak_voice = (
                    peak
                    >
                    max(
                        self.threshold
                        *
                        3.0,
                        0.008
                    )
                )


                if (
                    rms_voice
                    or
                    peak_voice
                ):

                    consecutive_voice += 1


                else:

                    consecutive_voice = 0


                # Cerca de 40 ms de áudio acima do limiar.
                if consecutive_voice >= 2:

                    speech_started = True

                    speech_started_at = now

                    last_voice_at = now


                    recorded.extend(
                        list(
                            pre_roll
                        )
                    )


                    pre_roll.clear()


                    print()
                    print(
                        "[AUDIO] >>> VOCÊ COMEÇOU A FALAR"
                    )


                continue


            # =================================================
            # DURANTE A FRASE
            # =================================================

            recorded.append(
                block
            )


            continue_threshold = max(

                self.noise_floor
                *
                1.45,

                self.minimum_threshold
                *
                0.65
            )


            voice_present = (

                level
                >
                continue_threshold

                or

                peak
                >
                max(
                    continue_threshold
                    *
                    3.0,
                    0.006
                )
            )


            if voice_present:

                last_voice_at = now


            # =================================================
            # SILÊNCIO FINAL
            # =================================================

            if (
                last_voice_at is not None
                and
                now - last_voice_at
                >=
                silence_duration
            ):

                print(
                    "[AUDIO] <<< VOCÊ TERMINOU DE FALAR"
                )

                break


        if not recorded:

            return None


        try:

            audio = np.concatenate(
                recorded
            )


        except Exception:

            return None


        duration = (

            audio.shape[0]

            /
            float(
                self.sample_rate
            )
        )


        if duration < 0.20:

            return None


        print(
            f"[AUDIO] Duração capturada: {duration:.2f}s"
        )


        return audio


    # =========================================================
    # LEVEL
    # =========================================================

    def get_level(
        self
    ):

        with self.lock:

            return (
                self.last_level,
                self.last_peak
            )


    # =========================================================
    # ENCERRAR
    # =========================================================

    def close(
        self
    ):

        self.running = False


        if self.stream is not None:

            try:

                self.stream.stop()

            except Exception:

                pass


            try:

                self.stream.close()

            except Exception:

                pass


            self.stream = None