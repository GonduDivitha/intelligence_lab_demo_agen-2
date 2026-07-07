import os
import cv2
import math
import numpy as np
from PIL import Image

def create_presenter_gifs():
    img_path = 'presenter_base.jpg'
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found.")
        return

    # Load original image (896x1200)
    img = cv2.imread(img_path)
    h, w, _ = img.shape

    # Exact coordinates on original 896x1200 image
    mouth_x, mouth_y = 455, 422
    left_eye_x, right_eye_x, eye_y = 403, 508, 326

    output_dir = os.path.join('assets', 'gifs')
    os.makedirs(output_dir, exist_ok=True)

    states = ['idle', 'speaking', 'thinking', 'greeting', 'greeting_silent', 'presenting', 'presenting_silent']
    fps = 30
    duration = 2.0 # 2 seconds per GIF
    total_frames = int(fps * duration)

    print("Generating digital human GIFs...")

    for state in states:
        gif_path = os.path.join(output_dir, f"{state}.gif")
        frames_list = []

        for frame_idx in range(total_frames):
            phase = (frame_idx / total_frames) * math.pi * 2
            
            # Sub-pixel organic breathing (Y bob) and gesturing (X sway)
            bob = math.sin(phase) * 6.0
            
            if state in ['speaking', 'presenting', 'presenting_silent']:
                sway = math.sin(phase * 2) * 12.0 if 'silent' not in state else math.sin(phase) * 6.0
                tilt = math.sin(phase) * 1.5 if 'silent' not in state else math.sin(phase) * 0.8
            elif state in ['greeting', 'greeting_silent']:
                sway = math.sin(phase) * 10.0
                tilt = math.cos(phase) * 2.0
            elif state == 'thinking':
                sway = 0.0
                tilt = -3.0
            else: # idle
                sway = math.sin(phase) * 2.0
                tilt = 0.0

            # Apply affine transformation (rotate, scale, translate)
            center_x, center_y = w // 2, h // 2
            scale = 360 / w
            M = cv2.getRotationMatrix2D((center_x, center_y), tilt, scale)
            
            M[0, 2] += 180 - center_x + sway
            M[1, 2] += 240 - center_y + bob

            # Warp the image to target size
            frame = cv2.warpAffine(img, M, (360, 480), flags=cv2.INTER_LINEAR)

            # Mask out background (make it transparent/black)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mask = gray < 15
            frame[mask] = [0, 0, 0]

            # Calculate coordinates on the warped frame
            def transform_point(px, py, M):
                pt = np.array([px, py, 1.0])
                tx = np.dot(M[0], pt)
                ty = np.dot(M[1], pt)
                return int(tx), int(ty)

            f_left_eye = transform_point(left_eye_x, eye_y, M)
            f_right_eye = transform_point(right_eye_x, eye_y, M)
            f_mouth = transform_point(mouth_x, mouth_y, M)

            # Draw blinking eyes (blink every 60 frames for 3 frames)
            is_blinking = (frame_idx % 60) in [25, 26, 27]
            if is_blinking:
                # Eyelid cover matching her skin tone
                cv2.ellipse(frame, f_left_eye, (12, 5), 0, 0, 360, (190, 203, 248), -1)
                cv2.ellipse(frame, f_right_eye, (12, 5), 0, 0, 360, (190, 203, 248), -1)
                # Eyelash line
                cv2.line(frame, (f_left_eye[0] - 13, f_left_eye[1]), (f_left_eye[0] + 13, f_left_eye[1]), (20, 25, 36), 2)
                cv2.line(frame, (f_right_eye[0] - 13, f_right_eye[1]), (f_right_eye[0] + 13, f_right_eye[1]), (20, 25, 36), 2)

            # Apply photo-realistic lip sync warp (vertical stretching/compression of her actual lips)
            if state in ['speaking', 'greeting', 'presenting']:
                mouth_phase = (frame_idx / 10.0) * math.pi * 2
                open_factor = 0.5 + 0.5 * math.sin(mouth_phase)
                scale_y = 0.90 + open_factor * 0.35  # Varies between 0.90 (closed) and 1.25 (open)

                mx, my = f_mouth
                # Crop a region centered on her mouth
                w_box, h_box = 70, 24
                x1, x2 = mx - w_box // 2, mx + w_box // 2
                y1, y2 = my - h_box // 2, my + h_box // 2

                # Ensure boundaries are within frame size
                if y1 >= 0 and y2 <= 480 and x1 >= 0 and x2 <= 360:
                    mouth_roi = frame[y1:y2, x1:x2].copy()
                    new_h = int((y2 - y1) * scale_y)
                    # Stretch/compress the mouth region
                    mouth_resized = cv2.resize(mouth_roi, (x2 - x1, new_h), interpolation=cv2.INTER_LINEAR)

                    # Paste back centered on 'my'
                    y_start = my - (new_h // 2)
                    y_end = y_start + new_h
                    frame[y_start:y_end, x1:x2] = mouth_resized

                    # Smooth the top and bottom boundaries to blend seamlessly
                    if y_start - 3 >= 0 and y_start + 3 <= 480:
                        roi_top = frame[y_start-3:y_start+3, x1:x2]
                        frame[y_start-3:y_start+3, x1:x2] = cv2.GaussianBlur(roi_top, (3, 3), 0)
                    if y_end - 3 >= 0 and y_end + 3 <= 480:
                        roi_bot = frame[y_end-3:y_end+3, x1:x2]
                        frame[y_end-3:y_end+3, x1:x2] = cv2.GaussianBlur(roi_bot, (3, 3), 0)

            # Apply pointing gesture overlay during presenting states
            if state in ['presenting', 'presenting_silent']:
                # Animate pointing arm slightly with breathing phase
                hand_x = 90 + int(math.sin(phase) * 5)
                hand_y = 260 + int(math.cos(phase) * 3)
                
                # Draw dark navy blue suit sleeve (matches her jacket)
                # Start near shoulder/chest (170, 340) and extend to hand
                sleeve_pts = np.array([
                    [170, 340],
                    [180, 290],
                    [hand_x + 10, hand_y - 5],
                    [hand_x - 5, hand_y + 15]
                ], dtype=np.int32)
                cv2.fillPoly(frame, [sleeve_pts], (90, 45, 25)) # Dark navy BGR
                cv2.polylines(frame, [sleeve_pts], True, (60, 30, 15), 1)
                
                # Draw skin-colored hand pointing left
                # Hand base
                cv2.circle(frame, (hand_x, hand_y), 10, (190, 203, 248), -1)
                # Extended index finger pointing left
                cv2.line(frame, (hand_x, hand_y - 2), (hand_x - 25, hand_y - 5), (190, 203, 248), 4)
                # Thumb pointing up-left
                cv2.line(frame, (hand_x + 2, hand_y - 5), (hand_x - 10, hand_y - 15), (190, 203, 248), 3)

            # Convert BGR (OpenCV) to RGB (Pillow)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            frames_list.append(pil_img)

        # Save frames list as animated GIF
        if frames_list:
            frames_list[0].save(
                gif_path,
                save_all=True,
                append_images=frames_list[1:],
                duration=33, # ~30 FPS (33ms per frame)
                loop=0 # Infinite loop
            )
            print(f"Generated: {state}.gif")

    # Generate slide gifs
    import shutil
    for i in range(5):
        slide_gif_path = os.path.join(output_dir, f"slide{i}.gif")
        slide_silent_gif_path = os.path.join(output_dir, f"slide{i}_silent.gif")
        shutil.copy2(os.path.join(output_dir, "presenting.gif"), slide_gif_path)
        shutil.copy2(os.path.join(output_dir, "presenting_silent.gif"), slide_silent_gif_path)
        print(f"Linked slide{i}.gif and slide{i}_silent.gif")

if __name__ == '__main__':
    create_presenter_gifs()



