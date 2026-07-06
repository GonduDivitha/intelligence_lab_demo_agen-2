import sys
import logging
from PySide6.QtWidgets import QApplication

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RuntimeVerifier")

def verify_all():
    logger.info("Starting runtime verification check...")
    
    # 1. Initialize PySide QApplication (required for QWidget and QThread instantiation)
    app = QApplication(sys.argv)
    logger.info("✅ QApplication initialized successfully.")

    # 2. Test LLMBrain instantiation
    try:
        from llm_brain import LLMBrain
        brain = LLMBrain()
        logger.info("✅ LLMBrain instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate LLMBrain: {e}")
        return False

    # 3. Test LanguageManager instantiation
    try:
        from language_manager import LanguageManager
        lm = LanguageManager()
        logger.info("✅ LanguageManager instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate LanguageManager: {e}")
        return False

    # 4. Test TTSEngine instantiation
    try:
        from tts_engine import TTSEngine
        tts = TTSEngine()
        logger.info("✅ TTSEngine instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate TTSEngine: {e}")
        return False

    # 5. Test InterruptHandler instantiation
    try:
        from interrupt_handler import InterruptHandler
        ih = InterruptHandler(tts)
        logger.info("✅ InterruptHandler instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate InterruptHandler: {e}")
        return False

    # 6. Test EnhancedAvatar instantiation
    try:
        from enhanced_avatar import EnhancedAvatar
        avatar = EnhancedAvatar()
        logger.info("✅ EnhancedAvatar instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate EnhancedAvatar: {e}")
        return False

    # 7. Test ContinuousVoiceListener instantiation
    try:
        from voice_listener import ContinuousVoiceListener
        from app import VOSK_MODEL_PATH
        listener = ContinuousVoiceListener(str(VOSK_MODEL_PATH))
        logger.info("✅ ContinuousVoiceListener instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate ContinuousVoiceListener: {e}")
        return False

    # 8. Test ConversationEngine instantiation
    try:
        from conversation_engine import ConversationEngine
        from app import PPTManager, PPT_PATH
        ppt = PPTManager(PPT_PATH)
        engine = ConversationEngine(brain, tts, ppt, ih, lm)
        logger.info("✅ ConversationEngine instantiated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to import or instantiate ConversationEngine: {e}")
        return False

    logger.info("🎉 All runtime module instantiations and dependencies are 100% correct!")
    return True

if __name__ == "__main__":
    success = verify_all()
    sys.exit(0 if success else 1)
