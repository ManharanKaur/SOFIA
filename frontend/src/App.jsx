import './App.css';
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import VoiceAssistantOrb from './components/VoiceAssistantOrb';

const MicIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="9" y="2" width="6" height="12" rx="3" stroke="black" strokeWidth="2"/>
    <path d="M5 10a7 7 0 0 0 14 0" stroke="black" strokeWidth="2"/>
    <line x1="12" y1="17" x2="12" y2="22" stroke="black" strokeWidth="2"/>
    <line x1="8" y1="22" x2="16" y2="22" stroke="black" strokeWidth="2"/>
  </svg>
);

function App() {
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState('Type a command or use microphone...');
  const [fullAnswer, setFullAnswer] = useState('HI! I am Sofia, your local AI assistant. Ask me anything or give me a command!');
  const [visibleAnswer, setVisibleAnswer] = useState('HI! I am Sofia, your local AI assistant. Ask me anything or give me a command!');
  const [status, setStatus] = useState('Checking backend...');
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [micSupported, setMicSupported] = useState(false);

  // Speech recognition instance and helper refs.
  const recognitionRef = useRef(null);
  const shouldRestartRef = useRef(false);
  const isListeningRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const isSendingRef = useRef(false);

  // Speech synthesis refs.
  const selectedVoiceRef = useRef(null);
  const speechSynthesisRef = useRef(null);
  const autoResumeAfterSpeechRef = useRef(false);

  const backendBase = 'http://127.0.0.1:8000';

  // Keep refs in sync with React state so speech callbacks always get current values.
  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  useEffect(() => {
    isSendingRef.current = isSending;
  }, [isSending]);

  // Pick a female voice if available (for example Google UK English Female).
  const pickPreferredVoice = (voices) => {
    if (!voices || voices.length === 0) {
      return null;
    }

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
      if (match) {
        return match;
      }
    }

    const femaleByName = voices.find((voice) =>
      voice.name.toLowerCase().includes('female'),
    );
    if (femaleByName) {
      return femaleByName;
    }

    return voices.find((voice) => voice.lang?.toLowerCase().startsWith('en')) || voices[0];
  };

  // Start recognition safely.
  const startRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) {
      return;
    }

    try {
      recognition.start();
      console.log('mic started');
    } catch (error) {
      // start() can throw if called twice quickly.
      console.log('mic start skipped:', error);
    }
  };

  // Stop recognition safely.
  const stopRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) {
      return;
    }

    try {
      recognition.stop();
    } catch (error) {
      console.log('mic stop skipped:', error);
    }
  };

  // Speak Sofia's answer. It pauses mic listening while speaking, then resumes.
  const speakText = (text) => {
    const synth = speechSynthesisRef.current;
    if (!synth || !text) {
      return;
    }

    // Prevent overlapping voice output.
    synth.cancel();

    // Pause listening while assistant speaks to avoid feedback loop.
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

    utterance.onstart = () => {
      setIsSpeaking(true);
      console.log('speech started');
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      console.log('speech ended');

      // Resume continuous listening after speech if mic is still ON.
      if (autoResumeAfterSpeechRef.current && isListeningRef.current) {
        shouldRestartRef.current = true;
        startRecognition();
      }
    };

    utterance.onerror = () => {
      setIsSpeaking(false);
      console.log('speech error');

      if (autoResumeAfterSpeechRef.current && isListeningRef.current) {
        shouldRestartRef.current = true;
        startRecognition();
      }
    };

    synth.speak(utterance);
  };

  // Sends command to backend and handles both text + voice response.
  const processCommand = async (rawCommand) => {
    const command = rawCommand.trim();
    if (!command || isSendingRef.current) {
      return;
    }

    setIsSending(true);
    setQuestion(command);

    try {
      const response = await fetch(`${backendBase}/api/command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ command }),
      });

      if (!response.ok) {
        throw new Error('Failed to process command');
      }

      const data = await response.json();
      const message = data.message || 'No response from backend.';

      setFullAnswer(message);

      if (data.action === 'open_url' || data.action === 'search') {
        if (data.url) {
          window.open(data.url, '_blank', 'noopener,noreferrer');
        }
      }

      // Speak Sofia response automatically.
      speakText(message);
      setStatus('Backend connected');
    } catch {
      const fallbackMessage = 'Could not reach backend. Start the Python server and try again.';
      setFullAnswer(fallbackMessage);
      speakText(fallbackMessage);
      setStatus('Backend offline');
    } finally {
      setInput('');
      setIsSending(false);
    }
  };

  useEffect(() => {
    // Browser support check for speech recognition.
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setMicSupported(!!SpeechRecognition);

    // Speech synthesis setup and voice selection.
    if ('speechSynthesis' in window) {
      speechSynthesisRef.current = window.speechSynthesis;

      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        selectedVoiceRef.current = pickPreferredVoice(voices);
      };

      loadVoices();
      window.speechSynthesis.addEventListener('voiceschanged', loadVoices);

      // Cleanup voices listener.
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
      };
    }

    return undefined;
  }, []);

  useEffect(() => {
    // Simple backend health check.
    const checkHealth = async () => {
      try {
        const res = await fetch(`${backendBase}/health`);
        if (!res.ok) {
          throw new Error('Backend unavailable');
        }
        setStatus('Backend connected');
      } catch {
        setStatus('Backend offline');
      }
    };

    checkHealth();
  }, [backendBase]);

  useEffect(() => {
    // Create recognition instance once, then reuse it while mic is ON.
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      return undefined;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      // Collect only final transcript(s) and process directly.
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          transcript += `${result[0].transcript} `;
        }
      }

      const finalTranscript = transcript.trim();
      if (!finalTranscript) {
        return;
      }

      console.log('transcript received:', finalTranscript);
      setInput(finalTranscript);
      processCommand(finalTranscript);
    };

    recognition.onend = () => {
      // Continuous mode: restart mic when user left it ON.
      if (shouldRestartRef.current && isListeningRef.current && !isSpeakingRef.current) {
        setTimeout(() => {
          startRecognition();
        }, 250);
      }
    };

    recognition.onerror = (event) => {
      console.log('mic error:', event.error);

      // Permission denied or blocked: stop listening and show friendly message.
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        shouldRestartRef.current = false;
        setIsListening(false);
        setFullAnswer('Microphone permission denied. Please allow microphone access and try again.');
        return;
      }

      // If mic is ON, keep trying unless permission is denied.
      if (isListeningRef.current && !isSpeakingRef.current) {
        shouldRestartRef.current = true;
      }
    };

    recognitionRef.current = recognition;

    // Stop mic and speech when navigating away/unloading page.
    const handlePageExit = () => {
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
  }, []);

  const toggleMicrophone = () => {
    if (!micSupported || isSending) {
      setFullAnswer('Microphone is not supported in this browser.');
      return;
    }

    // Turn mic OFF.
    if (isListening) {
      shouldRestartRef.current = false;
      setIsListening(false);
      stopRecognition();
      return;
    }

    // Turn mic ON and start continuous listening.
    shouldRestartRef.current = true;
    setIsListening(true);
    setFullAnswer('Listening...');
    startRecognition();
  };

  const sendCommand = async () => {
    if (!input.trim() || isSending) {
      return;
    }

    processCommand(input);
  };

  useEffect(() => {
    // Show the response with a simple typewriter effect, like a chat assistant.
    let index = 0;
    setVisibleAnswer('');

    const timer = setInterval(() => {
      index += 1;
      setVisibleAnswer(fullAnswer.slice(0, index));

      if (index >= fullAnswer.length) {
        clearInterval(timer);
      }
    }, 12);

    return () => clearInterval(timer);
  }, [fullAnswer]);

  const onInputKeyDown = (event) => {
    if (event.key === 'Enter') {
      sendCommand();
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header__brand">
          <div className="header__logo-box">
            S
          </div>
          <h1 className="header__title">Sofia</h1>
        </div>
        <div className="header__status">
          <span className="header__status-indicator" />
          <span>{status}</span>
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
      </main>

      <footer className="search-section">
        <div className="search-bar">
          <button
            className={`search-bar__icon-btn search-bar__icon-btn--secondary${isListening ? ' is-active' : ''}`}
            type="button"
            onClick={toggleMicrophone}
            disabled={!micSupported || isSending}
            aria-label={micSupported ? 'Use microphone input' : 'Microphone not supported'}
            title={micSupported ? 'Use microphone input' : 'Microphone not supported in this browser'}
          >
            <span className="search-bar__icon-btn-label">
              {isListening ? 'Stop' : <MicIcon />}
            </span>
          </button>
          <input 
            type="text" 
            className="search-bar__input" 
            placeholder={micSupported ? 'Type a command or use the microphone...' : 'Type a command and press Enter...'}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onInputKeyDown}
          />
          <button
            className="search-bar__icon-btn search-bar__icon-btn--primary"
            type="button"
            onClick={sendCommand}
            disabled={isSending}
          >
            {isSending ? '...' : 'Send'}
          </button>
        </div>
        <div className="search-section__footer">
          <span>
            Commands are sent to your local backend at 127.0.0.1:8000.
            {micSupported
              ? ` Mic is ${isListening ? 'ON' : 'OFF'}. ${isSpeaking ? 'Sofia is speaking.' : 'Sofia is ready.'}`
              : ' Mic input is not supported in this browser.'}
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;