import cv2
import numpy as np

# Load image
img = cv2.imread("presenter_base.jpg")
h, w, _ = img.shape
print(f"Image loaded: {w}x{h}")

# Load Haar Cascades (using PySide6 / cv2 default XML paths if available, or downloading/using standard ones)
# Since the project runs face detection, let's look for xml paths in the codebase
# app.py loads frontal_cascade: "models/haarcascade_frontalface_default.xml"
face_cascade_path = "models/haarcascade_frontalface_default.xml"
import os
if not os.path.exists(face_cascade_path):
    face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

face_cascade = cv2.CascadeClassifier(face_cascade_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(gray, 1.1, 5)

if len(faces) > 0:
    for (x, y, fw, fh) in faces:
        print(f"Face detected at x={x}, y={y}, w={fw}, h={fh}")
        # Crop face and look for eyes and mouth
        face_gray = gray[y:y+fh, x:x+fw]
        
        # Estimate features based on face proportions (very robust on Pixar 3D characters!)
        # Typically:
        # - Left Eye is at ~30% of face width, ~35% of face height
        # - Right Eye is at ~70% of face width, ~35% of face height
        # - Mouth is at ~50% of face width, ~75% of face height
        # Let's print these estimated coordinates relative to the full image:
        left_eye_x = x + int(fw * 0.35)
        right_eye_x = x + int(fw * 0.65)
        eye_y = y + int(fh * 0.40)
        mouth_x = x + int(fw * 0.50)
        mouth_y = y + int(fh * 0.72)
        
        print(f"ESTIMATED COORDINATES FOR 896x1200 IMAGE:")
        print(f"mouth_x, mouth_y = {mouth_x}, {mouth_y}")
        print(f"left_eye_x, right_eye_x, eye_y = {left_eye_x}, {right_eye_x}, {eye_y}")
else:
    print("No face detected by Haar Cascade, estimating default center-face values...")
    # Default center-face coordinates for standard 3:4 portrait:
    # Face center is at x=448
    # Head top is around y=100-200, chin is around y=600
    # Let's estimate:
    # mouth_x, mouth_y = 448, 305
    # left_eye_x, right_eye_x, eye_y = 405, 491, 230
