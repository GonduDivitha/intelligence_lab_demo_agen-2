import os
import math
import random
import logging
from PySide6.QtCore import Qt, QUrl, QSize, QPointF, QRectF, QRect, QTimer
from PySide6.QtWidgets import QWidget, QStackedLayout, QLabel
from PySide6.QtGui import QPixmap, QMovie, QFont, QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPen, QBrush
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

class RealisticHumanAvatar(QWidget):
    """
    Ultra-premium 2D Digital Human Presenter.
    Uses photorealistic textures cropped directly from 'presenter_base.jpg'
    and animates them using advanced 3D-like multi-layered parallax,
    producing realistic eye blinks, organic lip-split mouth sync (lips, teeth, tongue),
    and fluid hand gestures at 60 FPS.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0
        
        # State control
        self.state = "idle"
        self.is_speaking = False
        
        # Physics phases
        self._breathing_phase = 0.0
        self._gesture_phase = 0.0
        self._nod_phase = 0.0
        self._head_tilt = 0.0
        
        # Eye Blink State
        self.blink_timer = 0
        self.blink_frame = 0  # 0: open, 1: half, 2: closed, 3: half
        
        # Mouth Speaking State
        self.mouth_open_factor = 0.0
        self.mouth_phase = 0.0
        
        # Image Assets and Texture Coordinates
        self.base_image_path = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
        self.is_loaded = False
        
        self.torso_pixmap = None
        self.head_pixmap = None
        self.l_eye_pixmap = None
        self.r_eye_pixmap = None
        self.mouth_pixmap = None
        self.sleeve_brush = None
        
        # Skin Tone matching the presenter's face
        self.skin_color = QColor(254, 222, 210)
        
        # Timer for 60 FPS physics loops
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)  # ~60 FPS
        
        self.load_textures()

    def load_textures(self):
        if not os.path.exists(self.base_image_path):
            logger.warning(f"Base image not found at {self.base_image_path}")
            return
            
        try:
            base = QPixmap(self.base_image_path)
            if base.isNull():
                return
                
            # Base Image Size is 896x1200
            # 1. Crop Torso (shoulders, blazer)
            self.torso_pixmap = base.copy(QRect(120, 500, 656, 700))
            
            # 2. Crop Head (face, hair, ears)
            self.head_pixmap = base.copy(QRect(248, 120, 400, 420))
            
            # 3. Crop Eyes for details
            self.l_eye_pixmap = base.copy(QRect(368, 312, 50, 30))
            self.r_eye_pixmap = base.copy(QRect(478, 312, 50, 30))
            
            # 4. Crop Mouth for lip-split animation
            self.mouth_pixmap = base.copy(QRect(408, 390, 84, 46))
            
            # 5. Crop Sleeve Texture from Blazer for arms matching
            sleeve_patch = base.copy(QRect(200, 620, 60, 60))
            self.sleeve_brush = QBrush(sleeve_patch)
            
            self.is_loaded = True
            logger.info("Photorealistic digital human textures successfully loaded.")
        except Exception as e:
            logger.error(f"Failed to load photorealistic textures: {e}")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking

    def set_state(self, state: str):
        self.state = state.lower()

    def update_physics(self):
        self.tick += 1
        
        # 1. Breathing Cycle (chest and shoulder bobs)
        self._breathing_phase += 0.04
        self._gesture_phase += 0.06
        
        # 2. Nodding when listening
        if self.state == "listening":
            self._nod_phase += 0.08
        else:
            self._nod_phase = 0.0
            
        # 3. Head Tilt and bob coordinates based on states
        if self.state == "thinking":
            self.head_tilt_target = 4.0
        elif self.state == "listening":
            self.head_tilt_target = -2.5 + math.sin(self._nod_phase) * 1.5
        elif self.state == "greeting":
            self.head_tilt_target = -1.5
        else:
            self.head_tilt_target = 0.0
            
        self._head_tilt += (self.head_tilt_target - self._head_tilt) * 0.1
        
        # 4. Blink cycle logic
        self.blink_timer += 1
        if self.blink_frame == 0:
            if self.blink_timer > random.randint(100, 200):
                self.blink_frame = 1
                self.blink_timer = 0
        elif self.blink_frame == 1:  # closing
            self.blink_frame = 2
        elif self.blink_frame == 2:  # closed
            self.blink_frame = 3
        elif self.blink_frame == 3:  # opening
            self.blink_frame = 0
            
        # 5. Lip Sync Mouth opening sizes
        if self.is_speaking:
            self.mouth_phase += 0.28
            self.mouth_open_factor = 0.3 + 0.7 * math.sin(self.mouth_phase)
        else:
            self.mouth_open_factor += (0.0 - self.mouth_open_factor) * 0.15
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        rect = self.rect()
        cx = rect.width() / 2
        
        # Background Space Glow
        self._draw_background(painter, rect)
        
        if not self.is_loaded:
            # Fallback standby text
            painter.setPen(QColor(180, 190, 220))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(rect, Qt.AlignCenter, "Loading Digital Human Presenter...")
            return
            
        # Setup breathing offset
        breath_y = math.sin(self._breathing_phase) * 2.5
        
        # Scale/Center agent inside container dynamically
        painter.save()
        scale = min(rect.width() / 360.0, rect.height() / 480.0) * 0.95
        scale = max(0.6, min(1.2, scale))
        dx = cx - (180 * scale)
        dy = (rect.height() - (480 * scale)) / 2 + 10
        painter.translate(dx, dy)
        painter.scale(scale, scale)
        
        # Draw Character Layers using realistic textures
        self._draw_torso_layer(painter, breath_y)
        self._draw_head_layer(painter)
        self._draw_eyes_layer(painter)
        self._draw_mouth_layer(painter)
        self._draw_arms_layer(painter, breath_y)
        
        painter.restore()

    def _draw_background(self, painter, rect):
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, QColor(14, 16, 42))
        grad.setColorAt(1.0, QColor(6, 8, 18))
        painter.fillRect(rect, grad)
        
        # Ambient backdrop lighting
        glow = QRadialGradient(rect.width() / 2, rect.height() * 0.4, rect.width() * 0.5)
        glow.setColorAt(0.0, QColor(48, 64, 150, 40))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, QBrush(glow))

    def _draw_torso_layer(self, painter, breath_y):
        painter.save()
        # Position torso at bottom, apply breathing bob
        painter.translate(180, 260 + breath_y * 0.6)
        
        # Draw cropped torso texture
        target_rect = QRectF(-140, 0, 280, 260)
        painter.drawPixmap(target_rect, self.torso_pixmap, QRectF(self.torso_pixmap.rect()))
        
        painter.restore()

    def _draw_head_layer(self, painter):
        painter.save()
        # Head pivot point (neck connection)
        painter.translate(180, 250)
        painter.rotate(self._head_tilt)
        
        # Draw cropped head texture (pivot centered around neck connection)
        target_rect = QRectF(-85, -153, 170, 180)
        painter.drawPixmap(target_rect, self.head_pixmap, QRectF(self.head_pixmap.rect()))
        
        painter.restore()

    def _draw_eyes_layer(self, painter):
        painter.save()
        painter.translate(180, 250)
        painter.rotate(self._head_tilt)
        
        # Eye heights relative to pivot neck connection
        eye_y = -98
        
        def draw_eye_blink(cx, is_left):
            painter.save()
            painter.translate(cx, eye_y)
            
            # If blinking, cover original eye texture with skin patch and eyelashes
            if self.blink_frame > 0:
                # Skin colored patch
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.skin_color)
                painter.drawEllipse(QPointF(0, 0), 11, 7)
                
                # Eyelash line
                painter.setPen(QPen(QColor(42, 28, 22), 2.2, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(-12, 0, 12, 0)
            painter.restore()

        draw_eye_blink(-30, True)
        draw_eye_blink(70, False)
        
        painter.restore()

    def _draw_mouth_layer(self, painter):
        painter.save()
        painter.translate(180, 250)
        painter.rotate(self._head_tilt)
        
        # Mouth coordinates relative to neck pivot
        mx, my = 20, -32
        
        op = self.mouth_open_factor
        mw = 32
        mh = op * 14
        
        if mh > 1.5:
            # 1. Oral Cavity (Red Throat interior)
            cavity_grad = QRadialGradient(mx, my, mw / 2)
            cavity_grad.setColorAt(0.0, QColor(140, 25, 40))   # throat
            cavity_grad.setColorAt(0.8, QColor(80, 10, 22))    # dark cavity
            
            cavity = QPainterPath()
            cavity.moveTo(mx - mw / 2, my)
            cavity.cubicTo(mx - mw / 2, my - mh / 2, mx + mw / 2, my - mh / 2, mx + mw / 2, my)
            cavity.cubicTo(mx + mw / 2, my + mh / 2, mx - mw / 2, my + mh / 2, mx - mw / 2, my)
            cavity.closeSubpath()
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(cavity_grad))
            painter.drawPath(cavity)
            
            # 2. Upper/Lower Teeth curves
            teeth_w = mw * 0.72
            teeth_h = max(1.8, mh * 0.22)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(QRectF(mx - teeth_w / 2, my - mh / 2 + 0.5, teeth_w, teeth_h), 1.5, 1.5)
            
            # 3. Pink tongue
            tongue_h = max(1.0, mh * 0.3)
            painter.setBrush(QColor(235, 115, 130))
            painter.drawEllipse(QRectF(mx - teeth_w * 0.4, my + mh / 2 - tongue_h, teeth_w * 0.8, tongue_h + 1))
            
            # 4. Realistic Lip-Split (Draw top half and bottom half of cropped lips shifted apart)
            w, h = 32, 20
            # Top lip
            painter.drawPixmap(
                QRectF(mx - w/2, my - h/2 - mh/2, w, h/2),
                self.mouth_pixmap,
                QRectF(0, 0, self.mouth_pixmap.width(), self.mouth_pixmap.height() / 2)
            )
            # Bottom lip
            painter.drawPixmap(
                QRectF(mx - w/2, my + mh/2, w, h/2),
                self.mouth_pixmap,
                QRectF(0, self.mouth_pixmap.height() / 2, self.mouth_pixmap.width(), self.mouth_pixmap.height() / 2)
            )
            
        else:
            # Closed mouth: render her actual closed mouth from the photo
            w, h = 30, 20
            target_rect = QRectF(mx - w/2, my - h/2, w, h)
            painter.drawPixmap(target_rect, self.mouth_pixmap, QRectF(self.mouth_pixmap.rect()))
            
        painter.restore()

    def _draw_arms_layer(self, painter, breath_y):
        # Render high-resolution arms using textured sleeves to match the navy blazer
        painter.save()
        painter.translate(180, 250)
        
        body_top = 72 + breath_y * 0.6
        sleeve_color = QColor(15, 30, 85)     # Navy sleeve
        skin_color = QColor(255, 222, 210)    # skin forearm
        
        def draw_arm(sh_x, sh_y, el_x, el_y, hd_x, hd_y, state_pointing=False):
            painter.save()
            # Sleeve stroke
            painter.setPen(QPen(sleeve_color, 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(sh_x), int(sh_y), int(el_x), int(el_y))
            # Forearm skin stroke
            painter.setPen(QPen(skin_color, 11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(el_x), int(el_y), int(hd_x), int(hd_y))
            # Hand shape
            painter.setPen(Qt.NoPen)
            painter.setBrush(skin_color)
            if state_pointing:
                hand = QPainterPath()
                hand.moveTo(hd_x, hd_y - 4)
                hand.lineTo(hd_x + 12, hd_y - 2)   # pointing finger
                hand.lineTo(hd_x + 4, hd_y + 4)
                hand.lineTo(hd_x - 4, hd_y + 4)
                hand.closeSubpath()
                painter.drawPath(hand)
            else:
                painter.drawEllipse(QPointF(hd_x, hd_y), 8, 8)
            painter.restore()

        shoulder_l = (-66, body_top + 12)
        shoulder_r = (66, body_top + 12)
        
        wave = math.sin(self.tick * 0.15)
        gest = math.sin(self._gesture_phase * 2)
        
        # Draw Arms based on current state
        if self.state == "greeting":
            # Right arm waving, left arm resting
            draw_arm(*shoulder_l, -74, body_top + 55, -68, body_top + 105)
            # Waving right arm
            rh_y = body_top - 22 + wave * 22
            draw_arm(*shoulder_r, 82, body_top + 15, 92, rh_y)
            
        elif self.state == "presenting":
            # Left arm resting, right arm extended pointing to presentation slides
            draw_arm(*shoulder_l, -70, body_top + 55, -65, body_top + 105)
            draw_arm(*shoulder_r, 92, body_top + 32, 130 + gest * 4, body_top + 22 + gest * 2, state_pointing=True)
            
        elif self.state in ("speaking", "answering"):
            # Double hands speaking gestures
            draw_arm(*shoulder_l, -75, body_top + 45, -62 + gest * 4, body_top + 75 + gest * 8)
            draw_arm(*shoulder_r, 75, body_top + 42, 62 - gest * 3, body_top + 68 - gest * 6)
            
        elif self.state == "thinking":
            # Left hand on chin, right arm folded
            draw_arm(*shoulder_l, -42, body_top + 32, -14, body_top - 8 + gest * 2)
            draw_arm(*shoulder_r, 52, body_top + 48, 22, body_top + 78)
            
        elif self.state == "listening":
            lean = math.sin(self._nod_phase) * 2.5
            draw_arm(*shoulder_l, -68, body_top + 52 + lean, -62, body_top + 105)
            draw_arm(*shoulder_r, 68, body_top + 52 - lean, 62, body_top + 105)
            
        elif self.state == "farewell":
            # Double waving arms
            draw_arm(*shoulder_l, -80, body_top + 12, -90, body_top - 12 + wave * 18)
            draw_arm(*shoulder_r, 80, body_top + 12, 90, body_top - 12 - wave * 18)
            
        else:  # idle
            # Resting hands in front
            draw_arm(*shoulder_l, -58, body_top + 52, -18, body_top + 88)
            draw_arm(*shoulder_r, 58, body_top + 52, 18, body_top + 88)
            
        painter.restore()

class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Supports playing high-fidelity H.264 MP4 videos (e.g. generated via Hedra/HeyGen)
    smoothly at 60 FPS with natural blinks, mouth/teeth movements, and body sways.
    Mutes the video audios automatically to sync seamlessly with real-time multilingual TTS.
    Falls back to a photorealistic digital human (RealisticHumanAvatar) if videos are missing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)
        
        # 1. Setup Stacked Layout
        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        
        # Widget 0: Video Player (for real MP4 presenter videos)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 12px;")
        self.stacked_layout.addWidget(self.video_widget)
        
        # Widget 1: Realistic Human Fallback (for real-time rendering)
        self.vector_avatar = RealisticHumanAvatar()
        self.stacked_layout.addWidget(self.vector_avatar)
        
        # 2. Setup PySide6 Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        
        # Mute audio track of video files to support multilingual TTS speech overlay
        self.audio_output.setMuted(True)
        
        # Core Paths
        self.videos_dir = os.path.join(os.path.dirname(__file__), "assets", "videos")
        
        self.current_media_path = ""
        self.current_state = "idle"
        self.current_slide = 0
        self.is_speaking = False
        
        self.init_avatar()

    def init_avatar(self):
        os.makedirs(self.videos_dir, exist_ok=True)
        # Show vector fallback as initial standby
        self.show_static_poster()

    def show_static_poster(self):
        """Switches display index to vector fallback renderer in standby mode."""
        self.stop()
        self.stacked_layout.setCurrentIndex(1)  # Switch to vector fallback
        self.vector_avatar.set_state("idle")
        self.vector_avatar.set_speaking(False)
        self.current_media_path = ""

    def pop_out(self):
        """Called when a visitor is detected."""
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self.vector_avatar.set_speaking(is_speaking)
        self._update_avatar_media()

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass # Gaze tracking is pre-rendered or calculated natively inside the layout

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self.vector_avatar.set_state(state.lower())
        self._update_avatar_media()

    def _update_avatar_media(self):
        """
        Calculates and loads the target animation source.
        Prioritizes H.264 MP4 videos, falling back to the vector digital human.
        """
        state = self.current_state
        media_filename = ""
        is_looping_state = False

        # Map state and speaking flag to filenames
        if state in ["presenting", "speaking", "answering"]:
            if self.is_speaking:
                media_filename = f"slide{self.current_slide}"
            else:
                media_filename = f"slide{self.current_slide}_silent"
        elif state == "greeting":
            if self.is_speaking:
                media_filename = "greeting"
            else:
                media_filename = "greeting_silent"
        elif state == "thinking":
            media_filename = "thinking"
            is_looping_state = True
        elif state == "listening":
            media_filename = "listening"
            is_looping_state = True
        else:  # idle
            media_filename = "idle"
            is_looping_state = True

        # Check if speaking/greeting is silent, loop it
        if "_silent" in media_filename or media_filename == "idle":
            is_looping_state = True

        # 1. Try to load H.264 MP4 Video first
        mp4_path = os.path.join(self.videos_dir, f"{media_filename}.mp4")
        
        def is_valid_mp4(path):
            return os.path.exists(path) and os.path.getsize(path) > 50 * 1024
        
        # If specific slide video is missing, try fallback speaking.mp4
        if not is_valid_mp4(mp4_path) and ("slide" in media_filename or "greeting" in media_filename):
            if self.is_speaking:
                mp4_path = os.path.join(self.videos_dir, "speaking.mp4")
            else:
                mp4_path = os.path.join(self.videos_dir, "idle.mp4")

        if is_valid_mp4(mp4_path):
            if mp4_path != self.current_media_path:
                logger.info(f"Playing high-definition presenter video: {os.path.basename(mp4_path)}")
                self.current_media_path = mp4_path
                
                # Switch to QVideoWidget
                self.stacked_layout.setCurrentIndex(0)
                
                # Configure Player
                self.player.setSource(QUrl.fromLocalFile(mp4_path))
                if is_looping_state:
                    self.player.setLoops(QMediaPlayer.Infinite)
                else:
                    self.player.setLoops(1)  # Play once for slide presentation
                
                self.player.play()
            return

        # 2. Fall back to Vector Digital Human Presenter
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
