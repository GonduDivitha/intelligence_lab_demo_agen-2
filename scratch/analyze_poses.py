import os
import cv2
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh

poses_dir = "../assets/poses"
pose_files = {
    "idle": "idle.jpg",
    "speaking": "speaking.jpg",
    "pointing": "pointing.jpg",
    "blinking": "blinking.jpg",
    "mouth_wide": "mouth_wide.jpg",
    "mouth_o": "mouth_o.jpg",
    "both_hands": "gesture_both_hands.jpg",
    "mouth_closed": "mouth_closed.jpg",
}

print("Starting pose analysis...")

with mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
) as face_mesh:
    for name, fname in pose_files.items():
        path = os.path.join(poses_dir, fname)
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
        
        image = cv2.imread(path)
        if image is None:
            print(f"Failed to load image: {path}")
            continue
            
        h, w, _ = image.shape
        # Convert the BGR image to RGB before processing.
        results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        if not results.multi_face_landmarks:
            print(f"No face detected in {fname}")
            continue
            
        landmarks = results.multi_face_landmarks[0].landmark
        
        # Mouth landmarks (Indices around lips)
        # Inner lips: 13, 14, 78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308
        # Let's compute bounding box for lips.
        # Outer lips indices: 61, 291, 37, 267, 0, 269, 39, 270, 40, 271, 41, 272, 42, 273...
        # Let's take general mouth bounding area.
        # 164 is chin/nose area, 57, 287 are corners.
        # Let's use indices 61 (left corner), 291 (right corner), 11 (upper lip), 16 (lower lip)
        mouth_indices = [61, 291, 11, 16, 13, 14, 78, 308]
        xs = [landmarks[i].x * w for i in mouth_indices]
        ys = [landmarks[i].y * h for i in mouth_indices]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Add some padding around the mouth
        pad_x = (max_x - min_x) * 0.4
        pad_y = (max_y - min_y) * 0.4
        
        mouth_box = (
            (min_x - pad_x) / w,
            (min_y - pad_y) / h,
            (max_x - min_x + 2 * pad_x) / w,
            (max_y - min_y + 2 * pad_y) / h
        )
        
        # Eye landmarks (Indices for left and right eyes)
        # Left eye: 33, 133, 159, 145 (corners, top, bottom)
        # Right eye: 263, 362, 386, 374
        eye_indices = [33, 133, 159, 145, 263, 362, 386, 374]
        eye_xs = [landmarks[i].x * w for i in eye_indices]
        eye_ys = [landmarks[i].y * h for i in eye_indices]
        
        min_ex, max_ex = min(eye_xs), max(eye_xs)
        min_ey, max_ey = min(eye_ys), max(eye_ys)
        
        pad_ex = (max_ex - min_ex) * 0.25
        pad_ey = (max_ey - min_ey) * 0.4
        
        eye_box = (
            (min_ex - pad_ex) / w,
            (min_ey - pad_ey) / h,
            (max_ex - min_ex + 2 * pad_ex) / w,
            (max_y - min_y + 2 * pad_ey) / h # wait, let's keep height relative to eyes
        )
        
        eye_box = (
            (min_ex - pad_ex) / w,
            (min_ey - pad_ey) / h,
            (max_ex - min_ex + 2 * pad_ex) / w,
            (max_ey - min_ey + 2 * pad_ey) / h
        )
        
        print(f'"{name}": {{')
        print(f'    "mouth": ({mouth_box[0]:.4f}, {mouth_box[1]:.4f}, {mouth_box[2]:.4f}, {mouth_box[3]:.4f}),')
        print(f'    "eyes": ({eye_box[0]:.4f}, {eye_box[1]:.4f}, {eye_box[2]:.4f}, {eye_box[3]:.4f})')
        print(f'}},')
