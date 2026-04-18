# Sofia

<p align="center">
  <img src="https://img.shields.io/badge/React-19.2.4-61DAFB?logo=react&logoColor=white" alt="React Badge" />
  <img src="https://img.shields.io/badge/FastAPI-0.116.1-009688?logo=fastapi&logoColor=white" alt="FastAPI Badge" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python Badge" />
</p>

Sofia is a voice-first GenAI assistant that listens continuously, responds intelligently, and speaks back in natural language.

Sofia supports both text and voice interaction. In voice mode, it listens continuously, sends your spoken command to the backend, and speaks the response back.

## Tech Stack

- Frontend: React + Vite
- Backend: FastAPI (Python)
- AI: Google Gemini API (optional)
- Voice Input: Web Speech API
- Voice Output: Speech Synthesis API

## Features

- Text command input
- Microphone toggle for voice mode
- Continuous speech recognition
- Automatic text-to-speech responses
- Beginner-friendly backend intent handling
- Gemini fallback for open-ended chat

## Demo Flow

1. Turn mic ON.
2. Speak a command.
3. Sofia processes it automatically.
4. Sofia replies in text and voice.
5. Listening resumes until mic is turned OFF.

## Project Structure

```text
Sofia/
  backend/
    app.py
    requirements.txt
    process_command/
    support_functions/
  frontend/
    src/
    package.json
```

## Voice Mode Notes

- Mic permission is requested only when mic is turned ON.
- If mic stays ON, recognition restarts automatically.
- Sofia pauses listening while speaking to reduce feedback loops.
- Mic stops on page unload/navigation.

### Microphone not working

- Allow microphone permission in browser settings.
- Use Chrome or Edge for best Web Speech API support.
- If denied previously, reset site permissions and refresh.

### No voice output

- Ensure your browser supports `speechSynthesis`.
- Check tab audio and system volume.
- Refresh once if voices were not loaded yet.

##  Deployment Status

**Live Demo:**
[https://your-render-link.onrender.com](https://your-render-link.onrender.com)

⚠️ **Current Status:**
Sofia is **not fully deployed yet**. Some features (like AI chat and external API integrations) may not work as expected in the live version.

**Local Version:**
The project is fully functional on the local machine, and all features are being tested and integrated before final deployment.
