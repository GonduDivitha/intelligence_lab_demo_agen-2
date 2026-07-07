import os
import math
import random
import logging
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QSize
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QImage, QPainterPath,
    QLinearGradient, QRadialGradient, QFont
)

logger = logging.getLogger(__name__)

class VideoAvatar(QWidget):
    """
    Hybrid Vector-on-Image Anime Presenter widget.
    Loads the high-fidelity presenter base image and overlays dynamically drawn,
    smooth 2D vector anime features (blinking, pupil eye tracking, and lips/lip sync)
    running at 60 FPS for ultra-realistic rendering.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)
        
        # State variables
        self.current_state = "idle"
        self.current_slide = 0
        self.is_speaking = False
        
        # Gaze tracking variables
        self.visitor_x = 0.0
        self.visitor_y = 0.0
        self.current_gaze_x = 0.0
        self.current_gaze_y = 0.0
        
        # slide refer timer variables
        self.slide_gaze_timer = 0
        self.is_looking_at_slide = False
        
        # Animation ticks
        self.tick = 0
        self.breathing_phase = 0.0
        
        # Eye blink states
        self.left_blink_progress = 1.0  # 1.0 = fully open, 0.0 = fully closed
        self.right_blink_progress = 1.0
        self.next_blink_tick = random.randint(120, 240)
        self.blink_duration = 10
        self.blink_active_tick = 0
        
        # Mouth states
        self.mouth_open = 0.0  # 0.0 = fully closed, 1.0 = fully open
        self.mouth_shape_type = 0  # 0 = normal smile, 1 = round O, 2 = wide smile
        
        # Load base image
        self.fallback_image_path = os.path.join(os.path.dirname(__file__), "presenter_base.jpg")
        self.base_image = QImage()
        self.skin_color = QColor(253, 215, 203)  # Fallback skin color
        self.init_avatar()

        # Core Coordinates on the original 896x1200 image
        self.img_w = 896
        self.img_h = 1200
        self.l_eye_center = QPointF(398.0, 305.0)
        self.r_eye_center = QPointF(498.0, 305.0)
        self.mouth_center = QPointF(448.0, 480.0)

        # Scale and render variables
        self.render_scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Start 60 FPS update timer
        self.timer = QTimer(self)
        self.timer.setInterval(16)  # ~60 FPS
        self.timer.timeout.connect(self._update_animation)
        self.timer.start()

    def init_avatar(self):
        if os.path.exists(self.fallback_image_path):
            self.base_image.load(self.fallback_image_path)
            if not self.base_image.isNull():
                logger.info("Successfully loaded base presenter image.")
                # Sample skin tone outside the facial features to cover them perfectly
                # Left cheek: (360, 305) on the original image
                if self.base_image.width() >= 896 and self.base_image.height() >= 1200:
                    self.skin_color = QColor(self.base_image.pixel(360, 305))
                    logger.info(f"Sampled face skin tone color: RGB({self.skin_color.red()}, {self.skin_color.green()}, {self.skin_color.blue()})")
            else:
                logger.error("Failed to parse presenter_base.jpg image contents.")
        else:
            logger.error(f"Presenter base image file not found at: {self.fallback_image_path}")

    def pop_out(self):
        """Called when a visitor is detected."""
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking

    def set_visitor_position(self, rel_x: float, rel_y: float):
        """Receive normalized camera coordinates [-1.0, 1.0] from face tracker."""
        self.visitor_x = rel_x
        self.visitor_y = rel_y

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index

    def pause(self):
        self.timer.stop()

    def play(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _update_animation(self):
        self.tick += 1
        
        # 1. Breathing vertical motion
        self.breathing_phase += 0.045
        
        # 2. Smoothly update gaze coordinates towards target
        target_gaze_x = self.visitor_x
        target_gaze_y = self.visitor_y

        # Presentation slide referral gaze mechanic
        if self.current_state in ["presenting", "speaking"] and not self.is_speaking:
            self.slide_gaze_timer += 1
            if self.is_looking_at_slide:
                target_gaze_x = 0.7  # Glancing towards presentation area (right)
                target_gaze_y = 0.1
                if self.slide_gaze_timer > random.randint(70, 110):
                    self.is_looking_at_slide = False
                    self.slide_gaze_timer = 0
            else:
                if self.slide_gaze_timer > random.randint(180, 280):
                    self.is_looking_at_slide = True
                    self.slide_gaze_timer = 0
        else:
            self.is_looking_at_slide = False
            self.slide_gaze_timer = 0

        self.current_gaze_x += (target_gaze_x - self.current_gaze_x) * 0.08
        self.current_gaze_y += (target_gaze_y - self.current_gaze_y) * 0.08

        # 3. Blink timer & animation
        self.next_blink_tick -= 1
        if self.next_blink_tick <= 0 and self.blink_active_tick == 0:
            self.blink_active_tick = self.blink_duration
            self.next_blink_tick = random.randint(150, 300)

        if self.blink_active_tick > 0:
            self.blink_active_tick -= 1
            half_dur = self.blink_duration / 2
            if self.blink_active_tick > half_dur:
                progress = (self.blink_active_tick - half_dur) / half_dur
            else:
                progress = (half_dur - self.blink_active_tick) / half_dur
            self.left_blink_progress = progress
            self.right_blink_progress = progress
        else:
            self.left_blink_progress = 1.0
            self.right_blink_progress = 1.0

        # 4. Mouth lip sync logic
        target_open = 0.0
        if self.is_speaking:
            # Multi-frequency oscillator for natural speech open/close rhythm
            target_open = 0.2 + 0.8 * abs(math.sin(self.tick * 0.2)) * (0.7 + 0.3 * math.cos(self.tick * 0.07))
            # Occasionally select different shapes
            if self.tick % 40 == 0:
                self.mouth_shape_type = random.choice([0, 1, 2])
        else:
            if self.current_state in ["greeting", "idle"]:
                self.mouth_shape_type = 2  # Warm smile shape when silent
            else:
                self.mouth_shape_type = 0  # Normal line shape
        
        self.mouth_open += (target_open - self.mouth_open) * 0.24

        # Redraw
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Clear background to dark color
        painter.fillRect(self.rect(), QColor(10, 12, 22))

        if self.base_image.isNull():
            # Error fallback
            painter.setPen(QColor(164, 178, 252))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Presenter image missing\n(Please verify presenter_base.jpg)")
            return

        # 1. Scale image maintaining aspect ratio
        w, h = self.width(), self.height()
        scale_w = w / self.img_w
        scale_h = h / self.img_h
        self.render_scale = min(scale_w, scale_h)

        scaled_w = int(self.img_w * self.render_scale)
        scaled_h = int(self.img_h * self.render_scale)
        
        self.offset_x = (w - scaled_w) / 2
        self.offset_y = (h - scaled_h) / 2

        # Apply breathing offset (vertical motion of 3 pixels max scaled)
        y_breath = math.sin(self.breathing_phase) * 2.5 * self.render_scale
        
        # Render presenter base
        target_rect = QRectF(self.offset_x, self.offset_y + y_breath, scaled_w, scaled_h)
        painter.drawImage(target_rect, self.base_image)

        # 2. Draw Cover-up patches to hide original static features
        self._draw_static_patch_overlays(painter, y_breath)

        # 3. Draw Vector eyes (Blinking + Pupil eye-tracking)
        self._draw_vector_eye(painter, self.l_eye_center, self.left_blink_progress, y_breath, is_left=True)
        self._draw_vector_eye(painter, self.r_eye_center, self.right_blink_progress, y_breath, is_left=False)

        # 4. Draw Vector mouth (Lip-sync cavity + teeth + lips)
        self._draw_vector_mouth(painter, self.mouth_center, self.mouth_open, y_breath)

    def _draw_static_patch_overlays(self, painter, y_breath):
        """Draws skin-colored matching ovals to perfectly cover original static eyes/mouth."""
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.skin_color))

        scale = self.render_scale
        
        # Cover Left Eye
        lx = self.offset_x + self.l_eye_center.x() * scale
        ly = self.offset_y + self.l_eye_center.y() * scale + y_breath
        lw = 40.0 * scale
        lh = 28.0 * scale
        painter.drawEllipse(QRectF(lx - lw/2, ly - lh/2, lw, lh))

        # Cover Right Eye
        rx = self.offset_x + self.r_eye_center.x() * scale
        ry = self.offset_y + self.r_eye_center.y() * scale + y_breath
        rw = 40.0 * scale
        rh = 28.0 * scale
        painter.drawEllipse(QRectF(rx - rw/2, ry - rh/2, rw, rh))

        # Cover Mouth
        mx = self.offset_x + self.mouth_center.x() * scale
        my = self.offset_y + self.mouth_center.y() * scale + y_breath
        mw = 75.0 * scale
        mh = 35.0 * scale
        painter.drawEllipse(QRectF(mx - mw/2, my - mh/2, mw, mh))

        painter.restore()

    def _draw_vector_eye(self, painter, center_pt, blink_progress, y_breath, is_left):
        """Draws dynamic, scalable 2D anime-style eyes over coordinates."""
        painter.save()
        scale = self.render_scale
        
        ex = self.offset_x + center_pt.x() * scale
        ey = self.offset_y + center_pt.y() * scale + y_breath
        
        ew = 23.0 * scale
        eh = 18.0 * scale
        
        # Check if blinking (fully closed or almost closed)
        if blink_progress < 0.15:
            # Closed eye eyelash curve
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(35, 30, 70), 3.0 * scale, Qt.SolidLine, Qt.RoundCap))
            path = QPainterPath()
            path.moveTo(ex - ew * 1.1, ey)
            path.quadTo(ex, ey + eh * 0.3, ex + ew * 1.1, ey)
            painter.drawPath(path)
            
            # Subtle accent bottom lash
            painter.setPen(QPen(QColor(35, 30, 70, 120), 1.2 * scale))
            painter.drawArc(QRectF(ex - ew * 0.7, ey + eh * 0.3, ew * 1.4, eh * 0.4), 0, -180 * 16)
            painter.restore()
            return

        # 1. Draw Eye Socket / Sclera (White background)
        painter.setPen(QPen(QColor(50, 40, 80, 50), 1.0 * scale))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        sclera_path = QPainterPath()
        # Scale vertical size by blink progress
        curr_eh = eh * blink_progress
        sclera_path.moveTo(ex - ew, ey)
        sclera_path.quadTo(ex, ey - curr_eh, ex + ew, ey)
        sclera_path.quadTo(ex, ey + curr_eh, ex - ew, ey)
        painter.drawPath(sclera_path)

        # 2. Draw Iris (Beautiful blue gradient matching original model)
        # Compute gaze shifts (limited pupil movement radius)
        max_shift_x = 4.5 * scale
        max_shift_y = 2.5 * scale
        gaze_x = self.current_gaze_x * max_shift_x
        gaze_y = self.current_gaze_y * max_shift_y
        
        iris_cx = ex + gaze_x
        iris_cy = ey + gaze_y
        iris_w = 15.0 * scale
        iris_h = 15.0 * scale * blink_progress
        
        # Radial gradient for pupil/iris texture
        iris_grad = QRadialGradient(iris_cx, iris_cy, iris_w)
        iris_grad.setColorAt(0.0, QColor(90, 195, 255))   # Bright cyan highlight
        iris_grad.setColorAt(0.5, QColor(40, 115, 220))   # Mid blue
        iris_grad.setColorAt(1.0, QColor(15, 35, 95))     # Dark navy border
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(iris_grad))
        
        # Clip iris to fit inside sclera
        painter.setClipPath(sclera_path)
        painter.drawEllipse(QRectF(iris_cx - iris_w, iris_cy - iris_h, iris_w * 2, iris_h * 2))
        
        # 3. Draw Pupil (Deep center)
        pupil_w = 6.0 * scale
        pupil_h = 6.0 * scale * blink_progress
        painter.setBrush(QBrush(QColor(12, 18, 48)))
        painter.drawEllipse(QRectF(iris_cx - pupil_w, iris_cy - pupil_h, pupil_w * 2, pupil_h * 2))

        # 4. Draw Double Sparkle highlights (Anime eye sparkle)
        highlight_w = 3.5 * scale
        highlight_h = 3.5 * scale * blink_progress
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        # Upper-left sparkle
        painter.drawEllipse(QRectF(iris_cx - highlight_w - 2*scale, iris_cy - highlight_h - 2*scale, highlight_w * 2, highlight_h * 2))
        
        # Lower-right secondary soft sparkle
        sec_w = 1.8 * scale
        sec_h = 1.8 * scale * blink_progress
        painter.setBrush(QBrush(QColor(255, 255, 255, 140)))
        painter.drawEllipse(QRectF(iris_cx + 2*scale, iris_cy + 2*scale, sec_w * 2, sec_h * 2))
        
        # Restore clip
        painter.setClipping(False)

        # 5. Draw Eyelashes & Eyelids (Upper and Lower curves)
        # Upper thick eyelash line
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(35, 30, 70), 2.5 * scale, Qt.SolidLine, Qt.RoundCap))
        upper_lash = QPainterPath()
        upper_lash.moveTo(ex - ew * 1.05, ey - curr_eh * 0.1)
        upper_lash.quadTo(ex, ey - curr_eh - 1.5 * scale, ex + ew * 1.05, ey - curr_eh * 0.1)
        painter.drawPath(upper_lash)
        
        # Outer thick eyeliner corner accent
        accent = QPainterPath()
        if is_left:
            accent.moveTo(ex - ew * 1.05, ey - curr_eh * 0.1)
            accent.quadTo(ex - ew * 1.2, ey - curr_eh * 0.3, ex - ew * 0.9, ey - curr_eh * 0.5)
        else:
            accent.moveTo(ex + ew * 1.05, ey - curr_eh * 0.1)
            accent.quadTo(ex + ew * 1.2, ey - curr_eh * 0.3, ex + ew * 0.9, ey - curr_eh * 0.5)
        painter.drawPath(accent)

        # Lower lash line
        painter.setPen(QPen(QColor(35, 30, 70, 150), 1.3 * scale))
        lower_lash = QPainterPath()
        lower_lash.moveTo(ex - ew * 0.7, ey + curr_eh * 0.8)
        lower_lash.quadTo(ex, ey + curr_eh + 1.0 * scale, ex + ew * 0.7, ey + curr_eh * 0.8)
        painter.drawPath(lower_lash)

        painter.restore()

    def _draw_vector_mouth(self, painter, center_pt, mouth_open, y_breath):
        """Draws dynamic anti-aliased lips, cavity, teeth, and tongue mapping speech state."""
        painter.save()
        scale = self.render_scale
        
        mx = self.offset_x + center_pt.x() * scale
        my = self.offset_y + center_pt.y() * scale + y_breath
        
        mw = 26.0 * scale
        mh = 14.0 * scale
        
        # 1. Closed state
        if mouth_open < 0.06:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(185, 80, 95), 2.2 * scale, Qt.SolidLine, Qt.RoundCap))
            
            # Draw a beautiful closed smile arc
            smile_path = QPainterPath()
            if self.mouth_shape_type == 2:  # Happy smile
                smile_path.moveTo(mx - mw * 0.9, my - 1*scale)
                smile_path.quadTo(mx, my + 3.5 * scale, mx + mw * 0.9, my - 1*scale)
                # corners
                smile_path.moveTo(mx - mw * 0.9, my - 1*scale)
                smile_path.lineTo(mx - mw * 0.97, my - 2.5*scale)
                smile_path.moveTo(mx + mw * 0.9, my - 1*scale)
                smile_path.lineTo(mx + mw * 0.97, my - 2.5*scale)
            else:  # Neutral smile
                smile_path.moveTo(mx - mw * 0.85, my)
                smile_path.quadTo(mx, my + 1.8 * scale, mx + mw * 0.85, my)
            painter.drawPath(smile_path)
            painter.restore()
            return

        # 2. Open state (Animate cavity + details)
        open_h = mh * mouth_open * 1.1
        open_w = mw * (0.95 + 0.15 * math.sin(self.tick * 0.1))
        
        # Generate mouth cavity mask path
        cavity = QPainterPath()
        cavity.moveTo(mx - open_w, my)
        
        # Shape curves based on phonetic shape type
        if self.mouth_shape_type == 1:  # Round O shape
            r_w = open_w * 0.75
            cavity.cubicTo(mx - r_w, my - open_h * 1.1, mx + r_w, my - open_h * 1.1, mx + r_w, my)
            cavity.cubicTo(mx + r_w, my + open_h * 1.1, mx - r_w, my + open_h * 1.1, mx - r_w, my)
        else:  # Open smile cavity
            cavity.quadTo(mx, my - open_h * 0.6, mx + open_w, my)
            cavity.cubicTo(mx + open_w * 0.85, my + open_h * 1.4, mx - open_w * 0.85, my + open_h * 1.4, mx - open_w, my)
        
        # Fill cavity (Deep red interior)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(115, 20, 32)))  # Deep dark wine cavity color
        painter.drawPath(cavity)

        # Draw details inside the cavity
        painter.setClipPath(cavity)
        
        # Draw Tongue (Soft pink ellipse at the bottom)
        tongue_y = my + open_h * 0.4
        tongue_h = open_h * 0.7
        tongue_w = open_w * 0.75
        painter.setBrush(QBrush(QColor(235, 125, 140)))
        painter.drawEllipse(QRectF(mx - tongue_w, tongue_y - tongue_h, tongue_w * 2, tongue_h * 2))

        # Draw Teeth (White arc along the upper ceiling)
        teeth_h = open_h * 0.28
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        teeth_path = QPainterPath()
        teeth_path.moveTo(mx - open_w * 0.9, my - teeth_h)
        teeth_path.quadTo(mx, my + teeth_h * 0.5, mx + open_w * 0.9, my - teeth_h)
        teeth_path.lineTo(mx + open_w * 0.9, my - open_h)
        teeth_path.lineTo(mx - open_w * 0.9, my - open_h)
        teeth_path.closeSubpath()
        painter.drawPath(teeth_path)

        # Restore clip
        painter.setClipping(False)

        # 3. Draw lips outline over the cavity (Smooth lip lines)
        painter.setPen(QPen(QColor(185, 75, 90), 2.2 * scale, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(cavity)

        # Draw subtle upper/lower lip shading highlights
        painter.restore()
