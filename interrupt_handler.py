import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class InterruptHandler(QObject):
    interrupt_detected = Signal(str)
    resume_requested = Signal()

    def __init__(self, tts_engine, parent=None):
        super().__init__(parent)
        self.tts_engine = tts_engine
        self._saved_state = None
        self._is_interrupted = False
        self._pending_resume = False

    def interrupt(self, question: str, current_slide_index: int, slide_title: str, was_auto_presenting: bool):
        logger.info(f"Interrupting presentation for question: {question}")
        self._is_interrupted = True
        self._saved_state = {
            "question": question,
            "slide_index": current_slide_index,
            "slide_title": slide_title,
            "was_auto_presenting": was_auto_presenting
        }
        # Stop speech immediately
        self.tts_engine.stop_speaking()
        self.interrupt_detected.emit(question)

    def request_resume(self):
        logger.info("Resume requested")
        self._pending_resume = True
        self._is_interrupted = False
        self.resume_requested.emit()

    def get_saved_state(self) -> dict | None:
        return self._saved_state

    def clear_state(self):
        self._saved_state = None
        self._is_interrupted = False
        self._pending_resume = False

    def is_interrupted(self) -> bool:
        return self._is_interrupted

    def has_pending_resume(self) -> bool:
        return self._pending_resume

    def consume_resume(self) -> dict | None:
        self._pending_resume = False
        state = self._saved_state
        return state
