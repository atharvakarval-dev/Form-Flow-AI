import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Mic, MicOff, ChevronLeft, ChevronRight, SkipForward, Send, Volume2, Keyboard, Terminal, Activity, CheckCircle, Sparkles, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { SiriWave } from '@/components/ui';
import api, { API_BASE_URL, refineText, startConversationSession, sendConversationMessage } from '@/services/api';

const VoiceFormFiller = ({ formSchema, formContext, onComplete, onClose }) => {
    const [isListening, setIsListening] = useState(false);
    const [currentFieldIndex, setCurrentFieldIndex] = useState(0);
    const [formData, setFormData] = useState({});
    const [transcript, setTranscript] = useState('');
    const [processing, setProcessing] = useState(false);
    const [showTextInput, setShowTextInput] = useState(false);
    const [textInputValue, setTextInputValue] = useState('');

    // Magic Fill State
    const [magicFillLoading, setMagicFillLoading] = useState(true);
    const [magicFillSummary, setMagicFillSummary] = useState('');

    // Refs
    const recognitionRef = useRef(null);
    const pauseTimeoutRef = useRef(null);
    const indexRef = useRef(0);
    const formDataRef = useRef({});
    const audioRef = useRef(null);
    const idleTimeoutRef = useRef(null);
    const [userProfile, setUserProfile] = useState(null);
    const [autoFilledFields, setAutoFilledFields] = useState({});
    const [lastFilled, setLastFilled] = useState(null);

    // Q&A history for AI context - tracks previous answers for better refinement
    const [qaHistory, setQaHistory] = useState([]);
    const qaHistoryRef = useRef([]);  // Ref to avoid stale closure in async callbacks

    // Audio visualization
    const [volumeLevel, setVolumeLevel] = useState(0);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const micStreamRef = useRef(null);
    const animationFrameRef = useRef(null);

    // Field Mappings
    const fieldMappings = {
        'fullname': 'fullname', 'yourname': 'fullname',
        'firstname': 'first_name', 'lastname': 'last_name',
        'email': 'email', 'phone': 'mobile', 'mobile': 'mobile',
        'city': 'city', 'state': 'state', 'country': 'country',
        'zip': 'pincode', 'pin': 'pincode', 'pincode': 'pincode',
        'address': 'address', 'company': 'company', 'job': 'job_title'
    };

    useEffect(() => { indexRef.current = currentFieldIndex; }, [currentFieldIndex]);

    const allFields = useMemo(() => {
        return formSchema.flatMap(form =>
            form.fields.filter(field => {
                const name = (field.name || '').toLowerCase();
                const label = (field.label || '').toLowerCase();
                const isHidden = field.hidden || field.type === 'hidden';
                const isSubmit = field.type === 'submit';

                // Robust check for confirmation fields (password confirm/verify)
                const isConfirm = ['confirm', 'verify', 'repeat', 'retype'].some(k => name.includes(k) || label.includes(k)) &&
                    (name.includes('password') || label.includes('password') || field.type === 'password');

                const isTerms = ['terms', 'agree', 'policy'].some(kw => name.includes(kw));

                return !isHidden && !isSubmit && !isConfirm && !isTerms;
            })
        );
    }, [formSchema]);

    // Conversation State
    const [sessionId, setSessionId] = useState(null);
    const [aiResponse, setAiResponse] = useState('');

    // Init Speech
    useEffect(() => {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = true;
            recognitionRef.current.interimResults = true;
            recognitionRef.current.lang = 'en-IN';
            recognitionRef.current.onresult = handleBrowserSpeechResult;
        }
        return () => {
            recognitionRef.current?.stop();
            audioRef.current?.pause();
            window.speechSynthesis.cancel(); // Stop AI speech
            clearTimeout(idleTimeoutRef.current);
            stopAudioAnalysis();
        };
    }, []);

    // Load Profile
    useEffect(() => {
        const load = async () => {
            const token = localStorage.getItem('token');
            if (!token) return;
            try {
                const res = await api.get('/users/me');
                setUserProfile(res.data);
            } catch (e) { }
        };
        load();
    }, []);

    // 🪄 MAGIC FILL & CONVERSATION START
    useEffect(() => {
        const init = async () => {
            // Wait for user profile to be loaded first (or confirmed null)
            if (!formSchema?.length) return;
            if (magicFillLoading && userProfile === null) return; // Wait strictly for profile attempt

            let currentData = { ...formDataRef.current };

            // 1. Run Magic Fill
            if (userProfile && !sessionId) {
                try {
                    console.log('✨ Starting Magic Fill...');
                    const response = await api.post('/magic-fill', {
                        form_schema: formSchema,
                        user_profile: userProfile
                    });

                    if (response.data?.success && response.data.filled) {
                        const filled = response.data.filled;
                        setAutoFilledFields(prev => ({ ...prev, ...filled }));
                        setFormData(prev => ({ ...prev, ...filled }));
                        formDataRef.current = { ...formDataRef.current, ...filled };
                        currentData = { ...currentData, ...filled };
                        const firstUnfilled = allFields.findIndex(f => !filled[f.name] && !formDataRef.current[f.name]);
                        if (firstUnfilled > 0) setCurrentFieldIndex(firstUnfilled);
                        setMagicFillSummary(response.data.summary || `Filled ${Object.keys(filled).length} fields`);
                    }
                } catch (e) {
                    console.error('❌ Magic Fill failed:', e);
                } finally {
                    setMagicFillLoading(false);
                }
            } else {
                setMagicFillLoading(false);
            }

            // 2. Start Conversation Session (once, after magic fill)
            if (!sessionId) {
                try {
                    console.log('💬 Starting Conversation Session...');
                    const sessionRes = await startConversationSession(formSchema, window.location.href, currentData);
                    console.log('💬 Session Started:', sessionRes);
                    setSessionId(sessionRes.session_id);
                    if (sessionRes.greeting) {
                        const utter = new SpeechSynthesisUtterance(sessionRes.greeting);
                        window.speechSynthesis.speak(utter);
                        setAiResponse(sessionRes.greeting);
                    }
                } catch (e) {
                    console.error('❌ Failed to start conversation session:', e);
                }
            }
        };

        init();
    }, [formSchema, userProfile]);

    // Fallback: Simple profile mapping (runs if Magic Fill doesn't cover everything)
    useEffect(() => {
        if (!userProfile || !allFields.length || magicFillLoading) return;
        const autoFilled = {};
        const profile = { ...userProfile, fullname: `${userProfile.first_name} ${userProfile.last_name}`.trim() };

        allFields.forEach(field => {
            // Skip if already filled by Magic Fill
            if (formDataRef.current[field.name]) return;

            // Check both name and label for matches
            const cleanName = (field.name + ' ' + (field.label || '')).toLowerCase().replace(/[^a-z]/g, '');
            for (const [key, profileKey] of Object.entries(fieldMappings)) {
                if (cleanName.includes(key)) {
                    if (profile[profileKey]) autoFilled[field.name] = profile[profileKey];
                    break;
                }
            }
        });

        if (Object.keys(autoFilled).length) {
            setAutoFilledFields(prev => ({ ...prev, ...autoFilled }));
            setFormData(prev => ({ ...prev, ...autoFilled }));
            formDataRef.current = { ...formDataRef.current, ...autoFilled };
        }
    }, [userProfile, allFields, magicFillLoading]);

    // Prompt Playback & Input Pre-fill
    useEffect(() => {
        if (allFields.length && currentFieldIndex < allFields.length) {
            const field = allFields[currentFieldIndex];
            const preFilledValue = formDataRef.current[field.name] || autoFilledFields[field.name];

            setTranscript(preFilledValue || '');
            setTextInputValue(preFilledValue || '');
            setShowTextInput(false);

            // Only play standard prompt if we don't have an active AI response regarding this field
            // Or just play it anyway as a label?
            playPrompt(field.name);
        }
    }, [currentFieldIndex, allFields, autoFilledFields]);

    const playPrompt = async (fieldName) => {
        try {
            const audio = new Audio(`${API_BASE_URL}/speech/${fieldName}?t=${Date.now()}`);
            audioRef.current = audio;
            audio.onended = () => {
                idleTimeoutRef.current = setTimeout(() => playPrompt(fieldName), 20000);
            };
            await audio.play().catch(() => { });
        } catch (e) { }
    };

    const handleBrowserSpeechResult = (event) => {
        let final = '', interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            event.results[i].isFinal ? (final += event.results[i][0].transcript) : (interim += event.results[i][0].transcript);
        }
        setTranscript(final || interim);
        if (final) {
            clearTimeout(pauseTimeoutRef.current);
            pauseTimeoutRef.current = setTimeout(() => processVoiceInput(final.trim(), indexRef.current), 1000);
        }
    };

    const processVoiceInput = async (text, idx) => {
        if (!text || idx >= allFields.length) return;
        setProcessing(true);
        const field = allFields[idx];

        // Use Conversation Agent if session exists
        if (sessionId) {
            try {
                console.log(`💬 Sending to Agent: "${text}"`);
                const result = await sendConversationMessage(sessionId, text);
                console.log('💬 Agent Response:', result);

                // Update extracted values
                if (result.extracted_values) {
                    // Merge new values
                    setFormData(prev => ({ ...prev, ...result.extracted_values }));
                    formDataRef.current = { ...formDataRef.current, ...result.extracted_values };
                    // Identify what was just filled to show toast
                    const filledKeys = Object.keys(result.extracted_values);
                    if (filledKeys.length > 0) {
                        const lastKey = filledKeys[filledKeys.length - 1];
                        setLastFilled({ label: lastKey, value: result.extracted_values[lastKey] });
                    }
                }

                // Handle AI Speech Response
                if (result.response) {
                    setAiResponse(result.response);
                    window.speechSynthesis.cancel();
                    const utter = new SpeechSynthesisUtterance(result.response);
                    // Use a good English voice if available
                    const voices = window.speechSynthesis.getVoices();
                    const preferredVoice = voices.find(v => v.name.includes('Google') && v.lang.includes('en')) || voices[0];
                    if (preferredVoice) utter.voice = preferredVoice;
                    window.speechSynthesis.speak(utter);
                }

                if (result.is_complete) {
                    onComplete?.(formDataRef.current);
                }

                // If the current field was filled, move next or jump to AI suggestion
                if (result.extracted_values && result.extracted_values[field.name]) {
                    setTimeout(() => handleNext(idx), 1000);
                } else if (result.next_questions && result.next_questions.length > 0) {
                    // AI suggested a new path/question
                    // "next_questions" is now a list of field objects: [{name: 'email', ...}]
                    const nextFieldObj = result.next_questions[0];
                    if (nextFieldObj && nextFieldObj.name) {
                        const nextIdx = allFields.findIndex(f => f.name === nextFieldObj.name);
                        if (nextIdx !== -1 && nextIdx !== idx) {
                            console.log(`🦘 Jumping to field: ${nextFieldObj.name} (Index ${nextIdx})`);
                            setCurrentFieldIndex(nextIdx);
                        }
                    }
                }

            } catch (e) {
                console.error("Agent failed, falling back:", e);
                // Fallback to simple update if agent fails
                updateField(field, text);
                setTimeout(() => handleNext(idx), 600);
            }
        } else {
            // Fallback: simple text refinement
            try {
                const fieldLabel = field.label || field.display_name || field.name;
                const fieldType = inferFieldType(field);
                const result = await api.refineText(text, fieldLabel, fieldType, qaHistoryRef.current);
                const val = (result.success && result.refined) ? result.refined : text;
                updateField(field, val);
            } catch (e) {
                updateField(field, text);
            }
            setTimeout(() => handleNext(idx), 600);
        }

        setProcessing(false);
    };

    // Infer field type from field metadata for better AI formatting
    const inferFieldType = (field) => {
        const name = (field.name || '').toLowerCase();
        const label = (field.label || '').toLowerCase();
        const type = (field.type || 'text').toLowerCase();

        if (type === 'email' || name.includes('email') || label.includes('email')) return 'email';
        if (type === 'tel' || name.includes('phone') || name.includes('mobile') || label.includes('phone')) return 'phone';
        if (name.includes('name') || label.includes('name')) return 'name';
        if (type === 'number' || name.includes('age') || name.includes('experience')) return 'number';
        if (type === 'date' || name.includes('date')) return 'date';
        return 'text';
    };

    const updateField = (field, val) => {
        setFormData(prev => ({ ...prev, [field.name]: val }));
        formDataRef.current = { ...formDataRef.current, [field.name]: val };
        setLastFilled({ label: field.label || field.name, value: val });
    };

    const handleNext = (curr) => {
        let nextIdx = curr + 1;

        // Skip fields that are already filled (Magic Fill or Profile)
        // We check formDataRef because it holds the committed values
        while (nextIdx < allFields.length) {
            const field = allFields[nextIdx];
            if (!formDataRef.current[field.name]) {
                break; // Found an empty field
            }
            nextIdx++;
        }

        if (nextIdx >= allFields.length) {
            recognitionRef.current?.stop();
            onComplete?.(formDataRef.current);
        } else {
            setCurrentFieldIndex(nextIdx);
        }
    };

    // Audio Analysis
    const toggleListening = async () => {
        if (isListening) {
            recognitionRef.current?.stop();
            stopAudioAnalysis();
        } else {
            try {
                recognitionRef.current?.start();
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                micStreamRef.current = stream;
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                audioContextRef.current = ctx;
                const analyser = ctx.createAnalyser();
                analyser.fftSize = 256;
                analyserRef.current = analyser;
                ctx.createMediaStreamSource(stream).connect(analyser);
                const data = new Uint8Array(analyser.frequencyBinCount);
                const draw = () => {
                    analyser.getByteFrequencyData(data);
                    const vol = data.reduce((a, b) => a + b) / data.length;
                    setVolumeLevel(Math.min(vol / 128, 1));
                    animationFrameRef.current = requestAnimationFrame(draw);
                };
                draw();
            } catch (e) { }
        }
        setIsListening(!isListening);
    };

    const stopAudioAnalysis = () => {
        cancelAnimationFrame(animationFrameRef.current);
        micStreamRef.current?.getTracks().forEach(t => t.stop());
        audioContextRef.current?.close();
        setVolumeLevel(0);
    };

    const currentField = allFields[currentFieldIndex];
    const progress = Math.round(((currentFieldIndex + 1) / allFields.length) * 100);

    if (currentFieldIndex >= allFields.length) return null;

    return (
        // OVERLAY: Completely clear (bg-black/20 for slight dim, NO BLUR)
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/20 font-sans">
            <style jsx>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 255, 255, 0.15);
                    border-radius: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: rgba(255, 255, 255, 0.3);
                }
            `}</style>

            {/* WINDOW: TerminalLoader Style (bg-black/40 + backdrop-blur-2xl) */}
            <div className="w-full max-w-5xl h-[650px] bg-black/40 backdrop-blur-2xl rounded-2xl border border-white/20 shadow-2xl flex flex-col overflow-hidden relative ring-1 ring-white/5">

                {/* 1. Window Chrome / Header */}
                <div className="h-12 bg-white/5 border-b border-white/10 flex items-center justify-between px-4 shrink-0 backdrop-blur-md">
                    <div className="flex items-center gap-2">
                        <div className="flex gap-1.5 mr-4">
                            <div className="w-3 h-3 rounded-full bg-[#FF5F56] shadow-[0_0_10px_rgba(255,95,86,0.3)]" />
                            <div className="w-3 h-3 rounded-full bg-[#FFBD2E] shadow-[0_0_10px_rgba(255,189,46,0.3)]" />
                            <div className="w-3 h-3 rounded-full bg-[#27C93F] shadow-[0_0_10px_rgba(39,201,63,0.3)]" />
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1 rounded bg-white/5 border border-white/5">
                            <Terminal size={12} className="text-white/40" />
                            <span className="text-xs font-mono text-white/60 tracking-wide text-shadow">VOICE_INTERFACE.exe --active</span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        {onClose && (
                            <button onClick={onClose} className="p-1 hover:bg-white/10 rounded text-white/40 hover:text-white transition-colors">
                                <X size={16} />
                            </button>
                        )}
                    </div>
                </div>

                {/* 2. Main Content Area */}
                <div className="flex-1 flex overflow-hidden">

                    {/* LEFT PANE: Context (Simplified background for cohesiveness) */}
                    <div className="w-[45%] bg-black/20 p-8 md:p-10 flex flex-col justify-center border-r border-white/10 relative overflow-hidden backdrop-blur-sm">
                        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-30" />

                        <div className="relative z-10 space-y-6">
                            <div className="inline-flex items-center gap-2 mb-2">
                                <span className="text-xs font-bold font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]">
                                    FIELD {currentFieldIndex + 1} OF {allFields.length}
                                </span>
                                {currentField.required && <span className="text-xs text-red-400 font-mono tracking-wider">* REQUIRED</span>}
                            </div>

                            <motion.div
                                key={currentField.name}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="space-y-4"
                            >
                                <h2 className="text-4xl font-bold text-white leading-tight tracking-tight drop-shadow-lg">
                                    {currentField.label || currentField.display_name || "Enter Detail"}
                                </h2>

                                <p className="text-lg text-white/50 leading-relaxed font-light drop-shadow-md">
                                    {currentField.description || currentField.placeholder || (currentField.options?.length ? "Select an option below." : "Speak or type your answer.")}
                                </p>
                            </motion.div>

                            {/* Auto-fill Status */}
                            {autoFilledFields[currentField.name] && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                    className="mt-6 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10 backdrop-blur-md"
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <Sparkles size={14} className="text-emerald-400" />
                                        <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider">Suggested Answer</span>
                                    </div>
                                    <p className="text-white font-medium text-lg">{autoFilledFields[currentField.name]}</p>
                                </motion.div>
                            )}
                        </div>
                    </div>

                    {/* RIGHT PANE: Interaction (Very subtle glass) */}
                    <div className="flex-1 bg-white/[0.01] p-8 md:p-12 flex flex-col relative">
                        <div className="absolute top-6 right-6">
                            <button
                                onClick={() => playPrompt(currentField.name)}
                                className="p-3 rounded-full bg-white/5 text-white/30 hover:text-white hover:bg-white/10 transition-all border border-white/5 hover:border-white/20 backdrop-blur-sm"
                            >
                                <Volume2 size={20} />
                            </button>
                        </div>

                        <div className="flex-1 flex flex-col justify-center items-center w-full max-w-lg mx-auto relative h-full py-4">

                            {/* CASE A: OPTIONS SELECTION */}
                            {currentField.options?.length > 0 ? (
                                <div className="w-full flex flex-col gap-4 h-full">
                                    <div className="flex items-center justify-between mb-2 px-2">
                                        <span className="text-white/40 text-sm font-mono uppercase tracking-widest">Select an option</span>
                                        {isListening && (
                                            <div className="flex items-center gap-2 text-emerald-400 text-xs animate-pulse">
                                                <Mic size={12} /> Listening...
                                            </div>
                                        )}
                                    </div>

                                    <div className="w-full grid grid-cols-1 gap-3 overflow-y-auto pr-2 custom-scrollbar flex-1 max-h-[450px]">
                                        {currentField.options.map((opt, idx) => {
                                            const val = opt.value || opt.label;
                                            const label = opt.label || val;
                                            const selected = formData[currentField.name] === val;
                                            return (
                                                <button
                                                    key={idx}
                                                    onClick={() => { updateField(currentField, val); handleNext(currentFieldIndex); }}
                                                    className={`group flex items-center justify-between p-4 rounded-xl border text-left transition-all backdrop-blur-sm shrink-0
                                                        ${selected
                                                            ? 'bg-emerald-500/20 border-emerald-500/50 text-white shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                                                            : 'bg-white/5 border-white/5 text-white/60 hover:bg-white/10 hover:border-white/10 hover:text-white'
                                                        }`}
                                                >
                                                    <div className="flex items-center gap-4">
                                                        <span className={`flex items-center justify-center w-6 h-6 rounded border text-xs font-mono transition-colors
                                                            ${selected ? 'border-emerald-500/50 text-emerald-400' : 'border-white/10 text-white/20 group-hover:border-white/30'}`}>
                                                            {idx + 1}
                                                        </span>
                                                        <span className="font-medium text-lg drop-shadow-sm">{label}</span>
                                                    </div>
                                                    {selected && <CheckCircle size={20} className="text-emerald-400" />}
                                                </button>
                                            )
                                        })}
                                    </div>

                                    {/* Mic Toggle for Options (Small) */}
                                    <button
                                        onClick={toggleListening}
                                        className="self-center mt-2 p-3 rounded-full bg-white/5 text-white/20 hover:text-emerald-400 hover:bg-white/10 transition-all"
                                        title="Toggle Voice Selection"
                                    >
                                        {isListening ? <Mic size={20} className="animate-pulse text-emerald-400" /> : <MicOff size={20} />}
                                    </button>
                                </div>
                            ) : (
                                /* CASE B: TEXT / VOICE INPUT (Siri Orb) */
                                <div className="flex-1 w-full flex flex-col items-center justify-center relative min-h-[300px]">
                                    {!showTextInput && (
                                        <div className="flex flex-col items-center justify-center gap-6 relative z-10 w-full">

                                            {/* SIRI ORB */}
                                            <button
                                                onClick={toggleListening}
                                                className="relative group cursor-pointer !outline-none !border-none !ring-0 !shadow-none focus:!outline-none focus-visible:!outline-none focus:!ring-0 focus-visible:!ring-0 transition-transform active:scale-95"
                                                style={{ outline: 'none', boxShadow: 'none', border: 'none' }}
                                            >
                                                <div className="relative w-28 h-28 flex items-center justify-center">
                                                    <motion.div
                                                        animate={
                                                            processing ? { scale: [1, 1.1, 1], rotate: 360 } :
                                                                isListening ? { scale: [1, 1.2 + (volumeLevel || 0), 1] } :
                                                                    { scale: [1, 1.05, 1] }
                                                        }
                                                        transition={
                                                            processing ? { duration: 2, repeat: Infinity, ease: "linear" } :
                                                                isListening ? { duration: 0.2, ease: "easeInOut" } :
                                                                    { duration: 2, repeat: Infinity, ease: "easeInOut" }
                                                        }
                                                        className={`w-20 h-20 rounded-full blur-md transition-all duration-500
                                                            ${isListening
                                                                ? 'bg-gradient-to-br from-cyan-400 via-emerald-400 to-purple-500 shadow-[0_0_80px_rgba(52,211,153,0.5)]'
                                                                : 'bg-white/10 border border-white/10 shadow-[0_0_30px_rgba(255,255,255,0.05)]'
                                                            }`}
                                                    />

                                                    {isListening && (
                                                        <>
                                                            <motion.div
                                                                animate={{ scale: [1, 2.2], opacity: [0.4, 0] }}
                                                                transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
                                                                className="absolute inset-0 rounded-full border border-emerald-500/20"
                                                            />
                                                            <motion.div
                                                                animate={{ scale: [1, 1.6], opacity: [0.3, 0] }}
                                                                transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
                                                                className="absolute inset-0 rounded-full border border-cyan-400/20"
                                                            />
                                                        </>
                                                    )}

                                                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                                        {isListening ? (
                                                            <Mic size={28} className="text-white drop-shadow-md" />
                                                        ) : (
                                                            <MicOff size={28} className="text-white/40" />
                                                        )}
                                                    </div>
                                                </div>
                                            </button>

                                            {/* Status */}
                                            <div className="h-6 flex items-center justify-center">
                                                {processing ? (
                                                    <span className="text-xs font-mono text-emerald-400 animate-pulse flex items-center gap-2">
                                                        <Sparkles size={12} /> PROCESSING...
                                                    </span>
                                                ) : isListening ? (
                                                    <span className="text-xs font-mono text-cyan-400 animate-pulse">
                                                        LISTENING...
                                                    </span>
                                                ) : (
                                                    <span className="text-xs font-mono text-white/30 uppercase tracking-widest">
                                                        Tap Orb to Speak
                                                    </span>
                                                )}
                                            </div>

                                            {/* Transcript (Resizable & Scrollable) */}
                                            <div className="w-full flex justify-center px-4">
                                                <AnimatePresence mode='wait'>
                                                    {transcript && (
                                                        <motion.div
                                                            key="transcript"
                                                            initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                                            exit={{ opacity: 0, scale: 0.9 }}
                                                            className="bg-white/5 backdrop-blur-md border border-white/10 px-6 py-4 rounded-2xl w-full shadow-xl text-center max-h-[160px] overflow-y-auto custom-scrollbar"
                                                        >
                                                            <p className="text-xl font-light text-white leading-relaxed break-words">
                                                                "{transcript}"
                                                            </p>
                                                        </motion.div>
                                                    )}
                                                </AnimatePresence>
                                            </div>
                                        </div>
                                    )}

                                    {/* Fallback to Keyboard */}
                                    {!showTextInput && (
                                        <button
                                            onClick={() => setShowTextInput(true)}
                                            className="absolute bottom-0 w-full flex justify-center py-4 text-white/30 hover:text-white/60 text-xs font-mono border-t border-transparent hover:border-white/5 transition-all gap-2 items-center tracking-widest uppercase"
                                        >
                                            <Keyboard size={12} /> Switch to Keyboard
                                        </button>
                                    )}

                                    {showTextInput && (
                                        <div className="w-full relative animate-in fade-in slide-in-from-bottom-4 duration-300">
                                            <input
                                                autoFocus
                                                type="text"
                                                value={textInputValue}
                                                onChange={(e) => setTextInputValue(e.target.value)}
                                                onKeyDown={(e) => e.key === 'Enter' && textInputValue && processVoiceInput(textInputValue, currentFieldIndex)}
                                                placeholder="Type your answer..."
                                                className="w-full bg-black/40 backdrop-blur-xl border border-white/10 rounded-xl px-5 py-4 text-xl text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all font-light shadow-inner"
                                            />
                                            <button
                                                onClick={() => textInputValue && processVoiceInput(textInputValue, currentFieldIndex)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-emerald-500 rounded-lg text-black hover:bg-emerald-400 shadow-lg hover:shadow-emerald-500/20 transition-all"
                                            >
                                                <Send size={18} />
                                            </button>

                                            <button
                                                onClick={() => setShowTextInput(false)}
                                                className="w-full flex justify-center py-2 mt-2 text-white/30 hover:text-white/60 text-sm transition-colors gap-2 items-center"
                                            >
                                                <Mic size={14} /> Switch back to Voice
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* 3. Footer */}
                <div className="h-20 border-t border-white/10 bg-white/[0.02] backdrop-blur-md flex items-center justify-between px-8 relative z-20">
                    <div className="flex-1 flex items-center gap-4">
                        <div className="w-48 h-1.5 bg-white/10 rounded-full overflow-hidden backdrop-blur-sm">
                            <motion.div
                                className="h-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                            />
                        </div>
                        <span className="font-mono text-xs text-white/30 text-shadow">
                            {progress}% COMPLETE
                        </span>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => currentFieldIndex > 0 && setCurrentFieldIndex(currentFieldIndex - 1)}
                            disabled={currentFieldIndex === 0}
                            className={`px-6 py-3 rounded-xl font-medium border border-transparent transition-all flex items-center gap-2 backdrop-blur-sm
                                ${currentFieldIndex === 0 ? 'text-white/20 cursor-not-allowed' : 'text-white/60 hover:text-white hover:bg-white/5 hover:border-white/10'}`}
                        >
                            <ChevronLeft size={18} /> Back
                        </button>

                        <div className="h-8 w-px bg-white/10 mx-2" />

                        <button
                            onClick={() => handleNext(currentFieldIndex)}
                            className="px-6 py-3 rounded-xl font-medium text-white/50 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2 backdrop-blur-sm"
                        >
                            <SkipForward size={18} /> Skip
                        </button>

                        <button
                            onClick={() => handleNext(currentFieldIndex)}
                            className="ml-2 px-8 py-3 rounded-xl font-bold bg-white text-black hover:bg-emerald-400 transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_30px_rgba(16,185,129,0.3)] border border-transparent"
                        >
                            Next <ChevronRight size={18} />
                        </button>
                    </div>
                </div>

                {/* Toast */}
                <AnimatePresence>
                    {lastFilled && (
                        <motion.div
                            initial={{ opacity: 0, y: 50, x: '-50%' }}
                            animate={{ opacity: 1, y: 0, x: '-50%' }}
                            exit={{ opacity: 0 }}
                            className="absolute bottom-24 left-1/2 px-6 py-3 bg-black/60 border border-emerald-500/30 rounded-full shadow-2xl flex items-center gap-3 z-50 pointer-events-none backdrop-blur-xl"
                        >
                            <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center">
                                <CheckCircle size={12} className="text-emerald-500" />
                            </div>
                            <span className="text-white/80 font-mono text-sm">
                                Saved <span className="text-white font-bold text-shadow-sm">{lastFilled.value}</span>
                            </span>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default VoiceFormFiller;
