import sys
import os
import json
import random
import webbrowser
import pyautogui
import pyperclip
import ollama
from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel
)

# ----------------- Worker Thread for Ollama -----------------
class AIWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        prompt = f"""You are a smart desktop assistant blob named Jarvis.
Analyze the user command and return ONLY a valid JSON object matching this schema:
{{
  "action": "open_url" | "open_app" | "type_text" | "chat",
  "payload": "<url, app name, text to type, or response>",
  "emotion": "happy" | "thinking" | "typing" | "surprised",
  "speech": "<short cute phrase under 6 words>"
}}

Rules:
- If user wants antigravity: action is "open_url", payload is "https://mrdoob.com/projects/chromeexperiments/google-gravity/"
- If user asks to open common apps (notepad, calculator, cmd, explorer): action is "open_app"
- If user asks to write, type, or generate a prompt/email/code: action is "type_text", emotion is "typing"
- If user asks a general question: action is "chat", emotion is "happy"

User input: "{self.user_text}"
"""
        try:
            # Force JSON format so 3B model adheres strictly
            res = ollama.chat(
                model='qwen2.5:3b',
                format='json',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.2}
            )
            raw = res['message']['content'].strip()
            data = json.loads(raw)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


# ----------------- Cute Blob Window -----------------
class CuteBlobWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless, transparent floating overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(240, 270)

        # Animation states
        self.emotion = "idle"  # idle, thinking, typing, happy, surprised
        self.radius_offset = 0.0
        self.pulse_dir = 1.0
        self.is_blinking = False
        self.blink_counter = 0
        self.old_pos = None
        self.pending_payload = ""

        # UI Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 160, 12, 10)

        # Cute speech bubble / Status caption
        self.speech_lbl = QLabel("Hi! I'm Jarvis ✨", self)
        self.speech_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speech_lbl.setStyleSheet("""
            color: #2D3748; 
            font-weight: 700; 
            font-size: 11px;
            background: rgba(255, 255, 255, 0.85);
            border-radius: 8px;
            padding: 3px;
        """)
        layout.addWidget(self.speech_lbl)

        # Rounded modern input box
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Tell me what to do...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid #CBD5E0;
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
                color: #1A202C;
            }
            QLineEdit:focus {
                border: 2px solid #805AD5;
            }
        """)
        self.input_field.returnPressed.connect(self.start_ai_task)
        layout.addWidget(self.input_field)

        # 30 FPS pulse & blink timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(33)

        # Return to idle after actions
        self.reset_timer = QTimer(self)
        self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self.set_idle)

    # --- Animations & Facial Expressions ---
    def update_animation(self):
        # Breathing pulse
        speed = 0.4 if self.emotion == "thinking" else 0.2
        self.radius_offset += speed * self.pulse_dir
        if abs(self.radius_offset) > 5:
            self.pulse_dir *= -1

        # Random natural blink
        self.blink_counter += 1
        if self.blink_counter > 100:
            if random.random() < 0.05:
                self.is_blinking = True
                if self.blink_counter > 106:
                    self.is_blinking = False
                    self.blink_counter = 0

        self.update()

    def set_idle(self):
        self.emotion = "idle"
        self.speech_lbl.setText("I'm ready! ✨")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 120, 75
        r = 48 + self.radius_offset

        # 1. Body Color based on Emotion
        color_map = {
            "idle": QColor(214, 188, 250),       # Soft lilac
            "thinking": QColor(251, 211, 141),   # Warm golden orange
            "typing": QColor(144, 205, 244),     # Tech cyan
            "happy": QColor(251, 182, 206),      # Sweet pink
            "surprised": QColor(198, 246, 213)   # Mint green
        }
        body_color = color_map.get(self.emotion, color_map["idle"])

        painter.setBrush(QBrush(body_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # 2. Cheeks (Blush)
        painter.setBrush(QBrush(QColor(245, 101, 101, 140)))
        painter.drawEllipse(cx - 30, cy + 6, 12, 7)
        painter.drawEllipse(cx + 18, cy + 6, 12, 7)

        # 3. Eyes & Expressions
        eye_color = QColor(45, 55, 72)
        painter.setPen(QPen(eye_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QBrush(eye_color))

        if self.is_blinking:
            # Closed eyes (flat line)
            painter.drawLine(cx - 20, cy - 4, cx - 10, cy - 4)
            painter.drawLine(cx + 10, cy - 4, cx + 20, cy - 4)

        elif self.emotion == "happy":
            # Happy smiling eyes (^ ^)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(cx - 22, cy - 12, 14, 12, 30 * 16, 120 * 16)
            painter.drawArc(cx + 8, cy - 12, 14, 12, 30 * 16, 120 * 16)

        elif self.emotion == "thinking":
            # Looking up into thoughts
            painter.drawEllipse(cx - 16, cy - 12, 8, 9)
            painter.drawEllipse(cx + 12, cy - 12, 8, 9)
            # Highlights
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(cx - 14, cy - 11, 3, 3)
            painter.drawEllipse(cx + 14, cy - 11, 3, 3)

        elif self.emotion == "typing":
            # Looking down at work
            painter.drawEllipse(cx - 16, cy + 1, 8, 8)
            painter.drawEllipse(cx + 8, cy + 1, 8, 8)

        else:
            # Standard cute big eyes
            painter.drawEllipse(cx - 18, cy - 7, 9, 11)
            painter.drawEllipse(cx + 9, cy - 7, 9, 11)
            # Sparkle shine
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - 16, cy - 6, 3, 4)
            painter.drawEllipse(cx + 11, cy - 6, 3, 4)

        # 4. Cute Mouth
        painter.setPen(QPen(eye_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.emotion == "happy":
            # Wide smile
            painter.drawArc(cx - 7, cy + 2, 14, 10, 200 * 16, 140 * 16)
        elif self.emotion == "surprised":
            # Little :o mouth
            painter.setBrush(QBrush(eye_color))
            painter.drawEllipse(cx - 3, cy + 8, 6, 8)
        else:
            # Gentle smile
            painter.drawArc(cx - 6, cy + 4, 12, 8, 200 * 16, 140 * 16)

    # --- Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # --- AI Processing ---
    def start_ai_task(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self.input_field.clear()
        self.emotion = "thinking"
        self.speech_lbl.setText("Thinking...")
        self.update()

        # Run model asynchronously
        self.worker = AIWorker(text)
        self.worker.finished.connect(self.on_ai_success)
        self.worker.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_success(self, data):
        action = data.get("action", "chat")
        payload = data.get("payload", "")
        self.emotion = data.get("emotion", "happy")
        speech = data.get("speech", "Done!")

        self.speech_lbl.setText(speech)
        self.update()

        # 1. Open Website / URL
        if action == "open_url":
            webbrowser.open(payload)
            self.reset_timer.start(4000)

        # 2. Launch Windows Application
        elif action == "open_app":
            app_name = payload.lower()
            if "calc" in app_name:
                os.system("start calc")
            elif "note" in app_name:
                os.system("start notepad")
            elif "cmd" in app_name:
                os.system("start cmd")
            elif "explorer" in app_name or "file" in app_name:
                os.system("start explorer")
            else:
                os.system(f"start {app_name}")
            self.reset_timer.start(4000)

        # 3. Type text into user's active window
        elif action == "type_text":
            self.pending_payload = payload
            self.speech_lbl.setText("Click text box now! (2s)")
            # Wait 2 seconds so user can click Notepad or input box
            QTimer.singleShot(2000, self.execute_typing)

        # 4. Standard Chat
        else:
            self.speech_lbl.setText(payload[:28] if payload else speech)
            self.reset_timer.start(6000)

    def execute_typing(self):
        # Quick clipboard paste preserves multiline format cleanly
        pyperclip.copy(self.pending_payload)
        pyautogui.hotkey('ctrl', 'v')
        self.speech_lbl.setText("Finished writing! ✍️")
        self.reset_timer.start(3500)

    def on_ai_error(self, err_msg):
        self.emotion = "surprised"
        self.speech_lbl.setText("Oops, error!")
        print("AI Error:", err_msg)
        self.reset_timer.start(4000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    blob = CuteBlobWidget()
    
    # Position in bottom-right corner of screen
    screen_geo = app.primaryScreen().geometry()
    blob.move(screen_geo.width() - 270, screen_geo.height() - 360)
    blob.show()
    sys.exit(app.exec())