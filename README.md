# 🫧 Rimuru Slime & Great Sage Raphael — 3D Desktop AI Companion

An interactive, animated 3D desktop companion inspired by **Rimuru Tempest (Slime form)** and **Great Sage / Raphael (Wisdom King)** from *Tensura*. Powered by local AI (**Ollama**) with multi-model automatic task routing and neural voice feedback.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![Ollama](https://img.shields.io/badge/AI-Ollama%20(qwen2.5)-purple.svg)
![Three.js](https://img.shields.io/badge/3D-Three.js%20(Translucent%20Slime)-cyan.svg)

---

## ✨ Features
- 🔮 **Rimuru Slime Form in 3D:** Semi-translucent sky-blue droplet body with water refraction (`MeshPhysicalMaterial`), squishy jelly physics, and expressive curved line eyes `( ^ ^ )`.
- 🧠 **Great Sage / Raphael Persona:** Composed, analytical, sharp responses addressing you as Master.
- ⚡ **Raphael Inner Wisdom Core:** Glowing inner core that shifts into a golden wisdom pulse when calculating.
- 🎙️ **Voice-to-Chat:** In-built microphone support for hands-free voice commands.
- 🗣️ **Raphael Neural Voice:** Calm, articulate, omniscient neural voice (`en-US-AvaNeural`, pitch `+6Hz`).
- 🧠 **Multi-Model Dynamic Routing:** Auto-switches between fast (`0.5B`), balanced (`3B`), and heavy coding (`7B`) models based on task complexity.
- ⚡ **Desktop Automation:** Opens websites, launches applications, and types text on command.
- 🔒 **100% Private & Local:** Runs completely on your PC using Ollama.

---


## 🧠 Multi-Model AI Architecture (Auto-Task Routing)

Blob Helper uses a tiered AI routing system so that small tasks run fast while heavy tasks get deep reasoning power without slowing down your computer:

| Tier | Model | Best For | Typical Latency | Active RAM |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Fast)** | `qwen2.5:0.5b` | Small tasks, greetings, open apps, quick replies | ~0.2s | ~400 MB |
| **Tier 2 (Daily)** | `qwen2.5:3b` | General chat, desktop helper, everyday Q&A | ~1.5s | ~2.0 GB |
| **Tier 3 (Heavy)** | `qwen2.5-coder:7b` | Coding, debugging, complex math & logic | ~4-6s | ~4.8 GB |
| **Tier 4 (Voice)** | `edge-tts` / `piper` | Studio-quality neural human/companion speech | Real-time | <50 MB |

> 📖 *For full technical specifications, hardware analysis, and routing logic, see [MULTI_MODEL_PLAN.md](MULTI_MODEL_PLAN.md).*

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**: Make sure Python is installed and added to PATH.
- **Ollama**: Download and install Ollama from [ollama.com](https://ollama.com).

### 2. Download the AI Models
Open a terminal (CMD or PowerShell) and run:
```bash
# 1. Tier 1 (Fast / Quick Tasks - ~400 MB)
ollama pull qwen2.5:0.5b

# 2. Tier 2 (Balanced / Daily Companion - ~2.0 GB)
ollama pull qwen2.5:3b

# 3. Tier 3 (Heavy / Coding & Complex Logic - ~4.7 GB)
ollama pull qwen2.5-coder:7b
```
*(Once downloaded, Ollama keeps running in the background and automatically swaps models into RAM as needed).*

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
  - *"Open notepad"* *(Fast Tier 1)*
  - *"Open calculator"* *(Fast Tier 1)*
  - *"Write a Python script to sort a list"* *(Heavy Tier 3 Coder)*
  - *"Type a polite thank you email"* *(Balanced Tier 2)*
  - *"Show me antigravity"*
  - *"What is quantum computing?"*

---

## 📄 License
MIT License

