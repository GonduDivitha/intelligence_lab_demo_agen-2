import logging
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from language_manager import LanguageManager

logger = logging.getLogger(__name__)

class LLMQueryThread(QThread):
    completed = Signal(str, str)  # (result_text, token)

    def __init__(self, func, args=(), kwargs=None, token=""):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.token = token

    def run(self):
        try:
            res = self.func(*self.args, **self.kwargs)
            self.completed.emit(res, self.token)
        except Exception as e:
            logger.error(f"Error in LLM background query thread: {e}")
            self.completed.emit("", self.token)

class ConversationEngine(QObject):
    state_changed = Signal(str)  # Emits current state name
    text_to_speak = Signal(str, str, str)  # (text, token, language)
    chat_message = Signal(str, str)  # (sender, message)
    slide_navigation = Signal(int)  # Emits slide index to show
    ui_status_update = Signal(str)  # Status bar text

    def __init__(self, llm_brain, tts_engine, ppt_manager, interrupt_handler, language_manager, parent=None):
        super().__init__(parent)
        self.llm = llm_brain
        self.tts = tts_engine
        self.ppt = ppt_manager
        self.interrupt_handler = interrupt_handler
        self.lm = language_manager
        
        self.state = "IDLE"
        self.current_slide = 0
        self.auto_presenting = False
        
        self._llm_thread = None
        self._pending_question = ""
        
        # Connect TTS signals to coordinate flow
        self.tts.speech_finished.connect(self.on_speech_finished)
        self.tts.speech_interrupted.connect(self.on_speech_interrupted)
        
        # Connect Interrupt handler resume request
        self.interrupt_handler.resume_requested.connect(self.resume_presentation)

    def set_state(self, new_state: str):
        if new_state == self.state:
            return
        logger.info(f"State transition: {self.state} -> {new_state}")
        self.state = new_state
        self.state_changed.emit(new_state)

    def start_llm_query(self, func, args=(), kwargs=None, token=""):
        # Stop any currently running query to avoid duplicate actions
        if self._llm_thread and self._llm_thread.isRunning():
            self._llm_thread.terminate()
            self._llm_thread.wait()
            
        self._llm_thread = LLMQueryThread(func, args, kwargs, token)
        self._llm_thread.completed.connect(self._on_llm_query_completed)
        self._llm_thread.start()

    def _on_llm_query_completed(self, response: str, token: str):
        lang = self.lm.get_language()
        
        if token == "greeting":
            self.chat_message.emit("Aiko", response)
            self.text_to_speak.emit(response, "greeting", lang)
            
        elif token.startswith("slide:"):
            slide_idx = int(token.split(":")[1])
            self.set_state("PRESENTING")
            self.text_to_speak.emit(response, f"slide:{slide_idx}", lang)
            
        elif token == "answer":
            self.llm.add_to_history("user", self._pending_question)
            self.llm.add_to_history("agent", response)
            self.set_state("ANSWERING")
            self.chat_message.emit("Aiko", response)
            self.text_to_speak.emit(response, "answer", lang)
            self._pending_question = ""
            
        elif token == "resume_transition":
            self.set_state("RESUMING")
            self.chat_message.emit("Aiko", response)
            self.text_to_speak.emit(response, "resume_transition", lang)
            
        elif token == "farewell":
            self.chat_message.emit("Aiko", response)
            self.text_to_speak.emit(response, "farewell", lang)

    def start_interaction(self):
        """Triggered when a face/person is detected, or manually started."""
        if self.state != "IDLE":
            return
            
        self.set_state("GREETING")
        self.ui_status_update.emit("Visitor detected. Initializing greeting...")
        self.chat_message.emit("System", "Visitor detected. Starting interaction.")
        
        lang = self.lm.get_language()
        # Start background LLM thread for greeting
        self.start_llm_query(self.llm.generate_greeting, (lang,), token="greeting")

    def choose_language(self, language_code: str):
        """Set language and advance state from LANGUAGE_SELECT to PRESENTING."""
        if self.state not in ["GREETING", "LANGUAGE_SELECT"]:
            # If already presenting/in Q&A, we can change language but don't reset state
            self.lm.set_language(language_code)
            self.tts.set_language(language_code)
            confirm_msg = self.lm.get_ui_text("language_confirmed")
            self.chat_message.emit("Aiko", confirm_msg)
            self.text_to_speak.emit(confirm_msg, "language_confirm", language_code)
            return

        self.lm.set_language(language_code)
        self.tts.set_language(language_code)
        self.set_state("LANGUAGE_SELECT")
        
        confirm_msg = self.lm.get_ui_text("language_confirmed")
        self.chat_message.emit("Aiko", confirm_msg)
        self.text_to_speak.emit(confirm_msg, "language_confirm", language_code)

    def start_presentation(self):
        """Begins presenting the PPT slides."""
        self.interrupt_handler.clear_state()
        self.current_slide = 0
        self.auto_presenting = True
        self.slide_navigation.emit(0)
        self.set_state("PRESENTING")
        
        # Explain the first slide after a short delay to let greeting finish
        QTimer.singleShot(500, self.explain_current_slide)

    def explain_current_slide(self):
        if not self.ppt.slides:
            return
            
        if self.current_slide >= len(self.ppt.slides):
            self.complete_presentation()
            return

        slide = self.ppt.slides[self.current_slide]
        lang = self.lm.get_language()
        
        self.ui_status_update.emit(f"Generating explanation for slide {slide['number']}...")
        self.set_state("THINKING")
        
        # Start background LLM thread for explanation
        self.start_llm_query(
            self.llm.explain_slide, 
            (slide["title"], slide["text"], slide["number"], len(self.ppt.slides), lang),
            token=f"slide:{self.current_slide}"
        )

    def handle_partial_speech(self, partial_text: str):
        """Triggered as soon as the user starts speaking, to cut off the presenter instantly."""
        if self.state == "PRESENTING":
            logger.info(f"Voice cut-off triggered by partial speech: '{partial_text}'")
            self.set_state("INTERRUPTED")
            # Stop the voice immediately (triggers speech_interrupted)
            self.tts.stop_speaking()

    def handle_voice_question(self, question: str):
        """Triggered when the user finishes speaking a full question."""
        if not question.strip():
            return
            
        logger.info(f"Voice question completed: '{question}'")
        lang = self.lm.get_language()
        
        if self.state == "INTERRUPTED":
            # Save state so we can resume presenting later
            self.interrupt_handler.interrupt(
                question=question,
                current_slide_index=self.current_slide,
                slide_title=self.ppt.slides[self.current_slide]["title"] if self.ppt.slides else "Slide",
                was_auto_presenting=self.auto_presenting
            )
            
            # Transition to answering state
            self.set_state("THINKING")
            self.ui_status_update.emit("Generating answer...")
            
            current_slide_txt = ""
            if self.ppt.slides and 0 <= self.current_slide < len(self.ppt.slides):
                current_slide_txt = self.ppt.slides[self.current_slide]["text"]
                
            self._pending_question = question
            self.start_llm_query(
                self.llm.answer_question,
                (question, current_slide_txt, self.llm.conversation_history.copy(), lang, self.ppt.slides),
                token="answer"
            )
        else:
            # Not in presentation, standard Q&A
            self.handle_question(question)

    def handle_question(self, question: str):
        """Processes a typed question. Interrupts if presenting."""
        if not question.strip():
            return

        lang = self.lm.get_language()
        
        if self.state == "PRESENTING":
            self.set_state("INTERRUPTED")
            self.interrupt_handler.interrupt(
                question=question,
                current_slide_index=self.current_slide,
                slide_title=self.ppt.slides[self.current_slide]["title"] if self.ppt.slides else "Slide",
                was_auto_presenting=self.auto_presenting
            )
            
            # Answer immediately
            self.set_state("THINKING")
            self.ui_status_update.emit("Generating answer...")
            
            current_slide_txt = ""
            if self.ppt.slides and 0 <= self.current_slide < len(self.ppt.slides):
                current_slide_txt = self.ppt.slides[self.current_slide]["text"]
                
            self._pending_question = question
            self.start_llm_query(
                self.llm.answer_question,
                (question, current_slide_txt, self.llm.conversation_history.copy(), lang, self.ppt.slides),
                token="answer"
            )
            return

        # Regular answer flow (GREETING, QA_SESSION, idle, etc.)
        self.set_state("THINKING")
        self.ui_status_update.emit("Generating answer...")
        
        current_slide_txt = ""
        if self.ppt.slides and 0 <= self.current_slide < len(self.ppt.slides):
            current_slide_txt = self.ppt.slides[self.current_slide]["text"]
            
        self._pending_question = question
        self.start_llm_query(
            self.llm.answer_question,
            (question, current_slide_txt, self.llm.conversation_history.copy(), lang, self.ppt.slides),
            token="answer"
        )

    def resume_presentation(self):
        """Called by interrupt_handler to resume explanation after question."""
        if not self.interrupt_handler.has_pending_resume():
            return
            
        saved_state = self.interrupt_handler.consume_resume()
        if not saved_state:
            self.set_state("PRESENTING")
            return
            
        self.set_state("THINKING")
        self.current_slide = saved_state["slide_index"]
        self.auto_presenting = saved_state["was_auto_presenting"]
        self.slide_navigation.emit(self.current_slide)
        
        lang = self.lm.get_language()
        self.start_llm_query(
            self.llm.generate_resume_transition,
            (saved_state["slide_title"], lang),
            token="resume_transition"
        )

    def complete_presentation(self):
        self.auto_presenting = False
        self.set_state("COMPLETED")
        
        lang = self.lm.get_language()
        msg = self.lm.get_ui_text("presentation_complete") + " " + self.lm.get_ui_text("ready_questions")
        
        self.chat_message.emit("Aiko", msg)
        self.text_to_speak.emit(msg, "completed", lang)

    def handle_visitor_leaving(self):
        """Triggered when OpenCV detects no face/person for a sustained period."""
        if self.state == "IDLE":
            return
            
        self.set_state("THINKING")
        self.ui_status_update.emit("Visitor left. Saying goodbye...")
        
        lang = self.lm.get_language()
        self.start_llm_query(
            self.llm.generate_farewell,
            (lang,),
            token="farewell"
        )

    def on_speech_finished(self, token: str):
        """Coordinate state progress based on completed spoken segments."""
        logger.info(f"Speech finished for token: {token}")
        
        if token == "greeting":
            self.set_state("LANGUAGE_SELECT")
            return
            
        if token == "language_confirm":
            self.start_presentation()
            return
            
        if token.startswith("slide:") and self.state == "PRESENTING":
            if self.auto_presenting:
                # Advance slide after brief pause (1.5 seconds)
                QTimer.singleShot(1500, self.next_slide_auto)
            return
            
        if token == "resume_transition":
            # Resumed, now explain the slide content
            self.set_state("PRESENTING")
            self.explain_current_slide()
            return
            
        if token == "answer":
            # Transition to Q&A session and stay there, letting the user ask follow-up questions.
            # The presentation remains paused until the user explicitly resumes or moves slide.
            self.set_state("QA_SESSION")
            return
            
        if token == "completed":
            self.set_state("QA_SESSION")
            return
            
        if token == "farewell":
            # Interaction ends, reset engine
            self.reset_engine()

    def on_speech_interrupted(self, token: str):
        """If speech was interrupted, handle the transition state."""
        logger.info(f"Speech interrupted for token: {token}")

    def next_slide_auto(self):
        if self.state != "PRESENTING":
            return
        if self.current_slide < len(self.ppt.slides) - 1:
            self.current_slide += 1
            self.slide_navigation.emit(self.current_slide)
            self.explain_current_slide()
        else:
            self.complete_presentation()

    def reset_engine(self):
        self.state = "IDLE"
        self.current_slide = 0
        self.auto_presenting = False
        self.interrupt_handler.clear_state()
        self.llm.clear_history()
        self.set_state("IDLE")
        self.ui_status_update.emit("Ready. Waiting for visitor...")
