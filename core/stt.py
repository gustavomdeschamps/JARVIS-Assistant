import numpy as np
import speech_recognition as sr


class SpeechToText:

    def __init__(
        self
    ):

        self.recognizer = sr.Recognizer()

        self.recognizer.operation_timeout = 8


    # =========================================================
    # MELHORAR ÁUDIO
    # =========================================================

    def enhance_audio(
        self,
        audio
    ):

        if audio is None:

            return None


        audio = np.asarray(
            audio,
            dtype=np.float32
        ).reshape(-1)


        if audio.size == 0:

            return None


        # Remove pequeno offset DC.
        audio = (
            audio
            -
            np.mean(
                audio
            )
        )


        peak = float(
            np.max(
                np.abs(
                    audio
                )
            )
        )


        if peak <= 0.00001:

            return audio


        # =====================================================
        # GANHO AUTOMÁTICO
        # =====================================================

        # Microfones de notebook às vezes entregam áudio
        # muito baixo. Amplificamos sem deixar clipar.

        if peak < 0.70:

            gain = min(

                8.0,

                0.75
                /
                peak
            )


            # Nunca exagera ganho absurdamente baixo.
            gain = max(
                1.0,
                gain
            )


            audio = (
                audio
                *
                gain
            )


        audio = np.clip(

            audio,

            -0.98,

            0.98
        )


        return audio


    # =========================================================
    # CONVERTER
    # =========================================================

    def convert(
        self,
        audio,
        sample_rate
    ):

        audio = self.enhance_audio(
            audio
        )


        if audio is None:

            return None


        int16_audio = (

            audio
            *
            32767.0

        ).astype(
            np.int16
        )


        raw = int16_audio.tobytes()


        return sr.AudioData(

            raw,

            int(
                sample_rate
            ),

            2
        )


    # =========================================================
    # RESULTADO GOOGLE
    # =========================================================

    def extract_google_result(
        self,
        result
    ):

        if not result:

            return None


        if isinstance(
            result,
            str
        ):

            return result.strip()


        if not isinstance(
            result,
            dict
        ):

            return None


        alternatives = result.get(
            "alternative",
            []
        )


        if not alternatives:

            return None


        print(
            "[STT] Alternativas:"
        )


        for index, alternative in enumerate(
            alternatives[:3]
        ):

            transcript = alternative.get(
                "transcript",
                ""
            )


            confidence = alternative.get(
                "confidence"
            )


            if confidence is None:

                print(
                    f"      {index + 1}. {transcript}"
                )


            else:

                print(
                    f"      {index + 1}. {transcript} ({confidence:.2f})"
                )


        best = alternatives[0].get(
            "transcript",
            ""
        )


        return best.strip()


    # =========================================================
    # TRANSCRIÇÃO
    # =========================================================

    def transcribe(
        self,
        audio,
        sample_rate
    ):

        audio_data = self.convert(

            audio,

            sample_rate
        )


        if audio_data is None:

            return None


        try:

            print()
            print(
                "[STT] Enviando áudio para reconhecimento..."
            )


            result = (
                self.recognizer
                .recognize_google(

                    audio_data,

                    language="pt-BR",

                    show_all=True
                )
            )


            text = self.extract_google_result(
                result
            )


            if not text:

                print(
                    "[STT] Nenhuma transcrição."
                )

                return None


            print()
            print(
                f"[VOCÊ] {text}"
            )

            print()


            return text


        except sr.UnknownValueError:

            print(
                "[STT] Não consegui entender sua voz."
            )


            return None


        except sr.RequestError as error:

            print(
                "[STT] Serviço de reconhecimento indisponível:"
            )

            print(
                error
            )


            return None


        except Exception as error:

            print(
                "[STT] Erro inesperado:"
            )

            print(
                error
            )


            return None