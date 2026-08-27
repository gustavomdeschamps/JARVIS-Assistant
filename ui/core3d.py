import math
import random

from OpenGL.GL import *

from OpenGL.GLU import (
    GLU_FILL,
    GLU_LINE,
    gluLookAt,
    gluNewQuadric,
    gluPerspective,
    gluQuadricDrawStyle,
    gluSphere
)

from PySide6.QtCore import QTimer

from PySide6.QtOpenGLWidgets import (
    QOpenGLWidget
)


# ============================================================
# PARTICLE
# ============================================================

class Particle:

    def __init__(
        self
    ):

        self.radius = random.uniform(
            3.0,
            10.5
        )


        self.angle = random.uniform(
            0.0,
            math.tau
        )


        self.height = random.uniform(
            -4.0,
            4.0
        )


        self.speed = random.uniform(
            0.08,
            0.38
        )


        self.size = random.uniform(
            1.0,
            3.2
        )


        self.alpha = random.uniform(
            0.12,
            0.70
        )


        self.phase = random.uniform(
            0.0,
            math.tau
        )


# ============================================================
# CORE 3D
# ============================================================

class JarvisCore3D(
    QOpenGLWidget
):

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )


        self.t = 0.0


        self.rotations = [
            0.0,
            0.0,
            0.0,
            0.0
        ]


        self.listening = False

        self.processing = False

        self.speaking = False


        self.audio_level = 0.0

        self.audio_peak = 0.0

        self.audio_smooth = 0.0


        self.intro = 0.0


        self.particles = [

            Particle()

            for _ in range(
                460
            )
        ]


        self.quadric = None


        self.timer = QTimer(
            self
        )


        self.timer.timeout.connect(
            self.animate
        )


        self.timer.start(
            16
        )


    # =========================================================
    # STATE
    # =========================================================

    def set_state(
        self,
        listening=False,
        processing=False,
        speaking=False
    ):

        self.listening = bool(
            listening
        )


        self.processing = bool(
            processing
        )


        self.speaking = bool(
            speaking
        )


    # =========================================================
    # AUDIO
    # =========================================================

    def set_audio_level(
        self,
        level,
        peak=0.0
    ):

        try:

            self.audio_level = max(
                0.0,
                float(
                    level
                )
            )


            self.audio_peak = max(
                0.0,
                float(
                    peak
                )
            )


        except Exception:

            self.audio_level = 0.0

            self.audio_peak = 0.0


    # =========================================================
    # INIT GL
    # =========================================================

    def initializeGL(
        self
    ):

        glClearColor(
            0.001,
            0.003,
            0.005,
            1.0
        )


        glEnable(
            GL_DEPTH_TEST
        )


        glDepthFunc(
            GL_LEQUAL
        )


        glEnable(
            GL_BLEND
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_LINE_SMOOTH
        )


        glEnable(
            GL_POINT_SMOOTH
        )


        glHint(

            GL_LINE_SMOOTH_HINT,

            GL_NICEST
        )


        glHint(

            GL_POINT_SMOOTH_HINT,

            GL_NICEST
        )


        self.quadric = (
            gluNewQuadric()
        )


    # =========================================================
    # RESIZE
    # =========================================================

    def resizeGL(
        self,
        width,
        height
    ):

        height = max(
            1,
            height
        )


        glViewport(
            0,
            0,
            width,
            height
        )


        glMatrixMode(
            GL_PROJECTION
        )


        glLoadIdentity()


        gluPerspective(

            44.0,

            width
            /
            height,

            0.1,

            100.0
        )


        glMatrixMode(
            GL_MODELVIEW
        )


    # =========================================================
    # SPEED
    # =========================================================

    def _speed(
        self
    ):

        if self.processing:

            return 3.4


        if self.listening:

            return 1.75


        if self.speaking:

            return 1.45


        return 0.48


    # =========================================================
    # ANIMATE
    # =========================================================

    def animate(
        self
    ):

        speed = (
            self._speed()
        )


        self.t += (
            0.018
            *
            speed
        )


        self.rotations[0] += (
            0.18
            *
            speed
        )


        self.rotations[1] -= (
            0.27
            *
            speed
        )


        self.rotations[2] += (
            0.39
            *
            speed
        )


        self.rotations[3] -= (
            0.12
            *
            speed
        )


        target_audio = min(

            self.audio_level
            *
            30.0,

            1.0
        )


        self.audio_smooth = (

            self.audio_smooth
            *
            0.82

            +

            target_audio
            *
            0.18
        )


        self.intro = min(

            1.0,

            self.intro
            +
            0.008
        )


        self.update()


    # =========================================================
    # PAINT
    # =========================================================

    def paintGL(
        self
    ):

        glClear(

            GL_COLOR_BUFFER_BIT

            |

            GL_DEPTH_BUFFER_BIT
        )


        glLoadIdentity()


        # =====================================================
        # INTRO EASING
        # =====================================================

        intro_ease = (

            1.0

            -

            (
                1.0
                -
                self.intro
            )
            ** 3
        )


        camera_z = (

            13.8

            -

            intro_ease
            *
            3.2

            -

            self.audio_smooth
            *
            0.12
        )


        camera_x = (

            math.sin(
                self.t
                *
                0.10
            )

            *
            0.16
        )


        camera_y = (

            math.cos(
                self.t
                *
                0.08
            )

            *
            0.10
        )


        gluLookAt(

            camera_x,

            camera_y,

            camera_z,

            0,
            0,
            0,

            0,
            1,
            0
        )


        glPushMatrix()


        scale = (

            0.35

            +

            intro_ease
            *
            0.65
        )


        glScalef(

            scale,

            scale,

            scale
        )


        self.draw_particles(
            intro_ease
        )


        self.draw_mechanical_stack(
            intro_ease
        )


        self.draw_energy_core(
            intro_ease
        )


        self.draw_signal_ring(
            intro_ease
        )


        glPopMatrix()


    # =========================================================
    # PARTICLES
    # =========================================================

    def draw_particles(
        self,
        alpha_scale
    ):

        glDisable(
            GL_DEPTH_TEST
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE
        )


        for particle in self.particles:

            angle = (

                particle.angle

                +

                self.t
                *
                particle.speed
                *
                0.18
            )


            x = (

                math.cos(
                    angle
                )

                *
                particle.radius
            )


            z = (

                math.sin(
                    angle
                )

                *
                particle.radius
            )


            y = (

                particle.height

                +

                math.sin(

                    self.t
                    *
                    0.7

                    +

                    particle.phase

                )

                *
                0.18
            )


            twinkle = (

                0.55

                +

                0.45
                *
                math.sin(

                    self.t
                    *
                    particle.speed
                    *
                    3

                    +

                    particle.phase
                )
            )


            glPointSize(
                particle.size
            )


            glColor4f(

                0.10,

                0.68,

                0.76,

                particle.alpha
                *
                twinkle
                *
                alpha_scale
            )


            glBegin(
                GL_POINTS
            )


            glVertex3f(
                x,
                y,
                z
            )


            glEnd()


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_DEPTH_TEST
        )


    # =========================================================
    # GEAR VERTICES
    # =========================================================

    def _gear_vertices(
        self,
        radius,
        teeth,
        tooth_depth
    ):

        vertices = []


        count = (
            teeth
            *
            4
        )


        for index in range(
            count
        ):

            phase = (
                index
                %
                4
            )


            current_radius = (

                radius

                +

                (
                    tooth_depth

                    if phase
                    in
                    [
                        1,
                        2
                    ]

                    else
                    0.0
                )
            )


            angle = (

                index

                /
                count

                *
                math.tau
            )


            vertices.append(

                (

                    math.cos(
                        angle
                    )
                    *
                    current_radius,

                    math.sin(
                        angle
                    )
                    *
                    current_radius
                )
            )


        return vertices


    # =========================================================
    # DRAW GEAR
    # =========================================================

    def draw_gear(
        self,
        radius,
        width,
        teeth,
        tooth_depth,
        depth,
        alpha,
        rotation,
        spokes=8
    ):

        outer = (
            self._gear_vertices(

                radius,

                teeth,

                tooth_depth
            )
        )


        inner_radius = (
            radius
            -
            width
        )


        front_z = (
            depth
            *
            0.5
        )


        back_z = (
            -depth
            *
            0.5
        )


        glPushMatrix()


        glRotatef(

            rotation,

            0,
            0,
            1
        )


        # =====================================================
        # FRONT SURFACE
        # =====================================================

        glColor4f(

            0.11,

            0.24,

            0.27,

            alpha
            *
            0.45
        )


        glBegin(
            GL_QUAD_STRIP
        )


        for (
            x,
            y
        ) in (

            outer

            +

            [
                outer[0]
            ]
        ):

            length = (

                math.hypot(
                    x,
                    y
                )

                or

                1.0
            )


            inner_x = (

                x
                /
                length
                *
                inner_radius
            )


            inner_y = (

                y
                /
                length
                *
                inner_radius
            )


            glVertex3f(
                x,
                y,
                front_z
            )


            glVertex3f(

                inner_x,

                inner_y,

                front_z
            )


        glEnd()


        # =====================================================
        # OUTLINE
        # =====================================================

        glColor4f(

            0.18,

            0.70,

            0.74,

            alpha
        )


        glLineWidth(
            1.3
        )


        for z in [

            front_z,

            back_z
        ]:

            glBegin(
                GL_LINE_LOOP
            )


            for (
                x,
                y
            ) in outer:

                glVertex3f(
                    x,
                    y,
                    z
                )


            glEnd()


            glBegin(
                GL_LINE_LOOP
            )


            for index in range(

                teeth
                *
                4
            ):

                angle = (

                    index

                    /
                    (
                        teeth
                        *
                        4
                    )

                    *
                    math.tau
                )


                glVertex3f(

                    math.cos(
                        angle
                    )
                    *
                    inner_radius,

                    math.sin(
                        angle
                    )
                    *
                    inner_radius,

                    z
                )


            glEnd()


        # =====================================================
        # DEPTH CONNECTIONS
        # =====================================================

        glColor4f(

            0.12,

            0.47,

            0.52,

            alpha
            *
            0.75
        )


        glBegin(
            GL_LINES
        )


        step = max(

            1,

            len(
                outer
            )
            //
            40
        )


        for index in range(

            0,

            len(
                outer
            ),

            step
        ):

            x, y = outer[
                index
            ]


            glVertex3f(
                x,
                y,
                back_z
            )


            glVertex3f(
                x,
                y,
                front_z
            )


        glEnd()


        # =====================================================
        # SPOKES
        # =====================================================

        glColor4f(

            0.20,

            0.80,

            0.82,

            alpha
            *
            0.72
        )


        glBegin(
            GL_LINES
        )


        for index in range(
            spokes
        ):

            angle = (

                index

                /
                spokes

                *
                math.tau
            )


            cosine = math.cos(
                angle
            )


            sine = math.sin(
                angle
            )


            glVertex3f(

                cosine
                *
                inner_radius
                *
                0.42,

                sine
                *
                inner_radius
                *
                0.42,

                front_z
                +
                0.01
            )


            glVertex3f(

                cosine
                *
                inner_radius
                *
                0.95,

                sine
                *
                inner_radius
                *
                0.95,

                front_z
                +
                0.01
            )


        glEnd()


        glPopMatrix()


    # =========================================================
    # MECHANICAL STACK
    # =========================================================

    def draw_mechanical_stack(
        self,
        alpha_scale
    ):

        layers = [

            (
                3.55,
                0.44,
                36,
                0.15,
                0.14,
                0.62,
                self.rotations[0],
                72,
                0
            ),

            (
                3.00,
                0.36,
                30,
                0.13,
                0.12,
                0.78,
                self.rotations[1],
                48,
                58
            ),

            (
                2.42,
                0.31,
                24,
                0.12,
                0.10,
                0.90,
                self.rotations[2],
                -38,
                22
            ),

            (
                1.88,
                0.25,
                20,
                0.10,
                0.09,
                0.88,
                self.rotations[3],
                80,
                -35
            )
        ]


        for (

            radius,
            width,
            teeth,
            tooth,
            depth,
            alpha,
            rotation,
            rotation_x,
            rotation_y

        ) in layers:

            glPushMatrix()


            glRotatef(

                rotation_x,

                1,
                0,
                0
            )


            glRotatef(

                rotation_y,

                0,
                1,
                0
            )


            self.draw_gear(

                radius,

                width,

                teeth,

                tooth,

                depth,

                alpha
                *
                alpha_scale,

                rotation
            )


            glPopMatrix()


        # =====================================================
        # LOCKING ARCS
        # =====================================================

        glDisable(
            GL_DEPTH_TEST
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE
        )


        for (

            ring_index,
            radius

        ) in enumerate(

            [
                3.95,
                3.62,
                2.72
            ]
        ):

            glPushMatrix()


            glRotatef(

                68
                -
                ring_index
                *
                18,

                1,
                0,
                0
            )


            glRotatef(

                self.rotations[
                    ring_index
                ]

                *

                (
                    0.7

                    +
                    ring_index
                    *
                    0.15
                ),

                0,
                0,
                1
            )


            glLineWidth(

                2.0

                if ring_index == 0

                else
                1.2
            )


            glColor4f(

                0.08,

                0.82,

                0.87,

                (
                    0.30
                    -
                    ring_index
                    *
                    0.06
                )
                *
                alpha_scale
            )


            for start in [

                4,
                95,
                185,
                278
            ]:

                self.draw_arc(

                    radius,

                    start,

                    start
                    +
                    48
                    -
                    ring_index
                    *
                    5
                )


            glPopMatrix()


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_DEPTH_TEST
        )


    # =========================================================
    # ARC
    # =========================================================

    def draw_arc(
        self,
        radius,
        start_degrees,
        end_degrees,
        segments=54
    ):

        glBegin(
            GL_LINE_STRIP
        )


        for index in range(
            segments + 1
        ):

            progress = (

                index
                /
                segments
            )


            angle = math.radians(

                start_degrees

                +

                (
                    end_degrees
                    -
                    start_degrees
                )

                *
                progress
            )


            glVertex3f(

                math.cos(
                    angle
                )
                *
                radius,

                math.sin(
                    angle
                )
                *
                radius,

                0
            )


        glEnd()


    # =========================================================
    # ENERGY CORE
    # =========================================================

    def draw_energy_core(
        self,
        alpha_scale
    ):

        if self.quadric is None:

            return


        pulse = (

            0.5

            +

            0.5
            *
            math.sin(
                self.t
                *
                4.0
            )
        )


        radius = (

            0.72

            +

            pulse
            *
            0.035

            +

            self.audio_smooth
            *
            0.10
        )


        # =====================================================
        # GLOW
        # =====================================================

        glDisable(
            GL_DEPTH_TEST
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE
        )


        for layer in range(

            9,

            0,

            -1
        ):

            glPushMatrix()


            scale = (

                1

                +

                layer
                *
                0.05
            )


            glScalef(

                scale,

                scale,

                scale
            )


            glColor4f(

                0.02,

                0.58,

                0.70,

                (
                    0.015

                    +

                    (
                        9
                        -
                        layer
                    )
                    *
                    0.008
                )

                *
                alpha_scale
            )


            gluQuadricDrawStyle(

                self.quadric,

                GLU_LINE
            )


            gluSphere(

                self.quadric,

                radius,

                28,

                18
            )


            glPopMatrix()


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_DEPTH_TEST
        )


        # =====================================================
        # CORE
        # =====================================================

        glPushMatrix()


        glRotatef(

            self.rotations[2]
            *
            0.25,

            0,
            1,
            0
        )


        glColor4f(

            0.02,

            0.34,

            0.40,

            0.28
            *
            alpha_scale
        )


        gluQuadricDrawStyle(

            self.quadric,

            GLU_FILL
        )


        gluSphere(

            self.quadric,

            radius
            *
            0.82,

            40,

            28
        )


        glColor4f(

            0.16,

            0.86,

            0.88,

            0.72
            *
            alpha_scale
        )


        gluQuadricDrawStyle(

            self.quadric,

            GLU_LINE
        )


        gluSphere(

            self.quadric,

            radius,

            32,

            20
        )


        glPopMatrix()


        # =====================================================
        # CENTER LIGHT
        # =====================================================

        glDisable(
            GL_DEPTH_TEST
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE
        )


        glPointSize(

            18

            +

            self.audio_smooth
            *
            22

            +

            (
                8
                if self.processing
                else
                0
            )
        )


        glColor4f(

            0.70,

            1.0,

            1.0,

            0.96
            *
            alpha_scale
        )


        glBegin(
            GL_POINTS
        )


        glVertex3f(
            0,
            0,
            0
        )


        glEnd()


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_DEPTH_TEST
        )


    # =========================================================
    # SIGNAL RING
    # =========================================================

    def draw_signal_ring(
        self,
        alpha_scale
    ):

        if not (

            self.listening

            or

            self.speaking

            or

            self.processing

        ):

            return


        glDisable(
            GL_DEPTH_TEST
        )


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE
        )


        glPushMatrix()


        glRotatef(

            -22,

            1,
            0,
            0
        )


        glRotatef(

            self.rotations[1]
            *
            0.30,

            0,
            0,
            1
        )


        glLineWidth(
            2.0
        )


        if self.processing:

            color = (
                0.78,
                0.86,
                0.90
            )


        elif self.listening:

            color = (
                0.18,
                0.95,
                0.82
            )


        else:

            color = (
                0.28,
                0.82,
                0.92
            )


        glColor4f(

            color[0],

            color[1],

            color[2],

            0.72
            *
            alpha_scale
        )


        glBegin(
            GL_LINE_LOOP
        )


        points = 180


        for index in range(
            points
        ):

            angle = (

                index

                /
                points

                *
                math.tau
            )


            wave = (

                math.sin(

                    angle
                    *
                    11

                    +

                    self.t
                    *
                    6

                )

                *

                (
                    0.018

                    +

                    self.audio_smooth
                    *
                    0.16
                )
            )


            radius = (

                1.48

                +

                wave
            )


            glVertex3f(

                math.cos(
                    angle
                )
                *
                radius,

                math.sin(
                    angle
                )
                *
                radius,

                0
            )


        glEnd()


        glPopMatrix()


        glBlendFunc(

            GL_SRC_ALPHA,

            GL_ONE_MINUS_SRC_ALPHA
        )


        glEnable(
            GL_DEPTH_TEST
        )