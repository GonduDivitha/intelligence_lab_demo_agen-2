import os
import logging
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QMovie, QFont

logger = logging.getLogger(__name__)

class VideoAvatar(QWidget):
    """
    Cross-platform high-fidelity Digital Human presenter component.
    Uses QMovie to play animated GIF presenter clips dynamically.
    Guarantees 100% reliable, hardware-independent render output on all platforms (macOS/Windows).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Main Display Label (Holds both QMovie and static QPixmap fallbacks)
        self.display_label = QLabel()
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: #000000; border-radius: 12px;")
        self.layout.addWidget(self.display_label)
        
        self.movie = None
        
        # Paths
        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets", "gifs")
        self.fallback_image_path = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
        
        self.current_gif_path = ""
        self.init_avatar()

    def init_avatar(self):
        os.makedirs(self.assets_dir, exist_ok=True)
        # Load initial standby poster
        self.show_static_poster()

    def show_static_poster(self):
        """Displays the high-resolution poster image as standby."""
        if self.movie:
            self.movie.stop()
            self.movie = None
            
        if os.path.exists(self.fallback_image_path):
            pixmap = QPixmap(self.fallback_image_path)
            pixmap = pixmap.scaled(
                340, 480, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.display_label.setPixmap(pixmap)
        else:
            self.display_label.setText("Digital Human Standby\n(Place presenter_base.jpg here)")
            self.display_label.setFont(QFont("Segoe UI", 11))
            self.display_label.setStyleSheet("color: #a4b2fc; background-color: #000000;")
        self.current_gif_path = ""

    def pop_out(self):
        """Called when a visitor is detected."""
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        pass

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass # Gaze tracking is pre-rendered in high-fidelity GIF loop

    def set_state(self, state: str, slide_index: int = 0):
        """
        Dynamically transitions the presenter loop based on the agent state.
        Switches animated GIF loops seamlessly.
        """
        state = state.lower()
        gif_filename = ""
        
        if state == "greeting":
            gif_filename = "greeting.gif"
        elif state == "farewell":
            gif_filename = "farewell.gif"
        elif state in ["presenting", "speaking", "answering"]:
            gif_filename = f"slide{slide_index}.gif"
            if not os.path.exists(os.path.join(self.assets_dir, gif_filename)):
                gif_filename = "speaking.gif"
        elif state == "listening":
            gif_filename = "listening.gif"
        elif state == "thinking":
            gif_filename = "thinking.gif"
        else:
            gif_filename = "idle.gif"

        gif_path = os.path.join(self.assets_dir, gif_filename)
        
        if os.path.exists(gif_path):
            if gif_path != self.current_gif_path:
                logger.info(f"Transitioning to animated presenter loop: {gif_filename}")
                self.current_gif_path = gif_path
                
                # Stop old movie
                if self.movie:
                    self.movie.stop()
                
                # Load new movie
                self.movie = QMovie(gif_path)
                
                # Dynamic scaling with fallback for initialization
                w = self.display_label.width()
                h = self.display_label.height()
                if w <= 10 or h <= 10:
                    w, h = 340, 480
                self.movie.setScaledSize(QSize(w, h))
                
                self.display_label.setMovie(self.movie)
                self.movie.start()
        else:
            # Standby mode if the GIF loop doesn't exist
            logger.debug(f"Animated loop '{gif_filename}' missing. Showing standby poster.")
            self.show_static_poster()

    def resizeEvent(self, event):
        """Ensure QMovie is scaled correctly if the window layout changes size."""
        super().resizeEvent(event)
        if self.movie:
            w = self.display_label.width()
            h = self.display_label.height()
            if w > 10 and h > 10:
                self.movie.setScaledSize(QSize(w, h))

    def pause(self):
        if self.movie:
            self.movie.setPaused(True)

    def play(self):
        if self.movie:
            self.movie.setPaused(False)

    def stop(self):
        if self.movie:
            self.movie.stop()
