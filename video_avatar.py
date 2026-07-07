import os
import math
import random
import logging
from PySide6.QtCore import Qt, QUrl, QTimer, QPointF, QRectF
from PySide6.QtWidgets import QWidget, QStackedLayout
from PySide6.QtGui import (QPixmap, QFont, QColor, QPainter, QLinearGradient,
                           QRadialGradient, QBrush, QPen)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)


class AnimatedPresenter(QWidget):
    """
    Sprite-sheet animation engine for a Pixar-quality 3D presenter.
    Uses pre-generated pose images (idle, speaking, pointing, blinking)
    and crossfades between them with smooth alpha blending to create
    the illusion of natural, living animation. The character images
    are NEVER cropped, split, or drawn over — each pose is a complete,
    beautiful, full-body Pixar render.

    Animation features:
      • Smooth crossfade transitions between poses (~300ms)
      • Natural eye blinking every 3-5 seconds (quick crossfade to blink pose)
      • Gentle breathing scale pulse on the whole image
      • Soft head-sway rotation applied to the whole image
      • Speaking glow indicator when the TTS engine is active
      • State-driven pose selection (idle, speaking, presenting, thinking)
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

        # Crossfade state
        self._current_pose = "idle"
        self._target_pose = "idle"
        self._crossfade = 1.0       # 0.0 = showing current, 1.0 = showing target
        self._crossfade_speed = 0.06  # ~300ms at 60fps

        # Blink state
        self._blink_timer = 0
        self._next_blink = random.randint(180, 300)  # frames until next blink
        self._is_blinking = False
        self._blink_phase = 0        # 0=not, 1=closing, 2=closed, 3=opening

        # Physics
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
        }
        for name, filename in pose_files.items():
            path = os.path.join(poses_dir, filename)
            if os.path.exists(path):
                px = QPixmap(path)
                if not px.isNull():
                    self.poses[name] = px
                    logger.info(f"Loaded pose: {name} ({px.width()}x{px.height()})")

        # Fallback: try presenter_base.jpg in project root
        if "idle" not in self.poses:
            fallback = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
            if os.path.exists(fallback):
                px = QPixmap(fallback)
                if not px.isNull():
                    self.poses["idle"] = px

    # ── public API ──────────────────────────────────────────────────
    def set_state(self, state: str):
        self.state = state.lower()
        self._update_target_pose()

    def set_speaking(self, speaking: bool):
        self.is_speaking = speaking
        self._update_target_pose()

    def _update_target_pose(self):
        """Select the best pose for the current state."""
        if self._is_blinking:
            return  # don't interrupt a blink

        if self.is_speaking:
            new_pose = "speaking"
        elif self.state in ("presenting",):
            new_pose = "pointing"
        elif self.state in ("thinking",):
            new_pose = "idle"  # subtle: thinking uses idle + head tilt
        else:
            new_pose = "idle"

        # Only trigger crossfade if pose actually changed
        if new_pose != self._target_pose and new_pose in self.poses:
            self._current_pose = self._target_pose
            self._target_pose = new_pose
            self._crossfade = 0.0

    # ── physics loop ────────────────────────────────────────────────
    def _physics_tick(self):
        self.tick += 1
        self._breath_phase += 0.045
        self._sway_phase += 0.025

        # Crossfade progress
        if self._crossfade < 1.0:
            self._crossfade = min(1.0, self._crossfade + self._crossfade_speed)

        # Speaking glow ramp
        target_glow = 1.0 if self.is_speaking else 0.0
        self._speak_glow += (target_glow - self._speak_glow) * 0.12

        # Blink logic
        self._blink_timer += 1
        if not self._is_blinking:
            if self._blink_timer >= self._next_blink:
                self._start_blink()
        else:
            self._blink_phase += 1
            if self._blink_phase <= 4:
                # Closing: crossfade to blink pose
                pass
            elif self._blink_phase <= 8:
                # Closed: hold
                pass
            else:
                # Opening: crossfade back
                self._end_blink()

        self.update()

    def _start_blink(self):
        """Trigger a natural eye blink."""
        if "blinking" not in self.poses:
            self._blink_timer = 0
            self._next_blink = random.randint(180, 300)
            return
        self._is_blinking = True
        self._blink_phase = 0
        self._pre_blink_pose = self._target_pose
        self._current_pose = self._target_pose
        self._target_pose = "blinking"
        self._crossfade = 0.0
        self._crossfade_speed = 0.25  # fast blink close (~4 frames)

    def _end_blink(self):
        """Return from blink to previous pose."""
        self._is_blinking = False
        self._blink_timer = 0
        self._next_blink = random.randint(180, 300)
        self._current_pose = "blinking"
        self._target_pose = self._pre_blink_pose if hasattr(self, '_pre_blink_pose') else "idle"
        self._crossfade = 0.0
        self._crossfade_speed = 0.25  # fast blink open
        # Restore normal crossfade speed after blink completes
        QTimer.singleShot(200, lambda: setattr(self, '_crossfade_speed', 0.06))

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

        # 2. Compute subtle transforms
        breath = math.sin(self._breath_phase)
        sway = math.sin(self._sway_phase)

        scale = 1.0 + breath * 0.003          # ±0.3% breathing pulse
        rotation = sway * 0.3                   # ±0.3° gentle sway
        bob_y = breath * 1.5                    # ±1.5px vertical bob

        if self.state == "thinking":
            rotation += 1.0
        elif self.state == "listening":
            bob_y += math.sin(self._sway_phase * 3) * 1.0

        cx, cy = w / 2.0, h / 2.0

        # 3. Draw current pose (fading out) and target pose (fading in)
        current_px = self.poses.get(self._current_pose, self.poses.get("idle"))
        target_px = self.poses.get(self._target_pose, self.poses.get("idle"))

        def draw_pose(pixmap, opacity):
            if pixmap is None or opacity <= 0.01:
                return
            p.save()
            p.setOpacity(opacity)

            # Scale to fit widget
            pw, ph = pixmap.width(), pixmap.height()
            aspect = pw / ph
            if w / h > aspect:
                draw_h = h
                draw_w = int(h * aspect)
            else:
                draw_w = w
                draw_h = int(w / aspect)

            p.translate(cx, cy + bob_y)
            p.rotate(rotation)
            p.scale(scale, scale)
            p.translate(-draw_w / 2.0, -draw_h / 2.0)
            p.drawPixmap(0, 0, draw_w, draw_h, pixmap)
            p.restore()

        # Layer 1: current pose (fading out)
        if self._crossfade < 1.0:
            draw_pose(current_px, 1.0 - self._crossfade)

        # Layer 2: target pose (fading in)
        draw_pose(target_px, min(1.0, self._crossfade + (1.0 - self._crossfade) * 0.3))

        # 4. Ambient glow
        glow = QRadialGradient(cx, cy * 0.85, w * 0.45)
        glow.setColorAt(0.0, QColor(50, 80, 180, 25))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setOpacity(1.0)
        p.fillRect(self.rect(), QBrush(glow))

        # 5. Speaking pulse ring
        if self._speak_glow > 0.02:
            alpha = int(self._speak_glow * 45)
            pulse = 1.0 + math.sin(self.tick * 0.12) * 0.06
            radius = min(w, h) * 0.42 * pulse
            ring = QRadialGradient(cx, cy * 0.9, radius)
            ring.setColorAt(0.88, QColor(80, 140, 255, 0))
            ring.setColorAt(0.96, QColor(80, 140, 255, alpha))
            ring.setColorAt(1.0, QColor(80, 140, 255, 0))
            p.fillRect(self.rect(), QBrush(ring))

        # 6. Cinematic letterbox fades
        top_fade = QLinearGradient(0, 0, 0, 30)
        top_fade.setColorAt(0.0, QColor(12, 14, 38, 180))
        top_fade.setColorAt(1.0, QColor(12, 14, 38, 0))
        p.fillRect(0, 0, w, 30, top_fade)

        bot_fade = QLinearGradient(0, h - 30, 0, h)
        bot_fade.setColorAt(0.0, QColor(4, 6, 16, 0))
        bot_fade.setColorAt(1.0, QColor(4, 6, 16, 180))
        p.fillRect(0, h - 30, w, 30, bot_fade)

        p.end()


class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Plays H.264 MP4 videos when available; otherwise shows a beautiful
    animated presenter using pre-generated Pixar-quality pose sprites
    with smooth crossfade transitions, natural blinking, and breathing.
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

        # Index 1 — animated presenter fallback
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
