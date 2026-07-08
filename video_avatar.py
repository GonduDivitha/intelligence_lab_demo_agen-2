import os
import logging
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtWidgets import QWidget, QStackedLayout
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

logger = logging.getLogger(__name__)


class WebGLAvatar(QWebEngineView):
    """
    Live2D-style WebGL mesh deformation avatar.
    Loads avatar_engine.html which renders the presenter image on a
    deformable WebGL mesh, producing genuine facial animation:
      - Real vertex deformation for lip shapes (not image switching)
      - Smooth jaw opening, lip morphing, cheek stretching
      - Natural eyelid blink via vertex displacement
      - Eyebrow raise for speech emphasis
      - Breathing and head sway via mesh transforms
    All running at 60fps inside a QWebEngineView.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#0c0e26;border:none;")

        # Enable WebGL
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        self._ready = False
        self.loadFinished.connect(self._on_load_finished)
        self._load_engine()

    def _load_engine(self):
        """Load the WebGL avatar engine HTML file."""
        html_path = os.path.join(os.path.dirname(__file__), "assets", "avatar_engine.html")
        if not os.path.exists(html_path):
            logger.warning(f"Avatar engine HTML not found: {html_path}")
            return

        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # Set baseUrl to project root so the HTML can load presenter_base.jpg
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_url = QUrl.fromLocalFile(base_dir + "/")
        self.setHtml(html, base_url)

    def _on_load_finished(self, ok):
        self._ready = ok
        if ok:
            logger.info("WebGL avatar engine loaded successfully")
        else:
            logger.warning("WebGL avatar engine failed to load")

    def _run_js(self, code):
        """Safely run JavaScript on the avatar engine."""
        if self._ready:
            self.page().runJavaScript(code)

    def set_speaking(self, speaking):
        val = "true" if speaking else "false"
        self._run_js(f"if(window.avatarAPI) avatarAPI.setSpeaking({val})")

    def set_speaking_text(self, text):
        safe = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", "")
        self._run_js(f"if(window.avatarAPI) avatarAPI.setText('{safe}')")

    def set_state(self, state):
        self._run_js(f"if(window.avatarAPI) avatarAPI.setState('{state}')")

    def set_viseme(self, viseme):
        self._run_js(f"if(window.avatarAPI) avatarAPI.setViseme('{viseme}')")

    def trigger_blink(self):
        self._run_js("if(window.avatarAPI) avatarAPI.triggerBlink()")


class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Priority 1: Plays H.264 MP4 videos when available in assets/videos/.
    Priority 2: WebGL mesh-deformation avatar engine with genuine facial
                 animation (lip sync, blink, breathing, head sway).
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

        # Index 1 — WebGL mesh deformation avatar
        self.webgl_avatar = WebGLAvatar()
        self.stacked_layout.addWidget(self.webgl_avatar)

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
        self.webgl_avatar.set_state("idle")
        self.webgl_avatar.set_speaking(False)
        self.current_media_path = ""

    def pop_out(self):
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self.webgl_avatar.set_speaking(is_speaking)
        self._update_media()

    def set_speaking_text(self, text: str):
        """Feed spoken text for phoneme-synced lip movement via mesh deformation."""
        self.webgl_avatar.set_speaking_text(text)

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self.webgl_avatar.set_state(state.lower())
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
