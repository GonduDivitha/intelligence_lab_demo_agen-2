import cv2

# Load image
img = cv2.imread("presenter_base.jpg")

mouth_x, mouth_y = 455, 422
left_eye_x, right_eye_x, eye_y = 403, 508, 326

# Draw circles on a copy
marked = img.copy()
cv2.circle(marked, (mouth_x, mouth_y), 5, (0, 0, 255), -1) # Red dot on mouth
cv2.circle(marked, (left_eye_x, eye_y), 5, (255, 0, 0), -1) # Blue dot on left eye
cv2.circle(marked, (right_eye_x, eye_y), 5, (0, 255, 0), -1) # Green dot on right eye

# Save cropped face to check
x, y, w, h = 333, 221, 246, 246
face_crop = marked[y-50:y+h+50, x-50:x+w+50]
cv2.imwrite("test_landmarks.jpg", face_crop)
print("Saved test_landmarks.jpg!")
