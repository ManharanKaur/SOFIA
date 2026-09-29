/**
 * App.jsx
 * -------
 * SOFIA main application component.
 *
 * Changes from original
 * ---------------------
 * - Added: AgentStatusBadge in the header (shows Desktop Agent connection state)
 * - Added: PermissionDialog overlay (shown when Desktop Agent needs approval)
 * - Added: useAgentStatus hook (polls /api/agent/status, handles permission flow)
 * - Added: agent_connected field consumed from command responses
 * - Removed: all inline styles (moved to CSS classes / BEM modifiers)
 * - Kept:  STT (Web Speech), TTS (Speech Synthesis), chat history, backend
 *          discovery, and all existing chat functionality unchanged.
 *
 * BEM blocks used: app-container, header, chat-display, search-section,
 *                  search-bar, chat-history (all defined in App.css)
 */

import './App.css';
import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import VoiceAssistantOrb from './components/VoiceAssistantOrb';
import AgentStatusBadge from './components/AgentStatusBadge';
import PermissionDialog from './components/PermissionDialog';
import useAgentStatus from './hooks/use-agent-status';

// ── Constants ────────────────────────────────────────────────────────────────

const CHAT_HISTORY_STORAGE_KEY = 'sofia.chatHistory';
const MAX_CHAT_HISTORY = 12;
const MAX_HISTORY_TO_SEND = 8;
const BACKEND_HEALTH_PATH = '/health';

const INITIAL_ASSISTANT_MESSAGE =
  'Hi! I am SOFIA, your local AI assistant. Ask me anything or give me a command!';

// ── Local storage helpers ────────────────────────────────────────────────────

const loadStoredChatHistory = () => {
  if (typeof window === 'undefined') return [];

  try {
    const rawValue = window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
    if (!rawValue) return [];

    const parsedValue = JSON.parse(rawValue);
    if (!Array.isArray(parsedValue)) return [];

    return parsedValue
      .filter(
        (entry) =>
          entry &&
          typeof entry.role === 'string' &&
          typeof entry.content === 'string',
      )
      .slice(-MAX_CHAT_HISTORY)
      .map((entry) => ({ role: entry.role, content: entry.content }));
  } catch {
    return [];
  }
};

const trimChatHistory = (history) => history.slice(-MAX_CHAT_HISTORY);

// ── Backend discovery ────────────────────────────────────────────────────────

const buildBackendCandidates = () => {
  const candidates = [];

  if (import.meta.env.VITE_BACKEND_URL) {
    candidates.push(import.meta.env.VITE_BACKEND_URL.replace(/\/$/, ''));
  }

  if (typeof window !== 'undefined') {
    candidates.push(window.location.origin);
  }

  candidates.push('http://127.0.0.1:8000');
  candidates.push('http://localhost:8000');

  return [...new Set(candidates)];
};

const probeBackend = async (baseUrl) => {
  try {
    const response = await fetch(`${baseUrl}${BACKEND_HEALTH_PATH}`, {
      method: 'GET',
    });
    return response.ok;
  } catch {
    return false;
  }
};

// ── Icon components ──────────────────────────────────────────────────────────

function MicIcon({ className = '' }) {
  return (
    <svg
      className={className}
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
      <line x1="8" y1="22" x2="16" y2="22" />
    </svg>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

const PAUSE_THRESHOLD_MS = 1500;

function App() {
  const [question, setQuestion] = useState('Tap microphone to start continuous listening...');
  const [liveTranscript, setLiveTranscript] = useState('');
  const [fullAnswer, setFullAnswer] = useState(INITIAL_ASSISTANT_MESSAGE);
  const [visibleAnswer, setVisibleAnswer] = useState(INITIAL_ASSISTANT_MESSAGE);
  const [backendStatus, setBackendStatus] = useState('Detecting backend...');
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const [chatHistory, setChatHistory] = useState(() => loadStoredChatHistory());
  const [backendBase, setBackendBase] = useState(null);

  // ── Agent status hook ────────────────────────────────────────────────────
  const { agentConnected, pendingPermission, respondToPermission, setPendingPermission } =
    useAgentStatus(backendBase);

  // ── Refs ─────────────────────────────────────────────────────────────────
  const recognitionRef = useRef(null);
  const shouldRestartRef = useRef(false);
  const isListeningRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const isSendingRef = useRef(false);
  const hasHydratedHistoryRef = useRef(false);
  const selectedVoiceRef = useRef(null);
  const speechSynthesisRef = useRef(null);
  const autoResumeAfterSpeechRef = useRef(false);
  const pauseTimerRef = useRef(null);
  const currentTranscriptRef = useRef('');

  // ── Persist chat history ─────────────────────────────────────────────────
  useEffect(() => {
    if (chatHistory.length === 0) return;
    window.localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(chatHistory));
  }, [chatHistory]);

  // ── Hydrate display from stored history ─────────────────────────────────
  useEffect(() => {
    if (hasHydratedHistoryRef.current) return;
    hasHydratedHistoryRef.current = true;
    if (chatHistory.length === 0) return;

    const lastUser = [...chatHistory].reverse().find((e) => e.role === 'user');
    const lastAssistant = [...chatHistory].reverse().find((e) => e.role === 'assistant');

    if (lastUser) setQuestion(lastUser.content);
    if (lastAssistant) setFullAnswer(lastAssistant.content);
  }, [chatHistory]);

  // ── Keep refs in sync with state ─────────────────────────────────────────
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);
  useEffect(() => { isSpeakingRef.current = isSpeaking; }, [isSpeaking]);
  useEffect(() => { isSendingRef.current = isSending; }, [isSending]);

  // ── Backend discovery ────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    const detectBackend = async () => {
      setBackendStatus('Detecting backend...');

      for (const candidate of buildBackendCandidates()) {
        if (await probeBackend(candidate)) {
          if (!cancelled) {
            setBackendBase(candidate);
            setBackendStatus('Backend connected');
          }
          return;
        }
      }

      if (!cancelled) {
        setBackendBase(null);
        setBackendStatus('Backend offline');
      }
    };

    detectBackend();
    return () => { cancelled = true; };
  }, []);

  // ── Voice selection ──────────────────────────────────────────────────────
  const pickPreferredVoice = (voices) => {
    if (!voices || voices.length === 0) return null;

    const preferredNames = [
      'Google UK English Female',
      'Microsoft Zira',
      'Samantha',
      'Karen',
      'Victoria',
      'Moira',
    ];

    for (const name of preferredNames) {
      const match = voices.find((voice) => voice.name === name);
      if (match) return match;
    }

    const femaleByName = voices.find((voice) =>
      voice.name.toLowerCase().includes('female'),
    );
    if (femaleByName) return femaleByName;

    return voices.find((voice) => voice.lang?.toLowerCase().startsWith('en')) || voices[0];
  };

  // ── Speech recognition helpers ───────────────────────────────────────────
  const startRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      recognition.start();
    } catch {
      // Swallow errors when recognition is already started.
    }
  };

  const stopRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      recognition.stop();
    } catch {
      // Swallow errors when recognition is already stopped.
    }
  };

  // ── TTS ──────────────────────────────────────────────────────────────────
  const speakText = useCallback((text) => {
    const synth = speechSynthesisRef.current;
    if (!synth || !text) return;

    synth.cancel();

    autoResumeAfterSpeechRef.current = isListeningRef.current;
    if (autoResumeAfterSpeechRef.current) {
      shouldRestartRef.current = false;
      stopRecognition();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;

    if (selectedVoiceRef.current) {
      utterance.voice = selectedVoiceRef.current;
    }

    utterance.onstart = () => setIsSpeaking(true);

    const onSpeechFinished = () => {
      setIsSpeaking(false);
      if (autoResumeAfterSpeechRef.current && isListeningRef.current) {
        shouldRestartRef.current = true;
        setTimeout(() => {
          if (isListeningRef.current && !isSpeakingRef.current && !isSendingRef.current) {
            startRecognition();
          }
        }, 200);
      }
    };

    utterance.onend = onSpeechFinished;
    utterance.onerror = onSpeechFinished;

    synth.speak(utterance);
  }, []);

  // ── Command processor ────────────────────────────────────────────────────
  const processCommand = useCallback(async (rawCommand) => {
    const command = rawCommand.trim();
    if (!command || isSendingRef.current || !backendBase) return;

    setIsSending(true);
    setQuestion(command);

    try {
      const historyForBackend = chatHistory
        .slice(-MAX_HISTORY_TO_SEND)
        .map((entry) => ({ role: entry.role, content: entry.content }));

      const response = await fetch(`${backendBase}/api/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, history: historyForBackend }),
      });

      if (!response.ok) {
        throw new Error('Failed to process command');
      }

      const data = await response.json();
      const message = data.message || 'No response from backend.';

      setFullAnswer(message);
      setChatHistory((current) =>
        trimChatHistory([
          ...current,
          { role: 'user', content: command },
          { role: 'assistant', content: message },
        ]),
      );

      if (data.action === 'open_url' || data.action === 'search') {
        if (data.url) {
          window.open(data.url, '_blank', 'noopener,noreferrer');
        }
      }

      // Surface pending permission request if the backend signals one.
      if (data.pending_permission) {
        setPendingPermission(data.pending_permission);
      }

      speakText(message);
      setBackendStatus('Backend connected');
    } catch {
      const fallbackMessage =
        'Could not reach backend. Start the Python server and try again.';
      setFullAnswer(fallbackMessage);
      setChatHistory((current) =>
        trimChatHistory([
          ...current,
          { role: 'user', content: command },
          { role: 'assistant', content: fallbackMessage },
        ]),
      );
      speakText(fallbackMessage);
      setBackendStatus('Backend offline');
    } finally {
      setIsSending(false);
    }
  }, [backendBase, chatHistory, speakText, setPendingPermission]);

  // ── Speech synthesis initialisation ─────────────────────────────────────
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    setMicSupported(!!SpeechRecognition);

    if ('speechSynthesis' in window) {
      speechSynthesisRef.current = window.speechSynthesis;

      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        selectedVoiceRef.current = pickPreferredVoice(voices);
      };

      loadVoices();
      window.speechSynthesis.addEventListener('voiceschanged', loadVoices);

      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
      };
    }

    return undefined;
  }, []);

  // ── Backend health polling ───────────────────────────────────────────────
  useEffect(() => {
    const checkHealth = async () => {
      if (!backendBase) return;

      try {
        const res = await fetch(`${backendBase}${BACKEND_HEALTH_PATH}`);
        if (!res.ok) throw new Error('Backend unavailable');
        setBackendStatus('Backend connected');
      } catch {
        setBackendStatus('Backend offline');
      }
    };

    checkHealth();
  }, [backendBase]);

  // ── Speech recognition setup with 1.5s pause detection ────────────────────
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return undefined;

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      if (isSpeakingRef.current || isSendingRef.current) return;

      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += `${result[0].transcript} `;
        } else {
          interimTranscript += result[0].transcript;
        }
      }

      const combined = `${finalTranscript}${interimTranscript}`.trim();
      if (!combined) return;

      currentTranscriptRef.current = combined;
      setLiveTranscript(combined);
      setQuestion(combined);

      // Clear existing pause timer while user is actively speaking
      if (pauseTimerRef.current) {
        clearTimeout(pauseTimerRef.current);
        pauseTimerRef.current = null;
      }

      // Detect 1.5s pause of silence after speech
      pauseTimerRef.current = setTimeout(() => {
        const textToProcess = currentTranscriptRef.current.trim();
        if (!textToProcess || isSendingRef.current || isSpeakingRef.current) return;

        currentTranscriptRef.current = '';
        setLiveTranscript('');

        // Pause recognition while processing command and speaking
        shouldRestartRef.current = false;
        stopRecognition();

        processCommand(textToProcess);
      }, PAUSE_THRESHOLD_MS);
    };

    recognition.onend = () => {
      // Auto-restart if continuous listening is still active
      if (
        shouldRestartRef.current &&
        isListeningRef.current &&
        !isSpeakingRef.current &&
        !isSendingRef.current
      ) {
        setTimeout(() => {
          if (
            shouldRestartRef.current &&
            isListeningRef.current &&
            !isSpeakingRef.current &&
            !isSendingRef.current
          ) {
            startRecognition();
          }
        }, 150);
      }
    };

    recognition.onerror = (event) => {
      if (
        event.error === 'not-allowed' ||
        event.error === 'service-not-allowed'
      ) {
        shouldRestartRef.current = false;
        setIsListening(false);
        setFullAnswer(
          'Microphone permission denied. Please allow microphone access and try again.',
        );
        return;
      }

      // no-speech or aborted are expected during pauses
      if (event.error === 'no-speech' || event.error === 'aborted') {
        return;
      }

      if (isListeningRef.current && !isSpeakingRef.current && !isSendingRef.current) {
        shouldRestartRef.current = true;
      }
    };

    recognitionRef.current = recognition;

    const handlePageExit = () => {
      if (pauseTimerRef.current) {
        clearTimeout(pauseTimerRef.current);
        pauseTimerRef.current = null;
      }
      shouldRestartRef.current = false;
      setIsListening(false);
      stopRecognition();
      if (speechSynthesisRef.current) {
        speechSynthesisRef.current.cancel();
      }
    };

    window.addEventListener('pagehide', handlePageExit);
    window.addEventListener('beforeunload', handlePageExit);

    return () => {
      window.removeEventListener('pagehide', handlePageExit);
      window.removeEventListener('beforeunload', handlePageExit);
      if (pauseTimerRef.current) {
        clearTimeout(pauseTimerRef.current);
        pauseTimerRef.current = null;
      }
      shouldRestartRef.current = false;
      stopRecognition();
      if (speechSynthesisRef.current) {
        speechSynthesisRef.current.cancel();
      }
      if (recognitionRef.current) {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
      }
    };
  }, [processCommand]);

  // ── Typewriter effect ────────────────────────────────────────────────────
  useEffect(() => {
    let index = 0;
    setVisibleAnswer('');

    const timer = setInterval(() => {
      index += 1;
      setVisibleAnswer(fullAnswer.slice(0, index));
      if (index >= fullAnswer.length) clearInterval(timer);
    }, 12);

    return () => clearInterval(timer);
  }, [fullAnswer]);

  // ── Microphone toggle (continuous listening mode) ───────────────────────
  const toggleMicrophone = () => {
    if (!micSupported) {
      setFullAnswer('Microphone is not supported in this browser.');
      return;
    }

    if (isListening) {
      if (pauseTimerRef.current) {
        clearTimeout(pauseTimerRef.current);
        pauseTimerRef.current = null;
      }
      currentTranscriptRef.current = '';
      setLiveTranscript('');
      shouldRestartRef.current = false;
      setIsListening(false);
      stopRecognition();
      return;
    }

    currentTranscriptRef.current = '';
    setLiveTranscript('');
    shouldRestartRef.current = true;
    setIsListening(true);
    setFullAnswer('Listening continuously. Speak any command, and pause for 1.5s when done...');
    startRecognition();
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="app-container">
      {/* Permission dialog — rendered at top level so it overlays everything */}
      <PermissionDialog
        permission={pendingPermission}
        onRespond={respondToPermission}
      />

      <header className="header">
        <div className="header__brand">
          <div className="header__logo-box">S</div>
          <h1 className="header__title">Sofia</h1>
        </div>

        <div className="header__status-group">
          {/* Backend connection status (original) */}
          <div className="header__status">
            <span className="header__status-indicator" />
            <span>{backendStatus}</span>
          </div>

          {/* Desktop Agent connection status (new) */}
          <AgentStatusBadge
            agentConnected={agentConnected}
            hasPendingPermission={Boolean(pendingPermission)}
          />
        </div>
      </header>

      <main className="chat-display">
        <VoiceAssistantOrb isThinking={isSending || isSpeaking} />

        <div className="chat-display__content">
          <p className="chat-display__question">{question}</p>
          <div className="chat-display__answer">
            <ReactMarkdown>{visibleAnswer}</ReactMarkdown>
          </div>
        </div>

        {chatHistory.length > 0 && (
          <section
            className="chat-history"
            aria-label="Conversation memory"
          >
            <div className="chat-history__header">Conversation memory</div>
            <div className="chat-history__list">
              {chatHistory.slice(-6).map((entry, index) => (
                <article
                  key={`${entry.role}-${index}-${entry.content.slice(0, 20)}`}
                  className={`chat-history__item chat-history__item--${entry.role}`}
                >
                  <span className="chat-history__role">
                    {entry.role === 'user' ? 'You' : 'Sofia'}
                  </span>
                  <p className="chat-history__content">{entry.content}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* Agent offline notice — shown only when backend is up but agent is not */}
        {backendBase && !agentConnected && (
          <div className="agent-offline-notice">
            <span className="agent-offline-notice__icon" aria-hidden="true">
              💻
            </span>
            <p className="agent-offline-notice__text">
              <strong>Desktop Agent not running.</strong> Computer-control
              commands (open apps, control Spotify, etc.) require the SOFIA
              Desktop Agent. Run{' '}
              <code className="agent-offline-notice__code">
                python agent_main.py
              </code>{' '}
              in the <code className="agent-offline-notice__code">desktop-agent/</code> folder.
            </p>
          </div>
        )}
      </main>

      {/* Voice Dock — Only microphone, continuous listening with 1.5s pause detection */}
      <footer className="voice-dock">
        {/* Live speech feedback pill */}
        {isListening && (
          <div
            className={`voice-dock__transcript-pill${liveTranscript ? ' voice-dock__transcript-pill--active' : ''}`}
            aria-live="polite"
          >
            <span className="voice-dock__transcript-dot" />
            <span className="voice-dock__transcript-text">
              {liveTranscript ? `“${liveTranscript}”` : 'Listening continuously... speak anytime'}
            </span>
            {liveTranscript && (
              <span className="voice-dock__transcript-countdown">
                Pause 1.5s to process
              </span>
            )}
          </div>
        )}

        {/* Main Microphone Button */}
        <div className="voice-dock__mic-container">
          <button
            id="microphone-toggle-btn"
            type="button"
            className={`voice-dock__mic-btn voice-dock__mic-btn--${
              isSending
                ? 'processing'
                : isSpeaking
                ? 'speaking'
                : isListening
                ? 'listening'
                : 'idle'
            }`}
            onClick={toggleMicrophone}
            disabled={!micSupported}
            aria-label={
              !micSupported
                ? 'Microphone not supported'
                : isListening
                ? 'Stop continuous listening'
                : 'Start continuous listening'
            }
            title={
              !micSupported
                ? 'Microphone not supported in this browser'
                : isListening
                ? 'Click to stop continuous listening'
                : 'Click to start continuous listening'
            }
          >
            {/* Concentric soundwave ripples during active listening */}
            {isListening && !isSpeaking && !isSending && (
              <span className="voice-dock__ripples" aria-hidden="true">
                <span className="voice-dock__ripple" />
                <span className="voice-dock__ripple" />
                <span className="voice-dock__ripple" />
              </span>
            )}

            <span className="voice-dock__mic-icon-wrap">
              <MicIcon className="voice-dock__icon" />
            </span>
          </button>
        </div>

        {/* Status text */}
        <div className="voice-dock__status">
          <span
            className={`voice-dock__status-indicator voice-dock__status-indicator--${
              isSending
                ? 'processing'
                : isSpeaking
                ? 'speaking'
                : isListening
                ? 'listening'
                : 'idle'
            }`}
          />
          <span className="voice-dock__status-label">
            {!micSupported
              ? 'Microphone input is not supported in this browser.'
              : isSending
              ? 'Processing command with local AI...'
              : isSpeaking
              ? 'Sofia is speaking...'
              : isListening
              ? 'Continuous listening active • Pause for 1.5s to process'
              : 'Tap microphone to start continuous listening'}
          </span>
        </div>
      </footer>
    </div>
  );
}


export default App;