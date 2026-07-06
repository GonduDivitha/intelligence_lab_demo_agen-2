import sys
import logging
from llm_brain import LLMBrain
from pptx import Presentation
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LLMTest")

def run_test():
    logger.info("Initializing LLMBrain...")
    brain = LLMBrain()
    
    # 1. Check if Ollama service is reachable
    logger.info("Checking if Ollama service is running on http://localhost:11434...")
    available = brain.is_available()
    
    if available:
        logger.info("✅ Ollama is running and reachable!")
    else:
        logger.warning("❌ Ollama is NOT running or NOT reachable on localhost:11434.")
        logger.info("The application will run using the built-in rule-based fallback system.")
        logger.info("To enable the full LLM experience, please start the Ollama service: 'ollama serve' or open the Ollama Desktop app.")
        logger.info("Then pull a model: 'ollama pull llama3.1:8b' or customize the model name in llm_brain.py.")
    
    # 2. Test Greeting Generation
    logger.info("\n=== Testing Greeting Generation ===")
    languages = ["English", "Hindi", "Telugu", "Tamil"]
    for lang in languages:
        logger.info(f"Testing greeting in {lang}...")
        greeting = brain.generate_greeting(lang)
        print(f"[{lang}] Greeting: {greeting}\n")

    # 3. Test Slide Explanation
    logger.info("\n=== Testing Slide Explanation ===")
    slide_title = "Core Technologies"
    slide_text = (
        "The demo uses PySide6 for the user interface, OpenCV for webcam face detection, "
        "python-pptx for reading PowerPoint text, Microsoft Edge TTS for speech output, "
        "and Vosk for continuous offline voice questions."
    )
    for lang in ["English", "Hindi", "Telugu"]:
        logger.info(f"Testing explanation in {lang}...")
        explanation = brain.explain_slide(
            slide_title=slide_title,
            slide_text=slide_text,
            slide_number=3,
            total_slides=6,
            language=lang
        )
        print(f"[{lang}] Explanation: {explanation}\n")

    # 4. Test Question Answering
    logger.info("\n=== Testing Question Answering ===")
    question = "Which technologies are used in this demo?"
    for lang in ["English", "Hindi", "Telugu"]:
        logger.info(f"Testing answer in {lang}...")
        answer = brain.answer_question(
            question=question,
            current_slide_text=slide_text,
            conversation_history=[],
            language=lang
        )
        print(f"[{lang}] Answer: {answer}\n")

    # 5. Test Resume Transition
    logger.info("\n=== Testing Resume Transition ===")
    for lang in ["English", "Hindi", "Telugu"]:
        logger.info(f"Testing transition in {lang}...")
        transition = brain.generate_resume_transition(slide_title, lang)
        print(f"[{lang}] Transition: {transition}\n")

    # 6. Test Farewell
    logger.info("\n=== Testing Farewell ===")
    for lang in ["English", "Hindi", "Telugu"]:
        logger.info(f"Testing farewell in {lang}...")
        farewell = brain.generate_farewell(lang)
        print(f"[{lang}] Farewell: {farewell}\n")

if __name__ == "__main__":
    run_test()
