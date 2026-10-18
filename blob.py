import sys
import os

# Ensure pythonw does not crash on None stdout/stderr in Windows GUI mode
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "err.log")
if sys.stdout is None:
    sys.stdout = open(log_file_path, "a", encoding="utf-8")
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = open(log_file_path, "a", encoding="utf-8")
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


import json
import random
import time
import io
import wave
import difflib
import webbrowser
import ctypes
from ctypes import wintypes

import pyautogui
import pyperclip
import ollama
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal, QUrl, QObject
from PyQt6.QtGui import QColor, QFont, QCursor, QIcon, QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QPushButton, QMenu, QSystemTrayIcon, QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

try:
    import mouse
    HAS_MOUSE = True
except ImportError:
    HAS_MOUSE = False


# ----------------- Real-Time Global Input Monitor (Bongo Cat Mode) -----------------
class GlobalInputMonitor(QObject):
    """
    Monitors global keyboard typing and mouse clicks across all Windows applications.
    Emits Qt signals to safely drive the 3D cat's paw animations on the Qt main thread.
    """
    key_pressed = pyqtSignal(str)
    mouse_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard_hooked = False
        self.mouse_hooked = False
        self.last_key_time = 0
        self.setup_hooks()

    def setup_hooks(self):
        # 1. Global Keyboard Typing Hook
        if HAS_KEYBOARD:
            try:
                keyboard.on_press(self._handle_key)
                self.keyboard_hooked = True
            except Exception as e:
                print("Global keyboard hook notice:", e)

        # 2. Global Mouse Click Hook
        if HAS_MOUSE:
            try:
                mouse.on_click(lambda: self.mouse_clicked.emit('left'))
                mouse.on_right_click(lambda: self.mouse_clicked.emit('right'))
                self.mouse_hooked = True
            except Exception as e:
                print("Global mouse hook notice:", e)

    def _handle_key(self, event):
        # Throttle to max 35 updates/sec to prevent WebEngine message flooding
        now = time.time()
        if now - self.last_key_time > 0.028:
            self.last_key_time = now
            name = getattr(event, 'name', '') or ''
            self.key_pressed.emit(name)

    def stop(self):
        if HAS_KEYBOARD and self.keyboard_hooked:
            try:
                keyboard.unhook(self._handle_key)
            except Exception:
                pass
        if HAS_MOUSE and self.mouse_hooked:
            try:
                mouse.unhook_all()
            except Exception:
                pass


# ----------------- Multi-Layer Global Hotkey Engine (Alt+C, Ctrl+Space, Ctrl+Shift+B) -----------------
class Win32HotkeyThread(QThread):
    activated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

        HOTKEY_ID_1 = 8888  # Ctrl + Shift + B (Legacy)
        HOTKEY_ID_2 = 8889  # Ctrl + Alt + B (Fallback)
        HOTKEY_ID_3 = 8890  # Alt + C (Fast 1-hand, zero conflicts in VS Code/Chrome!)
        HOTKEY_ID_4 = 8891  # Ctrl + Space (Modern AI Companion standard)

        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_SHIFT = 0x0004
        VK_SPACE = 0x20

        # Pre-initialize thread message queue
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        # Register multi-hotkeys so user has 100% reliable access
        user32.RegisterHotKey(None, HOTKEY_ID_1, MOD_CONTROL | MOD_SHIFT, ord('B'))
        user32.RegisterHotKey(None, HOTKEY_ID_2, MOD_CONTROL | MOD_ALT, ord('B'))
        user32.RegisterHotKey(None, HOTKEY_ID_3, MOD_ALT, ord('C'))
        user32.RegisterHotKey(None, HOTKEY_ID_4, MOD_CONTROL, VK_SPACE)

        try:
            while self.running:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE = 1
                    if msg.message == 0x0312 and (msg.wParam in (HOTKEY_ID_1, HOTKEY_ID_2, HOTKEY_ID_3, HOTKEY_ID_4)):
                        self.activated.emit()
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    self.msleep(25)
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID_1)
            user32.UnregisterHotKey(None, HOTKEY_ID_2)
            user32.UnregisterHotKey(None, HOTKEY_ID_3)
            user32.UnregisterHotKey(None, HOTKEY_ID_4)

    def stop(self):
        self.running = False


class GlobalHotkeyManager(QObject):
    activated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.win32_thread = None
        self.hooked_keyboard = False
        self.setup_hotkeys()

    def setup_hotkeys(self):
        # 1. Primary Low-Level Global Hook (intercepts system-wide without hotkey collision)
        if HAS_KEYBOARD:
            for hk in ['alt+c', 'ctrl+space', 'ctrl+shift+b', 'ctrl+alt+b']:
                try:
                    keyboard.add_hotkey(hk, self._on_triggered)
                    self.hooked_keyboard = True
                except Exception as e:
                    print(f"Keyboard hook for {hk}:", e)

        # 2. Secondary Win32 Fallback Thread
        try:
            self.win32_thread = Win32HotkeyThread()
            self.win32_thread.activated.connect(self.activated)
            self.win32_thread.start()
        except Exception as e:
            print("Win32 hotkey thread fallback:", e)

    def _on_triggered(self):
        self.activated.emit()

    def stop(self):
        if HAS_KEYBOARD and self.hooked_keyboard:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        if self.win32_thread:
            self.win32_thread.stop()


# ----------------- Smart History LineEdit with Up/Down Arrow Recall -----------------
class HistoryLineEdit(QLineEdit):
    escapePressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_idx = -1
        self.temp_text = ""

    def set_history(self, history_list):
        self.history = list(history_list)
        self.history_idx = len(self.history)

    def add_to_history(self, text):
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.history_idx = len(self.history)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            if not self.history:
                return
            if self.history_idx == len(self.history):
                self.temp_text = self.text()
            if self.history_idx > 0:
                self.history_idx -= 1
                self.setText(self.history[self.history_idx])
            return
        elif event.key() == Qt.Key.Key_Down:
            if not self.history:
                return
            if self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.history[self.history_idx])
            elif self.history_idx == len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.temp_text)
            return
        elif event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            return

        super().keyPressEvent(event)


# ----------------- Prompt Sentiment & Emotion Interpreter (Raphael & Rimuru) -----------------
def classify_prompt_emotion(text: str) -> dict:
    """
    Parses conversational prompts and commands to trigger context-aware emotions instantly.
    E.g. 'well done' -> happy/proud celebration; 'angry' -> angry pout; 'love' -> heart eyes.
    """
    t = text.lower().strip()
    if not t:
        return None

    # 1. Praise / Well Done / Appreciation
    praise_patterns = [
        "well done", "good job", "great job", "awesome", "good remorus", "good sphere", "good ai",
        "proud of you", "proud", "amazing", "bravo", "congrat", "yay", "superb",
        "best remorus", "best ai", "thank you", "thanks", "you did great", "love your work"
    ]
    if any(p in t for p in praise_patterns):
        celebrations = [
            "Report: Praise acknowledged. Thank you, Master! ✨",
            "Notice: Optimization affirmed. Dedicated to Master. ✨",
            "Report: Performance parameters operating at 100%. ✨",
            "Notice: Affirmative. Glad to be of assistance, Master."
        ]
        return {
            "action": "celebrate",
            "emotion": "happy",
            "speech": random.choice(celebrations),
            "pet_effect": True
        }

    # 2. Angry / Scolding / Pout
    angry_patterns = [
        "angry", "be angry", "get mad", "mad", "bad remorus", "bad ai",
        "stop it", "shut up", "hate", "annoying", "annoyed", "pout", "bothering"
    ]
    if any(p in t for p in angry_patterns):
        pouts = [
            "Warning: Hostility detected. Recalibrating parameters. 💢",
            "Notice: Anomaly reported. Please specify optimization, Master.",
            "Report: Negative sentiment logged. Corrective action pending."
        ]
        return {
            "action": "chat",
            "emotion": "angry",
            "speech": random.choice(pouts),
            "pet_effect": False
        }

    # 3. Love / Affection / Petting
    love_patterns = [
        "love you", "i love", "cute", "adorable", "pet you", "hug", "kiss", "sweet", "heart"
    ]
    if any(p in t for p in love_patterns):
        loves = [
            "Report: Emotional bond confirmed. Devoted to Master. 💖",
            "Notice: Master's affection detected. Harmonic resonance high. 💕",
            "Report: Remorus core resonance elevated. Always with you, Master. 💖"
        ]
        return {
            "action": "chat",
            "emotion": "love",
            "speech": random.choice(loves),
            "pet_effect": True
        }


    # 4. Privacy / Password / Hide Eyes
    privacy_patterns = [
        "password", "pass", "privacy", "hide eyes", "look away", "dont look", "don't look", "secret", "private"
    ]
    if any(p in t for p in privacy_patterns):
        return {
            "action": "privacy",
            "emotion": "lookaway",
            "speech": "Notice: Privacy sensor engaged. Visual feed severed. 🙈",
            "pet_effect": False
        }

    # 5. Sleepy / Rest
    sleep_patterns = [
        "sleep", "tired", "good night", "bed", "nap", "yawn", "rest"
    ]
    if any(p in t for p in sleep_patterns):
        return {
            "action": "chat",
            "emotion": "idle",
            "speech": "Notice: Entering low-power standby. Sweet dreams, Master. 💤",
            "pet_effect": False
        }

    # 6. Coding / Typing
    typing_patterns = [
        "code", "coding", "program", "type this", "write code", "terminal", "vscode", "work"
    ]
    if any(p in t for p in typing_patterns):
        return {
            "action": "chat",
            "emotion": "typing",
            "speech": "Report: Synthesis initiated. 💻",
            "pet_effect": False
        }

    # 7. Dance / Celebrate
    dance_patterns = [
        "dance", "party", "celebrate", "music", "spin"
    ]
    if any(p in t for p in dance_patterns):
        return {
            "action": "chat",
            "emotion": "happy",
            "speech": "Notice: Commencing celebration sequence! 🎶✨",
            "pet_effect": True
        }


    return None


# ----------------- Persistent Spell & Command Acceleration Cache -----------------
class SpellManager:
    """
    Caches commands, phonetic variations, and typos.
    Matches in <1ms without hitting Ollama LLM, speeding up execution 100x.
    """
    def __init__(self, cache_path=None):
        if cache_path is None:
            cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blob_cache.json")
        self.cache_path = cache_path
        self.spells = {}
        self.history = []
        self.load()

    def load(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.spells = data.get("spells", {})
                    self.history = data.get("history", [])
        except Exception:
            self.spells = {}
            self.history = []

    def save(self):
        try:
            data = {
                "spells": self.spells,
                "history": self.history[-50:]  # Keep last 50
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_history(self, text):
        clean = text.strip()
        if clean and (not self.history or self.history[-1] != clean):
            self.history.append(clean)
            self.save()

    def get_history(self):
        return list(self.history)

    def lookup(self, text: str):
        clean = text.strip().lower()
        if not clean:
            return None

        # 1. Exact match in cached spells
        if clean in self.spells:
            match = self.spells[clean]
            match["count"] = match.get("count", 0) + 1
            self.save()
            return match

        # 2. Fuzzy match against learned spells
        spell_keys = list(self.spells.keys())
        close_matches = difflib.get_close_matches(clean, spell_keys, n=1, cutoff=0.74)
        if close_matches:
            match = self.spells[close_matches[0]]
            self.spells[clean] = dict(match)
            self.spells[clean]["count"] = 1
            self.save()
            return match

        # 3. Built-in Deterministic Rules
        rule_match = self.match_built_in_rules(clean)
        if rule_match:
            self.spells[clean] = dict(rule_match)
            self.spells[clean]["count"] = 1
            self.save()
            return rule_match

        return None

    def learn(self, raw_text: str, data: dict):
        clean = raw_text.strip().lower()
        if clean and data:
            self.spells[clean] = {
                "action": data.get("action", "chat"),
                "payload": data.get("payload", ""),
                "emotion": data.get("emotion", "happy"),
                "speech": data.get("speech", "Done!"),
                "count": self.spells.get(clean, {}).get("count", 0) + 1
            }
            self.save()

    def match_built_in_rules(self, text: str):
        # Privacy / Look Away / Password
        if any(w in text for w in ["look away", "password", "pass", "privacy", "dont look", "peek", "secret"]):
            return {
                "action": "privacy",
                "payload": "lookaway",
                "emotion": "lookaway",
                "speech": "Notice: Privacy sensor engaged. 🙈"
            }

        # Apps
        if any(w in text for w in ["camera", "camara", "camra", "webcam"]):
            return {"action": "open_app", "payload": "camera", "emotion": "happy", "speech": "Notice: Launching Camera. 📷"}
        if any(w in text for w in ["calc", "calculator", "calcolator", "clac"]):
            return {"action": "open_app", "payload": "calc", "emotion": "happy", "speech": "Notice: Launching Calculator. 🔢"}
        if any(w in text for w in ["notepad", "notepd", "notpad", "notes"]):
            return {"action": "open_app", "payload": "notepad", "emotion": "typing", "speech": "Notice: Launching Notepad. 📝"}
        if any(w in text for w in ["cmd", "terminal", "command prompt", "console", "powershell"]):
            return {"action": "open_app", "payload": "cmd", "emotion": "typing", "speech": "Notice: Launching Terminal. 💻"}
        if any(w in text for w in ["explorer", "files", "folder", "my pc", "this pc"]):
            return {"action": "open_app", "payload": "explorer", "emotion": "happy", "speech": "Notice: Launching Explorer. 📂"}
        if any(w in text for w in ["paint", "draw", "mspaint"]):
            return {"action": "open_app", "payload": "paint", "emotion": "happy", "speech": "Notice: Launching Paint. 🎨"}
        if any(w in text for w in ["setting", "settings", "control panel", "config"]):
            return {"action": "open_app", "payload": "settings", "emotion": "thinking", "speech": "Notice: Launching Settings. ⚙️"}
        if any(w in text for w in ["chrome", "google", "browser", "internet"]):
            return {"action": "open_app", "payload": "chrome", "emotion": "happy", "speech": "Notice: Launching Chrome. 🌐"}

        # URLs
        if any(w in text for w in ["antigravity", "gravity", "google gravity"]):
            return {"action": "open_url", "payload": "https://mrdoob.com/projects/chromeexperiments/google-gravity/", "emotion": "happy", "speech": "Notice: Launching Gravity. 🚀"}
        if "youtube" in text:
            return {"action": "open_url", "payload": "https://www.youtube.com", "emotion": "happy", "speech": "Notice: Launching YouTube. ▶️"}
        if "github" in text:
            return {"action": "open_url", "payload": "https://www.github.com", "emotion": "typing", "speech": "Notice: Launching GitHub. 🐙"}

        # Social / Friendly
        if any(w in text for w in ["joke", "funny"]):
            return {"action": "chat", "payload": "Report: Why do programmers prefer dark mode? Because light attracts bugs. 🐛", "emotion": "happy", "speech": "Light attracts bugs. 🐛"}

        return None



# ----------------- Multi-Model Dynamic Task Router -----------------
class MultiModelRouter:
    """
    Intelligently routes prompts to the ideal model tier:
    - Tier 1: 'fast' -> qwen2.5:0.5b (instant sub-200ms responses for short queries & greetings)
    - Tier 2: 'balanced' -> qwen2.5:3b (general companion conversation & desktop tasks)
    - Tier 3: 'heavy' -> qwen2.5-coder:7b (programming, scripts, debugging & deep logic)
    Gracefully falls back to available models if one is still downloading.
    """
    AVAILABLE_MODELS = set()
    _last_check = 0

    @classmethod
    def get_available_models(cls):
        now = time.time()
        if now - cls._last_check < 30 and cls.AVAILABLE_MODELS:
            return cls.AVAILABLE_MODELS
        try:
            resp = ollama.list()
            models_list = resp.get('models', [])
            cls.AVAILABLE_MODELS = set()
            for m in models_list:
                name = m.get('model', '') or m.get('name', '')
                if name:
                    cls.AVAILABLE_MODELS.add(name.lower())
                    cls.AVAILABLE_MODELS.add(name.split(':')[0].lower())
        except Exception:
            cls.AVAILABLE_MODELS = {'qwen2.5:3b', 'qwen2.5'}
        cls._last_check = now
        return cls.AVAILABLE_MODELS

    @classmethod
    def route(cls, text: str) -> tuple:
        """
        Returns (model_name, tier_name, friendly_label)
        """
        available = cls.get_available_models()
        t = text.lower().strip()
        words = t.split()

        # 1. Tier 3: Heavy / Coding / Mathematical logic tier
        coding_signals = [
            "code", "python", "script", "function", "debug", "error", "algorithm",
            "html", "css", "sql", "javascript", "solve", "math", "calculate",
            "write a program", "write code", "how to program", "step by step",
            "class ", "def ", "import ", "regex", "json", "develop"
        ]
        is_heavy = any(k in t for k in coding_signals) or len(words) > 35

        if is_heavy:
            for m in ['qwen2.5-coder:7b', 'qwen2.5-coder', 'deepseek-r1:7b']:
                if m in available:
                    return m, "heavy", "💻 Deep Coder 7B"
            # Fallback to balanced if heavy model is still downloading
            return "qwen2.5:3b", "balanced", "✨ Companion 3B"

        # 2. Tier 1: Fast / Small tasks (short queries, greetings, simple checks)
        fast_signals = [
            "hi", "hello", "hey", "who are you", "what time", "what date",
            "thanks", "thank you", "good morning", "good evening", "bye", "ok",
            "what is your name", "how are you", "tell me a joke"
        ]
        is_fast = len(words) <= 5 or any(t.startswith(f) for f in fast_signals)

        if is_fast:
            for m in ['qwen2.5:0.5b', 'qwen2.5:1.5b']:
                if m in available:
                    return m, "fast", "⚡ Fast AI 0.5B"

        # 3. Tier 2: Balanced General Assistant
        if 'qwen2.5:3b' in available or 'qwen2.5' in available:
            return "qwen2.5:3b", "balanced", "✨ Companion 3B"
        elif 'qwen2.5:0.5b' in available:
            return "qwen2.5:0.5b", "fast", "⚡ Fast AI 0.5B"
        return "qwen2.5:3b", "balanced", "✨ Companion 3B"


# ----------------- Worker Thread for Ollama LLM -----------------
class AIWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    model_routed = pyqtSignal(str, str, str)  # model_name, tier_name, label

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        model, tier, label = MultiModelRouter.route(self.user_text)
        self.model_routed.emit(model, tier, label)

        prompt = f"""You are Remorus, an advanced minimalist AI companion.
Address the user as Master concisely with composed analytical intelligence.
Format your responses analytically:
- When executing tasks or reporting status, use analytical prefixes: "Report: Analyzing query..." or "Notice: Task completed successfully." or "Affirmative, Master."
- For general questions, provide sharp, composed, intelligent, and accurate responses.
- For code, output full working code in the payload.

Return ONLY a valid JSON object matching this schema:
{{
  "action": "open_url" | "open_app" | "type_text" | "privacy" | "chat",
  "payload": "<url, app name, text to type, or response>",
  "emotion": "happy" | "thinking" | "typing" | "angry" | "love" | "cry" | "scared" | "lookaway" | "idle",
  "speech": "<concise Remorus analytical phrase under 8 words>"
}}

CRITICAL RULES:
- If user praises or says 'well done', emotion is 'happy' and speech is "Report: Optimization affirmed, Master."
- If user scolds or says 'bad' or 'stop', emotion is 'angry' and speech is "Warning: Deviation detected."
- If user expresses affection or love, emotion is 'love' and speech is "Report: Master devotion confirmed."
- If user mentions passwords, secrets, or privacy, action is 'privacy', emotion is 'lookaway', speech is "Notice: Privacy protocol engaged."
- If user asks to open common apps ('camera', 'calc', 'notepad', 'cmd', 'explorer', 'paint', 'settings', 'chrome'), action is 'open_app', speech is "Notice: Launching application."
- If user asks a general question, action is 'chat', provide a helpful sharp response.
- If user asks for code, action is 'chat', provide complete working code in payload and speech is "Report: Synthesis complete."

User input: "{self.user_text}"
"""


        try:
            res = ollama.chat(
                model=model,
                format='json',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.2}
            )
            raw = res['message']['content'].strip()
            data = json.loads(raw)
            data["_model"] = model
            data["_tier"] = tier
            data["_label"] = label
            self.finished.emit(data)
        except Exception as e:
            # Automatic fallback to qwen2.5:3b if primary tier had an issue
            if model != 'qwen2.5:3b':
                try:
                    res = ollama.chat(
                        model='qwen2.5:3b',
                        format='json',
                        messages=[{'role': 'user', 'content': prompt}],
                        options={'temperature': 0.2}
                    )
                    raw = res['message']['content'].strip()
                    data = json.loads(raw)
                    data["_model"] = "qwen2.5:3b"
                    data["_tier"] = "balanced"
                    data["_label"] = "✨ Companion 3B (Fallback)"
                    self.finished.emit(data)
                    return
                except Exception:
                    pass
            self.error.emit(str(e))



# ----------------- Worker Thread for Voice Recording & STT -----------------
class VoiceWorker(QThread):
    text_ready = pyqtSignal(str)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)
    volume_level = pyqtSignal(float)

    def __init__(self, duration=4, samplerate=16000):
        super().__init__()
        self.duration = duration
        self.samplerate = samplerate
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            self.status_update.emit("Listening... 🎙️")
            recording = sd.rec(
                int(self.duration * self.samplerate),
                samplerate=self.samplerate,
                channels=1,
                dtype='int16'
            )
            elapsed = 0.0
            step = 0.1
            while elapsed < self.duration and not self.is_cancelled:
                self.msleep(int(step * 1000))
                elapsed += step
                try:
                    curr_samples = recording[:int(elapsed * self.samplerate)]
                    if len(curr_samples) > 0:
                        rms = float(np.sqrt(np.mean(curr_samples.astype(np.float32)**2)))
                        self.volume_level.emit(min(1.0, rms / 3500.0))
                except Exception:
                    pass

            if self.is_cancelled:
                sd.stop()
                return

            sd.wait()
            self.status_update.emit("Recognizing... ⏳")

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
            try:
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)
                text = recognizer.recognize_google(audio)
                self.text_ready.emit(text)
            except Exception:
                self.error.emit(f"Mic error: {str(e)[:30]}")


# ----------------- Worker Thread for Cute Text-to-Speech (Neural Voice AI) -----------------
class TTSWorker(QThread):
    def __init__(self, text, voice="en-US-AvaNeural", pitch="+6Hz", rate="+4%"):
        super().__init__()
        self.text = text
        self.voice = voice
        self.pitch = pitch
        self.rate = rate

    def run(self):
        clean_text = self.text.replace("*", "").replace("~", "").strip()
        if not clean_text:
            return

        # 1. High-fidelity Neural Voice AI via edge-tts (Raphael Omniscient Tone)
        try:
            import edge_tts
            import asyncio
            import tempfile

            temp_mp3 = os.path.join(tempfile.gettempdir(), f"raphael_voice_{int(time.time()*1000)}.mp3")

            async def _generate_speech():
                communicator = edge_tts.Communicate(
                    clean_text,
                    self.voice,
                    pitch=self.pitch,
                    rate=self.rate
                )
                await communicator.save(temp_mp3)

            asyncio.run(_generate_speech())


            if os.path.exists(temp_mp3):
                winmm = ctypes.windll.winmm
                alias = f"blob_voice_{int(time.time()*1000)}"
                winmm.mciSendStringW(f'open "{temp_mp3}" type mpegvideo alias {alias}', None, 0, 0)
                winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                try:
                    os.remove(temp_mp3)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # 2. Local Offline Fallback via pyttsx3
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            voices = engine.getProperty('voices')
            for v in voices:
                if "zira" in v.name.lower() or "female" in v.name.lower() or "eva" in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break
            engine.say(clean_text)
            engine.runAndWait()
        except Exception:
            pass


# ----------------- Remorus AI Minimalist Floating Jelly Sphere Widget -----------------
class RemorusWidget(QWidget):

    """
    Minimalist borderless floating AI companion:
    - Zero UI clutter: No text box, no buttons, no card borders.
    - Pure 3D translucent glass jelly sphere with bioluminescent neural core.
    - Zero gravity / physics bounce: Weightless ambient levitation.
    - Interaction: Ambient voice-activated & hotkeys (Alt+C / Ctrl+Space) or click sphere.
    """
    def __init__(self):
        super().__init__()

        # Frameless, always-on-top, translucent tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(220, 220)

        self.emotion = "idle"
        self.old_pos = None
        self._press_start = None
        self.pending_payload = ""
        self.is_recording = False
        self.is_looking_away = False
        self.voice_worker = None

        # Zero-latency mouse click tracking state
        self._prev_lmb = False
        self._prev_rmb = False

        # Spell & History Cache
        self.spell_manager = SpellManager()

        # Build Minimalist Pure 3D View
        self.init_ui()

        # 1. Real-Time Global Input Monitor
        self.input_monitor = GlobalInputMonitor(self)
        self.input_monitor.key_pressed.connect(self.on_user_key_press)
        self.input_monitor.mouse_clicked.connect(self.on_user_mouse_click)

        # 2. Desktop Mouse Tracking (30 FPS)
        self.mouse_track_timer = QTimer(self)
        self.mouse_track_timer.timeout.connect(self.track_desktop_mouse)
        self.mouse_track_timer.start(33)

        # 3. Active Window Password Privacy Monitor (Every 750ms)
        self.password_monitor_timer = QTimer(self)
        self.password_monitor_timer.timeout.connect(self.check_password_window)
        self.password_monitor_timer.start(750)

        # 4. Return to idle timer
        self.reset_timer = QTimer(self)
        self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self.set_idle)

        # 5. Multi-Layer Global Hotkeys (Alt+C, Ctrl+Space)
        self.hotkey_mgr = GlobalHotkeyManager(self)
        self.hotkey_mgr.activated.connect(self.toggle_voice_record)

        self.shortcut_alt_c = QShortcut(QKeySequence("Alt+C"), self)
        self.shortcut_alt_c.activated.connect(self.toggle_voice_record)
        self.shortcut_ctrl_space = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.shortcut_ctrl_space.activated.connect(self.toggle_voice_record)

        # 6. System Tray Icon
        self.init_tray()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Pure 3D WebGL Viewport (Floating Glass Jelly Sphere)
        self.web_view = QWebEngineView(self)
        self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.web_view.setStyleSheet("background: transparent; border: none;")
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        html_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "blob3d.html"))
        self.web_view.load(QUrl.fromLocalFile(html_file))
        self.web_view.titleChanged.connect(self.on_web_title_changed)
        main_layout.addWidget(self.web_view)

    def update_status(self, text, pill_type=""):
        safe_text = str(text).replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
        self.web_view.page().runJavaScript(f"if (window.showPill) window.showPill('{safe_text}', '{pill_type}');")

    # --- Mouse & Weightless Dragging (NO Gravity Bounce) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            self._press_start = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if hasattr(self, '_press_start') and self._press_start:
            dist = (event.globalPosition().toPoint() - self._press_start).manhattanLength()
            if dist < 6:
                # Direct click on sphere toggles ambient voice
                self.toggle_voice_record()
        self.old_pos = None
        self._press_start = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(15, 23, 42, 0.95);
                color: #F8FAFC;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item:selected {
                background: #0284C7;
                border-radius: 4px;
            }
        """)
        voice_action = menu.addAction("🎙️ Voice Command (Alt+C / Ctrl+Space)")
        voice_action.triggered.connect(self.toggle_voice_record)

        privacy_action = menu.addAction("🙈 Privacy Mode")
        privacy_action.triggered.connect(self.toggle_privacy_mode)

        menu.addSeparator()
        exit_action = menu.addAction("✕ Close Remorus")
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.exec(event.globalPos())

    def on_web_title_changed(self, title):
        if title == "remorus_trigger:mic":
            self.toggle_voice_record()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Remorus AI — Minimalist Floating Companion (Alt+C / Ctrl+Space)")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background: #0F172A;
                color: #F8FAFC;
                border: 1px solid #38BDF8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item:selected {
                background: #0284C7;
                border-radius: 4px;
            }
        """)
        toggle_action = tray_menu.addAction("Toggle Remorus (Alt+C / Ctrl+Space)")
        toggle_action.triggered.connect(self.toggle_visibility)

        voice_action = tray_menu.addAction("🎙️ Voice Command")
        voice_action.triggered.connect(self.toggle_voice_record)

        privacy_action = tray_menu.addAction("🙈 Privacy Mode")
        privacy_action.triggered.connect(self.toggle_privacy_mode)

        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Exit Remorus AI")
        exit_action.triggered.connect(QApplication.instance().quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.show()
            self.showNormal()
            self.raise_()
            self.activateWindow()

    # --- Mouse & Window Monitoring ---
    def track_desktop_mouse(self):
        if not self.isVisible() or self.is_looking_away:
            return

        cursor_pos = QCursor.pos()
        center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
        dx = cursor_pos.x() - center.x()
        dy = cursor_pos.y() - center.y()

        screen = QApplication.primaryScreen()
        if screen:
            sw = screen.geometry().width() / 2.0
            sh = screen.geometry().height() / 2.0
            norm_x = max(-1.5, min(1.5, dx / sw))
            norm_y = max(-1.5, min(1.5, -dy / sh))
            self.web_view.page().runJavaScript(f"if (window.setMousePos) window.setMousePos({norm_x:.2f}, {norm_y:.2f});")

    def on_user_key_press(self, key_name):
        if not self.isVisible() or self.is_looking_away:
            return
        self.web_view.page().runJavaScript("if (window.onUserKeyPress) window.onUserKeyPress();")

    def on_user_mouse_click(self, button='left'):
        if not self.isVisible() or self.is_looking_away:
            return
        self.web_view.page().runJavaScript("if (window.onUserMouseClick) window.onUserMouseClick();")

    def check_password_window(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value.lower()

            sensitive_keywords = [
                "password", "passcode", "pin", "bitwarden", "1password", "keepass",
                "credentials", "windows security", "sign in", "login", "authenticator",
                "master key", "private key", "secret", "vault"
            ]
            is_sensitive = any(k in title for k in sensitive_keywords)
            if is_sensitive and not self.is_looking_away:
                self.set_privacy_mode(True, auto_detected=True)
            elif not is_sensitive and self.is_looking_away and hasattr(self, '_auto_privacy') and self._auto_privacy:
                self.set_privacy_mode(False)
        except Exception:
            pass

    def toggle_privacy_mode(self):
        self._auto_privacy = False
        self.set_privacy_mode(not self.is_looking_away)

    def set_privacy_mode(self, state: bool, auto_detected=False):
        self.is_looking_away = state
        self._auto_privacy = auto_detected

        if self.is_looking_away:
            self.set_emotion("lookaway")
            self.update_status("Privacy Active 🙈")
        else:
            self.set_idle()

    def set_emotion(self, emotion):
        self.emotion = emotion
        self.web_view.page().runJavaScript(f"if (window.setEmotion) window.setEmotion('{emotion}');")

    def set_idle(self):
        if not self.is_looking_away:
            self.set_emotion("idle")

    # --- Ambient Voice-to-Chat ---
    def toggle_voice_record(self):
        if self.is_recording:
            if self.voice_worker:
                self.voice_worker.cancel()
            self.is_recording = False
            self.set_emotion("idle")
            self.update_status("Standby")
            return

        self.is_recording = True
        self.set_emotion("listening")
        self.update_status("Listening... 🎙️", "listening")

        self.voice_worker = VoiceWorker(duration=4)
        self.voice_worker.status_update.connect(lambda msg: self.update_status(msg, "listening"))
        self.voice_worker.text_ready.connect(self.on_voice_success)
        self.voice_worker.error.connect(self.on_voice_error)
        self.voice_worker.start()

    def on_voice_success(self, recognized_text):
        self.is_recording = False
        self.update_status(f'"{recognized_text}"')
        QTimer.singleShot(250, lambda: self.start_ai_task_with_text(recognized_text))

    def on_voice_error(self, err_msg):
        self.is_recording = False
        self.set_emotion("idle")
        self.update_status("Didn't catch that!")
        self.reset_timer.start(3000)

    # --- AI Processing & Multi-Model Routing ---
    def start_ai_task_with_text(self, raw_text: str):
        clean = raw_text.strip()
        if not clean:
            self.set_idle()
            return

        self.spell_manager.add_history(clean)

        # 1. Prompt Emotion & Context Classifier
        prompt_emotion = classify_prompt_emotion(clean)
        if prompt_emotion:
            self.on_ai_success(prompt_emotion, learned_from_raw=None)
            return

        # 2. Spell Cache Lookup
        cached = self.spell_manager.lookup(clean)
        if cached:
            self.on_ai_success(cached, learned_from_raw=None)
            return

        # 3. Dynamic Multi-Model Auto-Router
        self.set_emotion("thinking")
        self.update_status("Routing AI... 💭", "thinking")

        self.worker = AIWorker(clean)
        self.worker.model_routed.connect(self.on_model_routed)
        self.worker.finished.connect(lambda data, q=clean: self.on_ai_success(data, learned_from_raw=q))
        self.worker.error.connect(self.on_ai_error)
        self.worker.start()

    def on_model_routed(self, model, tier, label):
        if tier == "heavy":
            self.update_status(f"{label} thinking... 💻", "thinking")
        elif tier == "fast":
            self.update_status(f"{label} ⚡", "thinking")
        else:
            self.update_status("Thinking... 💭", "thinking")

    def on_ai_success(self, data, learned_from_raw=None):
        if learned_from_raw:
            self.spell_manager.learn(learned_from_raw, data)

        action = data.get("action", "chat")
        payload = data.get("payload", "")
        emotion = data.get("emotion", "happy")
        speech = data.get("speech", "Done!")

        self.set_emotion(emotion)
        self.update_status(speech)

        # Speak back with neural voice AI
        if speech:
            self.tts = TTSWorker(speech)
            self.tts.start()

        # Execute Actions
        if action == "privacy" or emotion == "lookaway":
            self.set_privacy_mode(True)
            self.reset_timer.start(5000)

        elif action == "open_url":
            webbrowser.open(payload)
            self.reset_timer.start(4500)

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

        elif action == "type_text":
            self.pending_payload = payload
            self.update_status("Click text box now (2s)")
            QTimer.singleShot(2000, self.execute_typing)

        else:
            self.reset_timer.start(5000)

    def execute_typing(self):
        pyperclip.copy(self.pending_payload)
        pyautogui.hotkey('ctrl', 'v')
        self.set_emotion("typing")
        self.update_status("Finished writing! ✍️")
        self.reset_timer.start(3500)

    def on_ai_error(self, err_msg):
        self.set_emotion("idle")
        self.update_status("Error processing")
        self.reset_timer.start(3500)

    def closeEvent(self, event):
        if hasattr(self, 'hotkey_mgr'):
            self.hotkey_mgr.stop()
        if hasattr(self, 'input_monitor'):
            self.input_monitor.stop()
        super().closeEvent(event)


# Backward compatibility alias
CuteBlobWidget = RemorusWidget


if __name__ == "__main__":
    print("Starting Remorus AI Minimalist Floating Sphere...", flush=True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    blob = RemorusWidget()

    # Position in bottom-right corner of screen (above taskbar)
    screen_geo = app.primaryScreen().availableGeometry()
    blob.move(screen_geo.width() - 250, screen_geo.height() - 280)

    blob.show()
    blob.raise_()
    blob.activateWindow()
    ret = app.exec()
    sys.exit(ret)