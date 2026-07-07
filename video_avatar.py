import os
import math
import random
import logging
from PySide6.QtCore import Qt, QUrl, QSize, QPointF, QRectF, QTimer
from PySide6.QtWidgets import QWidget, QStackedLayout, QLabel
from PySide6.QtGui import QPixmap, QMovie, QFont, QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPen, QBrush
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

class RealisticHumanAvatar(QWidget):
    """
    Ultra-premium 2D Digital Human Presenter.
    Renders a realistic human female avatar with 3D gradient shading,
    flowing physical hair sways, natural eye blinks, detailed mouth/teeth sync,
    and smooth arm gestures (pointing, waving, thinking) at 60 FPS.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tick = 0
        
        # State control
        self.state = "idle"
        self.is_speaking = False
        
        # Physics phases
        self._breathing_phase = 0.0
        self._gesture_phase = 0.0
        self._nod_phase = 0.0
        self._head_tilt = 0.0
        
        # Eye Blink State
        self.blink_timer = 0
        self.blink_frame = 0  # 0: open, 1: half, 2: closed, 3: half
        
        # Mouth Speaking State
        self.mouth_open_factor = 0.0
        self.mouth_phase = 0.0
        
        # Hand & Head target alignment
        self.head_tilt_target = 0.0
        self.head_y_target = 155.0
        self.head_y_current = 155.0
        
        # Timer for 60 FPS physics loops
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)  # ~60 FPS

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking

    def set_state(self, state: str):
        self.state = state.lower()

    def update_physics(self):
        self.tick += 1
        
        # 1. Breathing Cycle (chest and shoulder bobs)
        self._breathing_phase += 0.04
        self._gesture_phase += 0.06
        
        # 2. Nodding when listening
        if self.state == "listening":
            self._nod_phase += 0.08
        else:
            self._nod_phase = 0.0
            
        # 3. Head Tilt and bob coordinates based on states
        if self.state == "thinking":
            self.head_tilt_target = 4.5
        elif self.state == "listening":
            self.head_tilt_target = -3.0 + math.sin(self._nod_phase) * 2.0
        elif self.state == "greeting":
            self.head_tilt_target = -2.0
        else:
            self.head_tilt_target = 0.0
            
        self._head_tilt += (self.head_tilt_target - self._head_tilt) * 0.1
        
        # 4. Blink cycle logic
        self.blink_timer += 1
        if self.blink_frame == 0:
            # Trigger a blink randomly every 90-180 ticks
            if self.blink_timer > random.randint(90, 180):
                self.blink_frame = 1
                self.blink_timer = 0
        elif self.blink_frame == 1:  # closing
            self.blink_frame = 2
        elif self.blink_frame == 2:  # closed
            self.blink_frame = 3
        elif self.blink_frame == 3:  # opening
            self.blink_frame = 0
            
        # 5. Lip Sync Mouth opening sizes
        if self.is_speaking:
            self.mouth_phase += 0.25
            self.mouth_open_factor = 0.4 + 0.6 * math.sin(self.mouth_phase)
        else:
            self.mouth_open_factor += (0.0 - self.mouth_open_factor) * 0.15
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        rect = self.rect()
        cx = rect.width() / 2
        
        # Background Space Glow
        self._draw_background(painter, rect)
        
        # Setup breathing offset
        breath_y = math.sin(self._breathing_phase) * 2.5
        cy = self.head_y_current + breath_y
        
        # Scale/Center agent inside container dynamically
        painter.save()
        scale = min(rect.width() / 360.0, rect.height() / 480.0) * 0.95
        scale = max(0.6, min(1.2, scale))
        dx = cx - (180 * scale)
        dy = (rect.height() - (480 * scale)) / 2
        painter.translate(dx, dy)
        painter.scale(scale, scale)
        
        # Draw Character Layers
        self._draw_hair_back(painter)
        self._draw_body(painter, breath_y)
        self._draw_neck(painter)
        self._draw_head(painter)
        self._draw_eyes(painter)
        self._draw_nose(painter)
        self._draw_mouth(painter)
        self._draw_hair_front(painter)
        self._draw_arms(painter, breath_y)
        
        painter.restore()

    def _draw_background(self, painter, rect):
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, QColor(14, 16, 42))
        grad.setColorAt(1.0, QColor(6, 8, 18))
        painter.fillRect(rect, grad)
        
        # Ambient backdrop lighting
        glow = QRadialGradient(rect.width() / 2, rect.height() * 0.4, rect.width() * 0.5)
        glow.setColorAt(0.0, QColor(48, 64, 150, 40))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, QBrush(glow))

    def _draw_hair_back(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt * 0.5)
        
        # Back hair silhouette with rich brown gradient shading
        hair_grad = QLinearGradient(0, -60, 0, 180)
        hair_grad.setColorAt(0.0, QColor(95, 60, 42))    # warm brown
        hair_grad.setColorAt(0.5, QColor(70, 42, 28))    # dark brown
        hair_grad.setColorAt(1.0, QColor(48, 28, 18))    # deep shadow
        
        path = QPainterPath()
        path.moveTo(-65, -30)
        path.cubicTo(-95, 20, -75, 160, -50, 200)
        path.lineTo(50, 200)
        path.cubicTo(75, 160, 95, 20, 65, -30)
        path.closeSubpath()
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(hair_grad))
        painter.drawPath(path)
        painter.restore()

    def _draw_body(self, painter, breath_y):
        painter.save()
        painter.translate(180, 155)
        
        body_top = 62 + breath_y * 0.7
        
        # 1. Navy Blue Blazer Torso Layer
        blazer_grad = QLinearGradient(-90, body_top, 90, body_top + 180)
        blazer_grad.setColorAt(0.0, QColor(25, 45, 110))
        blazer_grad.setColorAt(0.5, QColor(15, 30, 85))
        blazer_grad.setColorAt(1.0, QColor(8, 18, 55))
        
        torso = QPainterPath()
        torso.moveTo(-75, body_top + 10)
        torso.cubicTo(-95, body_top + 30, -90, body_top + 180, -70, body_top + 180)
        torso.lineTo(70, body_top + 180)
        torso.cubicTo(90, body_top + 180, 95, body_top + 30, 75, body_top + 10)
        torso.closeSubpath()
        
        painter.setPen(QPen(QColor(10, 20, 65), 1.2))
        painter.setBrush(QBrush(blazer_grad))
        painter.drawPath(torso)
        
        # 2. Gray Blouse layer underneath
        blouse_grad = QLinearGradient(0, body_top, 0, body_top + 45)
        blouse_grad.setColorAt(0.0, QColor(215, 218, 228))
        blouse_grad.setColorAt(1.0, QColor(170, 172, 182))
        
        blouse = QPainterPath()
        blouse.moveTo(-25, body_top)
        blouse.lineTo(-18, body_top + 32)
        blouse.quadTo(0, body_top + 38, 18, body_top + 32)
        blouse.lineTo(25, body_top)
        blouse.closeSubpath()
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(blouse_grad))
        painter.drawPath(blouse)
        
        # Creases on gray blouse
        painter.setPen(QPen(QColor(140, 142, 152, 90), 1))
        painter.drawLine(0, int(body_top + 15), 0, int(body_top + 32))
        
        # 3. Silver Necklace and pendant
        necklace = QPainterPath()
        necklace.moveTo(-12, body_top + 10)
        necklace.quadTo(0, body_top + 22, 12, body_top + 10)
        painter.setPen(QPen(QColor(225, 228, 238), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(necklace)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 248, 255))
        painter.drawEllipse(QPointF(0, body_top + 22), 2.2, 2.2)
        
        # 4. Blazer Lapels (Left and Right)
        lapel_l = QPainterPath()
        lapel_l.moveTo(-32, body_top - 2)
        lapel_l.lineTo(-14, body_top + 32)
        lapel_l.lineTo(-28, body_top + 32)
        lapel_l.closeSubpath()
        
        lapel_r = QPainterPath()
        lapel_r.moveTo(32, body_top - 2)
        lapel_r.lineTo(14, body_top + 32)
        lapel_r.lineTo(28, body_top + 32)
        lapel_r.closeSubpath()
        
        painter.setPen(QPen(QColor(40, 68, 155), 1.8))
        painter.setBrush(QColor(18, 32, 90))
        painter.drawPath(lapel_l)
        painter.drawPath(lapel_r)
        
        # 5. ID Badge on chest
        badge_x, badge_y = -35, body_top + 35
        painter.setPen(QPen(QColor(140, 150, 180), 1))
        painter.setBrush(QColor(95, 135, 215, 180))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, 16, 22), 2, 2)
        # Badge clip
        painter.setPen(QPen(QColor(180, 190, 210), 1.5))
        painter.drawLine(int(badge_x + 8), int(badge_y), int(badge_x + 8), int(badge_y - 6))
        
        painter.restore()

    def _draw_neck(self, painter):
        painter.save()
        painter.translate(180, 155)
        
        neck_top = 48
        neck_bot = 66
        neck_w = 17
        
        # Shaded Skin Neck
        skin_grad = QLinearGradient(0, neck_top, 0, neck_bot)
        skin_grad.setColorAt(0.0, QColor(245, 208, 195))  # deep neck shadow
        skin_grad.setColorAt(1.0, QColor(255, 224, 210))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(skin_grad))
        painter.drawRect(QRectF(-neck_w, neck_top, neck_w * 2, neck_bot - neck_top))
        
        # Neck shading details
        painter.setBrush(QColor(230, 190, 178, 90))
        painter.drawRect(QRectF(-neck_w, neck_top, 5, neck_bot - neck_top))
        
        painter.restore()

    def _draw_head(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt)
        
        # Face shape
        face = QPainterPath()
        face.moveTo(-54, -60)
        face.cubicTo(-62, -30, -58, 25, -45, 54)
        face.cubicTo(-35, 68, -15, 72, 0, 72)
        face.cubicTo(15, 72, 35, 68, 45, 54)
        face.cubicTo(58, 25, 62, -30, 54, -60)
        face.closeSubpath()
        
        # 3D Soft skin shading
        skin = QRadialGradient(0, -10, 80)
        skin.setColorAt(0.0, QColor(255, 235, 225))
        skin.setColorAt(0.6, QColor(255, 222, 210))
        skin.setColorAt(1.0, QColor(248, 210, 196))
        
        painter.setPen(QPen(QColor(232, 185, 170), 1.2))
        painter.setBrush(QBrush(skin))
        painter.drawPath(face)
        
        # Soft Makeup Blush
        blush_grad_l = QRadialGradient(-35, 25, 22)
        blush_grad_l.setColorAt(0.0, QColor(255, 170, 170, 110))
        blush_grad_l.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        blush_grad_r = QRadialGradient(35, 25, 22)
        blush_grad_r.setColorAt(0.0, QColor(255, 170, 170, 110))
        blush_grad_r.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(blush_grad_l))
        painter.drawEllipse(QPointF(-35, 25), 22, 14)
        
        painter.setBrush(QBrush(blush_grad_r))
        painter.drawEllipse(QPointF(35, 25), 22, 14)
        
        painter.restore()

    def _draw_eyes(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt)
        
        eye_y = -8
        eye_spacing = 28
        
        def draw_individual_eye(cx):
            painter.save()
            painter.translate(cx, eye_y)
            
            # Eyelash crease line (top border)
            painter.setPen(QPen(QColor(52, 32, 25), 2.5))
            painter.setBrush(Qt.NoBrush)
            top_fold = QPainterPath()
            top_fold.moveTo(-18, -2)
            top_fold.quadTo(0, -12, 18, -2)
            painter.drawPath(top_fold)
            
            if self.blink_frame == 0:  # Eye Fully Open
                # 1. White sclera
                sclera = QPainterPath()
                sclera.moveTo(-15, 0)
                sclera.quadTo(0, -7, 15, 0)
                sclera.quadTo(0, 7, -15, 0)
                sclera.closeSubpath()
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawPath(sclera)
                
                # 2. Rich Hazel Iris
                iris_grad = QRadialGradient(0, 0, 9)
                iris_grad.setColorAt(0.0, QColor(50, 120, 200))   # glowing blue/hazel center
                iris_grad.setColorAt(0.5, QColor(32, 64, 130))
                iris_grad.setColorAt(1.0, QColor(14, 25, 60))     # dark rim
                
                painter.setBrush(QBrush(iris_grad))
                painter.drawEllipse(QPointF(0, 0), 9.0, 9.5)
                
                # 3. Dark Pupil
                painter.setBrush(QColor(10, 12, 22))
                painter.drawEllipse(QPointF(0, 0), 4.2, 4.5)
                
                # 4. Highlight Sparkles (Primary and Secondary reflections)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawEllipse(QPointF(-3.5, -3.5), 2.2, 2.2)
                painter.drawEllipse(QPointF(3.5, 3.5), 1.2, 1.2)
                
            elif self.blink_frame in (1, 3):  # Half Closed
                sclera = QPainterPath()
                sclera.moveTo(-15, 0)
                sclera.quadTo(0, -3, 15, 0)
                sclera.quadTo(0, 3, -15, 0)
                sclera.closeSubpath()
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawPath(sclera)
                
                # Hidden Iris
                painter.setBrush(QColor(32, 64, 130))
                painter.drawEllipse(QPointF(0, 0), 7.5, 3.5)
                
            else:  # 2: Fully Closed (blink)
                # Drawing skin fold overlay
                fold = QPainterPath()
                fold.moveTo(-16, -1)
                fold.quadTo(0, 3, 16, -1)
                painter.setPen(QPen(QColor(195, 145, 130), 2.0))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(fold)
                
                # Lash line
                painter.setPen(QPen(QColor(52, 32, 25), 2.5))
                painter.drawLine(-17, 0, 17, 0)
                
            painter.restore()
            
        draw_individual_eye(-eye_spacing)
        draw_individual_eye(eye_spacing)
        
        # Draw elegant curved eyebrows
        painter.setPen(QPen(QColor(85, 52, 38), 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        # Left brow
        brow_l = QPainterPath()
        brow_l.moveTo(-40, -18)
        brow_l.quadTo(-28, -25, -12, -18)
        painter.drawPath(brow_l)
        # Right brow
        brow_r = QPainterPath()
        brow_r.moveTo(12, -18)
        brow_r.quadTo(28, -25, 40, -18)
        painter.drawPath(brow_r)
        
        painter.restore()

    def _draw_nose(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt)
        
        # Soft nose bridge shadow
        painter.setPen(QPen(QColor(230, 180, 165), 1.5, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        
        nose = QPainterPath()
        nose.moveTo(-2, 10)
        nose.lineTo(2, 16)
        nose.lineTo(-2, 20)
        painter.drawPath(nose)
        
        painter.restore()

    def _draw_mouth(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt)
        
        mouth_y = 38
        
        # Calculate size dynamics
        op = self.mouth_open_factor
        mw = 25 + op * 4
        mh = op * 18
        
        # 1. Oral Cavity (Red Throat gradient inside)
        if mh > 2:
            cavity_grad = QRadialGradient(0, mouth_y, mw / 2)
            cavity_grad.setColorAt(0.0, QColor(140, 25, 40))   # deep red throat
            cavity_grad.setColorAt(0.8, QColor(80, 10, 22))    # dark rim
            
            cavity = QPainterPath()
            cavity.moveTo(-mw / 2, mouth_y)
            cavity.cubicTo(-mw / 2, mouth_y - mh / 2, mw / 2, mouth_y - mh / 2, mw / 2, mouth_y)
            cavity.cubicTo(mw / 2, mouth_y + mh / 2, -mw / 2, mouth_y + mh / 2, -mw / 2, mouth_y)
            cavity.closeSubpath()
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(cavity_grad))
            painter.drawPath(cavity)
            
            # 2. Upper Teeth Arch
            teeth_w = mw * 0.7
            teeth_h = max(2.0, mh * 0.22)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(QRectF(-teeth_w / 2, mouth_y - mh / 2 + 0.5, teeth_w, teeth_h), 2, 2)
            
            # 3. Pink Tongue
            tongue_h = max(1.0, mh * 0.3)
            tongue_grad = QLinearGradient(0, mouth_y + mh / 2 - tongue_h, 0, mouth_y + mh / 2)
            tongue_grad.setColorAt(0.0, QColor(245, 125, 140))
            tongue_grad.setColorAt(1.0, QColor(220, 95, 110))
            painter.setBrush(QBrush(tongue_grad))
            painter.drawEllipse(QRectF(-teeth_w * 0.5, mouth_y + mh / 2 - tongue_h, teeth_w, tongue_h + 1))

        # 4. Glossy Lips (outline / cover overlay)
        painter.setPen(QPen(QColor(180, 50, 75), 1.8))
        lip_grad = QLinearGradient(0, mouth_y - 4, 0, mouth_y + 4)
        lip_grad.setColorAt(0.0, QColor(240, 110, 130))   # bright coral lip color
        lip_grad.setColorAt(1.0, QColor(210, 70, 90))
        painter.setBrush(QBrush(lip_grad))
        
        if mh <= 2:
            # Closed friendly smile
            lip_path = QPainterPath()
            lip_path.moveTo(-20, mouth_y)
            lip_path.quadTo(0, mouth_y + 4.5, 20, mouth_y)
            lip_path.quadTo(0, mouth_y + 1.5, -20, mouth_y)
            lip_path.closeSubpath()
            painter.drawPath(lip_path)
        else:
            # Open lips paths
            lip_path = QPainterPath()
            lip_path.moveTo(-mw / 2 - 2, mouth_y)
            # Upper lip curve
            lip_path.cubicTo(-mw / 4, mouth_y - mh / 2 - 2, mw / 4, mouth_y - mh / 2 - 2, mw / 2 + 2, mouth_y)
            # Lower lip curve
            lip_path.cubicTo(mw / 4, mouth_y + mh / 2 + 2, -mw / 4, mouth_y + mh / 2 + 2, -mw / 2 - 2, mouth_y)
            lip_path.closeSubpath()
            painter.drawPath(lip_path)

        painter.restore()

    def _draw_hair_front(self, painter):
        painter.save()
        painter.translate(180, 155)
        painter.rotate(self._head_tilt * 0.7)
        
        hair_grad = QLinearGradient(0, -90, 0, 80)
        hair_grad.setColorAt(0.0, QColor(115, 74, 52))    # Rich brown
        hair_grad.setColorAt(0.7, QColor(95, 60, 42))     # Warm base
        hair_grad.setColorAt(1.0, QColor(70, 42, 28))
        
        highlight = QColor(158, 114, 88)  # soft warm blonde highlights
        sway = math.sin(self._gesture_phase * 0.8) * 1.5
        
        # 1. Front Hair Bangs strands
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(hair_grad))
        
        bangs = QPainterPath()
        bangs.moveTo(-60, -50)
        bangs.cubicTo(-40, -82, 40, -82, 60, -50)
        # Strands falling on forehead
        bangs.cubicTo(50, -22, 42, 0, 36, -5)
        bangs.cubicTo(20, -28, 10, -5, 0, -8)
        bangs.cubicTo(-10, -5, -20, -28, -36, -5)
        bangs.cubicTo(-42, 0, -50, -22, -60, -50)
        bangs.closeSubpath()
        painter.drawPath(bangs)
        
        # 2. Side lock framing (Left and Right)
        lock_l = QPainterPath()
        lock_l.moveTo(-54, -40)
        lock_l.cubicTo(-68, 20, -52, 90 + sway, -45, 120 + sway)
        lock_l.cubicTo(-58, 90 + sway, -62, 20, -54, -40)
        lock_l.closeSubpath()
        
        lock_r = QPainterPath()
        lock_r.moveTo(54, -40)
        lock_r.cubicTo(68, 20, 52, 90 - sway, 45, 120 - sway)
        lock_r.cubicTo(58, 90 - sway, 62, 20, 54, -40)
        lock_r.closeSubpath()
        
        painter.drawPath(lock_l)
        painter.drawPath(lock_r)
        
        # 3. Soft Hair Shine Highlight
        shine = QPainterPath()
        shine.moveTo(-35, -55)
        shine.quadTo(0, -68, 35, -55)
        shine.quadTo(0, -65, -35, -55)
        shine.closeSubpath()
        painter.setBrush(highlight)
        painter.drawPath(shine)
        
        painter.restore()

    def _draw_arms(self, painter, breath_y):
        painter.save()
        painter.translate(180, 155)
        
        sleeve_color = QColor(15, 30, 85)     # Navy sleeve
        skin_color = QColor(255, 222, 210)    # Skin forearm
        body_top = 62 + breath_y * 0.7
        
        # Helper to draw realistic articulated arm segment
        def draw_arm(sh_x, sh_y, el_x, el_y, hd_x, hd_y, state_pointing=False):
            painter.save()
            # Sleeve stroke
            painter.setPen(QPen(sleeve_color, 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(sh_x), int(sh_y), int(el_x), int(el_y))
            # Forearm skin stroke
            painter.setPen(QPen(skin_color, 11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(int(el_x), int(el_y), int(hd_x), int(hd_y))
            # Hand shape (realistic vector hand)
            painter.setPen(Qt.NoPen)
            painter.setBrush(skin_color)
            if state_pointing:
                # Extend pointing hand path
                hand = QPainterPath()
                hand.moveTo(hd_x, hd_y - 4)
                hand.lineTo(hd_x + 12, hd_y - 2)   # pointing finger
                hand.lineTo(hd_x + 4, hd_y + 4)
                hand.lineTo(hd_x - 4, hd_y + 4)
                hand.closeSubpath()
                painter.drawPath(hand)
            else:
                painter.drawEllipse(QPointF(hd_x, hd_y), 8, 8)
            painter.restore()
            
        shoulder_l = (-66, body_top + 12)
        shoulder_r = (66, body_top + 12)
        
        wave = math.sin(self.tick * 0.15)
        gest = math.sin(self._gesture_phase * 2)
        
        # Draw Arms based on current state
        if self.state == "greeting":
            # Right arm waving, left arm resting
            draw_arm(*shoulder_l, -74, body_top + 55, -68, body_top + 105)
            # Waving right arm
            rh_y = body_top - 22 + wave * 22
            draw_arm(*shoulder_r, 82, body_top + 15, 92, rh_y)
            
        elif self.state == "presenting":
            # Left arm resting, right arm extended pointing to presentation slides
            draw_arm(*shoulder_l, -70, body_top + 55, -65, body_top + 105)
            draw_arm(*shoulder_r, 92, body_top + 32, 130 + gest * 4, body_top + 22 + gest * 2, state_pointing=True)
            
        elif self.state in ("speaking", "answering"):
            # Double hands speaking gestures
            draw_arm(*shoulder_l, -75, body_top + 45, -62 + gest * 4, body_top + 75 + gest * 8)
            draw_arm(*shoulder_r, 75, body_top + 42, 62 - gest * 3, body_top + 68 - gest * 6)
            
        elif self.state == "thinking":
            # Left hand on chin, right arm folded
            draw_arm(*shoulder_l, -42, body_top + 32, -14, body_top - 8 + gest * 2)
            draw_arm(*shoulder_r, 52, body_top + 48, 22, body_top + 78)
            
        elif self.state == "listening":
            # Balanced breathing rest
            lean = math.sin(self._nod_phase) * 2.5
            draw_arm(*shoulder_l, -68, body_top + 52 + lean, -62, body_top + 105)
            draw_arm(*shoulder_r, 68, body_top + 52 - lean, 62, body_top + 105)
            
        elif self.state == "farewell":
            # Double waving arms
            draw_arm(*shoulder_l, -80, body_top + 12, -90, body_top - 12 + wave * 18)
            draw_arm(*shoulder_r, 80, body_top + 12, 90, body_top - 12 - wave * 18)
            
        else:  # idle
            # Resting hands in front
            draw_arm(*shoulder_l, -58, body_top + 52, -18, body_top + 88)
            draw_arm(*shoulder_r, 58, body_top + 52, 18, body_top + 88)
            
        painter.restore()

class VideoAvatar(QWidget):
    """
    Hardware-accelerated Digital Human presenter component.
    Supports playing high-fidelity H.264 MP4 videos (e.g. generated via Hedra/HeyGen)
    smoothly at 60 FPS with natural blinks, mouth/teeth movements, and body sways.
    Mutes the video audios automatically to sync seamlessly with real-time multilingual TTS.
    Falls back to a high-fidelity vector digital human (RealisticHumanAvatar) if videos are missing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 480)
        
        # 1. Setup Stacked Layout
        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        
        # Widget 0: Video Player (for real MP4 presenter videos)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 12px;")
        self.stacked_layout.addWidget(self.video_widget)
        
        # Widget 1: Realistic Human Vector Fallback (for real-time rendering)
        self.vector_avatar = RealisticHumanAvatar()
        self.stacked_layout.addWidget(self.vector_avatar)
        
        # 2. Setup PySide6 Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        
        # Mute audio track of video files to support multilingual TTS speech overlay
        self.audio_output.setMuted(True)
        
        # Core Paths
        self.videos_dir = os.path.join(os.path.dirname(__file__), "assets", "videos")
        
        self.current_media_path = ""
        self.current_state = "idle"
        self.current_slide = 0
        self.is_speaking = False
        
        self.init_avatar()

    def init_avatar(self):
        os.makedirs(self.videos_dir, exist_ok=True)
        # Show vector fallback as initial standby
        self.show_static_poster()

    def show_static_poster(self):
        """Switches display index to vector fallback renderer in standby mode."""
        self.stop()
        self.stacked_layout.setCurrentIndex(1)  # Switch to vector fallback
        self.vector_avatar.set_state("idle")
        self.vector_avatar.set_speaking(False)
        self.current_media_path = ""

    def pop_out(self):
        """Called when a visitor is detected."""
        self.set_state("greeting")

    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        self.vector_avatar.set_speaking(is_speaking)
        self._update_avatar_media()

    def set_visitor_position(self, rel_x: float, rel_y: float):
        pass # Gaze tracking is pre-rendered or calculated natively inside the layout

    def set_state(self, state: str, slide_index: int = 0):
        self.current_state = state.lower()
        self.current_slide = slide_index
        self.vector_avatar.set_state(state.lower())
        self._update_avatar_media()

    def _update_avatar_media(self):
        """
        Calculates and loads the target animation source.
        Prioritizes H.264 MP4 videos, falling back to the vector digital human.
        """
        state = self.current_state
        media_filename = ""
        is_looping_state = False

        # Map state and speaking flag to filenames
        if state in ["presenting", "speaking", "answering"]:
            if self.is_speaking:
                media_filename = f"slide{self.current_slide}"
            else:
                media_filename = f"slide{self.current_slide}_silent"
        elif state == "greeting":
            if self.is_speaking:
                media_filename = "greeting"
            else:
                media_filename = "greeting_silent"
        elif state == "thinking":
            media_filename = "thinking"
            is_looping_state = True
        elif state == "listening":
            media_filename = "listening"
            is_looping_state = True
        else:  # idle
            media_filename = "idle"
            is_looping_state = True

        # Check if speaking/greeting is silent, loop it
        if "_silent" in media_filename or media_filename == "idle":
            is_looping_state = True

        # 1. Try to load H.264 MP4 Video first
        mp4_path = os.path.join(self.videos_dir, f"{media_filename}.mp4")
        
        def is_valid_mp4(path):
            return os.path.exists(path) and os.path.getsize(path) > 50 * 1024
        
        # If specific slide video is missing, try fallback speaking.mp4
        if not is_valid_mp4(mp4_path) and ("slide" in media_filename or "greeting" in media_filename):
            if self.is_speaking:
                mp4_path = os.path.join(self.videos_dir, "speaking.mp4")
            else:
                mp4_path = os.path.join(self.videos_dir, "idle.mp4")

        if is_valid_mp4(mp4_path):
            if mp4_path != self.current_media_path:
                logger.info(f"Playing high-definition presenter video: {os.path.basename(mp4_path)}")
                self.current_media_path = mp4_path
                
                # Switch to QVideoWidget
                self.stacked_layout.setCurrentIndex(0)
                
                # Configure Player
                self.player.setSource(QUrl.fromLocalFile(mp4_path))
                if is_looping_state:
                    self.player.setLoops(QMediaPlayer.Infinite)
                else:
                    self.player.setLoops(1)  # Play once for slide presentation
                
                self.player.play()
            return

        # 2. Fall back to Vector Digital Human Presenter
        if self.stacked_layout.currentIndex() != 1:
            self.player.stop()
            self.stacked_layout.setCurrentIndex(1)
            self.current_media_path = ""

    def pause(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.pause()

    def play(self):
        if self.stacked_layout.currentIndex() == 0:
            self.player.play()

    def stop(self):
        self.player.stop()
