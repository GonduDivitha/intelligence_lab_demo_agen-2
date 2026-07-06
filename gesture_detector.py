import time
import collections
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Standard connections for drawing hand skeleton manually
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (9, 10), (10, 11), (11, 12),
    # Ring
    (13, 14), (14, 15), (15, 16),
    # Pinky
    (17, 18), (18, 19), (19, 20),
    # Palm Base Loop
    (0, 5), (5, 9), (9, 13), (13, 17), (17, 0)
]

class GestureDetector:
    """
    Detects hand gestures (Swipe Left and Palm Held/Released) using MediaPipe Tasks API.
    Handles prioritization of Swipe gestures over stationary Palm holds.
    """
    def __init__(self):
        self.detector = None
        
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            
            base_options = python.BaseOptions(model_asset_path='models/hand_landmarker.task')
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5
            )
            
            self.detector = vision.HandLandmarker.create_from_options(options)
            logger.info("MediaPipe HandLandmarker Tasks API initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe HandLandmarker Tasks API: {e}")

        # Gesture tracking history
        self.history = collections.deque(maxlen=15) # Stores (timestamp, x, y)
        self.palm_frames = 0 # Stable palm frame counter for debounce
        self.palm_is_held = False # State tracker for hold-to-pause
        self.cooldown_until = 0.0
        
        # Display feedback states
        self.active_gesture_text = "None"
        self.gesture_display_until = 0.0

    def process_frame(self, frame_bgr, flipped_frame):
        """
        Processes a BGR video frame and draws real-time feedback.
        Returns:
            detected_gesture (str): 'Swipe Left', 'Palm Held', 'Palm Released', or 'None'
            display_text (str): Overlay text for visual feedback
        """
        if not self.detector:
            return "None", "None"

        try:
            import mediapipe as mp
            # MediaPipe Tasks requires RGB format
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            
            result = self.detector.detect(mp_image)
        except Exception as e:
            logger.error(f"Error during HandLandmarker detection: {e}")
            return "None", "None"
        
        detected_gesture = "None"
        now = time.time()
        
        is_currently_holding_palm = False

        if result and result.hand_landmarks:
            for hand_landmarks in result.hand_landmarks:
                h, w, _ = flipped_frame.shape
                
                # Draw the hand skeleton manually using connections
                for start_idx, end_idx in HAND_CONNECTIONS:
                    pt1 = (int(hand_landmarks[start_idx].x * w), int(hand_landmarks[start_idx].y * h))
                    pt2 = (int(hand_landmarks[end_idx].x * w), int(hand_landmarks[end_idx].y * h))
                    cv2.line(flipped_frame, pt1, pt2, (0, 255, 0), 2)  # Bright green bones
                    
                for lm in hand_landmarks:
                    pt = (int(lm.x * w), int(lm.y * h))
                    cv2.circle(flipped_frame, pt, 4, (0, 255, 0), -1)  # Green joints
                
                # Track position of middle finger MCP
                middle_mcp = hand_landmarks[9]
                self.history.append((now, middle_mcp.x, middle_mcp.y))

                # 1. SWIPE DETECTION (Prioritized, checked regardless of palm_is_held)
                if now > self.cooldown_until:
                    swipe_left = False
                    swipe_right = False
                    # Compare current position to older frames in sliding window
                    for t, prev_x, prev_y in list(self.history)[:-2]:
                        if now - t < 0.500: # Time window of 500ms
                            dx = prev_x - middle_mcp.x  # In flipped mirror view: leftward motion means X decreases
                            dy = abs(prev_y - middle_mcp.y)
                            # Swipe check: 13% horizontal width displacement, low vertical deviation
                            if dx > 0.13 and dy < 0.15:
                                swipe_left = True
                                break
                            elif dx < -0.13 and dy < 0.15:
                                swipe_right = True
                                break
                    
                    if swipe_left:
                        detected_gesture = "Swipe Left"
                        self.cooldown_until = now + 1.5  # 1.5s cooldown
                        self.active_gesture_text = "Gesture: Swipe Left"
                        self.gesture_display_until = now + 2.0
                        self.history.clear()
                        self.palm_frames = 0
                        self.palm_is_held = False # Clear palm states upon swiping
                        break
                    elif swipe_right:
                        detected_gesture = "Swipe Right"
                        self.cooldown_until = now + 1.5  # 1.5s cooldown
                        self.active_gesture_text = "Gesture: Swipe Right"
                        self.gesture_display_until = now + 2.0
                        self.history.clear()
                        self.palm_frames = 0
                        self.palm_is_held = False # Clear palm states upon swiping
                        break

                # 2. PALM Held Detection using Wrist Distance Ratio (Rotation & Tilt-Independent)
                def dist(p1, p2):
                    return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
                
                wrist = hand_landmarks[0]
                is_palm = True
                
                # Check if all four finger tips are significantly further from wrist than their MCP joints
                for tip_idx, mcp_idx in [(8, 5), (12, 9), (16, 13), (20, 17)]:
                    tip_dist = dist(hand_landmarks[tip_idx], wrist)
                    mcp_dist = dist(hand_landmarks[mcp_idx], wrist)
                    if tip_dist < mcp_dist * 1.25:
                        is_palm = False
                        break
                        
                if is_palm:
                    is_currently_holding_palm = True
                    self.palm_frames = min(12, self.palm_frames + 1)
                    if self.palm_frames >= 4: # ~120ms stable palm
                        if not self.palm_is_held:
                            self.palm_is_held = True
                            detected_gesture = "Palm Held"
                            self.cooldown_until = now + 0.5
                            break
                else:
                    self.palm_frames = max(0, self.palm_frames - 1)
                    if self.palm_frames == 0:
                        if self.palm_is_held:
                            self.palm_is_held = False
                            detected_gesture = "Palm Released"
                            break
        else:
            self.palm_frames = max(0, self.palm_frames - 1)
            if self.palm_frames == 0:
                if self.palm_is_held:
                    self.palm_is_held = False
                    detected_gesture = "Palm Released"
            self.history.clear()

        # Update overlay display feedback
        if self.palm_is_held:
            display_text = "Gesture: Palm (Pause Active)"
        elif is_currently_holding_palm and self.palm_frames > 0:
            display_text = "Gesture: Palm (Hold to Pause)"
        elif now < self.gesture_display_until:
            display_text = self.active_gesture_text
        else:
            display_text = "None"

        return detected_gesture, display_text
