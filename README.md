# 🫧 Blob Helper — 3D Desktop AI Companion

An interactive, animated 3D desktop companion powered by local AI (**Ollama**). Blob floats on your screen, listens via voice or text input, expresses emotions, and automates desktop tasks.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![Ollama](https://img.shields.io/badge/AI-Ollama%20(qwen2.5:3b)-purple.svg)

---

## ✨ Features
- 🔮 **Floating Desktop Pet:** Frameless, transparent desktop companion.
- 🎭 **Living Emotions:** Expressive reactions (Idle, Thinking, Happy, Typing, Surprised).
- 🎙️ **Voice-to-Chat:** In-built microphone support for hands-free voice commands.
- ⚡ **Desktop Automation:** Opens websites, launches applications, and types text on command.
- 🔒 **100% Private & Local:** Runs completely on your PC using Ollama.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**: Make sure Python is installed and added to PATH.
- **Ollama**: Download and install Ollama from [ollama.com](https://ollama.com).

### 2. Download the AI Model
Open a terminal (CMD or PowerShell) and run:
```bash
ollama run qwen2.5:3b
```
*(Once it finishes downloading, you can close the terminal. Ollama will keep running in the background).*

### 3. Clone & Install
```bash
# Clone the repository
git clone https://github.com/patelpratum3820-tech/blob-helper.git
cd blob-helper

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Run Blob AI
```bash
python blob.py
```

---

## 🛠️ Controls & Commands
- **Drag & Drop:** Click and hold anywhere on Blob to drag it around your screen.
- **Voice Input:** Click the Mic button or speak your command.
- **Example Commands:**
  - *"Open notepad"*
  - *"Open calculator"*
  - *"Type a polite thank you email"*
  - *"Show me antigravity"*
  - *"What is quantum computing?"*

---

## 📄 License
MIT License
