import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mic, MicOff, Play, Loader2, Bot, User, RefreshCw, AlertCircle, Key as KeyIcon, Volume2, X } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import toast from 'react-hot-toast';

/**
 * PluginTester - Premium Voice/Chat Interface
 * Replicates the high-end experience of the main VoiceFormFiller
 */
export function PluginTester({ plugin }) {
    const { isDark } = useTheme();

    // State
    const [apiKey, setApiKey] = useState('');
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState('idle'); // idle, active, completed, error
    const [progress, setProgress] = useState(0);
    const [isThinking, setIsThinking] = useState(false);

    // Voice State
    const [isListening, setIsListening] = useState(false);
    const [volumeLevel, setVolumeLevel] = useState(0);
    const recognitionRef = useRef(null);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const micStreamRef = useRef(null);
    const animationFrameRef = useRef(null);

    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isThinking]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopListening();
            window.speechSynthesis.cancel();
        };
    }, []);

    // Initialize Speech Recognition
    useEffect(() => {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false; // Stop after one sentence for simple turn-taking
            recognitionRef.current.interimResults = true;
            recognitionRef.current.lang = 'en-US';

            recognitionRef.current.onresult = (event) => {
                let final = '';
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    if (event.results[i].isFinal) {
                        final += event.results[i][0].transcript;
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }
                if (final) {
                    setInputValue(final);
                    handleVoiceSubmit(final); // Auto-submit on final result
                } else {
                    setInputValue(interim);
                }
            };

            recognitionRef.current.onend = () => {
                if (isListening) {
                    setIsListening(false);
                    stopAudioAnalysis();
                }
            };
        }
    }, [isListening]);

    // Audio Analysis (Visualizer)
    const startAudioAnalysis = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            micStreamRef.current = stream;
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            audioContextRef.current = ctx;
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 64; // Low res for simple orb
            analyserRef.current = analyser;
            const source = ctx.createMediaStreamSource(stream);
            source.connect(analyser);

            const data = new Uint8Array(analyser.frequencyBinCount);
            const draw = () => {
                if (!analyserRef.current) return;
                analyser.getByteFrequencyData(data);
                const vol = data.reduce((a, b) => a + b) / data.length;
                setVolumeLevel(Math.min(vol / 128, 1)); // Normalize 0-1
                animationFrameRef.current = requestAnimationFrame(draw);
            };
            draw();
        } catch (e) {
            console.error("Audio init failed", e);
        }
    };

    const stopAudioAnalysis = () => {
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (micStreamRef.current) micStreamRef.current.getTracks().forEach(t => t.stop());
        if (audioContextRef.current) audioContextRef.current.close();
        setVolumeLevel(0);
    };

    const toggleListening = () => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    };

    const startListening = () => {
        setIsListening(true);
        recognitionRef.current?.start();
        startAudioAnalysis();
        setInputValue(''); // Clear previous input
    };

    const stopListening = () => {
        setIsListening(false);
        recognitionRef.current?.stop();
        stopAudioAnalysis();
    };

    const speak = (text) => {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        const voices = window.speechSynthesis.getVoices();
        const preferred = voices.find(v => v.name.includes('Google') && v.lang.includes('en')) || voices[0];
        if (preferred) utter.voice = preferred;
        window.speechSynthesis.speak(utter);
    };

    // Format time
    const formatTime = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Start Session
    const startSession = useCallback(async () => {
        const trimmedKey = apiKey.trim();
        if (!trimmedKey || !trimmedKey.startsWith('ffp_')) {
            toast.error('Please enter a valid API key (starts with ffp_)');
            return;
        }

        setIsLoading(true);
        setMessages([]);
        setProgress(0);
        setStatus('active');
        setSessionId(null);

        try {
            const res = await fetch('http://localhost:8001/plugins/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': trimmedKey,
                    'X-Plugin-ID': plugin.id.toString()
                },
                body: JSON.stringify({ source_url: 'http://localhost/tester' })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to start session');

            setSessionId(data.session_id);
            if (data.current_question) {
                const msg = {
                    id: 'init',
                    role: 'bot',
                    text: data.current_question,
                    time: formatTime()
                };
                setMessages([msg]);
                speak(msg.text); // Speak initial question
            }
            toast.success('Session started');
        } catch (err) {
            toast.error(err.message);
            setStatus('error');
        } finally {
            setIsLoading(false);
        }
    }, [apiKey, plugin.id]);

    const handleVoiceSubmit = (text) => {
        submitMessage(text);
    };

    const handleSubmit = async (e) => {
        e?.preventDefault();
        submitMessage(inputValue);
    };

    const submitMessage = async (text) => {
        if (!text?.trim() || !sessionId || isThinking) return;

        const userText = text.trim();
        setInputValue('');
        stopListening(); // Stop listening while processing

        // Add user message
        setMessages(prev => [...prev, {
            id: 'u-' + Date.now(),
            role: 'user',
            text: userText,
            time: formatTime()
        }]);

        setIsThinking(true);

        try {
            const res = await fetch(`http://localhost:8001/plugins/sessions/${sessionId}/input`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey.trim(),
                    'X-Plugin-ID': plugin.id.toString()
                },
                body: JSON.stringify({ input: userText, request_id: 'req-' + Date.now() })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to submit input');

            setProgress(data.progress);

            if (data.is_complete) {
                await completeSession(sessionId);
            } else if (data.next_question) {
                const botMsg = {
                    id: 'b-' + Date.now(),
                    role: 'bot',
                    text: data.next_question,
                    time: formatTime()
                };
                setMessages(prev => [...prev, botMsg]);
                speak(botMsg.text);
            }
        } catch (err) {
            toast.error(err.message);
        } finally {
            setIsThinking(false);
        }
    };

    // Complete Session
    const completeSession = async (sid) => {
        try {
            setIsThinking(true);
            const res = await fetch(`http://localhost:8001/plugins/sessions/${sid}/complete`, {
                method: 'POST',
                headers: {
                    'X-API-Key': apiKey.trim(),
                    'X-Plugin-ID': plugin.id.toString()
                }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            setStatus('completed');
            setProgress(100);
            const completionMsg = `✅ Session Completed! ${data.records_created} record(s) saved.`;
            setMessages(prev => [...prev, {
                id: 'done-' + Date.now(),
                role: 'system',
                text: completionMsg,
                time: formatTime()
            }]);
            speak("Session completed successfully. Thank you.");
            toast.success('Session completed');
        } catch (err) {
            toast.error('Completion failed: ' + err.message);
        } finally {
            setIsThinking(false);
        }
    };

    // --- Render Components ---

    const MessageBubble = ({ msg }) => {
        const isUser = msg.role === 'user';
        const isSystem = msg.role === 'system';

        if (isSystem) return (
            <div className="flex justify-center my-6">
                <span className="text-xs px-4 py-1.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-medium tracking-wide">
                    {msg.text}
                </span>
            </div>
        );

        return (
            <div className={`flex gap-4 mb-6 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`
                    w-10 h-10 rounded-full flex items-center justify-center shrink-0 shadow-lg
                    ${isUser
                        ? isDark ? 'bg-zinc-800' : 'bg-white'
                        : 'bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-emerald-500/20'
                    }
                `}>
                    {isUser ? <User className="w-5 h-5 opacity-70" /> : <Bot className="w-5 h-5 text-white" />}
                </div>
                <div className={`max-w-[80%]`}>
                    <div className={`
                        p-4 rounded-2xl text-[15px] leading-relaxed shadow-sm
                        ${isUser
                            ? isDark ? 'bg-zinc-800 text-white rounded-tr-sm' : 'bg-white text-zinc-900 shadow-sm rounded-tr-sm'
                            : isDark ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-100 rounded-tl-sm' : 'bg-emerald-50 text-emerald-900 border border-emerald-100 rounded-tl-sm'
                        }
                    `}>
                        {msg.text}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col bg-transparent font-sans relative overflow-hidden">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between shrink-0">
                <div>
                    <h3 className={`text-xl font-bold tracking-tight flex items-center gap-2 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                        {status === 'active' && <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
                        Plugin Tester
                    </h3>
                    <p className={`text-xs opacity-60 ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                        {status === 'active' ? 'Voice session in progress' : 'Interactive simulation'}
                    </p>
                </div>
                {status !== 'idle' && (
                    <button
                        onClick={() => { setSessionId(null); setStatus('idle'); stopListening(); }}
                        className={`p-2 rounded-full hover:bg-white/5 transition-colors ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}
                        title="Reset Session"
                    >
                        <RefreshCw className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* API Key Input (if no session) */}
            {!sessionId && (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-8 animate-in fade-in zoom-in duration-500">
                    <div className="relative">
                        <div className="absolute inset-0 bg-emerald-500/20 blur-3xl rounded-full" />
                        <div className={`relative w-24 h-24 rounded-[2rem] flex items-center justify-center mb-2 shadow-2xl ${isDark ? 'bg-zinc-900 border border-white/10' : 'bg-white'}`}>
                            <Bot className="w-10 h-10 text-emerald-500" />
                        </div>
                    </div>

                    <div>
                        <h4 className={`text-2xl font-bold mb-3 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                            Start Simulation
                        </h4>
                        <p className={`text-sm max-w-xs mx-auto leading-relaxed ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                            Enter your API key to launch the voice interface simulator for <span className="text-emerald-500 font-medium">"{plugin.name}"</span>.
                        </p>
                    </div>

                    <div className="w-full max-w-sm space-y-4">
                        <div className="relative group">
                            <KeyIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 group-focus-within:text-emerald-500 transition-colors" />
                            <input
                                type="text"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="Paste your API key (ffp_...)"
                                className={`
                                    w-full pl-12 pr-4 py-4 rounded-2xl text-sm border transition-all shadow-sm
                                    ${isDark
                                        ? 'bg-black/20 border-white/10 text-white placeholder:text-white/20 focus:border-emerald-500/50 focus:bg-black/40'
                                        : 'bg-white border-zinc-200 text-zinc-900 focus:border-emerald-500'
                                    }
                                    focus:outline-none focus:ring-4 focus:ring-emerald-500/10
                                `}
                            />
                        </div>
                        <button
                            onClick={startSession}
                            disabled={!apiKey || isLoading}
                            className={`
                                w-full py-4 rounded-2xl font-bold uppercase tracking-widest text-xs flex items-center justify-center gap-3 transition-all
                                ${isDark
                                    ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-lg shadow-emerald-500/20'
                                    : 'bg-zinc-900 text-white hover:bg-zinc-800 shadow-xl shadow-zinc-900/10'
                                }
                                disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
                                hover:scale-[1.02] active:scale-[0.98]
                            `}
                        >
                            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                            Initialize Session
                        </button>
                    </div>
                </div>
            )}

            {/* Voice Interface */}
            {sessionId && (
                <>
                    {/* Progress */}
                    <div className="mb-6 px-1">
                        <div className="flex justify-between text-[10px] uppercase font-bold tracking-wider mb-2 opacity-50">
                            <span>Form Completion</span>
                            <span>{Math.round(progress)}%</span>
                        </div>
                        <div className={`h-1.5 w-full rounded-full overflow-hidden ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`}>
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                                className="h-full bg-emerald-500"
                                transition={{ type: "spring", stiffness: 50 }}
                            />
                        </div>
                    </div>

                    {/* Messages */}
                    <div className={`
                        flex-1 overflow-y-auto mb-6 -mx-4 px-4 custom-scrollbar
                        ${isDark ? 'bg-black/20 rounded-3xl mx-0 p-6 border border-white/5' : 'bg-zinc-50 rounded-3xl mx-0 p-6 border border-zinc-100'}
                    `}>
                        <AnimatePresence>
                            {messages.map((msg) => (
                                <motion.div
                                    key={msg.id}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                >
                                    <MessageBubble msg={msg} />
                                </motion.div>
                            ))}
                        </AnimatePresence>

                        {isThinking && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-2 p-4">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" />
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce delay-100" />
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce delay-200" />
                            </motion.div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Voice Orb Area */}
                    <div className="relative mb-6 flex justify-center py-4 min-h-[100px] items-center">
                        <AnimatePresence mode="wait">
                            {isListening ? (
                                <motion.div
                                    initial={{ scale: 0.8, opacity: 0 }}
                                    animate={{ scale: 1 + volumeLevel * 0.5, opacity: 1 }}
                                    exit={{ scale: 0.8, opacity: 0 }}
                                    className="relative flex items-center justify-center"
                                >
                                    {/* Visualizer Rings */}
                                    <div className="absolute inset-0 bg-emerald-500/20 blur-xl rounded-full" />
                                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30 z-10">
                                        <Mic className="w-8 h-8 text-white" />
                                    </div>
                                    {/* Ripple Effect */}
                                    {[1, 2, 3].map(i => (
                                        <motion.div
                                            key={i}
                                            className="absolute inset-0 rounded-full border border-emerald-500/30"
                                            animate={{ scale: [1, 1.5 + volumeLevel], opacity: [0.5, 0] }}
                                            transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.4 }}
                                        />
                                    ))}
                                </motion.div>
                            ) : (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="text-center"
                                >
                                    <button
                                        onClick={toggleListening}
                                        className={`
                                            w-16 h-16 rounded-full flex items-center justify-center transition-all
                                            ${isDark ? 'bg-white/10 hover:bg-white/20 text-white' : 'bg-black/5 hover:bg-black/10 text-zinc-600'}
                                        `}
                                    >
                                        <MicOff className="w-6 h-6 opacity-50" />
                                    </button>
                                    <p className="text-[10px] uppercase font-bold tracking-widest mt-3 opacity-40">Tap to Speak</p>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Input Bar */}
                    <form onSubmit={handleSubmit} className="relative">
                        <div className={`
                            flex items-center gap-2 p-2 pl-4 rounded-full border transition-all
                            ${isDark
                                ? 'bg-zinc-900 border-white/10 focus-within:border-emerald-500/50'
                                : 'bg-white border-zinc-200 focus-within:border-emerald-500 shadow-lg shadow-zinc-200/50'
                            }
                        `}>
                            <input
                                ref={inputRef}
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                placeholder="Type or speak..."
                                disabled={isThinking || status === 'completed'}
                                className="flex-1 bg-transparent border-none focus:outline-none py-3 text-sm"
                            />

                            {/* Send Button */}
                            <button
                                type="submit"
                                disabled={!inputValue.trim() || isThinking || status === 'completed'}
                                className={`
                                    w-10 h-10 rounded-full flex items-center justify-center transition-all shrink-0
                                    ${inputValue.trim() && !isThinking
                                        ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 hover:scale-110 active:scale-95'
                                        : 'bg-transparent text-zinc-300 cursor-not-allowed'
                                    }
                                `}
                            >
                                <Send className="w-4 h-4" />
                            </button>
                        </div>
                    </form>
                </>
            )}
        </div>
    );
}

export default PluginTester;
