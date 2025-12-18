import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Play, Pause, CheckCircle, AlertCircle, Volume2 } from 'lucide-react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import Aurora from '@/components/ui/Aurora';

const VoiceFormFiller = ({ formSchema, formContext, onComplete }) => {
  const [isListening, setIsListening] = useState(false);
  const [currentFieldIndex, setCurrentFieldIndex] = useState(0);
  const [formData, setFormData] = useState({});
  const [transcript, setTranscript] = useState('');
  const [processing, setProcessing] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState('');

  // Browser STT refs
  const recognitionRef = useRef(null);
  const pauseTimeoutRef = useRef(null);
  const indexRef = useRef(0); // Ref to track current index to avoid stale closures
  const formDataRef = useRef({}); // Ref to track form data to avoid stale closures
  const audioRef = useRef(null); // Ref for audio playback
  const idleTimeoutRef = useRef(null); // Ref for idle repeat timer

  const [lastFilled, setLastFilled] = useState(null); // Track last answer

  // Sync ref with state
  useEffect(() => {
    indexRef.current = currentFieldIndex;
  }, [currentFieldIndex]);

  // Memoize fields to prevent re-triggering effects on parent re-renders
  const allFields = React.useMemo(() => {
    return formSchema.flatMap(form =>
      form.fields.filter(field =>
        !field.hidden &&
        field.type !== 'submit' &&
        // Skip confirm password fields
        !(field.type === 'password' && (
          field.name.toLowerCase().includes('confirm') ||
          field.name.toLowerCase().includes('cpassword') ||
          field.name.toLowerCase().includes('verify')
        ))
      )
    );
  }, [formSchema]);

  useEffect(() => {
    // Initialize browser STT
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-IN';

      recognitionRef.current.onresult = handleBrowserSpeechResult;
      recognitionRef.current.onend = handleBrowserSpeechEnd;
      recognitionRef.current.onerror = handleBrowserSpeechError;
    }

    return () => {
      if (recognitionRef.current) recognitionRef.current.stop();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      clearTimeout(idleTimeoutRef.current);
    };
  }, []);

  // Effect to handle field changes: Update prompt and Play Audio ONCE
  useEffect(() => {
    if (allFields.length > 0 && currentFieldIndex < allFields.length) {
      const field = allFields[currentFieldIndex];
      const prompt = field.smart_prompt || `Please provide ${field.label || field.name}`;
      setCurrentPrompt(prompt);

      // Auto-play audio for the field (once)
      playPrompt(field.name);

      // Start idle timer - repeat after 15s if no user action
      startIdleTimer(field.name);
    }
  }, [currentFieldIndex, allFields]);

  // Idle timer: Repeat prompt after 15 seconds of silence
  const startIdleTimer = (fieldName) => {
    clearTimeout(idleTimeoutRef.current);
    idleTimeoutRef.current = setTimeout(() => {
      console.log("User idle, repeating prompt...");
      playPrompt(fieldName);
      // Restart timer for next repeat
      startIdleTimer(fieldName);
    }, 15000); // 15 seconds
  };

  // Clear idle timer when user speaks
  useEffect(() => {
    if (transcript) {
      clearTimeout(idleTimeoutRef.current);
    }
  }, [transcript]);

  const playPrompt = (fieldName) => {
    if (!fieldName) return;

    // Stop current audio if any
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    // Backend endpoint for speech
    const audioUrl = `http://127.0.0.1:8000/speech/${encodeURIComponent(fieldName)}`;

    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.play().catch(e => {
      console.warn("Audio auto-play blocked or failed:", e);
    });
  };

  const handleBrowserSpeechResult = (event) => {
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
    }

    if (finalTranscript) {
      setTranscript(finalTranscript);
      clearTimeout(pauseTimeoutRef.current);
      // Process logic using the CURRENT index from ref
      processVoiceInput(finalTranscript, indexRef.current);
    } else {
      // Show interim results too if desired, for now we stick to final for processing but we could show interim in UI
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (!event.results[i].isFinal) interim += event.results[i][0].transcript;
      }
      if (interim) setTranscript(interim);
    }
  };

  const processVoiceInput = async (text, activeIndex) => {
    setProcessing(true);
    // Simulate processing for UI demo
    setTimeout(() => {
      const field = allFields[activeIndex];

      // Update State (for UI)
      setFormData(prev => ({ ...prev, [field.name]: text }));

      // Update Ref (for logic/submission safety)
      formDataRef.current = { ...formDataRef.current, [field.name]: text };

      setLastFilled({ label: field.label || field.name, value: text }); // Store last answer
      setTranscript('');
      setProcessing(false);
      handleNextField(activeIndex);
    }, 1500);
  };

  const handleNextField = (currentIndex) => {
    if (currentIndex < allFields.length - 1) {
      const nextIndex = currentIndex + 1;
      setCurrentFieldIndex(nextIndex); // Update State
    } else {
      // Use Ref here to ensure we send the accumulated data, not the stale state closure
      console.log("Form Complete. Submitting:", formDataRef.current);
      onComplete(formDataRef.current);
    }
  };

  const handleBrowserSpeechEnd = () => { if (isListening) recognitionRef.current.start(); };
  const handleBrowserSpeechError = (e) => { console.error("Speech error", e); };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  const currentField = allFields[currentFieldIndex];
  const progressPercent = ((currentFieldIndex) / allFields.length) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 font-sans text-white">

      {/* Window Container */}
      <div className="w-full max-w-2xl bg-black/40 border border-white/20 rounded-2xl backdrop-blur-2xl shadow-2xl relative overflow-hidden flex flex-col min-h-[600px]">

        {/* Window Header */}
        <div className="bg-white/5 p-4 flex items-center justify-between border-b border-white/10 shrink-0">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
            <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
          </div>
          <div className="text-xs font-semibold text-white/40 flex items-center gap-2 font-mono uppercase tracking-widest">
            voice_interface.exe
          </div>
          <div className="w-14"></div>
        </div>

        <div className="p-10 flex flex-col items-center justify-between flex-1 relative">
          {/* Background Glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-green-500/10 blur-[80px] rounded-full pointer-events-none" />

          <div className="w-full space-y-8 relative z-10">
            <div className="flex justify-between items-end border-b border-white/10 pb-4">
              <div>
                <h2 className="text-3xl font-bold tracking-tight text-white">Voice Form Filling</h2>
                <p className="text-white/60 mt-1">Speak clearly to fill inputs</p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-mono font-bold text-green-400">
                  {currentFieldIndex + 1} <span className="text-white/30 text-base">/ {allFields.length}</span>
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="h-1 bg-white/10 rounded-full overflow-hidden w-full">
              <motion.div
                className="h-full bg-green-400 shadow-[0_0_10px_rgba(74,222,128,0.5)]"
                animate={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Previous Answer Feedback */}
            <div className="h-8 flex justify-center items-center">
              <AnimatePresence mode="wait">
                {lastFilled && (
                  <motion.div
                    key={lastFilled.label}
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-xs font-medium text-green-300"
                  >
                    <CheckCircle size={12} />
                    <span>Captured: <strong className="text-white">{lastFilled.value}</strong> for {lastFilled.label}</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Active Field Prompt */}
            <AnimatePresence mode="wait">
              <motion.div
                key={currentField?.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="py-2"
              >
                <div className="bg-white/5 border border-white/10 rounded-2xl p-8 text-center backdrop-blur-sm min-h-[160px] flex flex-col justify-center items-center relative group">
                  {/* Replay Button */}
                  <button
                    onClick={() => playPrompt(currentField?.name)}
                    className="absolute top-4 right-4 p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/40 hover:text-white transition-all opacity-0 group-hover:opacity-100"
                    title="Replay Voice"
                  >
                    <Volume2 size={16} />
                  </button>

                  <h3 className="text-3xl font-medium text-white mb-3 tracking-tight">
                    {currentPrompt}
                  </h3>
                  <p className="text-white/40 text-sm uppercase tracking-wider font-semibold flex items-center justify-center gap-2">
                    {currentField?.label || currentField?.name} {currentField?.required && <span className="text-red-400 text-xs tracking-normal px-2 py-0.5 rounded bg-red-400/10 border border-red-400/20">* Required</span>}
                  </p>
                </div>
              </motion.div>
            </AnimatePresence>

            {/* Live Transcript Display */}
            <div className="h-16 flex flex-col items-center justify-center space-y-2">
              {processing ? (
                <div className="flex items-center gap-2 text-green-400 animate-pulse bg-green-500/10 px-4 py-2 rounded-lg">
                  <div className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-sm font-medium">Processing answer...</span>
                </div>
              ) : transcript ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-center"
                >
                  <p className="text-xs text-white/40 uppercase tracking-widest mb-1">Interpreted Voice</p>
                  <p className="text-white text-xl font-medium px-6 py-2 bg-white/5 rounded-xl border border-white/10 shadow-inner">
                    "{transcript}"
                  </p>
                </motion.div>
              ) : (
                <div className="flex items-center gap-2 text-white/30 italic">
                  <div className="w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse" />
                  Listening...
                </div>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="mt-8 relative z-10">
            <button
              onClick={toggleListening}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl ${isListening
                ? 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30 shadow-[0_0_30px_rgba(239,68,68,0.3)]'
                : 'bg-green-500 text-black hover:scale-105 shadow-[0_0_30px_rgba(34,197,94,0.4)]'
                }`}
            >
              {isListening ? <MicOff size={32} /> : <Mic size={32} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceFormFiller;