import os
import time
import queue
import logging
import asyncio
import tempfile
import pygame

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

VOICE_MAP = {
    "english": "en-US-AriaNeural",
    "hindi": "hi-IN-SwaraNeural",
    "telugu": "te-IN-ShrutiNeural",
    "tamil": "ta-IN-PallaviNeural",
    "kannada": "kn-IN-SapnaNeural",
    "malayalam": "ml-IN-SobhanaNeural",
}

class TTSEngine(QThread):
    speech_started = Signal(str)
    speech_finished = Signal(str)
    speech_interrupted = Signal(str)
    status = Signal(str)
    speaking_state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        self._is_speaking = False
        self._current_token = ""
        
        import threading
        self._interrupted = threading.Event()
        self._temp_dir = tempfile.mkdtemp()
        self._language = "english"
        
        # Flag to indicate if pygame was initialized successfully
        self._pygame_ok = False

    def speak(self, text: str, token: str = "", language: str = None):
        clean_text = text.strip() if text else ""
        if clean_text:
            lang = language.lower() if language else self._language
            self._queue.put((token, clean_text, lang))

    def set_language(self, language: str):
        self._language = language.lower()

    def stop_speaking(self):
        self._interrupted.set()
        
        # Clear any queued speech tasks to stop immediately, preserving None shutdown sentinel
        try:
            items_to_keep = []
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item is None:
                        items_to_keep.append(item)
                except queue.Empty:
                    break
            for item in items_to_keep:
                self._queue.put(item)
        except Exception as e:
            logger.error(f"Error clearing TTS queue during stop: {e}")

        if self._pygame_ok:
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
            except Exception as e:
                logger.error(f"Error stopping pygame music: {e}")

    def is_speaking(self) -> bool:
        return self._is_speaking

    def run(self):
        self.status.emit("Neural TTS Engine initializing...")
        try:
            pygame.mixer.init(frequency=24000)
            self._pygame_ok = True
            self.status.emit("Neural TTS Engine ready.")
        except Exception as e:
            self._pygame_ok = False
            self.status.emit(f"Failed to init pygame.mixer, using pyttsx3: {e}")

        while self._running:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            token, text, language = item
            self._current_token = token
            self._is_speaking = True
            self._interrupted.clear()

            self.speech_started.emit(token)
            self.speaking_state_changed.emit(True)

            success = self._generate_and_play(text, language, token)

            self._is_speaking = False
            self.speaking_state_changed.emit(False)

            if self._interrupted.is_set():
                self.speech_interrupted.emit(token)
            else:
                if success:
                    self.speech_finished.emit(token)
                else:
                    self.speech_interrupted.emit(token)

        # Cleanup
        if self._pygame_ok:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
        
        # Try to remove temp directory and any leftover files
        try:
            for f in os.listdir(self._temp_dir):
                os.remove(os.path.join(self._temp_dir, f))
            os.rmdir(self._temp_dir)
        except Exception:
            pass

    def _generate_and_play(self, text: str, language: str, token: str) -> bool:
        audio_path = os.path.join(self._temp_dir, f"tts_{int(time.time() * 1000)}.mp3")
        voice = VOICE_MAP.get(language.lower(), "en-US-AriaNeural")

        # 1. Try edge-tts first if pygame is ok
        if self._pygame_ok:
            try:
                import edge_tts
                
                async def _save():
                    communicate = edge_tts.Communicate(text, voice, rate="-5%", pitch="+0Hz")
                    await communicate.save(audio_path)
                
                # Run the async save
                asyncio.run(_save())
                
                # Play using pygame
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    if self._interrupted.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
                
                # Cleanup the audio file
                try:
                    pygame.mixer.music.unload()
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                except Exception:
                    pass
                
                return True
                
            except Exception as e:
                self.status.emit(f"Edge-TTS failed: {e}. Falling back to pyttsx3.")
                logger.warning(f"Edge-TTS failed: {e}")

        # 2. Fallback to pyttsx3 (runs synchronously on this thread)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Set rate to be slightly slower and natural
            engine.setProperty("rate", 145)
            engine.setProperty("volume", 1.0)
            
            # Since pyttsx3 runAndWait block, interruption is hard to detect mid-sentence.
            # However, for a fallback it's acceptable.
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception as e:
            self.status.emit(f"TTS fallback failed completely: {e}")
            logger.error(f"TTS fallback failed completely: {e}")
            return False

    def stop(self):
        self._running = False
        self._queue.put(None)
        self.stop_speaking()
        self.wait(1500)
