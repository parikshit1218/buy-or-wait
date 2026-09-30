import React, { useState, useEffect, useRef } from 'react';
import { sendVoiceQuery } from '../api';
import { Mic, Send, Sparkles, AlertCircle, CheckCircle, Square, RefreshCw } from 'lucide-react';
import { formatINR } from '../utils/currencyFormatter';

/**
 * VoiceOrb Component
 * - Circular Voice Assistant Orb in Forest Ink (#163300) with Lime Voltage (#9fe870) ring
 * - Idle: gentle breathing pulse (scale 1 to 1.03, ~3s loop) with white mic icon
 * - Listening: Lime Voltage ripple pulsing outward, mic swaps for animated sound-wave bars
 * - Thinking: subtle spinning ring around orb awaiting API response
 * - Speaking: animated sound-wave bars + "Stop" link button
 * - "Try asking" suggestion chips
 * - Text input fallback with send button
 * - "Transcript & Interaction History" panel with Clear link directly below input
 */
export function VoiceOrb({ className = '' }) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [typedInput, setTypedInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Ask me any purchase question aloud or type it below. I will check your real 90-day numbers and deliver the verdict — without sugarcoating it.',
      verdict: null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const recognitionRef = useRef(null);
  const chatBottomRef = useRef(null);

  // Initialize Web Speech API
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-IN'; // Indian English

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      const current = event.resultIndex;
      const text = event.results[current][0].transcript;
      setTranscript(text);
      if (event.results[current].isFinal) {
        handleProcessQuery(text);
      }
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {
          // ignore
        }
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const toggleListening = () => {
    if (!speechSupported || !recognitionRef.current) {
      alert('Speech recognition is not supported in this browser. Please use Google Chrome or type your question below.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        setIsSpeaking(false);
      }
      try {
        recognitionRef.current.start();
      } catch (err) {
        console.warn('Recognition start error:', err);
      }
    }
  };

  const stopSpeaking = () => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  };

  const speakText = (textToSpeak) => {
    if (!window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-IN';

    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find((v) => v.lang.includes('en') || v.name.includes('India'));
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const handleProcessQuery = async (queryText) => {
    const cleanQuery = (queryText || '').trim();
    if (!cleanQuery) return;

    const userMsg = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: cleanQuery,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setTypedInput('');
    setTranscript('');
    setIsProcessing(true);

    try {
      const response = await sendVoiceQuery(cleanQuery, 'user_07');
      const spokenText = response.spoken_response || response.decision?.decision_explanation || 'Here is your verdict.';

      const assistantMsg = {
        id: `assistant_${Date.now()}`,
        sender: 'assistant',
        text: spokenText,
        verdict: response.verdict,
        intent: response.extracted_intent,
        decision: response.decision,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      speakText(spokenText);
    } catch (err) {
      const errorMsg = {
        id: `assistant_${Date.now()}`,
        sender: 'assistant',
        text: `Error connecting to voice engine: ${err.message || 'Please check backend connection.'}`,
        verdict: 'ERROR',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTypedSubmit = (e) => {
    e.preventDefault();
    if (typedInput.trim() && !isProcessing) {
      handleProcessQuery(typedInput);
    }
  };

  const samplePrompts = [
    'Can I buy a laptop for ₹65,000 today?',
    'Can I afford a ₹15,000 festival flight?',
    'Can I pay ₹1,97,400 for a rental deposit?',
    'Can I buy a smartwatch for ₹25,000 right now?',
  ];

  return (
    <div className={`w-full flex flex-col items-center justify-center space-y-16 ${className}`}>
      {/* Inline Keyframe Styles */}
      <style>{`
        @keyframes orbBreathe {
          0%, 100% {
            transform: scale(1);
            box-shadow: 0 0 25px rgba(159, 232, 112, 0.25), inset 0 0 20px rgba(159, 232, 112, 0.15);
          }
          50% {
            transform: scale(1.03);
            box-shadow: 0 0 45px rgba(159, 232, 112, 0.5), inset 0 0 30px rgba(159, 232, 112, 0.3);
          }
        }
        @keyframes soundWave {
          0%, 100% { height: 8px; }
          50% { height: 32px; }
        }
        .animate-orb-breathe {
          animation: orbBreathe 3s ease-in-out infinite;
        }
        .animate-wave-1 { animation: soundWave 0.8s ease-in-out infinite; }
        .animate-wave-2 { animation: soundWave 0.6s ease-in-out infinite 0.15s; }
        .animate-wave-3 { animation: soundWave 0.9s ease-in-out infinite 0.3s; }
        .animate-wave-4 { animation: soundWave 0.7s ease-in-out infinite 0.45s; }
        .animate-wave-5 { animation: soundWave 0.85s ease-in-out infinite 0.2s; }
      `}</style>

      {/* 1. THE ORB Container */}
      <div className="flex flex-col items-center justify-center">
        <div className="relative flex items-center justify-center my-2">
          {/* Outward Lime Voltage Ripples during Listening */}
          {isListening && (
            <>
              <div className="absolute h-[280px] w-[280px] sm:h-[320px] sm:w-[320px] rounded-full bg-lime-voltage/25 animate-ping" />
              <div className="absolute h-[310px] w-[310px] sm:h-[350px] sm:w-[350px] rounded-full border-2 border-lime-voltage/40 animate-pulse" />
            </>
          )}

          {/* Spinning Ring during Thinking State */}
          {isProcessing && (
            <div className="absolute h-[270px] w-[270px] sm:h-[300px] sm:w-[300px] rounded-full border-4 border-transparent border-t-lime-voltage border-r-lime-voltage/60 animate-spin" />
          )}

          {/* Circular Orb Button */}
          <button
            onClick={toggleListening}
            disabled={isProcessing}
            aria-label={isListening ? 'Stop listening' : 'Tap to ask with voice'}
            className={`relative z-10 h-[240px] w-[240px] sm:h-[270px] sm:w-[270px] rounded-full bg-forest-ink border-4 border-lime-voltage flex flex-col items-center justify-center text-paper transition-transform duration-300 cursor-pointer select-none ${
              isListening
                ? 'scale-105 shadow-[0_0_50px_rgba(159,232,112,0.6)]'
                : isSpeaking
                ? 'scale-102 shadow-[0_0_40px_rgba(159,232,112,0.45)]'
                : isProcessing
                ? 'scale-100 opacity-95'
                : 'animate-orb-breathe hover:scale-105'
            }`}
          >
            {/* Inner Content Icon / Sound Waves */}
            <div className="flex items-center justify-center h-16 w-16 mb-2">
              {isListening || isSpeaking ? (
                /* Animated Sound Wave Bars */
                <div className="flex items-center gap-1.5 h-10">
                  <span className="w-1.5 bg-lime-voltage rounded-full animate-wave-1" />
                  <span className="w-1.5 bg-lime-voltage rounded-full animate-wave-2" />
                  <span className="w-1.5 bg-lime-voltage rounded-full animate-wave-3" />
                  <span className="w-1.5 bg-lime-voltage rounded-full animate-wave-4" />
                  <span className="w-1.5 bg-lime-voltage rounded-full animate-wave-5" />
                </div>
              ) : isProcessing ? (
                /* Thinking Indicator */
                <div className="h-8 w-8 rounded-full border-3 border-paper/20 border-t-lime-voltage animate-spin" />
              ) : (
                /* Large White Microphone Icon */
                <Mic className="h-14 w-14 text-paper stroke-[2.2]" />
              )}
            </div>

            {/* Label in Inter 600 */}
            <span className="text-[17px] sm:text-[19px] font-semibold text-paper font-sans tracking-tight">
              {isListening
                ? 'Listening...'
                : isProcessing
                ? 'Checking numbers...'
                : isSpeaking
                ? 'Speaking verdict'
                : 'Tap to ask'}
            </span>

            <span className="text-[12px] text-lime-voltage font-medium mt-1">
              {isListening
                ? 'Speak now (in ₹)'
                : isSpeaking
                ? 'Tap to mute'
                : isProcessing
                ? 'Deterministic evaluation'
                : 'Voice or question'}
            </span>
          </button>
        </div>

        {/* Stop Speaking / Listening Button */}
        {(isSpeaking || isListening) && (
          <button
            onClick={stopSpeaking}
            className="mt-4 text-caption font-semibold text-alarm-red hover:underline inline-flex items-center gap-1 cursor-pointer"
          >
            <Square className="h-3.5 w-3.5 fill-alarm-red" />
            <span>Stop</span>
          </button>
        )}

        {/* Live Transcript Subtext when listening */}
        {isListening && transcript && (
          <p className="mt-4 text-caption text-forest-ink font-medium max-w-md text-center bg-lime-voltage/20 px-4 py-1.5 rounded-full animate-fadeIn">
            "{transcript}"
          </p>
        )}
      </div>

      {/* 2. "Try Asking" Suggestion Chips */}
      <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl px-4">
        <span className="text-micro font-bold uppercase text-slate flex items-center gap-1 mr-1">
          <Sparkles className="h-3.5 w-3.5 text-forest-ink" /> Try asking:
        </span>
        {samplePrompts.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => handleProcessQuery(prompt)}
            disabled={isProcessing}
            className="rounded-full bg-fog px-4 py-1.5 text-caption font-medium text-charcoal hover:bg-linen-mist hover:text-forest-ink hover:scale-105 active:scale-95 transition-all duration-200 ease-out cursor-pointer disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* 3. Text Input Fallback with Send Button */}
      <form
        onSubmit={handleTypedSubmit}
        className="w-full max-w-xl flex items-center gap-3 px-4"
      >
        <input
          type="text"
          value={typedInput}
          onChange={(e) => setTypedInput(e.target.value)}
          placeholder={speechSupported ? "Or type a purchase question in ₹..." : "Type your purchase question in ₹..."}
          disabled={isProcessing}
          className="flex-1 rounded-full bg-paper px-5 py-3 text-body-sm text-charcoal placeholder:text-pebble border border-fog focus:outline-none focus:border-forest-ink shadow-sm transition-colors duration-200"
        />
        <button
          type="submit"
          disabled={isProcessing || !typedInput.trim()}
          className="h-11 w-11 rounded-full bg-forest-ink text-paper flex items-center justify-center hover:bg-spruce hover:scale-105 active:scale-95 disabled:hover:scale-100 disabled:opacity-40 transition-all duration-200 ease-out cursor-pointer shrink-0 shadow-sm"
          aria-label="Send typed query"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>

      {/* 4. Transcript & Interaction History Panel */}
      <section className="w-full max-w-2xl rounded-cards bg-fog/80 p-6 sm:p-8 shadow-subtle flex flex-col h-[400px] border border-forest-ink/5">
        <div className="flex items-center justify-between pb-3 border-b border-forest-ink/10 mb-4">
          <span className="text-caption font-bold text-forest-ink uppercase tracking-wide">
            Transcript & Interaction History
          </span>
          <button
            onClick={() => setMessages([messages[0]])}
            className="text-micro font-bold text-slate hover:text-forest-ink active:scale-95 flex items-center gap-1 cursor-pointer transition-all duration-200"
          >
            <RefreshCw className="h-3 w-3" /> Clear
          </button>
        </div>

        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2 text-left">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col animate-stagger-fade ${
                msg.sender === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-[85%] rounded-[14px] p-4 text-body-sm shadow-sm ${
                  msg.sender === 'user'
                    ? 'bg-forest-ink text-paper rounded-br-none'
                    : 'bg-paper text-charcoal rounded-bl-none border border-fog'
                }`}
              >
                {/* Header for Assistant Messages */}
                {msg.sender === 'assistant' && msg.verdict && (
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-fog">
                    {msg.verdict === 'BUY_NOW' || msg.verdict === 'AFFORDABLE_WITH_PLAN' ? (
                      <span className="rounded-tags bg-linen-mist text-forest-ink px-2.5 py-0.5 text-micro font-bold flex items-center gap-1">
                        <CheckCircle className="h-3 w-3" /> {msg.verdict.replace(/_/g, ' ')}
                      </span>
                    ) : (
                      <span className="rounded-tags bg-alarm-red/10 text-alarm-red px-2.5 py-0.5 text-micro font-bold flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" /> {msg.verdict.replace(/_/g, ' ')}
                      </span>
                    )}

                    {msg.intent?.item_name && (
                      <span className="text-micro font-bold text-slate">
                        {msg.intent.item_name} ({formatINR(msg.intent.amount)})
                      </span>
                    )}
                  </div>
                )}

                <p className="leading-relaxed">{msg.text}</p>
              </div>

              <span className="text-[10px] text-slate mt-1 px-1">{msg.timestamp}</span>
            </div>
          ))}

          {isProcessing && (
            <div className="flex items-center gap-2 text-caption text-slate italic p-2">
              <span className="h-2 w-2 rounded-full bg-forest-ink animate-ping"></span>
              Consulting deterministic cashflow ledger...
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>
      </section>
    </div>
  );
}

export default VoiceOrb;

