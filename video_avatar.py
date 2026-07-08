import os
import math
import random
import logging
import time
from PySide6.QtCore import Qt, QUrl, QTimer, QPointF, QRectF
from PySide6.QtWidgets import QWidget, QStackedLayout
from PySide6.QtGui import (QPixmap, QFont, QColor, QPainter, QLinearGradient,
                           QRadialGradient, QBrush, QPen)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

# ── Phoneme-to-viseme mapping ───────────────────────────────────────
# Maps characters to mouth shape categories for lip sync
VISEME_MAP = {
    # Closed mouth (M, B, P)
    'm': 'closed', 'b': 'closed', 'p': 'closed',
    # Slightly open (D, T, N, L, S, Z)
    'd': 'slight', 't': 'slight', 'n': 'slight', 'l': 'slight',
    's': 'slight', 'z': 'slight', 'c': 'slight', 'j': 'slight',
    # Wide open (A, E, I)
    'a': 'wide', 'e': 'wide', 'i': 'wide', 'h': 'wide',
    # Rounded (O, U, W)
    'o': 'round', 'u': 'round', 'w': 'round',
    # Teeth (F, V)
    'f': 'slight', 'v': 'slight',
    # Other consonants
    'g': 'slight', 'k': 'slight', 'r': 'slight',
    'x': 'slight', 'q': 'round', 'y': 'wide',
    ' ': 'closed', ',': 'closed', '.': 'closed',
}

def text_to_viseme_sequence(text):
    """Convert text to a sequence of viseme mouth shapes for lip sync."""
    seq = []
    for ch in text.lower():
        viseme = VISEME_MAP.get(ch, 'slight')
        seq.append(viseme)
    return seq


class AnimatedPresenter(QWidget):
    """
    Industry-level sprite animation engine for a Pixar-quality 3D presenter.

    Uses 8 pre-generated character poses with different mouth shapes and
    hand gestures, crossfading between them to create:
      • Phoneme-synced lip movement matching the spoken text
      • Natural eye blinking at realistic 3-5 second intervals
      • Synchronized hand gesture rotation while presenting
      • Gentle breathing and head sway on the entire image
      • State-driven behavior (idle, speaking, presenting, thinking)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0

        # State
        self.state = "idle"
        self.is_speaking = False

        # Pose image library
        self.poses = {}
        self._load_poses()

        # ── Viseme lip sync state ──
        self._viseme_sequence = []
        self._viseme_index = 0
        self._viseme_timer = 0
        self._chars_per_second = 12  # reading speed for lip sync timing
        self._current_viseme = "closed"

        # ── Crossfade state ──
        self._display_pose_a = "idle"     # currently showing
        self._display_pose_b = "idle"     # fading into
        self._crossfade = 1.0             # 1.0 = fully showing pose_b
        self._crossfade_speed = 0.08

        # ── Gesture rotation state ──
        self._gesture_poses = ["speaking", "gesture_both_hands", "mouth_o", "pointing"]
        self._gesture_index = 0
        self._gesture_timer = 0
        self._gesture_interval = 150  # frames between gesture changes (~2.5s)

        # ── Blink state ──
        self._blink_timer = 0
        self._next_blink = random.randint(180, 320)
        self._is_blinking = False
        self._blink_phase = 0
        self._pre_blink_pose = "idle"

        # ── Physics ──
        self._breath_phase = 0.0
        self._sway_phase = 0.0
        self._speak_glow = 0.0

        # 60 FPS timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._physics_tick)
        self._timer.start(16)

    def _load_poses(self):
        """Load all pose images from assets/poses/ directory."""
        poses_dir = os.path.join(os.path.dirname(__file__), "assets", "poses")
        pose_files = {
            "idle": "idle.jpg",
            "speaking": "speaking.jpg",
            "pointing": "pointing.jpg",
            "blinking": "blinking.jpg",
            "mouth_wide": "mouth_wide.jpg",
            "mouth_o": "mouth_o.jpg",
            "gesture_both_hands": "gesture_both_hands.jpg",
            "mouth_closed": "mouth_closed.jpg",
        }
        for name, filename in pose_files.items():
            path = os.path.join(poses_dir, filename)
            if os.path.exists(path):
                px = QPixmap(path)
                if not px.isNull():
                    self.poses[name] = px
                    logger.info(f"Loaded pose: {name} ({px.width()}x{px.height()})")

        # Fallback: presenter_base.jpg
        if "idle" not in self.poses:
            fallback = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
            if os.path.exists(fallback):
                px = QPixmap(fallback)
                if not px.isNull():
                    self.poses["idle"] = px

    # ── public API ──────────────────────────────────────────────────
    def set_state(self, state: str):
        self.state = state.lower()
        if not self.is_speaking:
            self._transition_to(self._idle_pose_for_state())

    def set_speaking(self, speaking: bool):
        was_speaking = self.is_speaking
        self.is_speaking = speaking

        if speaking and not was_speaking:
            # Start lip sync cycle
            self._gesture_timer = 0
            self._gesture_index = 0
            self._viseme_index = 0
            self._viseme_timer = 0
        elif not speaking and was_speaking:
            # Return to idle
            self._viseme_sequence = []
            self._transition_to(self._idle_pose_for_state())

    def set_speaking_text(self, text: str):
        """Feed the current spoken text for phoneme-based lip sync."""
        self._viseme_sequence = text_to_viseme_sequence(text)
        self._viseme_index = 0
        self._viseme_timer = 0

    def _idle_pose_for_state(self):
        if self.state == "presenting":
            return "pointing"
        elif self.state == "thinking":
            return "mouth_closed"
        return "idle"

    def _viseme_to_pose(self, viseme):
        """Map a viseme category to the best matching pose image."""
        mapping = {
            'closed': 'mouth_closed',
            'slight': 'speaking',
            'wide': 'mouth_wide',
            'round': 'mouth_o',
        }
        pose = mapping.get(viseme, 'speaking')
        if pose in self.poses:
            return pose
        return 'speaking' if 'speaking' in self.poses else 'idle'

    def _transition_to(self, pose_name):
        """Initiate a smooth crossfade to a new pose."""
        if pose_name not in self.poses:
            pose_name = "idle"
        if pose_name == self._display_pose_b:
            return
        self._display_pose_a = self._display_pose_b
        self._display_pose_b = pose_name
        self._crossfade = 0.0

    # ── physics loop ────────────────────────────────────────────────
    def _physics_tick(self):
        self.tick += 1
        self._breath_phase += 0.045
        self._sway_phase += 0.025

        # Crossfade
        if self._crossfade < 1.0:
            self._crossfade = min(1.0, self._crossfade + self._crossfade_speed)

        # Speaking glow
        target_glow = 1.0 if self.is_speaking else 0.0
        self._speak_glow += (target_glow - self._speak_glow) * 0.12

        # ── Lip sync logic ──
        if self.is_speaking:
            self._viseme_timer += 1
            frames_per_char = max(2, int(60 / self._chars_per_second))

            if self._viseme_timer >= frames_per_char:
                self._viseme_timer = 0

                if self._viseme_sequence and self._viseme_index < len(self._viseme_sequence):
                    viseme = self._viseme_sequence[self._viseme_index]
                    self._viseme_index += 1
                else:
                    # No text provided or exhausted: cycle through mouth shapes
                    cycle = ['slight', 'wide', 'closed', 'round', 'slight', 'wide']
                    viseme = cycle[self.tick // frames_per_char % len(cycle)]

                if viseme != self._current_viseme:
                    self._current_viseme = viseme
                    target_pose = self._viseme_to_pose(viseme)

                    # Mix in gesture rotation periodically
                    self._gesture_timer += frames_per_char
                    if self._gesture_timer >= self._gesture_interval:
                        self._gesture_timer = 0
                        self._gesture_index = (self._gesture_index + 1) % len(self._gesture_poses)
                        target_pose = self._gesture_poses[self._gesture_index]
                        if target_pose not in self.poses:
                            target_pose = self._viseme_to_pose(viseme)

                    self._crossfade_speed = 0.15  # faster for lip sync
                    self._transition_to(target_pose)

        # ── Blink logic ──
        if not self._is_blinking:
            self._blink_timer += 1
            if self._blink_timer >= self._next_blink:
                self._start_blink()
        else:
            self._blink_phase += 1
            if self._blink_phase >= 10:
                self._end_blink()

        self.update()

    def _start_blink(self):
        if "blinking" not in self.poses:
            self._blink_timer = 0
            self._next_blink = random.randint(180, 320)
            return
        self._is_blinking = True
        self._blink_phase = 0
        self._pre_blink_pose = self._display_pose_b
        self._crossfade_speed = 0.3  # very fast for blink
        self._transition_to("blinking")

    def _end_blink(self):
        self._is_blinking = False
        self._blink_timer = 0
        self._next_blink = random.randint(180, 320)
        self._crossfade_speed = 0.3
        self._transition_to(self._pre_blink_pose)
        # Restore normal crossfade speed
        QTimer.singleShot(150, lambda: setattr(self, '_crossfade_speed', 0.08))

    # ── painting ────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()

        # 1. Dark cinematic background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(12, 14, 38))
        bg.setColorAt(1.0, QColor(4, 6, 16))
        p.fillRect(self.rect(), bg)

        if not self.poses:
            p.setPen(QColor(160, 170, 210))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Place presenter_base.jpg\nin the project folder")
            p.end()
            return

        # 2. Subtle transforms
        breath = math.sin(self._breath_phase)
        sway = math.sin(self._sway_phase)
        scale = 1.0 + breath * 0.003
        rotation = sway * 0.3
        bob_y = breath * 1.5

        if self.state == "thinking":
            rotation += 1.0
        elif self.state == "listening":
            bob_y += math.sin(self._sway_phase * 3) * 1.0

        cx, cy = w / 2.0, h / 2.0

        # 3. Crossfade render
        pose_a = self.poses.get(self._display_pose_a, self.poses.get("idle"))
        pose_b = self.poses.get(self._display_pose_b, self.poses.get("idle"))

        def draw_pose(pixmap, opacity):
            if pixmap is None or opacity <= 0.01:
                return
            p.save()
            p.setOpacity(opacity)
            pw, ph = pixmap.width(), pixmap.height()
            aspect = pw / ph
            if w / h > aspect:
                dh = h; dw = int(h * aspect)
            else:
                dw = w; dh = int(w / aspect)
            p.translate(cx, cy + bob_y)
            p.rotate(rotation)
            p.scale(scale, scale)
            p.translate(-dw / 2.0, -dh / 2.0)
            p.drawPixmap(0, 0, dw, dh, pixmap)
            p.restore()

        if self._crossfade < 1.0:
            draw_pose(pose_a, 1.0 - self._crossfade)
        draw_pose(pose_b, min(1.0, self._crossfade + (1.0 - self._crossfade) * 0.3))

        # 4. Ambient glow
        p.setOpacity(1.0)
        glow = QRadialGradient(cx, cy * 0.85, w * 0.45)
        glow.setColorAt(0.0, QColor(50, 80, 180, 25))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(glow))

        # 5. Speaking pulse
        if self._speak_glow > 0.02:
            alpha = int(self._speak_glow * 45)
            pulse = 1.0 + math.sin(self.tick * 0.12) * 0.06
            radius = min(w, h) * 0.42 * pulse
            ring = QRadialGradient(cx, cy * 0.9, radius)
            ring.setColorAt(0.88, QColor(80, 140, 255, 0))
            ring.setColorAt(0.96, QColor(80, 140, 255, alpha))
            ring.setColorAt(1.0, QColor(80, 140, 255, 0))
            p.fillRect(self.rect(), QBrush(ring))

        # 6. Letterbox
        tf = QLinearGradient(0, 0, 0, 30)
        tf.setColorAt(0.0, QColor(12, 14, 38, 180))
        tf.setColorAt(1.0, QColor(12, 14, 38, 0))
        p.fillRect(0, 0, w, 30, tf)
        bf = QLinearGradient(0, h - 30, 0, h)
        bf.setColorAt(0.0, QColor(4, 6, 16, 0))
        bf.setColorAt(1.0, QColor(4, 6, 16, 180))
        p.fillRect(0, h - 30, w, 30, bf)

        p.end()


class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Plays H.264 MP4 videos when available; otherwise shows a beautiful
    animated Pixar presenter with phoneme-synced lip movement, natural
    blinking, gesture rotation, and breathing.
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

        # Index 1 — animated presenter
        self.animated_presenter = AnimatedPresenter()
        self.stacked_layout.addWidget(self.animated_presenter)

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
        self.animated_presenter.set_state("idle")
        self.animated_presenter.set_speaking(False)
        self.current_media_path = ""

    def pop_out(self):
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self.animated_presenter.set_speaking(is_speaking)
        self._update_media()

    def set_speaking_text(self, text: str):
        """Feed spoken text for phoneme-synced lip movement."""
        self.animated_presenter.set_speaking_text(text)

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self.animated_presenter.set_state(state.lower())
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
