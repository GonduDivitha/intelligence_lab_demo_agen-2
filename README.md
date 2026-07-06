# Intelligence Lab Demo Agent - Interactive AI Presenter (Aiko) 🤖📊

An industry-grade, human-like AI presentation kiosk application. Featuring **Aiko**, an interactive anime presenter capable of continuous voice Q&A in multiple languages, gesture controls, and real-time face tracking.

---

## 🌟 Key Features

1. **Human-like Animated Presenter (Aiko)**
   * Built with PySide6, featuring breathing animations, eye blinks, facial expressions, and dynamic lip synchronization.
   * State-based emotional expressions (neutral, happy, thinking, explaining, warm smile).

2. **Multilingual Speech & Conversation**
   * High-quality text-to-speech (TTS) powered by Microsoft Edge Neural Voices.
   * Direct native language support for **English**, **Hindi (हिन्दी)**, **Telugu (తెలుగు)**, and **Tamil (தமிழ்)**.
   * Interruptible speech engine (Aiko stops speaking immediately when the user starts asking a question).

3. **MediaPipe Air-Gesture Controls**
   * Touchless interaction via webcam hand-tracking:
     * **Swipe Right-to-Left (Swipe Left)** ➡️ Go to **Next Slide**.
     * **Swipe Left-to-Right (Swipe Right)** ⬅️ Go to **Previous Slide**.
     * **Hold Open Palm** 🖐️ **Pause** presentation speech.
     * **Release Open Palm** 👋 **Resume** presentation speech.

4. **Dynamic Presentation Uploader**
   * Load any custom `.pptx` file dynamically from the dashboard.
   * Automatic slide content extraction and synchronized speech queue reset.

5. **Admin Analytics Dashboard**
   * Real-time visitor counts, questions asked, and session duration tracking.
   * Interactive chart displaying popular question keywords.
   * Recent question log detailing timestamps, language, and query text.

6. **Hybrid LLM Brain**
   * Configured for **Google Gemini API** (`gemini-1.5-flash` endpoint) and **OpenAI API** (`gpt-4o-mini`).
   * Fallback support for **Local Ollama** (`llama3.2`) to run 100% offline.

---

## 🛠️ Architecture & Modules

* `app.py`: Main desktop window coordinator. Houses the layout, camera loop, and custom Control Deck dashboard.
* `llm_brain.py`: AI logical reasoning module. Communicates with LLM APIs, translates slide content, and generates contextual answers.
* `conversation_engine.py`: Main state machine tracking presenter workflow (`GREETING`, `PRESENTING`, `ANSWERING`, `RESUMING`).
* `gesture_detector.py`: MediaPipe tasks-based hand landmark tracker.
* `tts_engine.py`: Pygame + `edge-tts` threaded voice generation manager.
* `language_manager.py`: System localization translations.
* `analytics_manager.py`: Local tracking database (`analytics_data.json`) for dashboard graphs.

---

## 🚀 Setup & Installation

### Prerequisites
* Python 3.10 or higher
* A webcam (for face tracking and hand gestures)

### 1. Clone the repository
```bash
git clone https://github.com/GonduDivitha/intelligence_lab_demo_agent.git
cd intelligence_lab_demo_agent
```

### 2. Set up virtual environment & install dependencies

#### 🍎 macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 🪟 Windows (Command Prompt)
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

#### 🪟 Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Add API Keys
Create a `.env` file in the root folder and add your Gemini or OpenAI API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
# OR
OPENAI_API_KEY=your_openai_api_key_here
```
*Note: If no cloud API keys are provided, the app will try connecting to a local Ollama server running `llama3.2`.*

### 4. Run the Application
```bash
python app.py
```

---

## 🖐️ Hand Gesture Quick Reference

| Action | Physical Gesture | Screen Feedback |
| :--- | :--- | :--- |
| **Next Slide** | Swipe hand quickly from right to left | `Gesture: Swipe Left` |
| **Previous Slide** | Swipe hand quickly from left to right | `Gesture: Swipe Right` |
| **Pause Speech** | Show flat palm towards webcam (hold) | `Gesture: Palm (Pause Active)` |
| **Resume Speech** | Drop or close your palm | `Gesture: Palm Released` |

---

## 👥 Authors
* Developed and maintained by the **Intelligence Lab Engineering Team**.
