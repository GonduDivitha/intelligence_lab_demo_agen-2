import os
import cv2
import numpy as np

poses_dir = "assets/poses"
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

# We'll use a template from the upper face / nose / eyes area of idle.jpg
# Normalized box for upper face: x: 0.40 to 0.58, y: 0.20 to 0.28
# Let's load idle.jpg first.
idle_path = os.path.join(poses_dir, "idle.jpg")
idle_img = cv2.imread(idle_path)
if idle_img is None:
    print("Failed to load idle.jpg")
    exit(1)
    
h, w, _ = idle_img.shape
print(f"Idle dimensions: {w}x{h}")

tx1, ty1 = int(0.42 * w), int(0.21 * h)
tx2, ty2 = int(0.56 * w), int(0.28 * h)
template = idle_img[ty1:ty2, tx1:tx2]

# Save template for debugging
cv2.imwrite("face_template.jpg", template)
print(f"Template size: {template.shape[1]}x{template.shape[0]}")

offsets = {}

for name, fname in pose_files.items():
    path = os.path.join(poses_dir, fname)
    if not os.path.exists(path):
        continue
    img = cv2.imread(path)
    if img is None:
        continue
        
    # We search in a region around the template coordinates (with +/- 40 pixels padding)
    search_x1 = max(0, tx1 - 50)
    search_y1 = max(0, ty1 - 50)
    search_x2 = min(w, tx2 + 50)
    search_y2 = min(h, ty2 + 50)
    search_area = img[search_y1:search_y2, search_x1:search_x2]
    
    res = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    # max_loc is relative to search area
    best_x = search_x1 + max_loc[0]
    best_y = search_y1 + max_loc[1]
    
    dx = best_x - tx1
    dy = best_y - ty1
    
    print(f'"{name}": ({dx}, {dy}),  # correlation: {max_val:.4f}')
