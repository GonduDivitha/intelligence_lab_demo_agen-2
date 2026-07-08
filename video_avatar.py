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
# Computed from face detection: face at (333,221,246,246)
LOWER_FACE = (0.385, 0.275, 0.230, 0.130)   # x, y, w, h — nose to chin
EYE_REGION = (0.390, 0.230, 0.220, 0.065)    # x, y, w, h — both eyes

# ── Viseme to source pose mapping ─────────────────────────────────────
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

# Gesture rotation (body poses during speaking)
SPEAK_GESTURES = ['speaking', 'both_hands', 'pointing', 'mouth_wide', 'mouth_o', 'speaking']
GESTURE_INTERVAL = 150  # frames (~2.5s at 60fps)

# Phoneme mapping
CHAR_VISEME = {
    'a':'aa','e':'ee','i':'ee','o':'oh','u':'oo',
    'b':'mm','m':'mm','p':'mm',
    'f':'ff','v':'ff',
    's':'ss','z':'ss','c':'ss','x':'ss',
    'w':'oo','r':'oh','q':'oo',
    'd':'th','t':'th','n':'th','l':'th',
    'g':'ss','k':'ss','j':'ee','y':'ee','h':'aa',
    ' ':'rest',',':'rest','.':'rest','!':'rest','?':'rest',
}


class FaceCompositingPresenter(QWidget):
    """
    Regional Face Compositing Avatar Engine.

    Instead of subtle mesh deformation or image switching, this engine:
    1. Draws the full body pose (gesture rotation every ~2.5s)
    2. COMPOSITES the mouth region from the matching viseme pose ON TOP
       (using elliptical feather mask for seamless blending)
    3. COMPOSITES the eye region from the blink pose during blinks

    Result: clearly visible lip movement, eye blinks, and gesture changes
    because each face region comes from a completely different Pixar render.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0

        # State
        self.is_speaking = False
        self.state = 'idle'

        # Load all pose images
        self.poses = {}
        self._load_poses()

        # ── Pre-compute face region sprites ──
        self.mouth_sprites = {}
        self.blink_sprite = None
        self._precompute_sprites()

        # ── Viseme lip sync state ──
        self._viseme_seq = []
        self._viseme_idx = 0
        self._viseme_timer = 0
        self._chars_per_sec = 13
        self._current_viseme = 'rest'

        # ── Gesture rotation ──
        self._gesture_idx = 0
        self._gesture_timer = 0
        self._current_gesture = 'idle'

        # ── Blink state ──
        self._blink_timer = 0
        self._next_blink = random.randint(180, 330)
        self._blink_alpha = 0.0   # 0=eyes open, 1=eyes closed
        self._blink_phase = 0     # 0=not blinking, >0=blinking

        # ── Physics ──
        self._breath = 0.0
        self._sway = 0.0

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
        """Extract a face region with soft elliptical feathering for seamless compositing."""
        x = int(region[0] * pixmap.width())
        y = int(region[1] * pixmap.height())
        w = int(region[2] * pixmap.width())
        h = int(region[3] * pixmap.height())

        # Crop region
        cropped = pixmap.copy(x, y, w, h)

        # Create elliptical feather mask
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

        # Apply mask via composition
        result = QPixmap(w, h)
        result.fill(Qt.transparent)
        rp = QPainter(result)
        rp.drawPixmap(0, 0, cropped)
        rp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        rp.drawPixmap(0, 0, mask)
        rp.end()

        return result

    def _precompute_sprites(self):
        """Pre-extract all mouth and eye region sprites at startup."""
        for viseme, pose_name in VISEME_POSE.items():
            if pose_name in self.poses:
                self.mouth_sprites[viseme] = self._extract_feathered_region(
                    self.poses[pose_name], LOWER_FACE, feather_ratio=0.30)
                logger.info(f"Pre-computed mouth sprite: {viseme} from {pose_name}")

        if 'blinking' in self.poses:
            self.blink_sprite = self._extract_feathered_region(
                self.poses['blinking'], EYE_REGION, feather_ratio=0.35)
            logger.info("Pre-computed blink eye sprite")

    # ── Public API ──────────────────────────────────────────────────
    def set_speaking(self, speaking):
        was = self.is_speaking
        self.is_speaking = speaking
        if speaking and not was:
            self._gesture_timer = 0
            self._gesture_idx = 0
            self._current_gesture = SPEAK_GESTURES[0]
            self._viseme_idx = 0
            self._viseme_timer = 0
        elif not speaking and was:
            self._viseme_seq = []
            self._current_viseme = 'rest'
            self._current_gesture = 'idle'

    def set_speaking_text(self, text):
        self._viseme_seq = [CHAR_VISEME.get(ch.lower(), 'ss') for ch in text]
        self._viseme_idx = 0
        self._viseme_timer = 0

    def set_state(self, state):
        self.state = state.lower()

    # ── Animation loop ──────────────────────────────────────────────
    def _tick(self):
        self.tick += 1
        self._breath += 0.045
        self._sway += 0.025

        # ── Lip sync ──
        if self.is_speaking:
            self._viseme_timer += 1
            frames_per_char = max(2, int(60 / self._chars_per_sec))
            if self._viseme_timer >= frames_per_char:
                self._viseme_timer = 0
                if self._viseme_seq and self._viseme_idx < len(self._viseme_seq):
                    self._current_viseme = self._viseme_seq[self._viseme_idx]
                    self._viseme_idx += 1
                else:
                    cycle = ['aa', 'ss', 'ee', 'rest', 'oh', 'ss', 'aa', 'mm', 'ee', 'th']
                    self._current_viseme = cycle[self.tick // frames_per_char % len(cycle)]

            # Gesture rotation
            self._gesture_timer += 1
            if self._gesture_timer >= GESTURE_INTERVAL:
                self._gesture_timer = 0
                self._gesture_idx = (self._gesture_idx + 1) % len(SPEAK_GESTURES)
                self._current_gesture = SPEAK_GESTURES[self._gesture_idx]

        # ── Blink ──
        if self._blink_phase == 0:
            self._blink_timer += 1
            if self._blink_timer >= self._next_blink:
                self._blink_phase = 1
                self._blink_timer = 0
                self._next_blink = random.randint(180, 330)
        else:
            self._blink_phase += 1
            if self._blink_phase <= 5:
                self._blink_alpha = min(1.0, self._blink_alpha + 0.25)
            elif self._blink_phase <= 9:
                self._blink_alpha = 1.0
            elif self._blink_phase <= 15:
                self._blink_alpha = max(0.0, self._blink_alpha - 0.2)
            else:
                self._blink_phase = 0
                self._blink_alpha = 0.0

        self.update()

    # ── Rendering ───────────────────────────────────────────────────
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
            p.drawText(self.rect(), Qt.AlignCenter, "Place presenter_base.jpg\nin the project folder")
            p.end()
            return

        # 2. Get body pose
        body = self.poses.get(self._current_gesture, self.poses.get('idle'))
        if body is None:
            p.end()
            return

        # 3. Compute display rect (fit to widget)
        aspect = body.width() / body.height()
        if w / h > aspect:
            dh = h; dw = int(h * aspect)
        else:
            dw = w; dh = int(w / aspect)
        dx = (w - dw) // 2
        dy = (h - dh) // 2

        # 4. Apply breathing/sway transform
        breath = math.sin(self._breath)
        sway = math.sin(self._sway)
        sc = 1.0 + breath * 0.003
        rot = sway * 0.3
        bob = breath * 1.5

        p.save()
        p.translate(w / 2, h / 2 + bob)
        p.rotate(rot)
        p.scale(sc, sc)
        p.translate(-w / 2, -h / 2)

        # 5. Draw full body pose
        p.drawPixmap(dx, dy, dw, dh, body)

        # 6. COMPOSITE mouth region from current viseme pose
        mouth = self.mouth_sprites.get(self._current_viseme)
        if mouth:
            mx = dx + int(LOWER_FACE[0] * dw)
            my = dy + int(LOWER_FACE[1] * dh)
            mw = int(LOWER_FACE[2] * dw)
            mh = int(LOWER_FACE[3] * dh)
            p.drawPixmap(mx, my, mw, mh, mouth)

        # 7. COMPOSITE blink eyes
        if self._blink_alpha > 0.01 and self.blink_sprite:
            p.setOpacity(self._blink_alpha)
            ex = dx + int(EYE_REGION[0] * dw)
            ey = dy + int(EYE_REGION[1] * dh)
            ew = int(EYE_REGION[2] * dw)
            eh = int(EYE_REGION[3] * dh)
            p.drawPixmap(ex, ey, ew, eh, self.blink_sprite)
            p.setOpacity(1.0)

        p.restore()

        # 8. Ambient glow
        glow = QRadialGradient(w / 2, h * 0.43, w * 0.45)
        glow.setColorAt(0.0, QColor(50, 80, 180, 25))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(glow))

        # 9. Speaking pulse ring
        if self.is_speaking:
            pulse = 0.5 + 0.5 * math.sin(self.tick * 0.08)
            alpha = int(pulse * 50)
            ring = QRadialGradient(w / 2, h * 0.45, min(w, h) * 0.44)
            ring.setColorAt(0.88, QColor(80, 140, 255, 0))
            ring.setColorAt(0.95, QColor(80, 140, 255, alpha))
            ring.setColorAt(1.0, QColor(80, 140, 255, 0))
            p.fillRect(self.rect(), QBrush(ring))

        # 10. Cinematic letterbox
        tf = QLinearGradient(0, 0, 0, 25)
        tf.setColorAt(0, QColor(12, 14, 38, 180))
        tf.setColorAt(1, QColor(12, 14, 38, 0))
        p.fillRect(0, 0, w, 25, tf)
        bf = QLinearGradient(0, h - 25, 0, h)
        bf.setColorAt(0, QColor(4, 6, 16, 0))
        bf.setColorAt(1, QColor(4, 6, 16, 180))
        p.fillRect(0, h - 25, w, 25, bf)

        p.end()


class VideoAvatar(QWidget):
    """
    Digital Human presenter component.
    Priority 1: Plays H.264 MP4 videos from assets/videos/.
    Priority 2: Face-compositing presenter with visible lip sync,
                 eye blinks, and gesture changes.
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

        # Index 1 — face compositing presenter
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
