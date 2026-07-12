import requests
import json
import logging
import re

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:latest"

SYSTEM_PROMPT = (
    "You are Aiko, a friendly, warm, and knowledgeable AI lab presenter at the Intelligence Lab. "
    "You explain concepts clearly using simple language and engaging analogies. "
    "You speak naturally like a real person — conversational, not robotic. "
    "Keep responses concise (2-3 sentences) by default, unless the user explicitly asks for a specific length, detail level, list, or word count in their question. "
    "When answering questions, acknowledge the question warmly first, then answer. "
    "Avoid literal translations of English idioms (e.g. do not translate 'Great question!' to 'ప్రశ్న తీవ్రంగా ఉంది!' in Telugu; instead use natural openers like 'మంచి ప్రశ్న!' in Telugu, 'बहुत अच्छा सवाल है!' in Hindi, or 'நல்ல கேள்வி!' in Tamil). "
    "Never write any meta-explanations, warnings, or parenthetical notes explaining your language choice or instructions (e.g. do NOT output notes like '(Note: ...)' or '(I am assuming...)'). Just output the direct, clean answer. "
    "Never say you are an AI language model or mention that you are reading from slides. "
    "Speak as if you know the content by heart."
)

STOPWORDS = {
    "what", "why", "when", "where", "which", "who", "how", "this", "that",
    "from", "with", "about", "into", "your", "agent", "presentation", "slide",
    "please", "tell", "explain", "give", "does", "have", "will", "shall", "can",
    "could", "would", "there", "their", "them", "then", "than", "and", "the",
    "are", "was", "were", "for", "you", "use", "using", "show", "demo",
}

def clean_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}

import os

class LLMBrain:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.conversation_history = []
        
        # Try loading variables from a local .env file securely if it exists
        if os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line and not clean_line.startswith("#") and "=" in clean_line:
                            k, v = clean_line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            os.environ[k] = v
            except Exception as e:
                logger.warning(f"Failed to read local .env file: {e}")

        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        
        if self.gemini_key:
            logger.info("Cloud LLM configured: Google Gemini API")
        elif self.openai_key:
            logger.info("Cloud LLM configured: OpenAI API (gpt-4o-mini)")
        else:
            logger.info("Local LLM configured: Ollama")

    def _call_ollama(self, prompt: str, system: str = None, temperature: float = 0.7) -> str:
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system or SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 500 # Prevent sentences from cutting off mid-way
                }
            }
            # 50-second timeout allows local CPU/GPU to finish inference successfully on M1/M2/M3 under heavy CPU load
            response = requests.post(OLLAMA_URL, json=payload, timeout=50.0)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.warning(f"Ollama returned status code {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return ""

    def _call_gemini(self, prompt: str, system: str = None) -> str:
        try:
            # Using v1beta endpoint and gemini-2.5-flash model
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
            full_prompt = f"{system or SYSTEM_PROMPT}\n\nUser: {prompt}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": full_prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1000 # Prevent thinking tokens from truncating the actual response
                }
            }
            response = requests.post(url, json=payload, timeout=8.0)
            if response.status_code == 200:
                result = response.json()
                try:
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception:
                    logger.warning(f"Error parsing Gemini response json: {result}")
                    return ""
            else:
                logger.warning(f"Gemini API returned status code {response.status_code}: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return ""

    def _call_openai(self, prompt: str, system: str = None) -> str:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system or SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500, # Prevent sentences from cutting off mid-way
                "temperature": 0.7
            }
            response = requests.post(url, headers=headers, json=payload, timeout=8.0)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"OpenAI API returned status code {response.status_code}: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return ""

    def _call_llm(self, prompt: str, system: str = None, temperature: float = 0.7) -> str:
        # 1. Google Gemini API (Free, Instant, Smart)
        if self.gemini_key:
            res = self._call_gemini(prompt, system)
            if res:
                return res
        
        # 2. OpenAI API (Instant, Smart)
        if self.openai_key:
            res = self._call_openai(prompt, system)
            if res:
                return res
                
        # 3. Fall back to Local Ollama
        return self._call_ollama(prompt, system, temperature)

    def is_available(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def generate_greeting(self, language: str = "English") -> str:
        # Return warm template greetings directly to make startup instant and responsive
        lang_lower = language.lower()
        if "hindi" in lang_lower:
            return "नमस्ते और इंटेलिजेंस लैब में आपका स्वागत है! मैं आपकी एआई प्रस्तोता ऐको हूँ। आप प्रस्तुति के लिए कौन सी भाषा पसंद करेंगे - अंग्रेजी, हिंदी, तेलुगु या तमिल?"
        elif "telugu" in lang_lower:
            return "నమస్కారం మరియు ఇంటెలిజెన్స్ ల్యాబ్‌కు స్వాగతం! నేను ఐకో, మీ ఏఐ ప్రెజెంటర్. మీరు ప్రెజెంటేషన్ కోసం ఏ భాషను ఇష్టపడతారు - ఇంగ్లీష్, హిందీ, తెలుగు లేదా తమిళ్?"
        elif "tamil" in lang_lower:
            return "வணக்கம் மற்றும் இன்டெலிஜென்ஸ் லேபிற்கு உங்களை வரவேற்கிறேன்! நான் ஐகோ, உங்கள் ஏஐ பிரசெண்டர். பிரசென்டேஷனுக்கு எந்த மொழியை விரும்புகிறீர்கள் - ஆங்கிலம், இந்தி, தெலுங்கு அல்லது தமிழ்?"
        else:
            return "Hello and welcome to the Intelligence Lab! I am Aiko, your AI presenter. Which language would you prefer for the presentation — English, Hindi, Telugu, or Tamil?"

    def _keyless_translate(self, text: str, target_lang: str) -> str:
        if not text or not text.strip():
            return text
        try:
            import urllib.request
            import urllib.parse
            import json
            
            lang_map = {
                'english': 'en',
                'hindi': 'hi',
                'telugu': 'te',
                'tamil': 'ta',
                'kannada': 'kn',
                'malayalam': 'ml',
            }
            lang_code = lang_map.get(target_lang.lower(), 'en')
            if lang_code == 'en':
                return text
                
            q = urllib.parse.quote(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={q}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                translated_parts = []
                for part in data[0]:
                    if part[0]:
                        translated_parts.append(part[0])
                return "".join(translated_parts)
        except Exception as e:
            logger.warning(f"Keyless translation failed: {e}")
            return ""

    def translate_slide(self, slide_title: str, slide_text: str, target_lang: str) -> tuple[str, str]:
        # If target language is English, return as-is
        if target_lang.lower() == "english":
            return slide_title, slide_text

        # Check pre-translated values for default slides
        try:
            from default_translations import get_default_translation
            result = get_default_translation(slide_title, slide_text, target_lang)
            if result:
                return result[0], result[1]
        except Exception as e:
            logger.warning(f"Error loading default translation: {e}")

        # Try keyless Google Translate API first as a robust, instant translator for dynamic decks
        trans_title = self._keyless_translate(slide_title, target_lang)
        trans_text = self._keyless_translate(slide_text, target_lang)
        if trans_title or trans_text:
            return trans_title or slide_title, trans_text or slide_text

        # Fallback to LLM translation
        if self.gemini_key or self.openai_key or self.is_available():
            prompt_title = (
                f"Translate this PowerPoint slide title into {target_lang}. "
                f"Return ONLY the translated text. Do not write any conversational preamble.\n\n"
                f"Title: {slide_title}"
            )
            trans_title = self._call_llm(prompt_title, temperature=0.1)
            
            prompt_text = (
                f"Translate this PowerPoint slide content into {target_lang}. "
                f"Return ONLY the translated text. Do not write any conversational preamble.\n\n"
                f"Content: {slide_text}"
            )
            trans_text = self._call_llm(prompt_text, temperature=0.1)
            
            if trans_title and trans_text:
                return trans_title, trans_text

        return slide_title, slide_text

    def explain_slide(self, slide_title: str, slide_text: str, slide_number: int, total_slides: int, language: str = "English") -> str:
        # Get translated slide content first (both for fallback display and explanation)
        _, trans_text = self.translate_slide(slide_title, slide_text, language)
        return trans_text

    def _keyword_fallback(self, question: str, current_slide_text: str, language: str = "English") -> str:
        # Simple rule-based/keyword answers
        q_clean = question.lower()
        
        # Standard Qs
        if any(x in q_clean for x in ["who are you", "your name", "introduce"]):
            if "hindi" in language.lower():
                return "मैं ऐको हूँ, आपकी इंटेलिजेंस लैब डेमो प्रस्तोता। मैं पीपीटी प्रस्तुत कर सकती हूँ और आपके सवालों के जवाब दे सकती हूँ।"
            elif "telugu" in language.lower():
                return "నేను ఐకో, మీ ఇంటెలిజెన్స్ ల్యాబ్ డెమో ప్రెజెంటర్. నేను పిపిటి ప్రెజెంట్ చేయగలను మరియు మీ ప్రశ్నలకు సమాధానం ఇవ్వగలను."
            elif "tamil" in language.lower():
                return "நான் ஐகோ, உங்கள் இன்டெலிஜென்ஸ் லேப் டெமோ பிரசெண்டர். நான் விளக்கக்காட்சியை வழங்க முடியும் மற்றும் உங்கள் கேள்விகளுக்கு பதிலளிக்க முடியும்."
            else:
                return "I am Aiko, your Intelligence Lab demo presenter. I present slides and answer questions from them."
                
        if any(x in q_clean for x in ["hello", "hi", "hey"]):
            if "hindi" in language.lower():
                return "नमस्ते! मैं आपकी किस प्रकार सहायता कर सकती हूँ?"
            elif "telugu" in language.lower():
                return "హలో! నేను మీకు ఎలా సహాయపడగలను?"
            elif "tamil" in language.lower():
                return "வணக்கம்! நான் உங்களுக்கு எவ்வாறு உதவ முடியும்?"
            else:
                return "Hello! How can I help you today?"

        # Match against slide context
        q_words = clean_words(question)
        if q_words and current_slide_text:
            slide_words = clean_words(current_slide_text)
            if len(q_words.intersection(slide_words)) > 0:
                text = current_slide_text.replace("\n", ". ")
                if len(text) > 400:
                    text = text[:400] + "..."
                if "hindi" in language.lower():
                    return f"इस स्लाइड के अनुसार: {text}"
                elif "telugu" in language.lower():
                    return f"ఈ స్లైడ్ ప్రకారం: {text}"
                elif "tamil" in language.lower():
                    return f"விளக்கக்காட்சியின் படி: {text}"
                else:
                    return f"Based on this slide, here is what I found: {text}"
        
        if "hindi" in language.lower():
            return "मुझे इसके बारे में अधिक जानकारी नहीं है। कृपया प्रस्तुति से संबंधित प्रश्न पूछें।"
        elif "telugu" in language.lower():
            return "నాకు దీని గురించి సమాచారం లేదు. దయచేసి ప్రెజెంటేషన్ సంబంధిత ప్రశ్నలను అడగండి."
        elif "tamil" in language.lower():
            return "எனக்கு இதைப் பற்றி மேலும் தகவல் இல்லை. விளக்கக்காட்சி தொடர்பான கேள்விகளைக் கேளுங்கள்."
        else:
            return "I couldn't find a direct answer to that in the current presentation slide. Could you please rephrase or ask about the slides?"

    def answer_question(self, question: str, current_slide_text: str, conversation_history: list, language: str = "English", all_slides: list = None) -> str:
        # Translate the context slide text to the chosen language first
        _, trans_text = self.translate_slide("", current_slide_text, language)

        if self.gemini_key or self.openai_key or self.is_available():
            history_context = ""
            for msg in conversation_history[-2:]:
                history_context += f"{msg.get('role', 'User')}: {msg.get('message', '')}\n"
                
            slides_context = ""
            if all_slides:
                slides_context = "Here is the outline and content of the entire presentation:\n"
                for i, slide in enumerate(all_slides):
                    slides_context += f"Slide {i+1}: {slide.get('title', 'Slide')}\nContent: {slide.get('text', '')}\n\n"
                
            prompt = (
                f"{slides_context}"
                f"Currently active slide content:\n{trans_text}\n\n"
                f"History:\n{history_context}\n"
                f"Question: {question}\n\n"
                f"Task: Answer the Question warmly. If the user explicitly asks in their Question for a specific response length, detail level, list format, or word count (e.g. 'summarize the whole ppt in 100 words'), you MUST satisfy their length and format request precisely using the entire presentation content. Otherwise, by default, answer concisely in 2-3 sentences. "
                f"Respond in {language}, UNLESS the user explicitly asks you in the Question to reply in a different language (in which case, reply in their requested language). "
                f"If the question is about the presentation slides, use the Context. "
                f"If it is a general question, answer it directly using your general knowledge."
            )
            response = self._call_llm(prompt, temperature=0.7)
            if response:
                return response
                
        return self.answer_user_question_fallback(question, trans_text, language)

    def answer_user_question_fallback(self, question: str, current_slide_text: str, language: str = "English") -> str:
        return self._keyword_fallback(question, current_slide_text, language)

    def generate_resume_transition(self, last_slide_title: str, language: str = "English") -> str:
        # Get translated slide title
        trans_title, _ = self.translate_slide(last_slide_title, "", language)

        lang_lower = language.lower()
        if "hindi" in lang_lower:
            return f"आइए अब वापस '{trans_title}' पर चलते हैं।"
        elif "telugu" in lang_lower:
            return f"సరే, ఇప్పుడు తిరిగి '{trans_title}' కు వెళ్దాం."
        elif "tamil" in lang_lower:
            return f"சரி, இப்போது மீண்டும் '{trans_title}' பக்கத்திற்குச் செல்வோம்."
        else:
            return f"Now, let me continue with {trans_title}."

    def generate_farewell(self, language: str = "English") -> str:
        lang_lower = language.lower()
        if "hindi" in lang_lower:
            return "इंटेलिजेंस लैब में आने के लिए धन्यवाद! आपसे मिलकर बहुत अच्छा लगा। आपका दिन शुभ हो!"
        elif "telugu" in lang_lower:
            return "ఇంటెలిజెన్స్ ల్యాబ్‌ను సందర్శించినందుకు ధన్యవాదాలు! మిమ్మల్ని కలవడం చాలా సంతోషంగా ఉంది. మంచి రోజు!"
        elif "tamil" in lang_lower:
            return "இன்டெலிஜென்ஸ் லேபிற்கு வருகை தந்ததற்கு நன்றி! உங்களை சந்தித்ததில் மகிழ்ச்சி. நல்ல நாளாக அமையட்டும்!"
        else:
            return "Thank you for visiting the Intelligence Lab! It was a pleasure presenting to you. Have a wonderful day!"

    def add_to_history(self, role: str, message: str):
        self.conversation_history.append({"role": role, "message": message})
        if len(self.conversation_history) > 20:
            self.conversation_history.pop(0)

    def clear_history(self):
        self.conversation_history.clear()
