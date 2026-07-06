"""
Language Manager — Handles language selection, voice mapping, and UI text localization.
Provides language configuration for the entire agent: TTS voice selection,
UI text translations, and LLM prompt language instructions.
"""
import logging
logger = logging.getLogger(__name__)
class LanguageConfig:
    """Configuration for a single supported language."""
    def __init__(self, code: str, name: str, native_name: str, tts_voice: str,
                 greeting: str, flag_emoji: str):
        self.code = code
        self.name = name
        self.native_name = native_name
        self.tts_voice = tts_voice
        self.greeting = greeting
        self.flag_emoji = flag_emoji
# ─── Supported Languages ───────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "english": LanguageConfig(
        code="english",
        name="English",
        native_name="English",
        tts_voice="en-US-AriaNeural",
        greeting="Hello! Welcome to the Intelligence Lab!",
        flag_emoji="🇺🇸",
    ),
    "hindi": LanguageConfig(
        code="hindi",
        name="Hindi",
        native_name="हिन्दी",
        tts_voice="hi-IN-SwaraNeural",
        greeting="नमस्ते! इंटेलिजेंस लैब में आपका स्वागत है!",
        flag_emoji="🇮🇳",
    ),
    "telugu": LanguageConfig(
        code="telugu",
        name="Telugu",
        native_name="తెలుగు",
        tts_voice="te-IN-ShrutiNeural",
        greeting="నమస్కారం! ఇంటెలిజెన్స్ ల్యాబ్‌కు స్వాగతం!",
        flag_emoji="🇮🇳",
    ),
    "tamil": LanguageConfig(
        code="tamil",
        name="Tamil",
        native_name="தமிழ்",
        tts_voice="ta-IN-PallaviNeural",
        greeting="வணக்கம்! இன்டெலிஜென்ஸ் லேபிற்கு வரவேற்கிறோம்!",
        flag_emoji="🇮🇳",
    ),
}
# ─── UI Text Localization ───────────────────────────────────────────────────────
UI_TEXTS = {
    "english": {
        "ask_language": "Which language would you prefer for the presentation?",
        "language_confirmed": "Great! I'll present in English for you.",
        "ready_questions": "I'm ready for your questions!",
        "presentation_complete": "That completes the presentation.",
        "farewell": "Thank you for visiting! Have a wonderful day!",
        "listening": "I'm listening...",
        "thinking": "Let me think about that...",
        "resuming": "Now, let me continue where I left off...",
        "send_placeholder": "Type a question and press Enter...",
        "start_btn": "🚀 Start Agent Now",
        "repeat_btn": "🔁 Repeat Slide",
        "next_btn": "➡ Next Slide",
        "restart_btn": "▶ Restart",
        "mic_btn": "🎙 Ask by Voice",
        "send_btn": "Send",
    },
    "hindi": {
        "ask_language": "प्रस्तुति के लिए आप कौन सी भाषा पसंद करेंगे?",
        "language_confirmed": "बढ़िया! मैं आपके लिए हिंदी में प्रस्तुत करूँगी।",
        "ready_questions": "मैं आपके सवालों के लिए तैयार हूँ!",
        "presentation_complete": "प्रस्तुति पूरी हुई।",
        "farewell": "आने के लिए धन्यवाद! आपका दिन शुभ हो!",
        "listening": "मैं सुन रही हूँ...",
        "thinking": "मुझे इसके बारे में सोचने दीजिए...",
        "resuming": "अब, मैं जहाँ रुकी थी वहाँ से जारी रखती हूँ...",
        "send_placeholder": "अपना सवाल टाइप करें और Enter दबाएं...",
        "start_btn": "🚀 एजेंट शुरू करें",
        "repeat_btn": "🔁 स्लाइड दोहराएं",
        "next_btn": "➡ अगली स्लाइड",
        "restart_btn": "▶ पुनः आरंभ",
        "mic_btn": "🎙 आवाज़ से पूछें",
        "send_btn": "भेजें",
    },
    "telugu": {
        "ask_language": "ప్రెజెంటేషన్ కోసం మీరు ఏ భాషను ఇష్టపడతారు?",
        "language_confirmed": "బాగుంది! నేను మీ కోసం తెలుగులో ప్రెజెంట్ చేస్తాను.",
        "ready_questions": "నేను మీ ప్రశ్నలకు సిద్ధంగా ఉన్నాను!",
        "presentation_complete": "ప్రెజెంటేషన్ పూర్తయింది.",
        "farewell": "వచ్చినందుకు ధన్యవాదాలు! మీ రోజు శుభంగా ఉండాలి!",
        "listening": "నేను వింటున్నాను...",
        "thinking": "నన్ను ఆలోచించనివ్వండి...",
        "resuming": "ఇప్పుడు నేను ఆగిన చోటు నుండి కొనసాగిస్తాను...",
        "send_placeholder": "మీ ప్రశ్నను టైప్ చేసి Enter నొక్కండి...",
        "start_btn": "🚀 ఏజెంట్ ప్రారంభించు",
        "repeat_btn": "🔁 స్లైడ్ రిపీట్",
        "next_btn": "➡ తదుపరి స్లైడ్",
        "restart_btn": "▶ మళ్ళీ ప్రారంభించు",
        "mic_btn": "🎙 వాయిస్ ద్వారా అడగండి",
        "send_btn": "పంపు",
    },
    "tamil": {
        "ask_language": "விளக்கத்திற்கு எந்த மொழியை விரும்புவீர்கள்?",
        "language_confirmed": "நல்லது! நான் உங்களுக்காக தமிழில் வழங்குகிறேன்.",
        "ready_questions": "நான் உங்கள் கேள்விகளுக்கு தயார்!",
        "presentation_complete": "விளக்கம் முடிந்தது.",
        "farewell": "வருகைக்கு நன்றி! உங்கள் நாள் நன்றாக இருக்கட்டும்!",
        "listening": "நான் கேட்கிறேன்...",
        "thinking": "யோசிக்க விடுங்கள்...",
        "resuming": "இப்போது நான் நிறுத்திய இடத்திலிருந்து தொடர்கிறேன்...",
        "send_placeholder": "உங்கள் கேள்வியை டைப் செய்து Enter அழுத்தவும்...",
        "start_btn": "🚀 ஏஜெண்ட் தொடங்கு",
        "repeat_btn": "🔁 ஸ்லைடு மீண்டும்",
        "next_btn": "➡ அடுத்த ஸ்லைடு",
        "restart_btn": "▶ மீண்டும் தொடங்கு",
        "mic_btn": "🎙 குரலில் கேளுங்கள்",
        "send_btn": "அனுப்பு",
    },
}
class LanguageManager:
    """
    Manages language selection, TTS voice mapping, and UI text localization.
    
    Usage:
        lm = LanguageManager()
        lm.set_language('hindi')
        voice = lm.get_tts_voice()       # 'hi-IN-SwaraNeural'
        text = lm.get_ui_text('farewell') # Hindi farewell string
    """
    def __init__(self, default_language: str = "english"):
        self._current = default_language.lower()
        if self._current not in SUPPORTED_LANGUAGES:
            logger.warning(f"Language '{self._current}' not supported, defaulting to English")
            self._current = "english"
    # ─── Language Selection ──────────────────────────────────────────────────
    def set_language(self, language: str):
        """Set the current language. Accepts name like 'Hindi', 'telugu', etc."""
        lang = language.strip().lower()
        if lang in SUPPORTED_LANGUAGES:
            self._current = lang
            logger.info(f"Language set to: {lang}")
        else:
            logger.warning(f"Unsupported language '{language}', keeping {self._current}")
    def get_language(self) -> str:
        """Return current language code (lowercase)."""
        return self._current
    def get_language_name(self) -> str:
        """Return the display name of the current language."""
        return SUPPORTED_LANGUAGES[self._current].name
    def get_native_name(self) -> str:
        """Return the native script name of the current language."""
        return SUPPORTED_LANGUAGES[self._current].native_name
    # ─── TTS Voice ───────────────────────────────────────────────────────────
    def get_tts_voice(self, language: str = None) -> str:
        """Get the edge-tts voice name for the given or current language."""
        lang = (language or self._current).strip().lower()
        config = SUPPORTED_LANGUAGES.get(lang)
        if config:
            return config.tts_voice
        return SUPPORTED_LANGUAGES["english"].tts_voice
    # ─── UI Text ─────────────────────────────────────────────────────────────
    def get_ui_text(self, key: str, language: str = None) -> str:
        """
        Get localized UI text for the given key.
        Falls back to English if the key or language is not found.
        """
        lang = (language or self._current).strip().lower()
        texts = UI_TEXTS.get(lang, UI_TEXTS["english"])
        return texts.get(key, UI_TEXTS["english"].get(key, key))
    # ─── Language Info ───────────────────────────────────────────────────────
    def get_supported_languages(self) -> list[dict]:
        """
        Return list of supported languages with their display info.
        Each dict has: code, name, native_name, flag_emoji
        """
        result = []
        for code, config in SUPPORTED_LANGUAGES.items():
            result.append({
                "code": config.code,
                "name": config.name,
                "native_name": config.native_name,
                "flag_emoji": config.flag_emoji,
            })
        return result
    def get_language_button_labels(self) -> list[tuple[str, str]]:
        """
        Return list of (code, display_label) tuples for language selection buttons.
        Display label format: '🇮🇳 Hindi (हिन्दी)'
        """
        labels = []
        for code, config in SUPPORTED_LANGUAGES.items():
            if config.name == config.native_name:
                label = f"{config.flag_emoji} {config.name}"
            else:
                label = f"{config.flag_emoji} {config.name} ({config.native_name})"
            labels.append((code, label))
        return labels
    def get_greeting(self, language: str = None) -> str:
        """Get the default greeting in the given or current language."""
        lang = (language or self._current).strip().lower()
        config = SUPPORTED_LANGUAGES.get(lang)
        if config:
            return config.greeting
        return SUPPORTED_LANGUAGES["english"].greeting
    # ─── Language Detection (Simple Heuristic) ───────────────────────────────
    @staticmethod
    def detect_language_from_text(text: str) -> str | None:
        """
        Attempt basic language detection from user input text.
        Uses simple keyword matching. Returns language code or None.
        """
        text_lower = text.strip().lower()
        # Check for explicit language mentions
        lang_keywords = {
            "english": ["english", "eng"],
            "hindi": ["hindi", "हिंदी", "हिन्दी"],
            "telugu": ["telugu", "తెలుగు"],
            "tamil": ["tamil", "தமிழ்"],
            "kannada": ["kannada", "ಕನ್ನಡ"],
            "malayalam": ["malayalam", "മലയാളം"],
        }
        for lang_code, keywords in lang_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return lang_code
        return None
