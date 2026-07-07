import os
import logging
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtWidgets import QWidget, QStackedLayout, QLabel
from PySide6.QtGui import QPixmap, QMovie, QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Supports playing high-fidelity H.264 MP4 videos (e.g. generated via Hedra/HeyGen)
    smoothly at 60 FPS with natural blinks, mouth/teeth movements, and body sways.
    Mutes the video audios automatically to sync seamlessly with real-time multilingual TTS.
    Falls back to displaying the high-resolution AI presenter photo as a standby poster if videos are missing.
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
        
        # Widget 1: Label (for fallback standby poster image)
        self.display_label = QLabel()
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: #000000; border-radius: 12px;")
        self.stacked_layout.addWidget(self.display_label)
        
        # 2. Setup PySide6 Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        
        # Mute audio track of video files to support multilingual TTS speech overlay
        self.audio_output.setMuted(True)
        
        # Core Paths
        self.videos_dir = os.path.join(os.path.dirname(__file__), "assets", "videos")
        self.fallback_image_path = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
        
        self.current_media_path = ""
        self.current_state = "idle"
        self.current_slide = 0
        self.is_speaking = False
        
        self.init_avatar()

    def init_avatar(self):
        os.makedirs(self.videos_dir, exist_ok=True)
        # Show static standby poster initially
        self.show_static_poster()

    def show_static_poster(self):
        """Displays the high-resolution Pixar-style poster image as standby."""
        self.stop()
        self.stacked_layout.setCurrentIndex(1)  # Switch to display label
        
        if os.path.exists(self.fallback_image_path):
            pixmap = QPixmap(self.fallback_image_path)
            # Smooth scaling to fit the widget boundaries beautifully
            pixmap = pixmap.scaled(
                self.width() if self.width() > 10 else 340, 
                self.height() if self.height() > 10 else 480, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.display_label.setPixmap(pixmap)
        else:
            self.display_label.setText("Digital Human Standby\n(Place presenter_base.jpg here)")
            self.display_label.setFont(QFont("Segoe UI", 11))
            self.display_label.setStyleSheet("color: #a4b2fc; background-color: #000000;")
        self.current_media_path = ""

    def pop_out(self):
        """Called when a visitor is detected."""
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self._update_avatar_media()

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass # Gaze tracking is pre-rendered inside the video files

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self._update_avatar_media()

    def _update_avatar_media(self):
        """
        Calculates and loads the target animation source.
        Prioritizes H.264 MP4 videos, falling back to the static standby poster.
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

        # 2. Fall back to static poster image
        self.show_static_poster()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update poster scaling on resize
        if self.stacked_layout.currentIndex() == 1:
            self.show_static_poster()

    def pause(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.pause()

    def play(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.play()

    def stop(self):
        self.player.stop()
