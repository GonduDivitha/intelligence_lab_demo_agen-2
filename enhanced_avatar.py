"""
Enhanced Avatar Module for Intelligence Lab Demo Agent.

Provides a high-quality, human-like anime character widget with lip sync,
gestures, expressions, and breathing animation using PySide6.
"""

import math
import random
import time
import numpy as np
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QConicalGradient
)
from PySide6.QtWidgets import QWidget

# Timed visemes mapping (real-world milliseconds) to EnhancedAvatar mouth shape indices (0-5, or -1)
def char_to_viseme_timed(ch):
    ch = ch.lower()
    
    # ── English Mapping ──
    mapping = {
        'a': (3, 70),   # 'aa' shape (wide)
        'e': (5, 60),   # 'ee' shape (smile)
        'i': (5, 55),   # 'ee' shape (smile)
        'o': (4, 70),   # 'oh' shape (O shape)
        'u': (4, 70),   # 'oh' shape (O shape)
        'b': (0, 45),   # 'mm' shape (closed)
        'm': (0, 50),   # 'mm' shape (closed)
        'p': (0, 45),   # 'mm' shape (closed)
        'f': (1, 45),   # 'ff' shape (slightly open)
        'v': (1, 45),
        's': (1, 45),   # 'ss' shape (slightly open)
        'z': (1, 45),
        'c': (1, 45),
        'x': (1, 45),
        'w': (4, 60),   # 'oo' shape (O shape)
        'r': (4, 50),
        'q': (4, 50),
        'd': (1, 40),   # 'th' shape (slightly open)
        't': (1, 40),
        'n': (1, 45),
        'l': (1, 45),
        'g': (1, 40),
        'k': (1, 40),
        'j': (5, 50),
        'y': (5, 50),
        'h': (3, 50),
        ' ': (0, 55),   # rest
        ',': (0, 120),
        '.': (0, 200),  # boundaries
        '!': (0, 200),
        '?': (0, 200),
    }
    
    if ch in mapping:
        v, dur = mapping[ch]
        is_boundary = ch in ('.', '!', '?')
        return (v, dur, is_boundary)
        
    # ── Multilingual Hindi & Telugu Phonetic Mapping ──
    # 1. Labials (Mouth closed): प, फ, ब, भ, म, ప, ఫ, బ, భ, మ
    if ch in ('प', 'फ', 'ब', 'भ', 'म', 'ప', 'ఫ', 'బ', 'భ', 'మ'):
        return (0, 50, False)
        
    # 2. Wide / Rounded Vowels: अ, आ, ओ, औ, ा, ो, ौ, అ, ఆ, ఒ, ఓ, ఔ, ా, ొ, ో, ౌ
    if ch in ('अ', 'आ', 'ओ', 'औ', 'ा', 'ो', 'ौ', 'అ', 'ఆ', 'ఒ', 'ఓ', 'ఔ', 'ా', 'ొ', 'ో', 'ౌ'):
        return (3, 70, False)
        
    # 3. Smile Vowels: इ, ई, ए, ऐ, ि, ी, े, ै, ఇ, ఈ, ఎ, ఏ, ఐ, ి, ీ, ె, ే, ై
    if ch in ('इ', 'ई', 'ए', 'ऐ', 'ि', 'ी', 'े', 'ै', 'ఇ', 'ఈ', 'ఎ', 'ఏ', 'ఐ', 'ి', 'ీ', 'ె', 'ే', 'ై'):
        return (5, 60, False)
        
    # 4. Sentence boundaries
    if ch in ('।', '|', '.', '!', '?'):
        return (0, 200, True)
        
    # Default slightly open consonant
    return (1, 45, False)


STATES = [
    'hidden', 'greeting', 'listening', 'thinking',
    'presenting', 'speaking', 'answering', 'idle', 'farewell'
]

EXPRESSIONS = [
    'neutral', 'happy', 'thinking', 'explaining',
    'listening', 'surprised', 'warm_smile'
]

MOUTH_SHAPES = [
    'closed', 'slightly_open', 'open', 'wide', 'o_shape', 'smile'
]

# State → expression mapping
_STATE_EXPRESSION_MAP = {
    'greeting': 'happy',
    'listening': 'listening',
    'thinking': 'thinking',
    'presenting': 'explaining',
    'speaking': 'explaining',
    'answering': 'explaining',
    'idle': 'warm_smile',
    'farewell': 'happy',
}


class EnhancedAvatar(QWidget):
    """A premium anime-style avatar widget with lip sync, gestures,
    expressions, and breathing animation."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 360)

        # Core state
        self.state = 'hidden'
        self.expression = 'neutral'
        self.visible_agent = False
        self.tick = 0

        # Speaking / lip-sync (time-based)
        self._is_speaking = False
        self._mouth_shape_index = 0
        self._viseme_queue = []
        self._viseme_idx = 0
        self._viseme_end_time = 0.0

        # Gesture timeline variables (seconds)
        self._gesture_state = "idle"  # "start", "mid", "rest"
        self._gesture_start_time = 0.0

        # Animation phases
        self._gesture_phase = 0.0
        self._breathing_phase = 0.0
        self._nod_phase = 0.0
        self._head_tilt = 0.0
        self._eyebrow_raise = 0.0
        self._eye_sparkle = 0.0

        # Eye tracking visitor coordinates (-1.0 to 1.0)
        self._visitor_x = 0.0
        self._visitor_y = 0.0
        self._target_visitor_x = 0.0
        self._target_visitor_y = 0.0

        # Smooth transitions
        self._transition_progress = 1.0
        self._target_state = 'hidden'

        # Background particles
        self._particles = []
        for _ in range(15):
            self._particles.append({
                'x': random.random(),
                'y': random.random(),
                'speed': 0.001 + random.random() * 0.003,
                'size': 2 + random.random() * 4,
                'drift': (random.random() - 0.5) * 0.002,
                'alpha': random.randint(40, 120),
                'hue': random.choice([210, 250, 280]),  # blue / purple / cyan-ish
            })

        # Animation timer (~30 fps)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._animate)
        self._timer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def pop_out(self):
        """Make the avatar visible and start with a greeting."""
        self.visible_agent = True
        self._target_state = 'greeting'
        self._transition_progress = 0.0
        self.expression = 'happy'

    def set_state(self, state: str):
        """Transition the avatar to *state* smoothly."""
        if not self.visible_agent:
            return
        if state in STATES:
            self._target_state = state
            self._transition_progress = 0.0
            self.expression = _STATE_EXPRESSION_MAP.get(state, 'neutral')

    def set_speaking(self, is_speaking: bool):
        """Enable / disable lip-sync animation."""
        was = self._is_speaking
        self._is_speaking = is_speaking
        if is_speaking and not was:
            self._viseme_idx = 0
            self._viseme_end_time = time.time()
            self._gesture_state = "start"
            self._gesture_start_time = time.time()
            self.set_state('presenting')
        elif not is_speaking and was:
            self._viseme_queue = []
            self._mouth_shape_index = 0
            self.set_state('idle')
            self._gesture_state = "idle"

    def set_speaking_text(self, text: str):
        """Convert text into a timed viseme queue."""
        self._viseme_queue = [char_to_viseme_timed(ch) for ch in text]
        self._viseme_idx = 0
        self._viseme_end_time = time.time()

    def set_visitor_position(self, rel_x: float, rel_y: float):
        """Set the target tracking coordinates of the visitor."""
        self._target_visitor_x = max(-1.0, min(1.0, rel_x))
        self._target_visitor_y = max(-1.0, min(1.0, rel_y))

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------
    def _animate(self):
        self.tick += 1

        # Breathing
        self._breathing_phase += 0.04

        # Gesture
        self._gesture_phase += 0.03

        # Time-based Lip Sync
        current_time = time.time()
        if self._is_speaking:
            if current_time >= self._viseme_end_time:
                if self._viseme_queue and self._viseme_idx < len(self._viseme_queue):
                    shape_idx, duration_ms, is_boundary = self._viseme_queue[self._viseme_idx]
                    self._mouth_shape_index = shape_idx
                    self._viseme_end_time = current_time + (duration_ms / 1000.0)
                    self._viseme_idx += 1

                    # Trigger dynamic state changes on sentence boundaries
                    if is_boundary and random.random() < 0.7:
                        self._gesture_state = "start"
                        self._gesture_start_time = current_time
                        self.set_state(random.choice(['presenting', 'speaking']))
                else:
                    # Backup speaking loop when queue runs dry
                    cycle = [(3, 100), (5, 90), (4, 100), (0, 80)]
                    idx = int(current_time * 6) % len(cycle)
                    self._mouth_shape_index = cycle[idx][0]
                    self._viseme_end_time = current_time + (cycle[idx][1] / 1000.0)

            # Event-driven gestures
            elapsed_gesture = current_time - self._gesture_start_time
            if self._gesture_state == "start" and elapsed_gesture >= 2.2:
                self._gesture_state = "mid"
                self.set_state("speaking")
            elif self._gesture_state == "mid" and elapsed_gesture >= 5.0:
                self._gesture_state = "rest"
                self.set_state("idle")
        else:
            self._mouth_shape_index = 0

        # Nodding while listening
        if self.state == 'listening':
            self._nod_phase += 0.05

        # Smooth state transition
        self._transition_progress = min(1.0, self._transition_progress + 0.08)
        if self._transition_progress >= 1.0:
            self.state = self._target_state

        # Eye sparkle fluctuation
        self._eye_sparkle = 0.5 + 0.5 * math.sin(self.tick * 0.08)

        # Eyebrow animation for explaining
        if self.expression == 'explaining':
            self._eyebrow_raise = math.sin(self._gesture_phase * 2) * 4
        elif self.expression == 'surprised':
            self._eyebrow_raise = 6
        else:
            self._eyebrow_raise *= 0.9  # ease back

        # Head tilt
        target_tilt = 0.0
        if self.state == 'thinking':
            target_tilt = 5.0
        elif self.state == 'listening':
            target_tilt = -4.0 + math.sin(self._nod_phase) * 3
        self._head_tilt += (target_tilt - self._head_tilt) * 0.1

        # Smooth easing for pupil tracking
        self._visitor_x += (self._target_visitor_x - self._visitor_x) * 0.15
        self._visitor_y += (self._target_visitor_y - self._visitor_y) * 0.15

        # Particle update
        for p in self._particles:
            p['y'] -= p['speed']
            p['x'] += p['drift']
            if p['y'] < -0.05:
                p['y'] = 1.05
                p['x'] = random.random()

        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = self.rect()

        self._draw_background(painter, rect)
        self._draw_particles(painter, rect)
        self._draw_title(painter, rect)

        if not self.visible_agent:
            self._draw_waiting_text(painter, rect)
            painter.end()
            return

        # Scale character rendering to make Aiko look big, premium, and professional
        painter.save()
        scale_factor = 1.3
        dx = (rect.width() * (1 - scale_factor)) / 2
        dy = 15 # push character slightly down to align naturally
        painter.translate(dx, dy)
        painter.scale(scale_factor, scale_factor)

        self._draw_character(painter, rect)
        painter.restore()

        self._draw_status_bar(painter, rect)
        painter.end()

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------
    def _draw_background(self, painter, rect):
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, QColor(18, 20, 52))
        grad.setColorAt(1.0, QColor(6, 8, 18))
        painter.fillRect(rect, grad)

        # Subtle radial glow behind character position
        cx = rect.width() / 2
        cy = rect.height() * 0.38
        glow = QRadialGradient(cx, cy, rect.width() * 0.45)
        glow.setColorAt(0.0, QColor(40, 70, 160, 45))
        glow.setColorAt(0.5, QColor(20, 30, 80, 20))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), rect.width() * 0.45, rect.height() * 0.35)

    # ------------------------------------------------------------------
    # Particles
    # ------------------------------------------------------------------
    def _draw_particles(self, painter, rect):
        w, h = rect.width(), rect.height()
        for p in self._particles:
            px = p['x'] * w
            py = p['y'] * h
            hue = p['hue']
            alpha = int(p['alpha'] * (0.5 + 0.5 * math.sin(self.tick * 0.04 + p['x'] * 10)))
            alpha = max(0, min(255, alpha))
            color = QColor.fromHsv(hue, 120, 220, alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), p['size'], p['size'])

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------
    def _draw_title(self, painter, rect):
        font = QFont("Segoe UI", 14, QFont.Bold)
        painter.setFont(font)

        # Glow layer
        painter.setPen(QColor(130, 170, 255, 60))
        title_rect = QRectF(0, 8, rect.width(), 30)
        painter.drawText(title_rect, Qt.AlignCenter, "AI Presenter: Aiko")

        # Main text with gradient pen
        painter.setPen(QColor(200, 220, 255))
        painter.drawText(title_rect, Qt.AlignCenter, "AI Presenter: Aiko")

    # ------------------------------------------------------------------
    # Waiting text
    # ------------------------------------------------------------------
    def _draw_waiting_text(self, painter, rect):
        painter.setPen(QColor(130, 150, 200, 160))
        font = QFont("Segoe UI", 12)
        painter.setFont(font)
        alpha = int(120 + 80 * math.sin(self.tick * 0.06))
        painter.setPen(QColor(130, 150, 200, alpha))
        painter.drawText(rect, Qt.AlignCenter, "Waiting for session to start…")

    # ------------------------------------------------------------------
    # Character orchestrator
    # ------------------------------------------------------------------
    def _draw_character(self, painter, rect):
        cx = rect.width() // 2
        breath_offset = int(math.sin(self._breathing_phase) * 3)
        cy = 165 + breath_offset

        self._draw_hair_back(painter, cx, cy)
        self._draw_body(painter, cx, cy)
        self._draw_neck(painter, cx, cy)
        self._draw_head(painter, cx, cy)
        self._draw_eyes(painter, cx, cy)
        self._draw_eyebrows(painter, cx, cy)
        self._draw_nose(painter, cx, cy)
        self._draw_mouth(painter, cx, cy)
        self._draw_blush(painter, cx, cy)
        self._draw_hair_front(painter, cx, cy)
        self._draw_arms(painter, cx, cy)

    # ------------------------------------------------------------------
    # Head / face
    # ------------------------------------------------------------------
    def _draw_head(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        # Face shape via QPainterPath for smooth curves
        path = QPainterPath()
        fw, fh = 60, 68  # half-widths
        # Start at top-center
        path.moveTo(0, -fh)
        # Right side
        path.cubicTo(fw * 1.1, -fh * 0.7, fw, fh * 0.3, fw * 0.45, fh * 0.85)
        # Chin
        path.cubicTo(fw * 0.2, fh, -fw * 0.2, fh, -fw * 0.45, fh * 0.85)
        # Left side
        path.cubicTo(-fw, fh * 0.3, -fw * 1.1, -fh * 0.7, 0, -fh)
        path.closeSubpath()

        # Skin gradient
        skin_grad = QLinearGradient(0, -fh, 0, fh)
        skin_grad.setColorAt(0.0, QColor(255, 228, 218))
        skin_grad.setColorAt(0.5, QColor(255, 222, 210))
        skin_grad.setColorAt(1.0, QColor(248, 210, 198))
        painter.setBrush(QBrush(skin_grad))
        painter.setPen(QPen(QColor(230, 190, 178), 1))
        painter.drawPath(path)

        # Subtle jaw shadow
        jaw = QPainterPath()
        jaw.moveTo(-fw * 0.45, fh * 0.75)
        jaw.cubicTo(-fw * 0.2, fh * 0.95, fw * 0.2, fh * 0.95, fw * 0.45, fh * 0.75)
        painter.setPen(QPen(QColor(230, 190, 178, 60), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(jaw)

        painter.restore()

    # ------------------------------------------------------------------
    # Eyes — THE most important anime feature
    # ------------------------------------------------------------------
    def _draw_eyes(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        eye_spacing = 26  # half-distance between eyes
        ey = -8  # vertical position relative to face center

        is_blinking = (self.tick % 90 < 4)

        for side in (-1, 1):
            ex = side * eye_spacing

            if is_blinking:
                # Blink — draw as a curved line
                painter.setPen(QPen(QColor(35, 30, 80), 2.5))
                painter.setBrush(Qt.NoBrush)
                blink_path = QPainterPath()
                blink_path.moveTo(ex - 14, ey)
                blink_path.quadTo(ex, ey + 4, ex + 14, ey)
                painter.drawPath(blink_path)
                continue

            # Expression-based eye modifications
            ew, eh = 15, 18  # half-width, half-height of eye
            gaze_y = 0
            draw_as_happy_curve = False

            if self.expression == 'thinking':
                eh = 14  # squint
                gaze_y = -4  # look up
            elif self.expression == 'surprised':
                eh = 22
                ew = 17
            elif self.expression in ('happy', 'warm_smile'):
                draw_as_happy_curve = True
            elif self.expression == 'listening':
                gaze_y = -2  # slight upward gaze

            if draw_as_happy_curve:
                # Happy anime eyes — upward curved arcs
                painter.setPen(QPen(QColor(35, 30, 80), 3))
                painter.setBrush(Qt.NoBrush)
                arc_path = QPainterPath()
                arc_path.moveTo(ex - 14, ey + 2)
                arc_path.quadTo(ex, ey - 10, ex + 14, ey + 2)
                painter.drawPath(arc_path)
                # Small sparkle under happy eye
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, 180))
                painter.drawEllipse(QPointF(ex - 5, ey - 3), 2, 2)
            else:
                # --- Full detailed anime eye ---
                # Outer eye shape (white)
                eye_path = QPainterPath()
                eye_path.addEllipse(QRectF(ex - ew, ey - eh + gaze_y, ew * 2, eh * 2))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawPath(eye_path)

                # Iris — gradient blue
                iris_r = min(ew, eh) * 0.72
                
                # Pupil offset for eye tracking (parallax depth)
                max_offset_x = iris_r * 0.35
                max_offset_y = iris_r * 0.25
                offset_x = self._visitor_x * max_offset_x
                offset_y = self._visitor_y * max_offset_y

                iris_grad = QRadialGradient(ex + offset_x, ey + gaze_y + offset_y, iris_r)
                iris_grad.setColorAt(0.0, QColor(100, 160, 255))
                iris_grad.setColorAt(0.45, QColor(50, 100, 255))
                iris_grad.setColorAt(1.0, QColor(30, 60, 200))
                painter.setBrush(QBrush(iris_grad))
                painter.drawEllipse(QPointF(ex + offset_x, ey + gaze_y + offset_y), iris_r, iris_r)

                # Pupil (slightly higher offset factor for 3D parallax depth)
                pupil_r = iris_r * 0.42
                painter.setBrush(QColor(10, 10, 30))
                painter.drawEllipse(QPointF(ex + offset_x * 1.15, ey + gaze_y + offset_y * 1.15), pupil_r, pupil_r)

                # --- Highlights / sparkles (critical for anime) ---
                # Large upper-left highlight (shifts slightly less to create depth against iris)
                hl_x = ex + offset_x * 0.8 - iris_r * 0.35
                hl_y = ey + gaze_y + offset_y * 0.8 - iris_r * 0.35
                sparkle_alpha = int(200 + 55 * self._eye_sparkle)
                painter.setBrush(QColor(255, 255, 255, min(255, sparkle_alpha)))
                painter.drawEllipse(QPointF(hl_x, hl_y), iris_r * 0.32, iris_r * 0.32)
                # Small lower-right highlight
                painter.drawEllipse(QPointF(ex + offset_x * 0.8 + iris_r * 0.3, ey + gaze_y + offset_y * 0.8 + iris_r * 0.25),
                                    iris_r * 0.15, iris_r * 0.15)

                # Outer eye line / lash
                painter.setPen(QPen(QColor(35, 30, 80), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(eye_path)

                # Upper eyelash accent
                lash = QPainterPath()
                lash.moveTo(ex - ew - 2, ey - eh * 0.3 + gaze_y)
                lash.quadTo(ex, ey - eh - 3 + gaze_y, ex + ew + 2, ey - eh * 0.3 + gaze_y)
                painter.setPen(QPen(QColor(25, 20, 60), 2.5))
                painter.drawPath(lash)

                # Lower lash (subtle)
                lower_lash = QPainterPath()
                lower_lash.moveTo(ex - ew * 0.7, ey + eh * 0.85 + gaze_y)
                lower_lash.quadTo(ex, ey + eh + 1 + gaze_y, ex + ew * 0.7, ey + eh * 0.85 + gaze_y)
                painter.setPen(QPen(QColor(35, 30, 80, 100), 1.2))
                painter.drawPath(lower_lash)

        painter.restore()

    # ------------------------------------------------------------------
    # Eyebrows
    # ------------------------------------------------------------------
    def _draw_eyebrows(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        color = QColor(30, 32, 90)
        painter.setPen(QPen(color, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)

        brow_y = -32
        brow_spacing = 26
        raise_l = 0
        raise_r = 0

        if self.expression == 'thinking':
            raise_l = -2  # furrow
            raise_r = 5   # raise
        elif self.expression == 'surprised':
            raise_l = 7
            raise_r = 7
        elif self.expression in ('happy', 'warm_smile'):
            raise_l = 3
            raise_r = 3
        elif self.expression == 'explaining':
            raise_l = self._eyebrow_raise
            raise_r = self._eyebrow_raise * 0.5

        for side, raise_amt in [(-1, raise_l), (1, raise_r)]:
            bx = side * brow_spacing
            by = brow_y - raise_amt
            brow = QPainterPath()
            brow.moveTo(bx - side * 14, by + 2)
            brow.quadTo(bx, by - 4, bx + side * 14, by + 1)
            painter.drawPath(brow)

        painter.restore()

    # ------------------------------------------------------------------
    # Nose
    # ------------------------------------------------------------------
    def _draw_nose(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        # Minimal anime nose — a small shadow curve
        painter.setPen(QPen(QColor(210, 175, 165, 180), 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        nose = QPainterPath()
        nose.moveTo(-3, 14)
        nose.quadTo(0, 20, 3, 17)
        painter.drawPath(nose)

        # Tiny highlight
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 240, 235, 100))
        painter.drawEllipse(QPointF(1, 15), 2, 1.5)

        painter.restore()

    # ------------------------------------------------------------------
    # Mouth — lip sync
    # ------------------------------------------------------------------
    def _draw_mouth(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        my = 34  # mouth vertical centre relative to face centre
        lip_color = QColor(220, 130, 150)
        lip_outline = QColor(190, 100, 120)

        if self._is_speaking:
            shape = self._mouth_shape_index
        else:
            # Expression-based mouth when not speaking
            if self.expression in ('happy', 'warm_smile'):
                shape = 5  # smile
            elif self.expression == 'thinking':
                shape = -1  # pursed (custom)
            elif self.expression == 'surprised':
                shape = 4  # O
            else:
                shape = 0  # closed

        painter.setPen(QPen(lip_outline, 1.5, Qt.SolidLine, Qt.RoundCap))

        if shape == 0:
            # Closed — gentle smile curve
            smile = QPainterPath()
            smile.moveTo(-12, my)
            smile.quadTo(0, my + 5, 12, my)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(smile)
        elif shape == 1:
            # Slightly open
            painter.setBrush(QColor(180, 60, 80))
            painter.drawEllipse(QRectF(-8, my - 3, 16, 8))
            painter.setPen(QPen(lip_color, 1.5))
            upper = QPainterPath()
            upper.moveTo(-9, my)
            upper.quadTo(0, my - 4, 9, my)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(upper)
        elif shape == 2:
            # Open
            painter.setBrush(QColor(160, 50, 70))
            painter.drawEllipse(QRectF(-10, my - 5, 20, 14))
            # Upper lip
            painter.setPen(QPen(lip_color, 1.5))
            painter.setBrush(Qt.NoBrush)
            ul = QPainterPath()
            ul.moveTo(-11, my)
            ul.quadTo(0, my - 6, 11, my)
            painter.drawPath(ul)
        elif shape == 3:
            # Wide
            painter.setBrush(QColor(150, 45, 65))
            painter.drawEllipse(QRectF(-14, my - 6, 28, 16))
            painter.setPen(QPen(lip_color, 1.5))
            painter.setBrush(Qt.NoBrush)
            ul = QPainterPath()
            ul.moveTo(-15, my)
            ul.quadTo(0, my - 7, 15, my)
            painter.drawPath(ul)
        elif shape == 4:
            # O shape
            painter.setBrush(QColor(160, 50, 70))
            painter.drawEllipse(QRectF(-7, my - 6, 14, 14))
            painter.setPen(QPen(lip_color, 1.8))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(-8, my - 7, 16, 16))
        elif shape == 5:
            # Wide smile
            smile = QPainterPath()
            smile.moveTo(-16, my - 1)
            smile.quadTo(0, my + 10, 16, my - 1)
            painter.setBrush(QColor(170, 55, 75))
            painter.drawPath(smile)
            # Upper lip line
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(lip_color, 1.5))
            ul = QPainterPath()
            ul.moveTo(-16, my - 1)
            ul.quadTo(-5, my - 3, 0, my - 2)
            ul.quadTo(5, my - 3, 16, my - 1)
            painter.drawPath(ul)
        elif shape == -1:
            # Pursed / thinking
            painter.setBrush(Qt.NoBrush)
            pursed = QPainterPath()
            pursed.moveTo(-5, my + 1)
            pursed.quadTo(0, my - 2, 5, my + 1)
            painter.drawPath(pursed)

        painter.restore()

    # ------------------------------------------------------------------
    # Blush
    # ------------------------------------------------------------------
    def _draw_blush(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt)

        alpha = 140 if self.expression in ('happy', 'warm_smile') else 80
        blush = QColor(255, 150, 175, alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(blush)

        # Left cheek
        painter.drawEllipse(QPointF(-36, 14), 14, 7)
        # Right cheek
        painter.drawEllipse(QPointF(36, 14), 14, 7)

        painter.restore()

    # ------------------------------------------------------------------
    # Hair — back layer
    # ------------------------------------------------------------------
    def _draw_hair_back(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt * 0.5)

        hair_color = QColor(115, 74, 52)  # Rich brown
        hair_dark = QColor(80, 48, 32)    # Dark brown shadow

        sway = math.sin(self._breathing_phase * 0.7) * 2

        painter.setPen(Qt.NoPen)

        # Main back hair volume — left side
        grad_l = QLinearGradient(-60, -70, -40, 180)
        grad_l.setColorAt(0.0, hair_color)
        grad_l.setColorAt(1.0, hair_dark)
        painter.setBrush(QBrush(grad_l))
        left_hair = QPainterPath()
        left_hair.moveTo(-15, -65)
        left_hair.cubicTo(-70, -50, -65 + sway, 60, -50 + sway, 160)
        left_hair.lineTo(-30 + sway, 165)
        left_hair.cubicTo(-40, 80, -50, -10, -5, -60)
        left_hair.closeSubpath()
        painter.drawPath(left_hair)

        # Right side
        grad_r = QLinearGradient(60, -70, 40, 180)
        grad_r.setColorAt(0.0, hair_color)
        grad_r.setColorAt(1.0, hair_dark)
        painter.setBrush(QBrush(grad_r))
        right_hair = QPainterPath()
        right_hair.moveTo(15, -65)
        right_hair.cubicTo(70, -50, 65 - sway, 60, 50 - sway, 160)
        right_hair.lineTo(30 - sway, 165)
        right_hair.cubicTo(40, 80, 50, -10, 5, -60)
        right_hair.closeSubpath()
        painter.drawPath(right_hair)

        # Center back volume
        painter.setBrush(hair_dark)
        center = QPainterPath()
        center.moveTo(-25, -55)
        center.cubicTo(-10, -70, 10, -70, 25, -55)
        center.cubicTo(30, 0, 20, 100, 15 - sway * 0.5, 150)
        center.lineTo(-15 + sway * 0.5, 150)
        center.cubicTo(-20, 100, -30, 0, -25, -55)
        center.closeSubpath()
        painter.drawPath(center)

        painter.restore()

    # ------------------------------------------------------------------
    # Hair — front layer (bangs, side strands)
    # ------------------------------------------------------------------
    def _draw_hair_front(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._head_tilt * 0.7)

        hair_color = QColor(115, 74, 52)  # Rich brown
        highlight = QColor(158, 114, 88)   # Soft warm highlights
        sway = math.sin(self._gesture_phase * 0.8) * 1.5

        painter.setPen(Qt.NoPen)
        painter.setBrush(hair_color)

        # Bangs — multiple overlapping strands
        strands = [
            (-30, -68, -35 + sway, -20, -18, -35),
            (-15, -72, -20 + sway, -15, -2, -38),
            (0, -74, -5 + sway, -12, 12, -38),
            (15, -72, 18 + sway, -15, 28, -35),
            (28, -68, 33 + sway, -20, 40, -30),
        ]
        for sx, sy, cx1, cy1, ex, ey in strands:
            strand = QPainterPath()
            strand.moveTo(sx, sy)
            strand.quadTo(cx1, cy1, ex, ey)
            # Widen strand
            strand.lineTo(ex + 8, ey + 2)
            strand.quadTo(cx1 + 6, cy1 + 5, sx + 6, sy + 2)
            strand.closeSubpath()
            painter.drawPath(strand)

        # Top hair cap
        cap = QPainterPath()
        cap.moveTo(-50, -50)
        cap.cubicTo(-55, -75, -20, -88, 0, -86)
        cap.cubicTo(20, -88, 55, -75, 50, -50)
        cap.cubicTo(35, -60, -35, -60, -50, -50)
        cap.closeSubpath()
        painter.drawPath(cap)

        # Side strands framing face
        for side in (-1, 1):
            sx = side * 55
            strand = QPainterPath()
            strand.moveTo(sx, -45)
            strand.cubicTo(sx + side * 8, -10, sx + side * 3 + sway, 40, sx - side * 5 + sway, 80)
            painter.setPen(QPen(hair_color, 10, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(strand)

        # Hair highlights / shine streaks
        painter.setPen(QPen(highlight, 1.2))
        painter.setBrush(Qt.NoBrush)
        for offset_x, offset_y, length in [(-20, -70, 30), (5, -74, 25), (25, -68, 20)]:
            hl = QPainterPath()
            hl.moveTo(offset_x, offset_y)
            hl.quadTo(offset_x + length * 0.5, offset_y - 3, offset_x + length, offset_y + 5)
            painter.drawPath(hl)

        painter.restore()

    # ------------------------------------------------------------------
    # Body (lab coat)
    # ------------------------------------------------------------------
    def _draw_body(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)

        body_top = 62
        body_w = 70  # half-width at shoulders
        body_h = 150

        # Navy blue blazer suit
        coat_grad = QLinearGradient(0, body_top, 0, body_top + body_h)
        coat_grad.setColorAt(0.0, QColor(25, 45, 110))    # Royal Navy Blue
        coat_grad.setColorAt(0.5, QColor(15, 30, 85))     # Deep Navy Blue
        coat_grad.setColorAt(1.0, QColor(8, 18, 55))      # Dark Navy shadow

        coat = QPainterPath()
        coat.moveTo(-body_w + 5, body_top)
        coat.cubicTo(-body_w, body_top + 20, -body_w + 10, body_top + body_h,
                     -body_w + 20, body_top + body_h)
        coat.lineTo(body_w - 20, body_top + body_h)
        coat.cubicTo(body_w - 10, body_top + body_h, body_w, body_top + 20,
                     body_w - 5, body_top)
        coat.closeSubpath()

        painter.setPen(QPen(QColor(10, 25, 75), 1))
        painter.setBrush(QBrush(coat_grad))
        painter.drawPath(coat)

        # Gray inner blouse underneath at neckline
        shirt = QPainterPath()
        shirt.moveTo(-22, body_top)
        shirt.lineTo(-15, body_top + 30)
        shirt.quadTo(0, body_top + 35, 15, body_top + 30)
        shirt.lineTo(22, body_top)
        shirt.closeSubpath()
        shirt_grad = QLinearGradient(0, body_top, 0, body_top + 30)
        shirt_grad.setColorAt(0.0, QColor(210, 212, 222))
        shirt_grad.setColorAt(1.0, QColor(165, 168, 178))
        painter.setBrush(QBrush(shirt_grad))
        painter.setPen(Qt.NoPen)
        painter.drawPath(shirt)

        # Silver necklace and pendant
        necklace = QPainterPath()
        necklace.moveTo(-10, body_top + 10)
        necklace.quadTo(0, body_top + 22, 10, body_top + 10)
        painter.setPen(QPen(QColor(220, 225, 235), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(necklace)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(240, 245, 255))
        painter.drawEllipse(QPointF(0, body_top + 22), 2, 2)

        # Blazer lapels
        painter.setPen(QPen(QColor(40, 70, 160), 1.8))
        painter.setBrush(QColor(15, 30, 85))
        collar_l = QPainterPath()
        collar_l.moveTo(-28, body_top - 2)
        collar_l.lineTo(-12, body_top + 30)
        collar_l.lineTo(-24, body_top + 30)
        collar_l.closeSubpath()
        painter.drawPath(collar_l)
        
        collar_r = QPainterPath()
        collar_r.moveTo(28, body_top - 2)
        collar_r.lineTo(12, body_top + 30)
        collar_r.lineTo(24, body_top + 30)
        collar_r.closeSubpath()
        painter.drawPath(collar_r)

        # Coat folds / creases
        painter.setPen(QPen(QColor(190, 195, 220, 80), 1))
        for fx in [-25, 0, 25]:
            fold = QPainterPath()
            fold.moveTo(fx, body_top + 40)
            fold.quadTo(fx + 2, body_top + 80, fx - 1, body_top + 120)
            painter.drawPath(fold)

        # ID badge on chest
        badge_x = -30
        badge_y = body_top + 25
        painter.setPen(QPen(QColor(150, 160, 190), 1))
        painter.setBrush(QColor(100, 140, 220, 180))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, 16, 20), 2, 2)
        # Badge clip
        painter.setPen(QPen(QColor(180, 190, 210), 1.5))
        painter.drawLine(int(badge_x + 8), int(badge_y), int(badge_x + 8), int(badge_y - 6))

        painter.restore()

    # ------------------------------------------------------------------
    # Neck
    # ------------------------------------------------------------------
    def _draw_neck(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)

        neck_w = 16  # half-width
        neck_top = 52
        neck_bot = 68

        # Skin
        skin_grad = QLinearGradient(0, neck_top, 0, neck_bot)
        skin_grad.setColorAt(0.0, QColor(255, 222, 210))
        skin_grad.setColorAt(1.0, QColor(248, 212, 200))
        painter.setBrush(QBrush(skin_grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(-neck_w, neck_top, neck_w * 2, neck_bot - neck_top))

        # Subtle shadow on left side
        painter.setBrush(QColor(230, 195, 185, 60))
        painter.drawRect(QRectF(-neck_w, neck_top, 6, neck_bot - neck_top))

        painter.restore()

    # ------------------------------------------------------------------
    # Arms — gesture-based positioning
    # ------------------------------------------------------------------
    def _draw_arms(self, painter, cx, cy):
        painter.save()
        painter.translate(cx, cy)

        sleeve_color = QColor(15, 30, 85)  # Navy blue sleeves to match blazer
        skin_color = QColor(255, 222, 210)
        body_top = 62

        state = self.state

        # Helper to draw an arm segment
        def draw_arm(shoulder_x, shoulder_y, elbow_x, elbow_y, hand_x, hand_y):
            # Sleeve (upper arm)
            painter.setPen(QPen(sleeve_color, 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(shoulder_x), int(shoulder_y), int(elbow_x), int(elbow_y))
            # Skin (forearm)
            painter.setPen(QPen(skin_color, 12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(elbow_x), int(elbow_y), int(hand_x), int(hand_y))
            # Hand — small circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(skin_color)
            painter.drawEllipse(QPointF(hand_x, hand_y), 8, 8)

        shoulder_l = (-60, body_top + 10)
        shoulder_r = (60, body_top + 10)

        wave = math.sin(self.tick * 0.15)
        gest = math.sin(self._gesture_phase * 2)

        if state == 'greeting':
            # Right arm waving
            draw_arm(*shoulder_l, -70, body_top + 60, -65, body_top + 110)
            rh_y = body_top - 20 + wave * 25
            draw_arm(*shoulder_r, 75, body_top + 10, 85, rh_y)

        elif state == 'presenting':
            # Right arm extended pointing right
            draw_arm(*shoulder_l, -65, body_top + 60, -55, body_top + 110)
            draw_arm(*shoulder_r, 85, body_top + 30, 120 + gest * 5, body_top + 20 + gest * 3)

        elif state in ('speaking', 'explaining', 'answering'):
            # Both hands gesturing
            draw_arm(*shoulder_l, -72, body_top + 50, -60 + gest * 5, body_top + 80 + gest * 10)
            draw_arm(*shoulder_r, 72, body_top + 45, 65 - gest * 3, body_top + 70 - gest * 8)

        elif state == 'thinking':
            # Left hand on chin, right arm crossed
            draw_arm(*shoulder_l, -45, body_top + 30, -15, body_top - 10 + gest * 2)
            draw_arm(*shoulder_r, 50, body_top + 50, 20, body_top + 80)

        elif state == 'listening':
            # Arms relaxed, slight lean
            lean = math.sin(self._nod_phase) * 3
            draw_arm(*shoulder_l, -65, body_top + 55 + lean, -58, body_top + 110)
            draw_arm(*shoulder_r, 65, body_top + 55 - lean, 58, body_top + 110)

        elif state == 'farewell':
            # Both arms waving
            draw_arm(*shoulder_l, -75, body_top + 10, -85, body_top - 15 + wave * 20)
            draw_arm(*shoulder_r, 75, body_top + 10, 85, body_top - 15 - wave * 20)

        elif state == 'idle':
            # Hands together in front
            draw_arm(*shoulder_l, -55, body_top + 55, -15, body_top + 90)
            draw_arm(*shoulder_r, 55, body_top + 55, 15, body_top + 90)

        else:
            # Default relaxed
            draw_arm(*shoulder_l, -65, body_top + 55, -60, body_top + 110)
            draw_arm(*shoulder_r, 65, body_top + 55, 60, body_top + 110)

        painter.restore()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _draw_status_bar(self, painter, rect):
        bar_h = 36
        bar_y = rect.height() - bar_h - 10
        bar_x = 15
        bar_w = rect.width() - 30

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15, 18, 40, 200))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 12, 12)

        # Border glow
        painter.setPen(QPen(QColor(80, 120, 220, 80), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 12, 12)

        # Text
        status_map = {
            'greeting': '✨ Hello! Welcome!',
            'listening': '👂 Listening to you...',
            'thinking': '🤔 Let me think...',
            'presenting': '📊 Presenting...',
            'speaking': '🗣️ Speaking...',
            'answering': '💡 Answering your question...',
            'idle': '😊 Ready for questions!',
            'farewell': '👋 Goodbye!',
        }
        text = status_map.get(self.state, '')
        if text:
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            painter.setPen(QColor(220, 225, 255))
            painter.drawText(QRectF(bar_x, bar_y, bar_w, bar_h), Qt.AlignCenter, text)
