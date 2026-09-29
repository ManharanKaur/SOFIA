# SOFIA Desktop Agent

The SOFIA Desktop Agent is a local Python daemon that runs on your Mac and acts as the bridge between the Vercel frontend, the Render backend, and your computer.

## What it does

1. Connects to the Render backend via an authenticated WebSocket
2. Receives voice commands forwarded from the frontend
3. Runs **local Ollama inference** (no cloud LLM API needed)
4. Decides whether a tool call is needed
5. Checks your **permission** for each action before executing
6. Executes safe, validated macOS tools (open apps, control Spotify, search, etc.)
7. Returns the result to the frontend

---

## Quick Start

### 1. Install Ollama

```bash
# Download from https://ollama.com/download  OR via Homebrew:
brew install ollama
```

### 2. Start Ollama and pull the model

```bash
ollama serve          # starts the local server at http://localhost:11434
ollama pull qwen2.5:7b-instruct   # ~4.7 GB download, one-time
```

**Alternative model (less RAM):**
```bash
ollama pull qwen2.5:3b-instruct   # ~2 GB
```
Then set `OLLAMA_MODEL=qwen2.5:3b-instruct` in `.env`.

### 3. Set up the Desktop Agent

```bash
cd sofia/desktop-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure environment variables

The `.env` file is pre-populated with a generated token:

```bash
cat .env      # review the token
```

**Important:** Copy the `AGENT_TOKEN` value into your **Render dashboard** → Environment → `SOFIA_AGENT_TOKEN`.

### 5. Start the agent

```bash
python agent_main.py
```

You should see:
```
✓ Ollama is running.
✓ Agent token configured.
Connecting to Render backend…
Registered with backend (session=xxxx-xxxx)
```

---

## Permission System

When SOFIA wants to control your computer, it asks first.

### Permission Groups (Least Privilege)

| Group | Key | What it allows |
|-------|-----|----------------|
| Browser Control | `browser_control` | Open Chrome, Safari, Firefox; navigate to URLs |
| Application Control | `app_control` | Open supported apps (Finder, Calendar, Notes, etc.) |
| Spotify Control | `spotify_control` | Play, pause, skip, search on Spotify |
| System Controls | `system_controls` | Adjust volume |
| File Access | `file_access` | Search for files by name in home folder |
| Web Search | `web_search` | Open Google search in the browser |

### How it works

1. You send a voice command: *"Open Chrome and play study music"*
2. SOFIA identifies two tools: `open_browser` + `play_spotify`
3. Each requires its own permission group
4. The frontend shows dialogs: **"SOFIA wants Browser Control. Allow?"** and **"SOFIA wants Spotify Control. Allow?"**
5. You click **Allow** (optionally tick **Remember this decision**)
6. SOFIA executes the tools
7. Next time you say the same type of command, no dialog appears if you chose Remember

### Sensitive operations always re-confirm

Even if you've granted File Access, searching for a specific file always asks again. This prevents accidental broad access.

### Stored permissions location

```
~/.sofia_permissions.json
```

Delete this file to reset all permissions.

---

## Authentication

The Desktop Agent authenticates to the Render backend using a shared secret token:

- **Render backend:** `SOFIA_AGENT_TOKEN` environment variable
- **Desktop Agent:** `AGENT_TOKEN` in `desktop-agent/.env`

Both must match. The Render WebSocket endpoint rejects connections with wrong/missing tokens with HTTP close code `4001`.

**Generate a new token:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Supported Tools

| Tool | Command | Example |
|------|---------|---------|
| `open_browser` | browser_control | "Open Chrome" |
| `open_url` | browser_control | "Open youtube.com" |
| `open_app` | app_control | "Open Spotify" / "Open Finder" |
| `play_spotify` | spotify_control | "Play Shape of You on Spotify" |
| `pause_spotify` | spotify_control | "Pause Spotify" |
| `next_spotify` | spotify_control | "Next track" |
| `previous_spotify` | spotify_control | "Previous song" |
| `search_spotify` | spotify_control | "Search Spotify for The Weeknd" |
| `control_volume` | system_controls | "Set volume to 50" / "Mute" |
| `find_file` | file_access | "Find my resume file" |
| `search_web` | web_search | "Search for machine learning courses" |

---

## Architecture

```
[Vercel Frontend]
       │
       │  POST /api/command
       ▼
[Render Backend (FastAPI)]
       │
       │  WebSocket wss://render-url/ws/agent
       ▼
[SOFIA Desktop Agent]  ←── runs on YOUR Mac
       │
       │  HTTP POST http://localhost:11434/api/chat
       ▼
[Ollama — local LLM]
       │
       ▼
[macOS: subprocess, osascript, AppleScript]
```

---

## Troubleshooting

**"Cannot connect to Ollama"**
→ Run `ollama serve` in a separate terminal.

**"AGENT_TOKEN is not set"**
→ Edit `desktop-agent/.env` and add your token.

**"Agent disconnected" in logs**
→ Check your internet connection; the agent reconnects automatically.

**"Invalid agent token" in backend logs**
→ Make sure `AGENT_TOKEN` in `.env` matches `SOFIA_AGENT_TOKEN` in Render.

**Spotify won't play**
→ Open Spotify manually first, log in, then retry the command.
