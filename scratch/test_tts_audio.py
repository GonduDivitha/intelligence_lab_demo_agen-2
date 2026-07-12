import sys
import time
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from tts_engine import TTSEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TTSTest")

def test_tts():
    app = QApplication(sys.argv)
    
    logger.info("Initializing TTSEngine...")
    tts = TTSEngine()
    
    # Connect signals to verify they are emitted
    started_emitted = False
    finished_emitted = False
    state_changes = []
    
    tts.speech_started.connect(lambda token: logger.info(f"Signal: speech_started for token {token}"))
    tts.speech_finished.connect(lambda token: logger.info(f"Signal: speech_finished for token {token}"))
    tts.speaking_state_changed.connect(lambda is_speaking: state_changes.append((time.time(), is_speaking)))
    tts.status.connect(lambda msg: logger.info(f"Status update: {msg}"))
    
    tts.start()
    
    # Wait for initialization status
    time.sleep(1.0)
    
    logger.info("Sending speak command...")
    tts.speak("Hello, this is a test of the neural text to speech engine.", "test_token", "english")
    
    # Let the event loop run for 8 seconds to play audio
    start_wait = time.time()
    while time.time() - start_wait < 8.0:
        QApplication.processEvents()
        time.sleep(0.05)
        
    logger.info(f"Speaking state changes recorded: {state_changes}")
    
    tts.stop()
    app.quit()

if __name__ == "__main__":
    test_tts()
