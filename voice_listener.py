import json
import queue
import logging
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class ContinuousVoiceListener(QThread):
    """
    Continuous voice recognition thread using Vosk and sounddevice.
    Supports real-time partial transcription for instant interruption.
    """
    partial_speech = Signal(str)      # Emitted on partial speech detection (user started talking)
    speech_completed = Signal(str)    # Emitted when a full phrase is completed (the question)
    status = Signal(str)              # Status updates
    error = Signal(str)               # Error messages

    def __init__(self, model_path: str, sample_rate: int = 16000):
        super().__init__()
        self.model_path = model_path
        self.sample_rate = sample_rate
        self._running = True
        self._enabled = True
        self._audio_queue = queue.Queue()

    def set_enabled(self, enabled: bool):
        """Enable or disable voice processing (e.g., disable when agent is speaking to avoid feedback)."""
        self._enabled = enabled
        state = "enabled" if enabled else "disabled"
        logger.info(f"Continuous voice listening {state}")

    def is_enabled(self) -> bool:
        return self._enabled

    def stop(self):
        """Stop the thread loop."""
        self._running = False
        self.wait(1500)

    def run(self):
        logger.info("Initializing Vosk model for continuous listening...")
        self.status.emit("Loading voice model...")
        
        try:
            model = Model(self.model_path)
            recognizer = KaldiRecognizer(model, self.sample_rate)
        except Exception as e:
            self.error.emit(f"Failed to load Vosk model: {e}")
            logger.error(f"Vosk model init error: {e}")
            return

        self.status.emit("Continuous listening active.")
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio stream status check: {status}")
            if self._running:
                self._audio_queue.put(bytes(indata))

        try:
            # Open the audio stream
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=4000,
                dtype="int16",
                channels=1,
                callback=audio_callback,
            ):
                logger.info("Audio stream opened successfully.")
                
                last_partial = ""
                
                while self._running:
                    try:
                        data = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if not self._enabled:
                        # Clear old data from the recognizer during disabled states
                        recognizer.Reset()
                        last_partial = ""
                        continue

                    if recognizer.AcceptWaveform(data):
                        # Full utterance detected
                        res_str = recognizer.Result()
                        res = json.loads(res_str)
                        text = res.get("text", "").strip()
                        if text:
                            logger.info(f"Vosk completed speech: '{text}'")
                            self.speech_completed.emit(text)
                            last_partial = ""
                    else:
                        # Partial transcription in progress
                        part_str = recognizer.PartialResult()
                        part = json.loads(part_str)
                        partial_text = part.get("partial", "").strip()
                        
                        if partial_text and partial_text != last_partial:
                            logger.info(f"Vosk partial speech: '{partial_text}'")
                            self.partial_speech.emit(partial_text)
                            last_partial = partial_text

        except Exception as e:
            self.error.emit(f"Microphone error: {e}")
            logger.error(f"Continuous microphone stream error: {e}")
