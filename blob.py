import sys
import os

# Ensure pythonw does not crash on None stdout/stderr in Windows GUI mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import json
import random
import time
import io
import wave
import difflib
import webbrowser
import pyautogui
import pyperclip
import ollama
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


# ----------------- Intelligent Typo & Spell Corrector -----------------
APP_DICTIONARY = {
    "camera": ["camera", "camara", "camer", "camra", "webcam", "video", "cam"],
    "notepad": ["notepad", "notepd", "notpad", "notepade", "notes", "text editor"],
    "calc": ["calculator", "calcolator", "calcualtor", "calc", "clac", "calculate"],
    "explorer": ["explorer", "explor", "files", "folder", "my pc", "this pc"],
    "paint": ["paint", "pant", "draw", "mspaint"],
    "settings": ["settings", "settngs", "setting", "config", "control panel"],
    "cmd": ["cmd", "terminal", "command prompt", "console", "powershell"],
    "chrome": ["chrome", "croem", "chrom", "browser", "internet", "google"],
    "antigravity": ["antigravity", "gravity", "anti gravity", "google gravity"]
}

VERB_DICTIONARY = {
    "open": ["open", "opn", "oen", "launch", "start", "run", "sho", "show"]
}

def auto_correct_command(text: str) -> str:
    """Intelligently detects spelling mistakes like 'oen camara' and fixes them to 'open camera'."""
    tokens = text.lower().strip().split()
    if not tokens:
        return text

    corrected_tokens = []
    for token in tokens:
        matched = False
        # 1. Check action verbs
        for standard_verb, variants in VERB_DICTIONARY.items():
            matches = difflib.get_close_matches(token, variants, n=1, cutoff=0.68)
            if matches or token in variants:
                corrected_tokens.append(standard_verb)
                matched = True
                break
        if matched:
            continue

        # 2. Check app/target names
        for standard_app, variants in APP_DICTIONARY.items():
            matches = difflib.get_close_matches(token, variants, n=1, cutoff=0.68)
            if matches or token in variants:
                corrected_tokens.append(standard_app)
                matched = True
                break
        if matched:
            continue

        # Keep original token if no close dictionary match
        corrected_tokens.append(token)

    return " ".join(corrected_tokens)


# ----------------- Worker Thread for Ollama -----------------
class AIWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, user_text):
        super().__init__()
        # Pre-clean typos before sending to AI
        self.user_text = auto_correct_command(user_text)

    def run(self):
        prompt = f"""You are a cute, intelligent desktop assistant blob named Blob.
Analyze the user command and return ONLY a valid JSON object matching this schema:
{{
  "action": "open_url" | "open_app" | "type_text" | "chat",
  "payload": "<url, app name, text to type, or response>",
  "emotion": "happy" | "thinking" | "typing" | "angry" | "love" | "cry" | "scared",
  "speech": "<short cute phrase under 6 words>"
}}

CRITICAL RULES:
- Auto-correct any spelling mistakes, phonetic words, or speech-to-text typos (e.g. "oen camara" or "camara" -> "camera", "calcolator" -> "calc", "notepd" -> "notepad").
- Valid app names for payload: "camera", "calc", "notepad", "cmd", "explorer", "paint", "settings", "chrome".
- If user wants antigravity: action is "open_url", payload is "https://mrdoob.com/projects/chromeexperiments/google-gravity/"
- If user asks to open common apps: action is "open_app"
- If user asks to write/type text: action is "type_text", emotion is "typing"
- If user expresses love/thanks: emotion is "love"
- If user is upset: emotion is "cry" or "scared"
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
        self.last_move_time = None
        self.pending_payload = ""
        self.is_recording = False

        # --- UI Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 10)
        main_layout.setSpacing(6)

        # 1. 3D WebGL Viewport (Three.js jelly model with Newton's laws physics)
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
                border: 2px solid #38BDF8;
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
                border: 2px solid #38BDF8;
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

    # --- Newton's Laws of Motion: Inertia & Elastic Spring Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            self.last_move_time = time.time()
            self.web_view.page().runJavaScript("window.triggerPoke();")

    def mouseMoveEvent(self, event):
        current_pos = event.globalPosition().toPoint()
        current_time = time.time()

        if self.old_pos and self.last_move_time:
            dt = max(0.001, current_time - self.last_move_time)
            delta = current_pos - self.old_pos
            # Calculate movement velocity (pixels / ms)
            vx = (delta.x() / dt) / 80.0
            vy = (delta.y() / dt) / 80.0
            self.move(self.x() + delta.x(), self.y() + delta.y())

            # Newton's 1st Law (Inertia): Body leans & squishes opposite to velocity
            self.web_view.page().runJavaScript(f"window.onWindowMove({vx:.2f}, {vy:.2f});")

        self.old_pos = current_pos
        self.last_move_time = current_time

        # 3D Eye Tracking follows cursor
        norm_x = event.position().x() / self.width()
        norm_y = event.position().y() / self.height()
        self.web_view.page().runJavaScript(f"window.setMousePos({norm_x:.2f}, {norm_y:.2f});")

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.last_move_time = None
        # Newton's 2nd & 3rd Law: Sudden stop transfers stored momentum into elastic spring rebound!
        self.web_view.page().runJavaScript("window.onWindowStop();")

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
        # Automatically correct any mishearings / typos
        cleaned = auto_correct_command(recognized_text)
        self.input_field.setText(cleaned)
        self.speech_lbl.setText(f'Heard: "{cleaned}"')
        QTimer.singleShot(600, self.start_ai_task)

    def on_voice_error(self, err_msg):
        self.reset_mic_button()
        self.set_emotion("scared")
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
                border: 2px solid #38BDF8;
            }
        """)

    # --- AI Processing ---
    def start_ai_task(self):
        raw_text = self.input_field.text().strip()
        if not raw_text:
            return

        # Auto-correct spelling mistakes before execution
        corrected_text = auto_correct_command(raw_text)
        self.input_field.clear()
        self.set_emotion("thinking")
        self.speech_lbl.setText("Thinking... 💭")

        self.worker = AIWorker(corrected_text)
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

        # 2. Launch Windows Application (with Typo-tolerant Fallbacks)
        elif action == "open_app":
            app_name = payload.lower()
            if "camera" in app_name or "cam" in app_name:
                os.system("start microsoft.windows.camera:")
            elif "calc" in app_name:
                os.system("start calc")
            elif "note" in app_name:
                os.system("start notepad")
            elif "cmd" in app_name or "terminal" in app_name:
                os.system("start cmd")
            elif "explorer" in app_name or "file" in app_name:
                os.system("start explorer")
            elif "paint" in app_name:
                os.system("start mspaint")
            elif "setting" in app_name:
                os.system("start ms-settings:")
            elif "chrom" in app_name:
                os.system("start chrome")
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
        self.set_emotion("scared")
        self.speech_lbl.setText("Oops, error!")
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