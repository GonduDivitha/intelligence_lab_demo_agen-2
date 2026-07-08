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
LOWER_FACE = (0.385, 0.275, 0.230, 0.130)   # x, y, w, h
EYE_REGION = (0.390, 0.230, 0.220, 0.065)    # x, y, w, h

# ── Pixel offsets relative to idle.jpg (from template matching) ──────
POSE_OFFSETS = {
    "idle": (0, 0),
    "speaking": (0, -3),
    "pointing": (0, 0),
    "blinking": (0, 0),
    "mouth_wide": (1, -11),
    "mouth_o": (1, -16),
    "both_hands": (-1, -7),
    "mouth_closed": (0, 0),
}

# ── Viseme → source pose mapping ──────────────────────────────────────
VISEME_POSE = {
    'rest': 'idle',
    'mm':   'mouth_closed',
    'aa':   'mouth_wide',
    'ee':   'speaking',
    'oh':   'mouth_o',
    'oo':   'mouth_o',
    'ff':   'speaking',
    'ss':   'both_hands',
    'th':   'speaking',
}

# Timed visemes mapping
def char_to_viseme_timed(ch):
    ch = ch.lower()
    mapping = {
        'a': ('aa', 5), 'e': ('ee', 5), 'i': ('ee', 4), 'o': ('oh', 5), 'u': ('oo', 5),
        'b': ('mm', 3), 'm': ('mm', 4), 'p': ('mm', 3),
        'f': ('ff', 3), 'v': ('ff', 3),
        's': ('ss', 3), 'z': ('ss', 3), 'c': ('ss', 3), 'x': ('ss', 3),
        'w': ('oo', 4), 'r': ('oh', 3), 'q': ('oo', 3),
        'd': ('th', 2), 't': ('th', 2), 'n': ('th', 3), 'l': ('th', 3),
        'g': ('ss', 2), 'k': ('ss', 2), 'j': ('ee', 3), 'y': ('ee', 3), 'h': ('aa', 3),
        ' ': ('rest', 4),
        ',': ('rest', 8),
        '.': ('rest', 12),
        '!': ('rest', 12),
        '?': ('rest', 12),
    }
    return mapping.get(ch, ('ss', 3))

# Body gesture rotation sequence
SPEAK_GESTURES = ['speaking', 'both_hands', 'pointing', 'both_hands', 'speaking']
GESTURE_INTERVAL = 140  # ~2.3 seconds


class FaceCompositingPresenter(QWidget):
    """
    Ultimate Hybrid 10/10 Presenter Engine.
    Uses QPainter regional compositing with pixel-perfect alignment offsets.
    Transitions are beautifully cross-faded to prevent flickering.
    Grounded breathing removes any 'floating in water' feel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0
        self.is_speaking = False
        self.state = 'idle'

        # Load all poses
        self.poses = {}
        self._load_poses()

        # Pre-compute aligned sprites
        self.mouth_sprites = {}
        self.blink_sprite = None
        self._precompute_sprites()

        # ── Smooth transitions ──
        self._prev_gesture = 'idle'
        self._curr_gesture = 'idle'
        self._body_blend = 1.0
        self._body_blend_speed = 0.06  # ~300ms crossfade

        self._prev_viseme = 'rest'
        self._curr_viseme = 'rest'
        self._mouth_blend = 1.0
        self._mouth_blend_speed = 0.25 # ~80ms crossfade

        # ── Timed Lip Sync ──
        self._viseme_queue = []
        self._viseme_idx = 0
        self._viseme_countdown = 0

        # ── Gesture rotation ──
        self._gesture_idx = 0
        self._gesture_timer = 0

        # ── Blink state ──
        self._blink_timer = 0
        self._next_blink = random.randint(180, 320)
        self._blink_alpha = 0.0
        self._blink_phase = 0

        # ── Grounded breathing physics (No floaty sway!) ──
        self._breath = 0.0

        # 60 FPS update
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

    def _extract_aligned_region(self, pixmap, region, offset, feather_ratio=0.35):
        """Extract a face region with alignment offsets and feathering."""
        # Align crop coordinates based on pose offset
        x = int(region[0] * pixmap.width()) + offset[0]
        y = int(region[1] * pixmap.height()) + offset[1]
        w = int(region[2] * pixmap.width())
        h = int(region[3] * pixmap.height())
        
        cropped = pixmap.copy(x, y, w, h)

        # Soft elliptical mask
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

    def _precompute_sprites(self):
        """Pre-extract and align mouth and blink sprites using POSE_OFFSETS."""
        for viseme, pose_name in VISEME_POSE.items():
            if pose_name in self.poses:
                offset = POSE_OFFSETS.get(pose_name, (0, 0))
                self.mouth_sprites[viseme] = self._extract_aligned_region(
                    self.poses[pose_name], LOWER_FACE, offset, feather_ratio=0.32)
                
        if 'blinking' in self.poses:
            offset = POSE_OFFSETS.get('blinking', (0, 0))
            self.blink_sprite = self._extract_aligned_region(
                self.poses['blinking'], EYE_REGION, offset, feather_ratio=0.35)

    def set_speaking(self, speaking):
        was = self.is_speaking
        self.is_speaking = speaking
        if speaking and not was:
            self._gesture_timer = 0
            self._gesture_idx = 0
            self._switch_gesture(SPEAK_GESTURES[0])
            self._viseme_idx = 0
            self._viseme_countdown = 0
        elif not speaking and was:
            self._viseme_queue = []
            self._switch_viseme('rest')
            self._switch_gesture('idle')

    def set_speaking_text(self, text):
        self._viseme_queue = [char_to_viseme_timed(ch) for ch in text]
        self._viseme_idx = 0
        self._viseme_countdown = 0

    def set_state(self, state):
        self.state = state.lower()

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

    def _tick(self):
        self.tick += 1
        
        # Grounded breathing (extremely subtle vertical bob, no sway/rotation!)
        self._breath += 0.035

        # Advance crossfades
        if self._mouth_blend < 1.0:
            self._mouth_blend = min(1.0, self._mouth_blend + self._mouth_blend_speed)
        if self._body_blend < 1.0:
            self._body_blend = min(1.0, self._body_blend + self._body_blend_speed)

        # Timed lip sync
        if self.is_speaking:
            self._viseme_countdown -= 1
            if self._viseme_countdown <= 0:
                if self._viseme_queue and self._viseme_idx < len(self._viseme_queue):
                    viseme, delay = self._viseme_queue[self._viseme_idx]
                    self._switch_viseme(viseme)
                    self._viseme_countdown = delay
                    self._viseme_idx += 1
                else:
                    # Idle cycle while speaking is active but text is exhausted
                    cycle = [('aa', 4), ('ss', 3), ('ee', 4), ('rest', 3), ('oh', 4)]
                    idx = (self.tick // 4) % len(cycle)
                    self._switch_viseme(cycle[idx][0])
                    self._viseme_countdown = cycle[idx][1]

            # Gesture rotation
            self._gesture_timer += 1
            if self._gesture_timer >= GESTURE_INTERVAL:
                self._gesture_timer = 0
                self._gesture_idx = (self._gesture_idx + 1) % len(SPEAK_GESTURES)
                self._switch_gesture(SPEAK_GESTURES[self._gesture_idx])

        # Eye blink
        if self._blink_phase == 0:
            self._blink_timer += 1
            if self._blink_timer >= self._next_blink:
                self._blink_phase = 1
                self._blink_timer = 0
                self._next_blink = random.randint(180, 320)
        else:
            self._blink_phase += 1
            if self._blink_phase <= 4:
                self._blink_alpha = min(1.0, self._blink_alpha + 0.35)
            elif self._blink_phase <= 7:
                self._blink_alpha = 1.0
            elif self._blink_phase <= 12:
                self._blink_alpha = max(0.0, self._blink_alpha - 0.25)
            else:
                self._blink_phase = 0
                self._blink_alpha = 0.0

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()

        # Cinematic background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(12, 14, 38))
        bg.setColorAt(1.0, QColor(4, 6, 16))
        p.fillRect(self.rect(), bg)

        if not self.poses:
            p.setPen(QColor(160, 170, 210))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignCenter, "Place presenter poses in assets/poses")
            p.end()
            return

        body_curr = self.poses.get(self._curr_gesture, self.poses.get('idle'))
        body_prev = self.poses.get(self._prev_gesture, body_curr)

        # Scale to fit
        aspect = body_curr.width() / body_curr.height()
        if w / h > aspect:
            dh = h; dw = int(h * aspect)
        else:
            dw = w; dh = int(w / aspect)
        dx = (w - dw) // 2
        dy = (h - dh) // 2

        # Grounded breathing (max 1.5px vertical shift, NO rotation, NO side sway)
        bob = math.sin(self._breath) * 1.5

        p.save()
        p.translate(0, bob)

        # 1. Draw body pose with crossfade transition
        if self._body_blend < 0.99:
            p.setOpacity(1.0 - self._body_blend)
            p.drawPixmap(dx, dy, dw, dh, body_prev)
            p.setOpacity(self._body_blend)
            p.drawPixmap(dx, dy, dw, dh, body_curr)
            p.setOpacity(1.0)
        else:
            p.drawPixmap(dx, dy, dw, dh, body_curr)

        # 2. Compute pixel-perfect mouth coordinates with pose offsets
        # We blend the offset of prev pose and curr pose for smooth mouth track during crossfades!
        offset_curr = POSE_OFFSETS.get(self._curr_gesture, (0, 0))
        offset_prev = POSE_OFFSETS.get(self._prev_gesture, (0, 0))
        
        # Blend offset
        off_x = offset_prev[0] + (offset_curr[0] - offset_prev[0]) * self._body_blend
        off_y = offset_prev[1] + (offset_curr[1] - offset_prev[1]) * self._body_blend

        # Map to display dimensions
        mx = dx + int((LOWER_FACE[0] + off_x / 896.0) * dw)
        my = dy + int((LOWER_FACE[1] + off_y / 1200.0) * dh)
        mw = int(LOWER_FACE[2] * dw)
        mh = int(LOWER_FACE[3] * dh)

        # Draw mouth with crossfade
        mouth_curr = self.mouth_sprites.get(self._curr_viseme)
        mouth_prev = self.mouth_sprites.get(self._prev_viseme)

        if self._mouth_blend < 0.99 and mouth_prev and mouth_curr:
            p.setOpacity(1.0 - self._mouth_blend)
            p.drawPixmap(mx, my, mw, mh, mouth_prev)
            p.setOpacity(self._mouth_blend)
            p.drawPixmap(mx, my, mw, mh, mouth_curr)
            p.setOpacity(1.0)
        elif mouth_curr:
            p.drawPixmap(mx, my, mw, mh, mouth_curr)

        # 3. Draw blinking overlay (uses blinking offset)
        if self._blink_alpha > 0.01 and self.blink_sprite:
            p.setOpacity(self._blink_alpha)
            
            # Map blink position
            blink_offset = POSE_OFFSETS.get('blinking', (0, 0))
            ex = dx + int((EYE_REGION[0] + blink_offset[0] / 896.0) * dw)
            ey = dy + int((EYE_REGION[1] + blink_offset[1] / 1200.0) * dh)
            ew = int(EYE_REGION[2] * dw)
            eh = int(EYE_REGION[3] * dh)
            
            p.drawPixmap(ex, ey, ew, eh, self.blink_sprite)
            p.setOpacity(1.0)

        p.restore()

        # Ambient glow
        glow = QRadialGradient(w / 2, h * 0.43, w * 0.45)
        glow.setColorAt(0.0, QColor(50, 80, 180, 25))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(glow))

        # Speaking pulse
        if self.is_speaking:
            pulse = 0.5 + 0.5 * math.sin(self.tick * 0.08)
            alpha = int(pulse * 40)
            ring = QRadialGradient(w / 2, h * 0.45, min(w, h) * 0.44)
            ring.setColorAt(0.88, QColor(80, 140, 255, 0))
            ring.setColorAt(0.95, QColor(80, 140, 255, alpha))
            ring.setColorAt(1.0, QColor(80, 140, 255, 0))
            p.fillRect(self.rect(), QBrush(ring))

        p.end()


class VideoAvatar(QWidget):
    """
    10/10 Digital Human Presenter.
    Combines H.264 video playback with pixel-perfect, cross-faded regional face compositing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)

        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        # Index 0 — video player
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background:#000;border-radius:12px;")
        self.stacked_layout.addWidget(self.video_widget)

        # Index 1 — Pixel-perfect Regional Face Compositing Presenter
        self.presenter = FaceCompositingPresenter()
        self.stacked_layout.addWidget(self.presenter)

        # Media player
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
