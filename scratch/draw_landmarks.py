import cv2

# Load image
img = cv2.imread("presenter_base.jpg")

# The coordinates we got from detection
mouth_x, mouth_y = 453, 372
left_eye_x, right_eye_x, eye_y = 420, 486, 295

# Draw circles on a copy
marked = img.copy()
cv2.circle(marked, (mouth_x, mouth_y), 5, (0, 0, 255), -1) # Red dot on mouth
cv2.circle(marked, (left_eye_x, eye_y), 5, (255, 0, 0), -1) # Blue dot on left eye
cv2.circle(marked, (right_eye_x, eye_y), 5, (0, 255, 0), -1) # Green dot on right eye

# Save cropped face to check
x, y, w, h = 369, 221, 169, 169
face_crop = marked[y-20:y+h+20, x-20:x+w+20]
cv2.imwrite("test_landmarks.jpg", face_crop)
print("Saved test_landmarks.jpg!")
