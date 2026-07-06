import os
import cv2
import math
import numpy as np

def create_presenter_videos():
    img_path = 'presenter_base.jpg'
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found.")
        return

    # Load original image (896x1200)
    img = cv2.imread(img_path)
    h, w, _ = img.shape

    # Exact coordinates on original 896x1200 image
    # Mouth center: x = 448, y = 389
    mouth_x, mouth_y = 448, 389
    # Eye centers: left x = 405, right x = 491, y = 280
    left_eye_x, right_eye_x, eye_y = 405, 491, 280

    output_dir = os.path.join('assets', 'videos')
    os.makedirs(output_dir, exist_ok=True)

    states = ['idle', 'speaking', 'thinking', 'greeting']
    fps = 30
    duration = 2.0 # 2 seconds per video
    total_frames = int(fps * duration)

    # Use standard H.264 (avc1) codec which is hardware accelerated on macOS
    fourcc = cv2.VideoWriter_fourcc(*'avc1')

    print("Generating digital human videos...")

    for state in states:
        out_path = os.path.join(output_dir, f"{state}.mp4")
        out = cv2.VideoWriter(out_path, fourcc, fps, (360, 480))

        for frame_idx in range(total_frames):
            # 1. Base transformations for organic movement
            phase = (frame_idx / total_frames) * math.pi * 2
            
            # Sub-pixel organic breathing (Y bob) and gesturing (X sway)
            bob = math.sin(phase) * 6.0
            
            if state == 'speaking':
                sway = math.sin(phase * 2) * 12.0
                tilt = math.sin(phase) * 1.5
            elif state == 'greeting':
                sway = math.sin(phase) * 10.0
                tilt = math.cos(phase) * 2.0
            elif state == 'thinking':
                sway = 0.0
                tilt = -3.0
            else: # idle
                sway = math.sin(phase) * 2.0
                tilt = 0.0

            # 2. Apply affine transformation to the source image (rotate, scale, translate)
            # Center of rotation is the face center
            center_x, center_y = w // 2, h // 2
            
            # Translation matrix
            tx = sway
            ty = bob
            
            # Combined rotation & scale matrix
            # We scale the original image to match target 360x480 container
            scale = 360 / w
            M = cv2.getRotationMatrix2D((center_x, center_y), tilt, scale)
            
            # Adjust translation in the matrix to center the output
            M[0, 2] += tx - (center_x * scale) + 180
            M[1, 2] += ty - (center_y * scale) + 240

            # Warp the image to target size
            frame = cv2.warpAffine(img, M, (360, 480), flags=cv2.INTER_LINEAR)

            # Mask out background (make it transparent/black)
            # The original image is already on a solid black background
            # A simple thresholding guarantees the background is completely pure black in the video
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mask = gray < 15
            frame[mask] = [0, 0, 0]

            # 3. Calculate dynamic coordinates on the warped frame
            # Transform mouth and eye coordinates using the same warp matrix M
            def transform_point(px, py, M):
                pt = np.array([px, py, 1.0])
                tx = np.dot(M[0], pt)
                ty = np.dot(M[1], pt)
                return int(tx), int(ty)

            f_left_eye = transform_point(left_eye_x, eye_y, M)
            f_right_eye = transform_point(right_eye_x, eye_y, M)
            f_mouth = transform_point(mouth_x, mouth_y, M)

            # 4. Draw blinking eyes (blink every 60 frames for 3 frames)
            is_blinking = (frame_idx % 60) in [25, 26, 27]
            if is_blinking:
                # Eyelid cover matching her skin tone
                cv2.ellipse(frame, f_left_eye, (10, 4), 0, 0, 360, (190, 203, 248), -1)
                cv2.ellipse(frame, f_right_eye, (10, 4), 0, 0, 360, (190, 203, 248), -1)
                # Eyelash line
                cv2.line(frame, (f_left_eye[0] - 11, f_left_eye[1]), (f_left_eye[0] + 11, f_left_eye[1]), (20, 25, 36), 2)
                cv2.line(frame, (f_right_eye[0] - 11, f_right_eye[1]), (f_right_eye[0] + 11, f_right_eye[1]), (20, 25, 36), 2)

            # 5. Draw Lip Sync Mouth Animation
            if state in ['speaking', 'greeting']:
                # Oscillate mouth opening size
                mouth_phase = (frame_idx / 10.0) * math.pi * 2
                open_factor = 0.5 + 0.5 * math.sin(mouth_phase)
                
                mouth_h = int(open_factor * 12) + 2
                mouth_w = 20 + int(open_factor * 4)

                # Skin patch to cover the static closed smile
                cv2.ellipse(frame, f_mouth, (18, 8), 0, 0, 360, (190, 203, 248), -1)
                # Inner oral cavity
                cv2.ellipse(frame, f_mouth, (mouth_w // 2, mouth_h // 2), 0, 0, 360, (35, 30, 115), -1)
                # Teeth
                teeth_w = (mouth_w * 2) // 3
                teeth_h = max(2, mouth_h // 5)
                cv2.rectangle(frame, 
                              (f_mouth[0] - teeth_w // 2, f_mouth[1] - mouth_h // 2 + 1),
                              (f_mouth[0] + teeth_w // 2, f_mouth[1] - mouth_h // 2 + 1 + teeth_h),
                              (255, 255, 255), -1)
                # Outer lips outline
                cv2.ellipse(frame, f_mouth, (mouth_w // 2, mouth_h // 2), 0, 0, 360, (120, 110, 200), 2)

            # Write the completed frame to the video file
            out.write(frame)

        out.release()
        print(f"Generated: {state}.mp4")

    # Generate slide videos as links/duplicates to speaking.mp4 to prevent missing files
    for i in range(5):
        slide_video_path = os.path.join(output_dir, f"slide{i}.mp4")
        # Copy speaking.mp4 to slide{i}.mp4
        cv2.imwrite('temp.jpg', img) # dummy placeholder trigger
        import shutil
        shutil.copy2(os.path.join(output_dir, "speaking.mp4"), slide_video_path)
        print(f"Linked slide{i}.mp4")

if __name__ == '__main__':
    create_presenter_videos()
