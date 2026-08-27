import math
import time

import sounddevice as sd

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QThread,
    QTimer,
    Qt,
    Signal
)

from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPolygonF
)

from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QWidget
)

from core.app_finder import AppFinder

from core.brain import JarvisBrain

from core.system_scanner import SystemScanner


# ============================================================
# STARTUP WORKER
# ============================================================

class StartupWorker(
    QThread
):

    step = Signal(
        str,
        int
    )


    ready = Signal(
        object
    )


    def run(
        self
    ):

        payload = {}


        # =====================================================
        # NOTEBOOK
        # =====================================================

        self.step.emit(
            "DEVICE PROFILE",
            12
        )


        scanner = (
            SystemScanner()
        )


        payload[
            "scanner"
        ] = scanner


        # =====================================================
        # APPS
        # =====================================================

        self.step.emit(
            "APPLICATION INDEX",
            38
        )


        app_finder = (
            AppFinder()
        )


        payload[
            "app_finder"
        ] = app_finder


        # =====================================================
        # AUDIO
        # =====================================================

        self.step.emit(
            "VOICE INTERFACE",
            58
        )


        try:

            devices = (
                sd.query_devices()
            )


            input_count = sum(

                1

                for item in devices

                if int(
                    item[
                        "max_input_channels"
                    ]
                )
                >
                0
            )


            payload[
                "input_devices"
            ] = input_count


        except Exception:

            payload[
                "input_devices"
            ] = 0


        # =====================================================
        # IA
        # =====================================================

        self.step.emit(
            "LOCAL INFERENCE",
            72
        )


        brain = JarvisBrain(

            scanner=scanner,

            app_finder=
                app_finder,

            auto_warmup=False
        )


        brain.warmup()


        payload[
            "brain"
        ] = brain


        payload[
            "model"
        ] = brain.model


        # =====================================================
        # READY
        # =====================================================

        self.step.emit(
            "SYSTEM READY",
            100
        )


        time.sleep(
            0.35
        )


        self.ready.emit(
            payload
        )


# ============================================================
# BOOT SCREEN
# ============================================================

class BootScreen(
    QWidget
):

    def __init__(
        self
    ):

        super().__init__()


        self.setWindowTitle(
            "JARVIS"
        )


        self.resize(
            1280,
            760
        )


        self.setMinimumSize(
            900,
            560
        )


        self.setAttribute(
            Qt.WA_OpaquePaintEvent,
            True
        )


        # =====================================================
        # ANIMATION
        # =====================================================

        self.angle_a = 0.0

        self.angle_b = 0.0

        self.angle_c = 0.0

        self.scan = 0.0


        self.progress = 0.0

        self.target_progress = 0.0


        self.status = (
            "POWER SEQUENCE"
        )


        self.started_at = (
            time.monotonic()
        )


        # =====================================================
        # TIMER
        # =====================================================

        self.timer = QTimer(
            self
        )


        self.timer.timeout.connect(
            self.animate
        )


        self.timer.start(
            16
        )


        # =====================================================
        # WORKER
        # =====================================================

        self.worker = (
            StartupWorker()
        )


        self.worker.step.connect(
            self.set_step
        )


        # =====================================================
        # OPACITY
        # =====================================================

        self.opacity = (
            QGraphicsOpacityEffect(
                self
            )
        )


        self.opacity.setOpacity(
            1.0
        )


        self.setGraphicsEffect(
            self.opacity
        )


        self.fade_animation = None


    # =========================================================
    # START
    # =========================================================

    def start(
        self
    ):

        self.worker.start()


    # =========================================================
    # STEP
    # =========================================================

    def set_step(
        self,
        text,
        progress
    ):

        self.status = text


        self.target_progress = float(
            progress
        )


    # =========================================================
    # ANIMATE
    # =========================================================

    def animate(
        self
    ):

        self.angle_a += 0.55

        self.angle_b -= 0.34

        self.angle_c += 0.17


        self.scan = (

            self.scan
            +
            0.0075

        ) % 1.0


        self.progress += (

            self.target_progress
            -
            self.progress

        ) * 0.065


        self.update()


    # =========================================================
    # FADE
    # =========================================================

    def fade_out(
        self,
        callback
    ):

        self.fade_animation = (
            QPropertyAnimation(

                self.opacity,

                b"opacity",

                self
            )
        )


        self.fade_animation.setDuration(
            520
        )


        self.fade_animation.setStartValue(
            1.0
        )


        self.fade_animation.setEndValue(
            0.0
        )


        self.fade_animation.setEasingCurve(
            QEasingCurve.InOutCubic
        )


        self.fade_animation.finished.connect(
            callback
        )


        self.fade_animation.start()


    # =========================================================
    # PAINT
    # =========================================================

    def paintEvent(
        self,
        event
    ):

        painter = QPainter(
            self
        )


        painter.setRenderHint(
            QPainter.Antialiasing,
            True
        )


        width = self.width()

        height = self.height()


        painter.fillRect(

            self.rect(),

            QColor(
                2,
                5,
                8
            )
        )


        self._draw_background(

            painter,

            width,

            height
        )


        center_x = (
            width
            *
            0.5
        )


        center_y = (
            height
            *
            0.47
        )


        base = (

            min(
                width,
                height
            )

            *
            0.22
        )


        center = QPointF(

            center_x,

            center_y
        )


        # =====================================================
        # MECHANICAL STACK
        # =====================================================

        self._draw_gear(

            painter,

            center,

            base * 1.35,

            34,

            self.angle_a,

            0.36
        )


        self._draw_gear(

            painter,

            center,

            base * 0.98,

            26,

            self.angle_b,

            0.56
        )


        self._draw_gear(

            painter,

            center,

            base * 0.64,

            18,

            self.angle_c,

            0.78
        )


        self._draw_core(

            painter,

            center,

            base * 0.34
        )


        # =====================================================
        # TITLE
        # =====================================================

        elapsed = (

            time.monotonic()

            -

            self.started_at
        )


        pulse = (

            0.5

            +

            0.5
            *
            math.sin(
                elapsed
                *
                3.2
            )
        )


        painter.setPen(

            QColor(

                125,

                220,

                235,

                int(
                    150
                    +
                    70
                    *
                    pulse
                )
            )
        )


        painter.setFont(

            QFont(

                "Segoe UI",

                max(
                    18,
                    int(
                        height
                        *
                        0.032
                    )
                ),

                QFont.DemiBold
            )
        )


        painter.drawText(

            0,

            int(
                height
                *
                0.16
            ),

            width,

            44,

            Qt.AlignCenter,

            "JARVIS"
        )


        # =====================================================
        # STATUS
        # =====================================================

        painter.setPen(

            QColor(
                90,
                130,
                138,
                210
            )
        )


        painter.setFont(

            QFont(

                "Consolas",

                max(
                    9,
                    int(
                        height
                        *
                        0.014
                    )
                )
            )
        )


        painter.drawText(

            0,

            int(
                height
                *
                0.77
            ),

            width,

            24,

            Qt.AlignCenter,

            self.status
        )


        # =====================================================
        # PROGRESS
        # =====================================================

        line_width = min(

            width
            *
            0.46,

            560
        )


        x0 = (

            width
            -
            line_width

        ) / 2


        y0 = (
            height
            *
            0.82
        )


        painter.setPen(

            QPen(

                QColor(
                    35,
                    55,
                    60,
                    230
                ),

                2
            )
        )


        painter.drawLine(

            QPointF(
                x0,
                y0
            ),

            QPointF(
                x0
                +
                line_width,
                y0
            )
        )


        painter.setPen(

            QPen(

                QColor(
                    75,
                    220,
                    235,
                    235
                ),

                2
            )
        )


        painter.drawLine(

            QPointF(
                x0,
                y0
            ),

            QPointF(

                x0
                +
                line_width
                *
                max(
                    0.0,
                    min(
                        self.progress
                        /
                        100.0,
                        1.0
                    )
                ),

                y0
            )
        )


        painter.setPen(

            QColor(
                75,
                110,
                118,
                190
            )
        )


        painter.setFont(

            QFont(

                "Consolas",

                max(
                    8,
                    int(
                        height
                        *
                        0.012
                    )
                )
            )
        )


        painter.drawText(

            0,

            int(
                height
                *
                0.845
            ),

            width,

            24,

            Qt.AlignCenter,

            f"{int(self.progress):02d}%"
        )


        painter.end()


    # =========================================================
    # BACKGROUND
    # =========================================================

    def _draw_background(
        self,
        painter,
        width,
        height
    ):

        painter.setPen(

            QPen(

                QColor(
                    20,
                    35,
                    40,
                    100
                ),

                1
            )
        )


        spacing = max(

            36,

            int(
                min(
                    width,
                    height
                )
                *
                0.055
            )
        )


        offset = int(

            self.scan
            *
            spacing
        )


        for x in range(

            -spacing
            +
            offset,

            width
            +
            spacing,

            spacing
        ):

            painter.drawLine(

                x,
                0,
                x,
                height
            )


        for y in range(

            -spacing
            +
            offset,

            height
            +
            spacing,

            spacing
        ):

            painter.drawLine(

                0,
                y,
                width,
                y
            )


        scan_y = int(

            self.scan
            *
            height
        )


        painter.setPen(

            QPen(

                QColor(
                    80,
                    220,
                    235,
                    42
                ),

                1
            )
        )


        painter.drawLine(

            0,
            scan_y,
            width,
            scan_y
        )


    # =========================================================
    # GEAR POLYGON
    # =========================================================

    def _gear_polygon(
        self,
        center,
        radius,
        teeth,
        angle
    ):

        points = []


        for index in range(
            teeth
            *
            4
        ):

            phase = (
                index
                %
                4
            )


            current_radius = (

                radius

                *

                (
                    1.0

                    if phase
                    in
                    [
                        1,
                        2
                    ]

                    else
                    0.89
                )
            )


            current_angle = (

                math.radians(
                    angle
                )

                +

                (
                    index
                    /
                    (
                        teeth
                        *
                        4
                    )
                )
                *
                math.tau
            )


            points.append(

                QPointF(

                    center.x()
                    +
                    math.cos(
                        current_angle
                    )
                    *
                    current_radius,

                    center.y()
                    +
                    math.sin(
                        current_angle
                    )
                    *
                    current_radius
                )
            )


        return QPolygonF(
            points
        )


    # =========================================================
    # GEAR
    # =========================================================

    def _draw_gear(
        self,
        painter,
        center,
        radius,
        teeth,
        angle,
        strength
    ):

        outer = (
            self._gear_polygon(

                center,

                radius,

                teeth,

                angle
            )
        )


        painter.setBrush(

            QColor(

                18,

                30,

                34,

                int(
                    85
                    *
                    strength
                )
            )
        )


        painter.setPen(

            QPen(

                QColor(

                    90,

                    185,

                    200,

                    int(
                        180
                        *
                        strength
                    )
                ),

                max(
                    1.0,
                    radius
                    *
                    0.006
                )
            )
        )


        painter.drawPolygon(
            outer
        )


        inner_radius = (
            radius
            *
            0.72
        )


        painter.setBrush(

            QColor(
                2,
                5,
                8,
                255
            )
        )


        painter.setPen(

            QPen(

                QColor(

                    55,

                    95,

                    105,

                    int(
                        180
                        *
                        strength
                    )
                ),

                1
            )
        )


        painter.drawEllipse(

            center,

            inner_radius,

            inner_radius
        )


        painter.save()

        painter.translate(
            center
        )

        painter.rotate(
            angle
        )


        painter.setPen(

            QPen(

                QColor(

                    70,

                    145,

                    155,

                    int(
                        150
                        *
                        strength
                    )
                ),

                1
            )
        )


        for index in range(

            0,

            teeth,

            max(
                1,
                teeth
                //
                8
            )
        ):

            current_angle = (

                index
                /
                teeth
                *
                math.tau
            )


            point_a = QPointF(

                math.cos(
                    current_angle
                )
                *
                radius
                *
                0.73,

                math.sin(
                    current_angle
                )
                *
                radius
                *
                0.73
            )


            point_b = QPointF(

                math.cos(
                    current_angle
                )
                *
                radius
                *
                0.88,

                math.sin(
                    current_angle
                )
                *
                radius
                *
                0.88
            )


            painter.drawLine(
                point_a,
                point_b
            )


        painter.restore()


    # =========================================================
    # CORE
    # =========================================================

    def _draw_core(
        self,
        painter,
        center,
        radius
    ):

        elapsed = (

            time.monotonic()

            -

            self.started_at
        )


        pulse = (

            0.88

            +

            0.12
            *
            math.sin(
                elapsed
                *
                4.0
            )
        )


        for layer in range(
            10,
            0,
            -1
        ):

            current_radius = (

                radius
                *
                pulse

                +

                layer
                *
                radius
                *
                0.10
            )


            alpha = max(

                6,

                35
                -
                layer
                *
                2
            )


            painter.setPen(

                QPen(

                    QColor(
                        75,
                        225,
                        240,
                        alpha
                    ),

                    2
                )
            )


            painter.setBrush(
                Qt.NoBrush
            )


            painter.drawEllipse(

                center,

                current_radius,

                current_radius
            )


        painter.setBrush(

            QColor(
                160,
                245,
                250,
                235
            )
        )


        painter.setPen(
            Qt.NoPen
        )


        painter.drawEllipse(

            center,

            radius
            *
            0.13,

            radius
            *
            0.13
        )