import os
import logging
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QStackedLayout
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage

logger = logging.getLogger(__name__)

class WebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        logger.info(f"JS Console: {message} (line {lineNumber} of {sourceID})")

class WebGLAvatar(QWebEngineView):
    """
    Loads the WebGL Live2D-style Skeletal Engine (avatar_engine.html).
    Communicates via JavaScript injections.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(WebPage(self))
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.setStyleSheet("background: transparent;")
        
        self._loaded = False
        self._pending_speaking = False
        self._pending_text = ""
        self._pending_state = "idle"
        
        self.loadFinished.connect(self._on_load_finished)
        
        html_path = os.path.join(os.path.dirname(__file__), "assets", "avatar_engine.html")
        self.load(QUrl.fromLocalFile(html_path))

    def _on_load_finished(self, ok):
        if ok:
            logger.info("WebGLAvatar page loaded successfully.")
            self._loaded = True
            # Push buffered state
            self.set_state(self._pending_state)
            self.set_speaking_text(self._pending_text)
            self.set_speaking(self._pending_speaking)
        else:
            logger.error("WebGLAvatar page failed to load.")

    def set_speaking(self, is_speaking: bool):
        self._pending_speaking = is_speaking
        if self._loaded:
            val = 'true' if is_speaking else 'false'
            self.page().runJavaScript(f"if(window.avatarAPI) avatarAPI.setSpeaking({val});")

    def set_speaking_text(self, text: str):
        self._pending_text = text
        if self._loaded:
            safe_text = text.replace("'", "\\'").replace('"', '\\"')
            self.page().runJavaScript(f"if(window.avatarAPI) avatarAPI.setText('{safe_text}');")

    def set_state(self, state: str):
        self._pending_state = state
        if self._loaded:
            self.page().runJavaScript(f"if(window.avatarAPI) avatarAPI.setState('{state}');")


class VideoAvatar(QWidget):
    """
    Digital Human presenter component.
    Priority 1: Plays H.264 MP4 videos from assets/videos/ (if they exist).
    Priority 2: WebGL Skeletal Engine (true 10/10 single-image dynamic mesh).
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

        # Index 1 — WebGL Live2D Engine
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

        # Fallback to Live2D WebGL
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
