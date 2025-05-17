# Sofia - Voice-Controlled Personal Assistant 🎙️

**Sofia** is a Python-based voice-controlled assistant designed to make digital interaction hands-free and seamless. By leveraging speech recognition and text-to-speech capabilities, Sofia listens to your voice commands and performs actions like opening websites, playing songs, and reading out the latest news in Punjabi.

## 🛠 Features

* 🎧 **Voice Recognition**: Uses your microphone to listen and interpret voice commands.
* 🔊 **Text-to-Speech (TTS)**: Replies back using speech output.
* 🌐 **Web Navigation**: Opens predefined websites through simple commands like `open YouTube`.
* 🎵 **Music Control**: Plays songs from a custom `Music_library`.
* 📰 **News Reader**: Fetches the latest Punjabi news using the [Mediastack API](https://mediastack.com/).
* 🔐 **Secure API Management**: API keys are managed securely using environment variables and a `.env` file.

## 📦 Requirements

* Python 3.x
* `speechrecognition`
* `pyttsx3`
* `requests`
* `python-dotenv`

```bash
pip install -r requirements.txt
```

## 🔐 Environment Variable

Create a `.env` file in the root directory and add your API key:

```
NEWS_API_KEY=your_mediastack_api_key_here
```

## 🗣 Usage

Run the assistant:

```bash
python main.py
```

Say **“Sofia”** or **“Sophia”** to activate it, then give a command like:

* "Open Google"
* "Play Water"
* "News"

Say **“exit”** anytime to stop the assistant.

## 👤 Author

Created by **Manharan Kaur** – Voice-based assistant project powered by Python and curiosity.