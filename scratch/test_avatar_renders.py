import sys
import os
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter
from video_avatar import VideoAvatar

def capture_frames():
    app = QApplication(sys.argv)
    
    avatar = VideoAvatar()
    avatar.resize(400, 500)
    avatar.show()
    
    os.makedirs("scratch/avatar_frames", exist_ok=True)
    
    # 1. State: Idle, not speaking
    avatar.set_state("idle")
    avatar.set_speaking(False)
    
    # Process events to let paintEvent render
    QApplication.processEvents()
    
    # Grab frame 1 (Idle)
    pix = avatar.grab()
    pix.save("scratch/avatar_frames/frame_0_idle.png")
    print("Saved idle frame.")
    
    # 2. State: Speaking text 'Hello, this is a test of the lip sync system.'
    avatar.set_state("presenting")
    avatar.set_speaking_text("Hello, this is a test of the lip sync system.")
    avatar.set_speaking(True)
    
    # We will step the time manually or let the timer run and capture frames every 100ms
    frames = []
    
    def capture_step(step):
        if step >= 15:
            app.quit()
            return
            
        QApplication.processEvents()
        
        # Grab frame
        pix = avatar.grab()
        path = f"scratch/avatar_frames/frame_{step}_speaking.png"
        pix.save(path)
        print(f"Saved frame {step} (speaking: viseme={avatar.presenter._curr_viseme if hasattr(avatar.presenter, '_curr_viseme') else 'N/A'}, shape={avatar.presenter._mouth_shape_index})")
        
        # Sleep a bit to let time advance
        time.sleep(0.1)
        QTimer.singleShot(50, lambda: capture_step(step + 1))

    QTimer.singleShot(100, lambda: capture_step(1))
    app.exec()

if __name__ == "__main__":
    capture_frames()
