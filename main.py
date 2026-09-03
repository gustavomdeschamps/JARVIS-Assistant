import datetime
import sys
import time

import psutil

from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    Signal
)

from PySide6.QtGui import (
    QFont,
    QSurfaceFormat
)

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget
)

from config import (
    CONVERSATION_ACTIVE_SECONDS
)

from core.commands import CommandSystem

from core.voice_engine import VoiceEngine

from ui.boot_screen import BootScreen

from ui.core3d import JarvisCore3D


# ============================================================
# VOICE WORKER
# ============================================================

class VoiceWorker(
    QThread
):

    status_changed = Signal(
        str
    )


    transcript_changed = Signal(
        str
    )


    response_changed = Signal(
        str
    )


    def __init__(
        self,
        voice,
        commands
    ):

        super().__init__()


        self.voice = voice

        self.commands = commands


        self.running = True

        self.paused = False


        self.conversation_until = 0.0


        self.wake_words = (

            "jarvis",

            "járvis",

            "javis",

            "jarves",

            "jardis"
        )


    # ========================================================
    # STOP
    # ========================================================

    def stop(
        self
    ):

        self.running = False


    # ========================================================
    # PAUSE
    # ========================================================

    def set_paused(
        self,
        paused
    ):

        self.paused = bool(
            paused
        )


    # ========================================================
    # CONVERSATION
    # ========================================================

    def _conversation_active(
        self
    ):

        return (

            time.monotonic()

            <

            self.conversation_until
        )


    def _activate_conversation(
        self
    ):

        self.conversation_until = (

            time.monotonic()

            +

            CONVERSATION_ACTIVE_SECONDS
        )


    # ========================================================
    # WAKE WORD
    # ========================================================

    def _extract_wake(
        self,
        text
    ):

        if not text:

            return (
                False,
                ""
            )


        lowered = (
            text
            .lower()
            .strip()
        )


        for wake in self.wake_words:

            if lowered.startswith(
                wake
            ):

                content = (

                    text[
                        len(
                            wake
                        ):
                    ]

                    .lstrip(
                        " ,.-:;!?"
                    )

                    .strip()
                )


                return (
                    True,
                    content
                )


        return (
            False,
            text
        )


    # ========================================================
    # EXECUTE
    # ========================================================

    def _execute(
        self,
        command
    ):

        if not command:

            return


        self.status_changed.emit(
            "PROCESSING"
        )


        self.transcript_changed.emit(
            command
        )


        result = (
            self.commands
            .execute(
                command
            )
        )


        response = (
            result.get(
                "text",
                ""
            )
        )


        if response:

            self.response_changed.emit(
                response
            )


        self.voice.wait_until_silent(
            60
        )


        self.voice.prepare_for_listening()


        self._activate_conversation()


        self.status_changed.emit(
            "LISTENING"
        )


    # ========================================================
    # WAKE + SIM
    # ========================================================

    def _wake_and_listen(
        self
    ):

        self.status_changed.emit(
            "RESPONDING"
        )


        self.voice.speak(
            "Sim?",
            wait=True
        )


        self.voice.prepare_for_listening()


        self.status_changed.emit(
            "LISTENING"
        )


        command = (
            self.voice
            .listen_once(

                max_wait=8.0,

                max_phrase=25.0
            )
        )


        if command:

            self._execute(
                command
            )


        else:

            self.status_changed.emit(
                "STANDBY"
            )


    # ========================================================
    # RUN
    # ========================================================

    def run(
        self
    ):

        if not self.voice.microphone_available:

            self.status_changed.emit(
                "NO MICROPHONE"
            )

            return


        # ====================================================
        # CALIBRATION
        # ====================================================

        self.status_changed.emit(
            "CALIBRATING"
        )


        self.voice.calibrate()


        self.status_changed.emit(
            "STANDBY"
        )


        # ====================================================
        # LOOP
        # ====================================================

        while self.running:

            if self.paused:

                self.msleep(
                    80
                )

                continue


            if self.voice.speaking:

                self.msleep(
                    25
                )

                continue


            active = (
                self._conversation_active()
            )


            self.status_changed.emit(

                "LISTENING"

                if active

                else

                "STANDBY"
            )


            text = (
                self.voice
                .listen_once(

                    max_wait=
                        3.6
                        if active
                        else
                        2.2,

                    max_phrase=25.0
                )
            )


            if not self.running:

                break


            if not text:

                continue


            wake_found, content = (
                self._extract_wake(
                    text
                )
            )


            # =================================================
            # JARVIS...
            # =================================================

            if wake_found:

                if content:

                    self._execute(
                        content
                    )


                else:

                    self._wake_and_listen()


                continue


            # =================================================
            # CONVERSATION ACTIVE
            # =================================================

            if active:

                self._execute(
                    content
                )


# ============================================================
# MAIN WINDOW
# ============================================================

class JarvisWindow(
    QWidget
):

    def __init__(
        self,
        startup_payload
    ):

        super().__init__()


        # ====================================================
        # WINDOW
        # ====================================================

        self.setWindowTitle(
            "JARVIS"
        )


        self.resize(
            1480,
            900
        )


        self.setMinimumSize(
            1040,
            680
        )


        self.setStyleSheet(

            """
            QWidget {
                background: rgb(1, 4, 6);
            }
            """
        )


        # ====================================================
        # STARTUP OBJECTS
        # ====================================================

        self.scanner = startup_payload[
            "scanner"
        ]


        self.app_finder = startup_payload[
            "app_finder"
        ]


        self.brain = startup_payload[
            "brain"
        ]


        # ====================================================
        # VOICE
        # ====================================================

        self.voice = (
            VoiceEngine()
        )


        # ====================================================
        # COMMANDS
        # ====================================================

        self.commands = (
            CommandSystem(

                self.voice,

                scanner=
                    self.scanner,

                app_finder=
                    self.app_finder,

                brain=
                    self.brain
            )
        )


        # ====================================================
        # 3D
        # ====================================================

        self.core3d = (
            JarvisCore3D(
                self
            )
        )


        # ====================================================
        # DEVICE
        # ====================================================

        device = (
            self.scanner
            .profile
        )


        device_name = " ".join(

            value

            for value in [

                device.get(
                    "manufacturer",
                    ""
                ),

                device.get(
                    "model",
                    ""
                )
            ]

            if value

        ).strip()


        self.device_label = QLabel(

            (
                device_name.upper()

                or

                "WINDOWS 11 DEVICE"
            ),

            self
        )


        self.device_label.setFont(

            QFont(
                "Consolas",
                9,
                QFont.DemiBold
            )
        )


        self.device_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(100,145,150,190);
            """
        )


        # ====================================================
        # STATS
        # ====================================================

        self.stats_label = QLabel(
            "",
            self
        )


        self.stats_label.setFont(

            QFont(
                "Consolas",
                9
            )
        )


        self.stats_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(76,112,118,185);
            """
        )


        # ====================================================
        # CLOCK
        # ====================================================

        self.clock_label = QLabel(
            "",
            self
        )


        self.clock_label.setAlignment(
            Qt.AlignRight
        )


        self.clock_label.setFont(

            QFont(
                "Consolas",
                9
            )
        )


        self.clock_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(76,112,118,185);
            """
        )


        # ====================================================
        # STATUS
        # ====================================================

        self.status_label = QLabel(
            "STANDBY",
            self
        )


        self.status_label.setAlignment(
            Qt.AlignCenter
        )


        self.status_label.setFont(

            QFont(
                "Consolas",
                10,
                QFont.DemiBold
            )
        )


        self.status_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(120,205,210,220);
            """
        )


        # ====================================================
        # TRANSCRIPT
        # ====================================================

        self.transcript_label = QLabel(
            "",
            self
        )


        self.transcript_label.setAlignment(
            Qt.AlignCenter
        )


        self.transcript_label.setWordWrap(
            True
        )


        self.transcript_label.setFont(

            QFont(
                "Segoe UI",
                14
            )
        )


        self.transcript_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(225,238,238,230);
            """
        )


        # ====================================================
        # RESPONSE
        # ====================================================

        self.response_label = QLabel(
            "",
            self
        )


        self.response_label.setAlignment(
            Qt.AlignCenter
        )


        self.response_label.setWordWrap(
            True
        )


        self.response_label.setFont(

            QFont(
                "Segoe UI",
                10
            )
        )


        self.response_label.setStyleSheet(

            """
            background: transparent;
            color: rgba(110,150,155,215);
            """
        )


        # ====================================================
        # INPUT
        # ====================================================

        self.command_input = QLineEdit(
            self
        )


        self.command_input.setPlaceholderText(

            "Fale com Jarvis ou digite..."
        )


        self.command_input.returnPressed.connect(
            self.handle_text_command
        )


        self.command_input.setStyleSheet(

            """
            QLineEdit {

                background:
                    rgba(3, 10, 13, 235);

                border:
                    1px solid rgba(72, 132, 140, 105);

                border-radius:
                    3px;

                color:
                    rgb(215, 230, 232);

                padding-left:
                    16px;

                padding-right:
                    16px;

                font-family:
                    Consolas;

                font-size:
                    13px;
            }

            QLineEdit:focus {

                border:
                    1px solid rgba(90, 210, 215, 190);

                background:
                    rgba(4, 15, 18, 242);
            }
            """
        )


        # ====================================================
        # MIC
        # ====================================================

        self.mic_button = QPushButton(
            "●",
            self
        )


        self.mic_button.setToolTip(

            "Ativar/pausar microfone"
        )


        self.mic_button.clicked.connect(
            self.toggle_microphone
        )


        self.mic_button.setStyleSheet(

            """
            QPushButton {

                background:
                    rgba(4, 13, 16, 240);

                border:
                    1px solid rgba(80, 145, 150, 120);

                border-radius:
                    21px;

                color:
                    rgb(105, 210, 215);

                font-size:
                    13px;
            }

            QPushButton:hover {

                border:
                    1px solid rgba(110, 230, 230, 220);

                background:
                    rgba(8, 29, 32, 245);
            }
            """
        )


        self.microphone_paused = False


        # ====================================================
        # WORKER
        # ====================================================

        self.worker = VoiceWorker(

            self.voice,

            self.commands
        )


        self.worker.status_changed.connect(
            self.set_status
        )


        self.worker.transcript_changed.connect(
            self.set_transcript
        )


        self.worker.response_changed.connect(
            self.set_response
        )


        # ====================================================
        # TIMERS
        # ====================================================

        self.system_timer = QTimer(
            self
        )


        self.system_timer.timeout.connect(
            self.update_system_info
        )


        self.system_timer.start(
            1000
        )


        self.visual_timer = QTimer(
            self
        )


        self.visual_timer.timeout.connect(
            self.update_visual
        )


        self.visual_timer.start(
            33
        )


        self.update_system_info()


        self.worker.start()


    # ========================================================
    # RESIZE
    # ========================================================

    def resizeEvent(
        self,
        event
    ):

        width = self.width()

        height = self.height()


        self.core3d.setGeometry(

            0,
            0,

            width,

            height
            -
            76
        )


        self.device_label.setGeometry(

            24,
            18,
            480,
            22
        )


        self.stats_label.setGeometry(

            24,
            42,
            400,
            22
        )


        self.clock_label.setGeometry(

            width
            -
            280,

            18,

            250,

            22
        )


        self.status_label.setGeometry(

            width // 2
            -
            180,

            height // 2
            +
            184,

            360,

            26
        )


        self.transcript_label.setGeometry(

            width // 2
            -
            470,

            height // 2
            +
            216,

            940,

            42
        )


        self.response_label.setGeometry(

            width // 2
            -
            470,

            height // 2
            +
            257,

            940,

            58
        )


        input_width = min(

            670,

            int(
                width
                *
                0.54
            )
        )


        self.command_input.setGeometry(

            width // 2
            -
            input_width // 2
            -
            25,

            height
            -
            61,

            input_width,

            42
        )


        self.mic_button.setGeometry(

            width // 2
            +
            input_width // 2
            -
            13,

            height
            -
            61,

            42,

            42
        )


    # ========================================================
    # UI
    # ========================================================

    def set_status(
        self,
        text
    ):

        self.status_label.setText(
            text
        )


    def set_transcript(
        self,
        text
    ):

        self.transcript_label.setText(

            f'“{text}”'
        )


    def set_response(
        self,
        text
    ):

        self.response_label.setText(
            text
        )


    # ========================================================
    # TEXT COMMAND
    # ========================================================

    def handle_text_command(
        self
    ):

        text = (
            self.command_input
            .text()
            .strip()
        )


        if not text:

            return


        self.command_input.clear()


        if text.lower().startswith(
            "jarvis"
        ):

            text = (

                text[
                    len(
                        "jarvis"
                    ):
                ]

                .lstrip(
                    " ,.-:;!?"
                )

                .strip()
            )


        if not text:

            return


        self.set_transcript(
            text
        )


        self.set_status(
            "PROCESSING"
        )


        result = (
            self.commands
            .execute(
                text
            )
        )


        self.set_response(

            result.get(
                "text",
                ""
            )
        )


        self.set_status(
            "STANDBY"
        )


    # ========================================================
    # MICROPHONE
    # ========================================================

    def toggle_microphone(
        self
    ):

        self.microphone_paused = (

            not
            self.microphone_paused
        )


        self.worker.set_paused(
            self.microphone_paused
        )


        self.mic_button.setText(

            "○"

            if self.microphone_paused

            else

            "●"
        )


        self.set_status(

            "MIC PAUSED"

            if self.microphone_paused

            else

            "STANDBY"
        )


    # ========================================================
    # VISUAL
    # ========================================================

    def update_visual(
        self
    ):

        status = (
            self.status_label
            .text()
            .upper()
        )


        self.core3d.set_state(

            listening=
                status
                ==
                "LISTENING",

            processing=
                status
                ==
                "PROCESSING",

            speaking=
                self.voice.speaking
        )


        try:

            level, peak = (
                self.voice
                .audio_level()
            )


            self.core3d.set_audio_level(

                level,

                peak
            )


        except Exception:

            pass


    # ========================================================
    # SYSTEM INFO
    # ========================================================

    def update_system_info(
        self
    ):

        cpu = (
            psutil
            .cpu_percent()
        )


        ram = (
            psutil
            .virtual_memory()
            .percent
        )


        self.stats_label.setText(

            f"CPU {int(cpu):02d}%   "
            f"RAM {int(ram):02d}%   "
            f"MODEL {self.brain.model.upper()}"
        )


        self.clock_label.setText(

            datetime
            .datetime
            .now()
            .strftime(
                "%H:%M:%S"
            )
        )


    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(
        self,
        event
    ):

        try:

            self.worker.stop()


            self.worker.wait(
                2500
            )


        except Exception:

            pass


        try:

            self.commands.shutdown()


        except Exception:

            pass


        try:

            self.voice.close()


        except Exception:

            pass


        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # OPENGL
    # ========================================================

    surface = (
        QSurfaceFormat()
    )


    surface.setVersion(
        2,
        1
    )


    surface.setProfile(
        QSurfaceFormat.CompatibilityProfile
    )


    surface.setDepthBufferSize(
        24
    )


    surface.setSamples(
        4
    )


    QSurfaceFormat.setDefaultFormat(
        surface
    )


    # ========================================================
    # QT
    # ========================================================

    app = QApplication(
        sys.argv
    )


    app.setApplicationName(
        "Jarvis"
    )


    # ========================================================
    # BOOT
    # ========================================================

    boot = BootScreen()


    boot.show()


    state = {

        "window":
            None
    }


    # ========================================================
    # AFTER BOOT
    # ========================================================

    def startup_complete(
        payload
    ):

        window = JarvisWindow(
            payload
        )


        state[
            "window"
        ] = window


        window.show()


        def close_boot():

            boot.close()


        boot.fade_out(
            close_boot
        )


    boot.worker.ready.connect(
        startup_complete
    )


    boot.start()


    sys.exit(
        app.exec()
    )


if __name__ == "__main__":

    main()