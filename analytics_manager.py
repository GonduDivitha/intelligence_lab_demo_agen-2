import os
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AnalyticsManager:
    """
    Manages session and interaction statistics for the kiosk.
    Persists data locally in a JSON file.
    """
    def __init__(self, filepath="analytics_data.json"):
        self.filepath = filepath
        self.session_start = None
        
        # Default empty analytics structure
        self.data = {
            "total_visitors": 0,
            "total_questions": 0,
            "slide_views": {},
            "recent_questions": [],
            "session_durations": []
        }
        
        self.load_data()

    def load_data(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Verify structure matches keys
                    for k in self.data.keys():
                        if k in loaded:
                            self.data[k] = loaded[k]
                logger.info(f"Analytics data loaded successfully from {self.filepath}.")
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")

    def save_data(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")

    def log_visitor(self):
        """Called when a new visitor interaction starts."""
        self.data["total_visitors"] += 1
        self.session_start = time.time()
        self.save_data()
        logger.info("Analytics: Logged new visitor.")

    def log_session_end(self):
        """Called when OpenCV detects the visitor has left."""
        if self.session_start is not None:
            duration = time.time() - self.session_start
            # Filter out tiny accidental triggers (less than 2 seconds)
            if duration > 2.0:
                self.data["session_durations"].append(round(duration, 1))
                # Keep last 100 durations to prevent unbounded growth
                if len(self.data["session_durations"]) > 100:
                    self.data["session_durations"].pop(0)
                self.save_data()
                logger.info(f"Analytics: Logged session end. Duration: {duration:.1f}s.")
            self.session_start = None

    def log_slide_view(self, slide_title: str):
        """Called when slide navigation changes."""
        if not slide_title or not slide_title.strip():
            return
        
        slide_title = slide_title.strip()
        views = self.data["slide_views"]
        views[slide_title] = views.get(slide_title, 0) + 1
        self.save_data()
        logger.info(f"Analytics: Logged slide view for '{slide_title}'.")

    def log_question(self, question: str, language: str):
        """Called when a visitor asks a question (typed or voice)."""
        if not question or not question.strip():
            return
            
        question = question.strip()
        self.data["total_questions"] += 1
        
        # Add to recent list with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["recent_questions"].append({
            "timestamp": timestamp,
            "question": question,
            "language": language
        })
        
        # Keep only the last 20 questions
        if len(self.data["recent_questions"]) > 20:
            self.data["recent_questions"].pop(0)
            
        self.save_data()
        logger.info(f"Analytics: Logged question: '{question[:30]}...' ({language}).")

    def get_stats(self) -> dict:
        """Returns aggregated stats for rendering on the dashboard."""
        durations = self.data.get("session_durations", [])
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # Sort slides by view popularity
        sorted_slides = sorted(
            self.data.get("slide_views", {}).items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "total_visitors": self.data.get("total_visitors", 0),
            "total_questions": self.data.get("total_questions", 0),
            "avg_session_time": round(avg_duration, 1),
            "slide_views": sorted_slides,
            "recent_questions": list(reversed(self.data.get("recent_questions", []))) # newest first
        }
