import os
import math
import random
import logging
from PySide6.QtCore import Qt, QUrl, QTimer, QRect, QRectF
from PySide6.QtWidgets import QWidget, QStackedLayout
from PySide6.QtGui import (QPixmap, QImage, QFont, QColor, QPainter,
                           QLinearGradient, QRadialGradient, QBrush, QPen)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

# ── Face regions (normalized 0-1 on 896x1200 image) ──────────────────
LOWER_FACE = (0.385, 0.275, 0.230, 0.130)
EYE_REGION = (0.390, 0.230, 0.220, 0.065)

# ── Viseme → source pose ──────────────────────────────────────────────
VISEME_POSE = {
    'rest': 'idle',       'mm': 'mouth_closed',
    'aa':   'mouth_wide', 'ee': 'speaking',
    'oh':   'mouth_o',    'oo': 'mouth_o',
    'ff':   'speaking',   'ss': 'both_hands',
    'th':   'speaking',
}

# Per-viseme mouth scale: (horizontal_scale, vertical_scale)
# Makes each viseme look MORE DISTINCT by subtly scaling the composited region
MOUTH_SCALE = {
    'rest': (1.00, 1.00),
    'mm':   (1.00, 0.96),   # pressed closed
    'aa':   (1.02, 1.07),   # wide open
    'ee':   (1.06, 1.00),   # stretched wide
    'oh':   (0.96, 1.05),   # narrow, tall
    'oo':   (0.92, 1.04),   # pursed
    'ff':   (1.00, 0.98),   # barely open
    'ss':   (1.03, 1.01),   # slightly wide
    'th':   (1.00, 1.03),   # slightly open
}

SPEAK_GESTURES = ['speaking', 'both_hands', 'pointing', 'mouth_wide', 'mouth_o', 'speaking']
GESTURE_INTERVAL_MIN = 120   # ~2 sec
GESTURE_INTERVAL_MAX = 200   # ~3.3 sec


def char_to_viseme_timed(ch):
    ch = ch.lower()
    m = {
        'a': ('aa', 5), 'e': ('ee', 5), 'i': ('ee', 4), 'o': ('oh', 5), 'u': ('oo', 5),
        'b': ('mm', 3), 'm': ('mm', 4), 'p': ('mm', 3),
        'f': ('ff', 3), 'v': ('ff', 3),
        's': ('ss', 3), 'z': ('ss', 3), 'c': ('ss', 3), 'x': ('ss', 3),
        'w': ('oo', 4), 'r': ('oh', 3), 'q': ('oo', 3),
        'd': ('th', 2), 't': ('th', 2), 'n': ('th', 3), 'l': ('th', 3),
        'g': ('ss', 2), 'k': ('ss', 2), 'j': ('ee', 3), 'y': ('ee', 3), 'h': ('aa', 3),
        ' ': ('rest', 4), ',': ('rest', 8), '.': ('rest', 12),
        '!': ('rest', 12), '?': ('rest', 12),
        ':': ('rest', 8), ';': ('rest', 8), '-': ('rest', 3), '\n': ('rest', 6),
    }
    return m.get(ch, ('ss', 3))


class FaceCompositingPresenter(QWidget):
    """
    Face Compositing Avatar with Smooth Crossfade + Micro-Expressions.

    Layers:
      1. Body pose — smooth crossfade between gesture images
      2. Mouth region — smooth crossfade + per-viseme scale
      3. Eye blink — smooth alpha from closed-eye render
      4. Physics — breathing, head sway, head nod on emphasis
      5. Micro-expressions — subtle jitter to prevent "dead" look
      6. VFX — ambient glow, speaking pulse, cinematic letterbox
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0
        self.is_speaking = False
        self.state = 'idle'

        # Load poses
        self.poses = {}
        self._load_poses()

        # Pre-compute sprites (base + blended intermediates)
        self.mouth_sprites = {}
        self.blink_sprite = None
        self._precompute_sprites()

        # ── SMOOTH MOUTH CROSSFADE ──
        self._prev_viseme = 'rest'
        self._curr_viseme = 'rest'
        self._mouth_blend = 1.0
        self._mouth_blend_speed = 0.28

        # ── SMOOTH BODY CROSSFADE ──
        self._prev_gesture = 'idle'
        self._curr_gesture = 'idle'
        self._body_blend = 1.0
        self._body_blend_speed = 0.05

        # ── Timed viseme queue ──
        self._viseme_queue = []
        self._viseme_idx = 0
        self._viseme_countdown = 0

        # ── Gesture rotation ──
        self._gesture_idx = 0
        self._gesture_timer = 0
        self._next_gesture_at = random.randint(GESTURE_INTERVAL_MIN, GESTURE_INTERVAL_MAX)
        self._gesture_order = list(range(len(SPEAK_GESTURES)))

        # ── Blink ──
        self._blink_timer = 0
        self._next_blink = random.randint(180, 330)
        self._blink_alpha = 0.0
        self._blink_phase = 0
        self._double_blink = False

        # ── Physics ──
        self._breath = 0.0
        self._sway = 0.0

        # ── Head nod (emphasis) ──
        self._nod_y = 0.0

        # ── Micro-expression jitter ──
        self._micro_x = 0.0
        self._micro_y = 0.0

        # 60 FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _load_poses(self):
        poses_dir = os.path.join(os.path.dirname(__file__), "assets", "poses")
        pose_files = {
            "idle": "idle.jpg", "speaking": "speaking.jpg",
            "pointing": "pointing.jpg", "blinking": "blinking.jpg",
            "mouth_wide": "mouth_wide.jpg", "mouth_o": "mouth_o.jpg",
            "both_hands": "gesture_both_hands.jpg", "mouth_closed": "mouth_closed.jpg",
        }
        for name, fname in pose_files.items():
            path = os.path.join(poses_dir, fname)
            if os.path.exists(path):
                px = QPixmap(path)
                if not px.isNull():
                    self.poses[name] = px
        if "idle" not in self.poses:
            fb = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
            if os.path.exists(fb):
                px = QPixmap(fb)
                if not px.isNull():
                    self.poses["idle"] = px

    def _extract_feathered_region(self, pixmap, region, feather_ratio=0.35):
        x = int(region[0] * pixmap.width())
        y = int(region[1] * pixmap.height())
        w = int(region[2] * pixmap.width())
        h = int(region[3] * pixmap.height())
        cropped = pixmap.copy(x, y, w, h)

        mask = QPixmap(w, h)
        mask.fill(Qt.transparent)
        mp = QPainter(mask)
        mp.setRenderHint(QPainter.Antialiasing, True)
        grad = QRadialGradient(w / 2, h / 2, max(w, h) / 2)
        grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        grad.setColorAt(1.0 - feather_ratio, QColor(255, 255, 255, 255))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        mp.setBrush(QBrush(grad))
        mp.setPen(Qt.NoPen)
        mp.drawEllipse(0, 0, w, h)
        mp.end()

        result = QPixmap(w, h)
        result.fill(Qt.transparent)
        rp = QPainter(result)
        rp.drawPixmap(0, 0, cropped)
        rp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        rp.drawPixmap(0, 0, mask)
        rp.end()
        return result

    def _blend_sprites(self, s1, s2, alpha=0.5):
        """Create a blended intermediate sprite from two existing sprites."""
        if s1.isNull() or s2.isNull():
            return s1
        result = QPixmap(s1.size())
        result.fill(Qt.transparent)
        rp = QPainter(result)
        rp.setOpacity(1.0 - alpha)
        rp.drawPixmap(0, 0, s1)
        rp.setOpacity(alpha)
        rp.drawPixmap(0, 0, s2)
        rp.end()
        return result

    def _precompute_sprites(self):
        # Base viseme sprites
        for viseme, pose_name in VISEME_POSE.items():
            if pose_name in self.poses:
                self.mouth_sprites[viseme] = self._extract_feathered_region(
                    self.poses[pose_name], LOWER_FACE, feather_ratio=0.30)

        # Blended intermediate sprites for smoother transitions
        blends = [
            ('rest_aa', 'rest', 'aa', 0.5),
            ('rest_ee', 'rest', 'ee', 0.5),
            ('aa_ee',   'aa',   'ee', 0.5),
            ('aa_oh',   'aa',   'oh', 0.5),
            ('oh_oo',   'oh',   'oo', 0.5),
            ('ee_ss',   'ee',   'ss', 0.5),
            ('mm_rest', 'mm',   'rest', 0.5),
        ]
        for name, v1, v2, alpha in blends:
            if v1 in self.mouth_sprites and v2 in self.mouth_sprites:
                self.mouth_sprites[name] = self._blend_sprites(
                    self.mouth_sprites[v1], self.mouth_sprites[v2], alpha)

        # Blink sprite
        if 'blinking' in self.poses:
            self.blink_sprite = self._extract_feathered_region(
                self.poses['blinking'], EYE_REGION, feather_ratio=0.35)

        logger.info(f"Pre-computed {len(self.mouth_sprites)} mouth sprites, blink={'YES' if self.blink_sprite else 'NO'}")

    # ── Public API ──────────────────────────────────────────────────
    def set_speaking(self, speaking):
        was = self.is_speaking
        self.is_speaking = speaking
        if speaking and not was:
            self._gesture_timer = 0
            self._gesture_idx = 0
            random.shuffle(self._gesture_order)
            self._switch_gesture(SPEAK_GESTURES[self._gesture_order[0]])
            self._viseme_idx = 0
            self._viseme_countdown = 0
            self._next_gesture_at = random.randint(GESTURE_INTERVAL_MIN, GESTURE_INTERVAL_MAX)
        elif not speaking and was:
            self._viseme_queue = []
            self._switch_viseme('rest')
            self._switch_gesture('idle')

    def set_speaking_text(self, text):
        """Convert PPT text to timed viseme sequence for synchronized lip movement."""
        self._viseme_queue = [char_to_viseme_timed(ch) for ch in text]
        self._viseme_idx = 0
        self._viseme_countdown = 0

    def set_state(self, state):
        self.state = state.lower()

    # ── Transition helpers ──────────────────────────────────────────
    def _switch_viseme(self, new_viseme):
        if new_viseme == self._curr_viseme:
            return
        self._prev_viseme = self._curr_viseme
        self._curr_viseme = new_viseme
        self._mouth_blend = 0.0

    def _switch_gesture(self, new_gesture):
        if new_gesture == self._curr_gesture or new_gesture not in self.poses:
            return
        self._prev_gesture = self._curr_gesture
        self._curr_gesture = new_gesture
        self._body_blend = 0.0

    # ── Animation loop ──────────────────────────────────────────────
    def _tick(self):
        self.tick += 1
        self._breath += 0.045
        self._sway += 0.025

        # Advance crossfades
        if self._mouth_blend < 1.0:
            self._mouth_blend = min(1.0, self._mouth_blend + self._mouth_blend_speed)
        if self._body_blend < 1.0:
            self._body_blend = min(1.0, self._body_blend + self._body_blend_speed)

        # ── Lip sync with variable timing ──
        if self.is_speaking:
            self._viseme_countdown -= 1
            if self._viseme_countdown <= 0:
                if self._viseme_queue and self._viseme_idx < len(self._viseme_queue):
                    viseme, delay = self._viseme_queue[self._viseme_idx]
                    self._switch_viseme(viseme)
                    self._viseme_countdown = delay
                    self._viseme_idx += 1

                    # Head nod on word starts
                    if self._viseme_idx > 1:
                        prev_v = self._viseme_queue[self._viseme_idx - 2][0]
                        if prev_v == 'rest':
                            self._nod_y = 2.5
                else:
                    cycle = [('aa', 4), ('rest_aa', 3), ('ee', 4), ('rest', 3),
                             ('oh', 4), ('ee_ss', 3), ('aa', 4), ('mm', 3),
                             ('aa_ee', 4), ('th', 3), ('oh_oo', 3), ('rest_ee', 3)]
                    idx = self.tick % len(cycle)
                    v, d = cycle[idx]
                    if v in self.mouth_sprites:
                        self._switch_viseme(v)
                    self._viseme_countdown = d

            # Gesture rotation (randomized interval)
            self._gesture_timer += 1
            if self._gesture_timer >= self._next_gesture_at:
                self._gesture_timer = 0
                self._gesture_idx = (self._gesture_idx + 1) % len(SPEAK_GESTURES)
                if self._gesture_idx == 0:
                    random.shuffle(self._gesture_order)
                gi = self._gesture_order[self._gesture_idx % len(self._gesture_order)]
                self._switch_gesture(SPEAK_GESTURES[gi])
                self._next_gesture_at = random.randint(GESTURE_INTERVAL_MIN, GESTURE_INTERVAL_MAX)

        # ── Nod decay ──
        self._nod_y *= 0.88

        # ── Micro-expression jitter (every 4 frames) ──
        if self.tick % 4 == 0:
            self._micro_x = random.uniform(-0.7, 0.7)
            self._micro_y = random.uniform(-0.4, 0.4)

        # ── Blink ──
        if self._blink_phase == 0:
            self._blink_timer += 1
            if self._blink_timer >= self._next_blink:
                self._blink_phase = 1
                self._blink_timer = 0
                self._double_blink = random.random() < 0.20
                self._next_blink = random.randint(180, 330)
        else:
            self._blink_phase += 1
            if self._blink_phase <= 4:
                self._blink_alpha = min(1.0, self._blink_alpha + 0.30)
            elif self._blink_phase <= 8:
                self._blink_alpha = 1.0
            elif self._blink_phase <= 14:
                self._blink_alpha = max(0.0, self._blink_alpha - 0.20)
            elif self._blink_phase == 15 and self._double_blink:
                # Quick second blink
                self._blink_alpha = 0.0
                self._blink_phase = 16
            elif self._double_blink and 18 <= self._blink_phase <= 21:
                self._blink_alpha = min(1.0, self._blink_alpha + 0.35)
            elif self._double_blink and 22 <= self._blink_phase <= 24:
                self._blink_alpha = 1.0
            elif self._double_blink and 25 <= self._blink_phase <= 30:
                self._blink_alpha = max(0.0, self._blink_alpha - 0.22)
            else:
                if self._blink_phase > 14 and not self._double_blink:
                    self._blink_phase = 0
                    self._blink_alpha = 0.0
                elif self._double_blink and self._blink_phase > 30:
                    self._blink_phase = 0
                    self._blink_alpha = 0.0
                    self._double_blink = False

        self.update()

    # ── Rendering ───────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()

        # Background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(12, 14, 38))
        bg.setColorAt(1.0, QColor(4, 6, 16))
        p.fillRect(self.rect(), bg)

        if not self.poses:
            p.setPen(QColor(160, 170, 210))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignCenter, "Place presenter_base.jpg\nin the project folder")
            p.end()
            return

        body_curr = self.poses.get(self._curr_gesture, self.poses.get('idle'))
        body_prev = self.poses.get(self._prev_gesture, body_curr)
        if body_curr is None:
            p.end()
            return

        # Display rect
        aspect = body_curr.width() / body_curr.height()
        if w / h > aspect:
            dh = h; dw = int(h * aspect)
        else:
            dw = w; dh = int(w / aspect)
        dx = (w - dw) // 2
        dy = (h - dh) // 2

        # Physics
        breath = math.sin(self._breath)
        sway = math.sin(self._sway)
        sc = 1.0 + breath * 0.003
        rot = sway * 0.3
        bob = breath * 1.5 - self._nod_y

        p.save()
        p.translate(w / 2, h / 2 + bob)
        p.rotate(rot)
        p.scale(sc, sc)
        p.translate(-w / 2, -h / 2)

        # ─── LAYER 1: Body pose with smooth crossfade ──────────────
        if self._body_blend < 0.99:
            p.setOpacity(1.0 - self._body_blend)
            p.drawPixmap(dx, dy, dw, dh, body_prev)
            p.setOpacity(self._body_blend)
            p.drawPixmap(dx, dy, dw, dh, body_curr)
            p.setOpacity(1.0)
        else:
            p.drawPixmap(dx, dy, dw, dh, body_curr)

        # ─── LAYER 2: Mouth with crossfade + per-viseme scale ─────
        mouth_prev = self.mouth_sprites.get(self._prev_viseme)
        mouth_curr = self.mouth_sprites.get(self._curr_viseme)

        # Base mouth rect
        base_mx = dx + int(LOWER_FACE[0] * dw)
        base_my = dy + int(LOWER_FACE[1] * dh)
        base_mw = int(LOWER_FACE[2] * dw)
        base_mh = int(LOWER_FACE[3] * dh)

        # Per-viseme scale for current viseme
        sx, sy = MOUTH_SCALE.get(self._curr_viseme, (1.0, 1.0))
        scaled_mw = int(base_mw * sx)
        scaled_mh = int(base_mh * sy)
        # Re-center after scale
        mx = base_mx + (base_mw - scaled_mw) // 2 + int(self._micro_x)
        my = base_my + (base_mh - scaled_mh) // 2 + int(self._micro_y)

        if self._mouth_blend < 0.99 and mouth_prev and mouth_curr:
            # Previous viseme scale
            psx, psy = MOUTH_SCALE.get(self._prev_viseme, (1.0, 1.0))
            pmw = int(base_mw * psx)
            pmh = int(base_mh * psy)
            pmx = base_mx + (base_mw - pmw) // 2 + int(self._micro_x)
            pmy = base_my + (base_mh - pmh) // 2 + int(self._micro_y)

            p.setOpacity(1.0 - self._mouth_blend)
            p.drawPixmap(pmx, pmy, pmw, pmh, mouth_prev)
            p.setOpacity(self._mouth_blend)
            p.drawPixmap(mx, my, scaled_mw, scaled_mh, mouth_curr)
            p.setOpacity(1.0)
        elif mouth_curr:
            p.drawPixmap(mx, my, scaled_mw, scaled_mh, mouth_curr)

        # ─── LAYER 3: Eye blink ───────────────────────────────────
        if self._blink_alpha > 0.01 and self.blink_sprite:
            p.setOpacity(self._blink_alpha)
            ex = dx + int(EYE_REGION[0] * dw)
            ey = dy + int(EYE_REGION[1] * dh)
            ew = int(EYE_REGION[2] * dw)
            eh = int(EYE_REGION[3] * dh)
            p.drawPixmap(ex, ey, ew, eh, self.blink_sprite)
            p.setOpacity(1.0)

        p.restore()

        # ─── LAYER 4: Ambient glow ───────────────────────────────
        glow = QRadialGradient(w / 2, h * 0.43, w * 0.45)
        glow.setColorAt(0.0, QColor(50, 80, 180, 25))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(glow))

        # ─── LAYER 5: Speaking pulse ──────────────────────────────
        if self.is_speaking:
            pulse = 0.5 + 0.5 * math.sin(self.tick * 0.08)
            alpha = int(pulse * 45)
            ring = QRadialGradient(w / 2, h * 0.45, min(w, h) * 0.44)
            ring.setColorAt(0.88, QColor(80, 140, 255, 0))
            ring.setColorAt(0.95, QColor(80, 140, 255, alpha))
            ring.setColorAt(1.0, QColor(80, 140, 255, 0))
            p.fillRect(self.rect(), QBrush(ring))

        # ─── LAYER 6: Cinematic letterbox ─────────────────────────
        tb = QLinearGradient(0, 0, 0, 20)
        tb.setColorAt(0, QColor(12, 14, 38, 160))
        tb.setColorAt(1, QColor(12, 14, 38, 0))
        p.fillRect(0, 0, w, 20, tb)
        bb = QLinearGradient(0, h - 20, 0, h)
        bb.setColorAt(0, QColor(4, 6, 16, 0))
        bb.setColorAt(1, QColor(4, 6, 16, 160))
        p.fillRect(0, h - 20, w, 20, bb)

        p.end()


class VideoAvatar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)

        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background:#000;border-radius:12px;")
        self.stacked_layout.addWidget(self.video_widget)

        self.presenter = FaceCompositingPresenter()
        self.stacked_layout.addWidget(self.presenter)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setMuted(True)

        self.videos_dir = os.path.join(os.path.dirname(__file__), "assets", "videos")
        self.current_media_path = ""
        self.current_state = "idle"
        self.current_slide = 0
        self.is_speaking = False
        self.init_avatar()

    def init_avatar(self):
        os.makedirs(self.videos_dir, exist_ok=True)
        self._show_fallback()

    def _show_fallback(self):
        self.stop()
        self.stacked_layout.setCurrentIndex(1)
        self.presenter.set_state("idle")
        self.presenter.set_speaking(False)
        self.current_media_path = ""

    def pop_out(self):
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self.presenter.set_speaking(is_speaking)
        self._update_media()

    def set_speaking_text(self, text: str):
        self.presenter.set_speaking_text(text)

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self.presenter.set_state(state.lower())
        self._update_media()

    def _update_media(self):
        state = self.current_state
        media_filename = ""
        is_looping = False

        if state in ("presenting", "speaking", "answering"):
            media_filename = f"slide{self.current_slide}" if self.is_speaking else f"slide{self.current_slide}_silent"
        elif state == "greeting":
            media_filename = "greeting" if self.is_speaking else "greeting_silent"
        elif state == "thinking":
            media_filename = "thinking"; is_looping = True
        elif state == "listening":
            media_filename = "listening"; is_looping = True
        else:
            media_filename = "idle"; is_looping = True

        if "_silent" in media_filename or media_filename == "idle":
            is_looping = True

        mp4 = os.path.join(self.videos_dir, f"{media_filename}.mp4")

        def valid(path):
            return os.path.exists(path) and os.path.getsize(path) > 50 * 1024

        if not valid(mp4) and ("slide" in media_filename or "greeting" in media_filename):
            mp4 = os.path.join(self.videos_dir, "speaking.mp4" if self.is_speaking else "idle.mp4")

        if valid(mp4):
            if mp4 != self.current_media_path:
                self.current_media_path = mp4
                self.stacked_layout.setCurrentIndex(0)
                self.player.setSource(QUrl.fromLocalFile(mp4))
                self.player.setLoops(QMediaPlayer.Infinite if is_looping else 1)
                self.player.play()
            return

        if self.stacked_layout.currentIndex() != 1:
            self.player.stop()
            self.stacked_layout.setCurrentIndex(1)
            self.current_media_path = ""

    def pause(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.pause()

    def play(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.play()

    def stop(self):
        self.player.stop()
