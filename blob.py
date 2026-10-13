import sys
import os

# Ensure pythonw does not crash on None stdout/stderr in Windows GUI mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import json
import random
import io
import wave
import webbrowser
import pyautogui
import pyperclip
import ollama
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


# ----------------- Worker Thread for Ollama -----------------
class AIWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        prompt = f"""You are a cute and smart desktop assistant blob named Blob.
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


# ----------------- Worker Thread for Voice Recording & STT -----------------
class VoiceWorker(QThread):
    text_ready = pyqtSignal(str)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, duration=4, samplerate=16000):
        super().__init__()
        self.duration = duration
        self.samplerate = samplerate

    def run(self):
        try:
            self.status_update.emit("Listening... 🎙️")
            recording = sd.rec(
                int(self.duration * self.samplerate),
                samplerate=self.samplerate,
                channels=1,
                dtype='int16'
            )
            sd.wait()
            self.status_update.emit("Recognizing... ⏳")

            # Convert numpy audio buffer into standard WAV in memory
            byte_io = io.BytesIO()
            with wave.open(byte_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.samplerate)
                wf.writeframes(recording.tobytes())
            byte_io.seek(0)

            recognizer = sr.Recognizer()
            with sr.AudioFile(byte_io) as source:
                audio = recognizer.record(source)

            # High-accuracy online Google STT (0% CPU impact)
            text = recognizer.recognize_google(audio)
            self.text_ready.emit(text)
        except sr.UnknownValueError:
            self.error.emit("Didn't catch that! Speak again?")
        except Exception as e:
            self.error.emit(f"Mic error: {str(e)[:30]}")


# ----------------- Worker Thread for Cute Text-to-Speech -----------------
class TTSWorker(QThread):
    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)  # Cheerful friendly pace
            voices = engine.getProperty('voices')
            for v in voices:
                if "zira" in v.name.lower() or "female" in v.name.lower() or "eva" in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break
            engine.say(self.text)
            engine.runAndWait()
        except Exception:
            pass


# ----------------- 3D Desktop Blob Widget -----------------
class CuteBlobWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Top-level frameless, always-on-top, translucent tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(260, 340)

        self.emotion = "idle"
        self.old_pos = None
        self.pending_payload = ""
        self.is_recording = False

        # --- UI Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 10)
        main_layout.setSpacing(6)

        # 1. 3D WebGL Viewport (Three.js jelly model with real-time physics)
        self.web_view = QWebEngineView(self)
        self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.web_view.setStyleSheet("background: transparent; border: none;")
        self.web_view.setFixedHeight(210)

        # Load local Three.js 3D scene
        html_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "blob3d.html"))
        self.web_view.load(QUrl.fromLocalFile(html_file))
        main_layout.addWidget(self.web_view)

        # 2. Cute Speech Bubble / Status Caption
        self.speech_lbl = QLabel("Hi! I'm Blob ✨", self)
        self.speech_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speech_lbl.setWordWrap(True)
        self.speech_lbl.setStyleSheet("""
            QLabel {
                color: #2D3748; 
                font-weight: 700; 
                font-size: 11px;
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid rgba(226, 232, 240, 0.8);
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        main_layout.addWidget(self.speech_lbl)

        # 3. Input & Voice Controls Bar
        control_bar = QHBoxLayout()
        control_bar.setSpacing(6)

        # Rounded modern input box
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Tell Blob what to do...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid #CBD5E0;
                border-radius: 14px;
                padding: 6px 10px;
                font-size: 11px;
                color: #1A202C;
            }
            QLineEdit:focus {
                border: 2px solid #9F7AEA;
            }
        """)
        self.input_field.returnPressed.connect(self.start_ai_task)
        control_bar.addWidget(self.input_field)

        # Built-in Microphone Button (Voice-To-Chat)
        self.mic_btn = QPushButton("🎙️", self)
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setToolTip("Click to speak with Blob")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid #CBD5E0;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #EDF2F7;
                border: 2px solid #9F7AEA;
            }
            QPushButton:pressed {
                background: #E2E8F0;
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_voice_record)
        control_bar.addWidget(self.mic_btn)

        main_layout.addLayout(control_bar)

        # Return to idle after actions timer
        self.reset_timer = QTimer(self)
        self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self.set_idle)

    # --- 3D Emotion & Physics Synchronization ---
    def set_emotion(self, emotion):
        self.emotion = emotion
        self.web_view.page().runJavaScript(f"window.setEmotion('{emotion}');")

    def set_idle(self):
        self.set_emotion("idle")
        self.speech_lbl.setText("I'm ready! ✨")

    # --- Mouse Dragging & Cursor Tracking in 3D ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            self.web_view.page().runJavaScript("window.triggerJiggle(0.35);")

    def mouseMoveEvent(self, event):
        # Calculate normalized mouse coordinates for 3D eye tracking
        norm_x = event.position().x() / self.width()
        norm_y = event.position().y() / self.height()
        self.web_view.page().runJavaScript(f"window.setMousePos({norm_x:.2f}, {norm_y:.2f});")

        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # --- Voice-to-Chat (Microphone) ---
    def toggle_voice_record(self):
        if self.is_recording:
            return

        self.is_recording = True
        self.mic_btn.setText("🔴")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: #FED7D7;
                border: 2px solid #E53E3E;
                border-radius: 16px;
                font-size: 14px;
            }
        """)
        self.set_emotion("thinking")
        self.speech_lbl.setText("Listening... 🎙️")

        self.voice_worker = VoiceWorker(duration=4)
        self.voice_worker.status_update.connect(self.on_voice_status)
        self.voice_worker.text_ready.connect(self.on_voice_success)
        self.voice_worker.error.connect(self.on_voice_error)
        self.voice_worker.start()

    def on_voice_status(self, msg):
        self.speech_lbl.setText(msg)

    def on_voice_success(self, recognized_text):
        self.reset_mic_button()
        self.input_field.setText(recognized_text)
        self.speech_lbl.setText(f'Heard: "{recognized_text}"')
        # Automatically process the voice command with Ollama
        QTimer.singleShot(600, self.start_ai_task)

    def on_voice_error(self, err_msg):
        self.reset_mic_button()
        self.set_emotion("surprised")
        self.speech_lbl.setText(err_msg)
        self.reset_timer.start(3500)

    def reset_mic_button(self):
        self.is_recording = False
        self.mic_btn.setText("🎙️")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid #CBD5E0;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #EDF2F7;
                border: 2px solid #9F7AEA;
            }
        """)

    # --- AI Processing ---
    def start_ai_task(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self.input_field.clear()
        self.set_emotion("thinking")
        self.speech_lbl.setText("Thinking... 💭")

        self.worker = AIWorker(text)
        self.worker.finished.connect(self.on_ai_success)
        self.worker.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_success(self, data):
        action = data.get("action", "chat")
        payload = data.get("payload", "")
        emotion = data.get("emotion", "happy")
        speech = data.get("speech", "Done!")

        self.set_emotion(emotion)
        self.speech_lbl.setText(speech)

        # Speak back with cute TTS voice in background
        if speech:
            self.tts = TTSWorker(speech)
            self.tts.start()

        # 1. Open Website / URL
        if action == "open_url":
            webbrowser.open(payload)
            self.reset_timer.start(4500)

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
            self.reset_timer.start(4500)

        # 3. Type text into user's active window
        elif action == "type_text":
            self.pending_payload = payload
            self.speech_lbl.setText("Click text box now! (2s)")
            QTimer.singleShot(2000, self.execute_typing)

        # 4. Standard Chat
        else:
            self.speech_lbl.setText(payload[:36] if payload else speech)
            self.reset_timer.start(6000)

    def execute_typing(self):
        pyperclip.copy(self.pending_payload)
        pyautogui.hotkey('ctrl', 'v')
        self.speech_lbl.setText("Finished writing! ✍️")
        self.reset_timer.start(3500)

    def on_ai_error(self, err_msg):
        self.set_emotion("surprised")
        self.speech_lbl.setText("Oops, error!")
        print("AI Error:", err_msg)
        self.reset_timer.start(4000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    blob = CuteBlobWidget()

    # Position in bottom-right corner of available screen geometry (above taskbar)
    screen_geo = app.primaryScreen().availableGeometry()
    blob.move(screen_geo.width() - 280, screen_geo.height() - 380)

    blob.show()
    blob.raise_()
    blob.activateWindow()

    sys.exit(app.exec())