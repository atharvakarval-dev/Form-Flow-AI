import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Mic, MicOff, ChevronLeft, ChevronRight, SkipForward, Send, Volume2, Keyboard, Terminal, Activity, CheckCircle, Sparkles, X, Brain, Lightbulb } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api, { API_BASE_URL, refineText, startConversationSession, sendConversationMessage, getSuggestions, getSmartSuggestions } from '@/services/api';

const VoiceFormFiller = ({ formSchema, formContext, onComplete, onClose }) => {
    const [isListening, setIsListening] = useState(false);
    const [currentFieldIndex, setCurrentFieldIndex] = useState(0);
    const [formData, setFormData] = useState({});
    const [transcript, setTranscript] = useState('');
    const [processing, setProcessing] = useState(false);
    const [showTextInput, setShowTextInput] = useState(false);
    const [textInputValue, setTextInputValue] = useState('');
    const [suggestions, setSuggestions] = useState([]);
    const [loadingSuggestions, setLoadingSuggestions] = useState(false);
    const fetchTimeoutRef = useRef(null);

    const [smartSuggestions, setSmartSuggestions] = useState([]);
    const [showSmartSuggestions, setShowSmartSuggestions] = useState(false);
    const [suggestionTier, setSuggestionTier] = useState(null);
    const [profileConfidence, setProfileConfidence] = useState(null);
    const hesitationTimerRef = useRef(null);
    const questionsAnsweredRef = useRef(0);

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
        'email': 'email',
        'phone': 'mobile', 'mobile': 'mobile', 'cell': 'mobile', 'contact': 'mobile',
        'contactnumber': 'mobile', 'primarycontact': 'mobile', 'primarycontactnumber': 'mobile', 'telephone': 'mobile',
        'city': 'city', 'state': 'state', 'country': 'country',
        'zip': 'pincode', 'pin': 'pincode', 'pincode': 'pincode', 'postal': 'pincode',
        'address': 'address', 'company': 'company', 'job': 'job_title', 'currentrole': 'job_title',
        'linkedin': 'linkedin_url', 'website': 'website', 'portfolio': 'website'
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

    const currentField = allFields[currentFieldIndex];
    // Fix Progress Calculation
    const progress = Math.min(Math.round(((currentFieldIndex) / allFields.length) * 100), 100);

    // Conversation State
    const [sessionId, setSessionId] = useState(null);
    const [aiResponse, setAiResponse] = useState('');

    // Smart Grouping State
    const [currentBatch, setCurrentBatch] = useState([]);  // Array of field objects in current group
    const [batchStatus, setBatchStatus] = useState({});    // {fieldName: 'pending'|'filled'|'missing'}
    const [singleFieldMode, setSingleFieldMode] = useState(false); // User toggle for linear mode

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
            if (!formSchema?.length) return;
            // Only wait for profile if we are actually intending to use it for magic fill
            if (magicFillLoading && userProfile === null) return;

            let currentData = { ...formDataRef.current };

            // -- 1. Trigger Magic Fill (SEQUENTIAL: Wait for it) --
            if (userProfile && !sessionId && magicFillLoading) {
                try {
                    console.log('✨ Starting Magic Fill (Sequential)...');
                    // We AWAIT this now, per user request, to ensure Agent knows about filled data
                    // With 1.5-flash, this should only take ~3-4 seconds.
                    const response = await api.post('/magic-fill', {
                        form_schema: formSchema,
                        user_profile: userProfile
                    });

                    if (response.data?.success && response.data.filled) {
                        const filled = response.data.filled;
                        console.log('✨ Magic Fill Completed:', Object.keys(filled).length);

                        setAutoFilledFields(prev => ({ ...prev, ...filled }));
                        setFormData(prev => ({ ...prev, ...filled }));
                        formDataRef.current = { ...formDataRef.current, ...filled };
                        currentData = { ...currentData, ...filled };

                        // Smart jump
                        const firstUnfilled = allFields.findIndex(f => !filled[f.name] && !formDataRef.current[f.name]);
                        if (firstUnfilled > 0 && currentFieldIndex === 0) {
                            setCurrentFieldIndex(firstUnfilled);
                            // Update ref for session start
                            indexRef.current = firstUnfilled;
                        }

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

            // -- 2. Start Conversation Session (After Magic Fill) --
            if (!sessionId) {
                try {
                    console.log('💬 Starting Conversation Session...');
                    // Pass the FULLY FILLED data to the agent so it doesn't ask redundant questions
                    // And pass clientType='web' to ensure single-field questions
                    const sessionRes = await startConversationSession(formSchema, window.location.href, currentData, 'web');
                    console.log('💬 Session Started:', sessionRes);
                    setSessionId(sessionRes.session_id);

                    // Smart Grouping: Initialize current batch from backend
                    if (sessionRes.next_questions?.length > 0) {
                        console.log('🎯 Initial Batch:', sessionRes.next_questions.map(f => f.name));
                        setCurrentBatch(sessionRes.next_questions);
                        // Initialize batch status
                        const initialStatus = {};
                        sessionRes.next_questions.forEach(f => {
                            initialStatus[f.name] = formDataRef.current[f.name] ? 'filled' : 'pending';
                        });
                        setBatchStatus(initialStatus);
                    }

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

        if (!sessionId) {
            init();
        }
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
                // EXCLUSION CHECK: Don't map "primary contact" to "emergency contact"
                if (cleanName.includes(key)) {
                    const isExcy = ['emergency', 'alternate', 'secondary', 'parent', 'guardian', 'partner', 'spouse'].some(bad => cleanName.includes(bad));
                    if (isExcy && (key === 'phone' || key === 'mobile' || key === 'email' || key === 'fullname' || key === 'contact')) {
                        continue;
                    }
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

            // FIX: Only play backend audio prompt when NO conversation session exists
            // When session exists, agent's response already speaks the question via SpeechSynthesis
            // This prevents dual TTS conflict (audio from /speech/ + SpeechSynthesis)
            if (!sessionId) {
                playPrompt(field.name);
            }
        }
    }, [currentFieldIndex, allFields, autoFilledFields, sessionId]);

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

    const processVoiceInput = async (text, idx, isDirectInput = false) => {
        if (!text || idx >= allFields.length) return;
        const field = allFields[idx];

        // --- OPTIMISTIC HANDLING FOR KEYBOARD INPUT ---
        if (isDirectInput) {
            console.log(`💪 FAST PATH: Direct input for ${field.name}: ${text}`);

            // 1. Update Frontend State Immediately
            updateField(field, text);
            setProcessing(true); // Short pulse of processing state if needed, or skip

            // 2. Sync with backend in background (don't block UI)
            if (sessionId) {
                sendConversationMessage(sessionId, text).then(result => {
                    console.log("💬 Background Agent Sync:", result);

                    // Optional: If agent returns a strictly formatted value (e.g. date normalization), update it
                    if (result.extracted_values && result.extracted_values[field.name]) {
                        const polishedValue = result.extracted_values[field.name];
                        if (polishedValue !== text) {
                            console.log(`✨ Refining value from "${text}" to "${polishedValue}"`);
                            updateField(field, polishedValue);
                        }
                    }

                    // Speak the response (confirmation + next question)
                    if (result.response) {
                        // FIX: Cancel any playing prompt audio before speaking
                        if (audioRef.current) {
                            audioRef.current.pause();
                            audioRef.current = null;
                        }
                        clearTimeout(idleTimeoutRef.current);

                        window.speechSynthesis.cancel();
                        const utter = new SpeechSynthesisUtterance(result.response);
                        // Use a good English voice if available
                        const voices = window.speechSynthesis.getVoices();
                        const preferredVoice = voices.find(v => v.name.includes('Google') && v.lang.includes('en')) || voices[0];
                        if (preferredVoice) utter.voice = preferredVoice;
                        window.speechSynthesis.speak(utter);
                    }
                }).catch(e => console.error("Background sync failed:", e));
            }

            // 3. Move to next field immediately
            setProcessing(false);
            handleNext(idx);
            return;
        }

        // --- STANDARD VOICE FLOW ---
        setProcessing(true);

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

                    // Smart Grouping: Update batch status for filled fields
                    setBatchStatus(prev => {
                        const updated = { ...prev };
                        filledKeys.forEach(key => { updated[key] = 'filled'; });
                        return updated;
                    });
                }

                // Smart Grouping: Handle partial extraction and update batch status
                if (result.missing_from_group?.length > 0) {
                    setBatchStatus(prev => {
                        const updated = { ...prev };
                        result.missing_from_group.forEach(key => { updated[key] = 'missing'; });
                        return updated;
                    });
                }

                // Handle AI Speech Response
                if (result.response) {
                    // FIX: Cancel any playing prompt audio before agent speaks
                    if (audioRef.current) {
                        audioRef.current.pause();
                        audioRef.current = null;
                    }
                    clearTimeout(idleTimeoutRef.current);

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

                // Smart Grouping: Update current batch from backend response
                if (result.next_questions?.length > 0 && !result.requires_followup) {
                    console.log('🎯 New Batch:', result.next_questions.map(f => f.name));
                    setCurrentBatch(result.next_questions);
                    // Reset batch status for new batch
                    const newStatus = {};
                    result.next_questions.forEach(f => {
                        newStatus[f.name] = formDataRef.current[f.name] ? 'filled' : 'pending';
                    });
                    setBatchStatus(newStatus);
                }

                // If the current field was filled, move next or jump to AI suggestion
                if (result.extracted_values && result.extracted_values[field.name]) {
                    // FIX: Trust agent's next_questions for field navigation instead of linear increment
                    setTimeout(() => {
                        if (result.next_questions?.length > 0) {
                            const nextFieldObj = result.next_questions[0];
                            const nextIdx = allFields.findIndex(f => f.name === nextFieldObj.name);
                            if (nextIdx !== -1 && nextIdx !== idx) {
                                console.log(`🦘 Agent-directed jump to: ${nextFieldObj.name} (Index ${nextIdx})`);
                                setCurrentFieldIndex(nextIdx);
                                return;
                            }
                        }
                        // Fallback to linear handleNext if no agent suggestion
                        handleNext(idx);
                    }, 100); // Shorter delay since TTS is already speaking
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
                } else {
                    // Fallback check: if no specific field was returned, but we sent text, 
                    // maybe the agent understood it as a generic confirmation. 
                    // But for Voice, we usually act conservative.
                    // However, we can re-evaluate this if needed.
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
                const result = await refineText(text, fieldLabel, fieldType, qaHistoryRef.current);
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

        if (nextIdx < allFields.length) {
            setCurrentFieldIndex(nextIdx);

            // SYNC BACKEND STATE: Tell the agent we moved to a new field
            // Use a special "system" message or just the field name as context
            if (sessionId && allFields[nextIdx]) {
                // We send a hidden system prompt to align the agent
                // This prevents the "answer to Q1 being treated as answer to Q2" issue
                const nextField = allFields[nextIdx];
                // We don't await this, minimal impact if it fails
                api.post('/conversation/context', {
                    session_id: sessionId,
                    current_field: nextField.name,
                    field_label: nextField.label
                }).catch(() => { });
            }
        } else {
            recognitionRef.current?.stop();
            onComplete?.(formDataRef.current);
        }
    };

    // Fetch suggestions with debouncing
    const fetchSuggestions = async (field, partialValue = null) => {
        try {
            setLoadingSuggestions(true);
            const result = await getSuggestions(
                field.name,
                field.label || field.display_name,
                inferFieldType(field),
                partialValue,
                5
            );
            setSuggestions(result.suggestions || []);
        } catch (e) {
            console.error('Failed to fetch suggestions:', e);
            setSuggestions([]);
        } finally {
            setLoadingSuggestions(false);
        }
    };

    // 🧠 Smart Suggestions - Profile-based intelligent suggestions
    const fetchSmartSuggestions = async (field) => {
        try {
            console.log('🧠 Fetching smart suggestions for:', field.name);
            const result = await getSmartSuggestions(
                field.name,
                field.label || field.display_name,
                inferFieldType(field),
                formContext || 'Form filling',
                formDataRef.current  // Pass already answered fields
            );

            if (result.suggestions && result.suggestions.length > 0) {
                setSmartSuggestions(result.suggestions);
                setSuggestionTier(result.tier_used);
                setProfileConfidence(result.profile_confidence);
                setShowSmartSuggestions(true);
                console.log(`🧠 Smart suggestions received (Tier: ${result.tier_used}):`, result.suggestions.length);
            }
        } catch (e) {
            console.error('Smart suggestions failed:', e);
        }
    };

    // 🕐 Hesitation Detection Timer
    // Progressive: 5 seconds initially, 3 seconds after 5 questions
    const startHesitationTimer = (field) => {
        clearTimeout(hesitationTimerRef.current);

        // Close any existing suggestion popup
        setShowSmartSuggestions(false);

        // Progressive delay: 5 seconds for new users, 3 seconds after 5 questions
        const delay = questionsAnsweredRef.current >= 5 ? 3000 : 5000;

        hesitationTimerRef.current = setTimeout(() => {
            // Only show if field is still empty and not processing
            if (!formDataRef.current[field.name] && !processing && !showTextInput) {
                console.log(`🕐 Hesitation detected on ${field.name} (delay: ${delay}ms)`);
                fetchSmartSuggestions(field);
            }
        }, delay);
    };

    // Clear hesitation timer on any user activity
    const clearHesitationTimer = () => {
        clearTimeout(hesitationTimerRef.current);
        setShowSmartSuggestions(false);
    };

    // Handle smart suggestion selection
    const handleSmartSuggestionSelect = (suggestion) => {
        if (!currentField) return;

        console.log(`✨ Smart suggestion selected: ${suggestion.value}`);
        updateField(currentField, suggestion.value);
        setShowSmartSuggestions(false);
        questionsAnsweredRef.current++;

        // Move to next field
        setTimeout(() => handleNext(currentFieldIndex), 100);
    };

    // Start hesitation timer when landing on a new field
    useEffect(() => {
        if (currentField && !processing && !magicFillLoading) {
            startHesitationTimer(currentField);
        }

        return () => clearTimeout(hesitationTimerRef.current);
    }, [currentFieldIndex, processing, magicFillLoading]);

    // Clear hesitation timer when user starts typing or speaking
    useEffect(() => {
        if (transcript || textInputValue || isListening) {
            clearHesitationTimer();
        }
    }, [transcript, textInputValue, isListening]);

    // Debounced suggestions on text input change
    useEffect(() => {
        if (!showTextInput || !currentField) return;

        clearTimeout(fetchTimeoutRef.current);
        clearHesitationTimer(); // User is typing, no need for hesitation suggestions

        if (textInputValue && textInputValue.length >= 1) {
            fetchTimeoutRef.current = setTimeout(() => {
                fetchSuggestions(currentField, textInputValue);
            }, 300); // 300ms debounce
        } else {
            // Show history suggestions when field is empty or just opened
            fetchSuggestions(currentField, null);
        }

        return () => clearTimeout(fetchTimeoutRef.current);
    }, [textInputValue, showTextInput, currentField]);

    // Fetch initial suggestions when landing on a new field in voice mode
    useEffect(() => {
        if (!showTextInput && currentField) {
            fetchSuggestions(currentField, null);
        }
    }, [currentFieldIndex, showTextInput]);


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

    // Moved to top
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

                {/* Magic Fill Loading Indicator */}
                <AnimatePresence>
                    {magicFillLoading && (
                        <motion.div
                            initial={{ opacity: 0, y: -20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="absolute top-16 left-0 w-full flex justify-center z-50 pointer-events-none"
                        >
                            <div className="bg-emerald-500/10 backdrop-blur-md border border-emerald-500/20 text-emerald-400 px-4 py-1.5 rounded-full text-xs font-mono flex items-center gap-2 shadow-lg">
                                <Sparkles size={12} className="animate-spin-slow" />
                                <span>AI MAGIC FILL RUNNING...</span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* 🧠 Smart Suggestions Modal (Profile-Based) */}
                <AnimatePresence>
                    {showSmartSuggestions && smartSuggestions.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 20, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 20, scale: 0.95 }}
                            transition={{ type: "spring", damping: 25, stiffness: 300 }}
                            className="absolute bottom-24 left-1/2 transform -translate-x-1/2 z-50 w-[500px] max-w-[90%]"
                        >
                            <div className="bg-gradient-to-br from-purple-900/80 to-indigo-900/80 backdrop-blur-xl rounded-2xl border border-purple-500/30 shadow-2xl overflow-hidden">
                                {/* Header */}
                                <div className="flex items-center justify-between px-5 py-3 border-b border-purple-500/20 bg-purple-500/10">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-purple-500/20">
                                            <Brain size={18} className="text-purple-300" />
                                        </div>
                                        <div>
                                            <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                Need help with this field?
                                                {suggestionTier && (
                                                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wider ${suggestionTier === 'profile_based'
                                                            ? 'bg-purple-500/30 text-purple-200'
                                                            : suggestionTier === 'profile_blended'
                                                                ? 'bg-blue-500/30 text-blue-200'
                                                                : 'bg-gray-500/30 text-gray-200'
                                                        }`}>
                                                        {suggestionTier === 'profile_based' ? '🧠 Personalized' :
                                                            suggestionTier === 'profile_blended' ? '🎯 Smart' : '⚡ Quick'}
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-xs text-purple-200/70">Based on your behavioral profile</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => setShowSmartSuggestions(false)}
                                        className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                                    >
                                        <X size={14} />
                                    </button>
                                </div>

                                {/* Suggestions List */}
                                <div className="p-3 space-y-2 max-h-[250px] overflow-y-auto custom-scrollbar">
                                    {smartSuggestions.map((suggestion, idx) => (
                                        <motion.button
                                            key={idx}
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: idx * 0.1 }}
                                            onClick={() => handleSmartSuggestionSelect(suggestion)}
                                            className="w-full text-left p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 hover:border-purple-500/30 transition-all group"
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex-1">
                                                    <div className="font-medium text-white group-hover:text-purple-200 transition-colors">
                                                        {suggestion.value}
                                                    </div>
                                                    {suggestion.reasoning && (
                                                        <p className="text-xs text-white/50 mt-1 line-clamp-2">
                                                            {suggestion.reasoning}
                                                        </p>
                                                    )}
                                                    {suggestion.behavioral_match && (
                                                        <div className="flex items-center gap-1 mt-2">
                                                            <Lightbulb size={10} className="text-amber-400/70" />
                                                            <span className="text-[10px] text-amber-400/70 italic">
                                                                {suggestion.behavioral_match}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="text-[10px] text-purple-300/60 bg-purple-500/10 px-2 py-1 rounded-full whitespace-nowrap">
                                                    {Math.round(suggestion.confidence * 100)}%
                                                </div>
                                            </div>
                                        </motion.button>
                                    ))}
                                </div>

                                {/* Footer */}
                                <div className="px-4 py-2 border-t border-purple-500/20 bg-purple-500/5">
                                    <p className="text-[10px] text-purple-300/50 text-center">
                                        Suggestions improve as you complete more forms • Press any key to dismiss
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* 2. Main Content Area */}
                <div className="flex-1 flex overflow-hidden">

                    {/* LEFT PANE: Context (Simplified background for cohesiveness) */}
                    <div className="w-[45%] bg-black/20 p-8 md:p-10 flex flex-col justify-center border-r border-white/10 relative overflow-hidden backdrop-blur-sm">
                        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-30" />

                        <div className="relative z-10 space-y-6">
                            <div className="inline-flex items-center gap-2 mb-2">
                                <span className="text-xs font-bold font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]">
                                    {(currentFieldIndex + 1) >= allFields.length ? "COMPLETED" : `FIELD ${currentFieldIndex + 1} OF ${allFields.length}`}
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

                            {/* Smart Grouping: Field Slots UI */}
                            {currentBatch.length > 1 && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                    className="mt-6 p-4 rounded-xl bg-purple-500/5 border border-purple-500/10 backdrop-blur-md"
                                >
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <Activity size={14} className="text-purple-400" />
                                            <span className="text-xs font-mono text-purple-400 uppercase tracking-wider">
                                                Capturing {currentBatch.length} Fields
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => setSingleFieldMode(prev => !prev)}
                                            className="text-xs text-white/40 hover:text-white/70 underline transition-colors"
                                        >
                                            {singleFieldMode ? 'Enable Grouping' : 'Ask One by One'}
                                        </button>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {currentBatch.map(field => {
                                            const status = batchStatus[field.name] || 'pending';
                                            const statusStyles = {
                                                filled: 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400',
                                                pending: 'bg-white/5 border-white/10 text-white/50',
                                                missing: 'bg-amber-500/20 border-amber-500/30 text-amber-400'
                                            };
                                            const statusIcons = {
                                                filled: <CheckCircle size={12} />,
                                                pending: <span className="w-3 h-3 rounded-full border border-current opacity-50" />,
                                                missing: <span className="text-amber-400">⚠</span>
                                            };
                                            return (
                                                <div
                                                    key={field.name}
                                                    className={`flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-mono ${statusStyles[status]}`}
                                                >
                                                    {statusIcons[status]}
                                                    <span>{field.label || field.name}</span>
                                                </div>
                                            );
                                        })}
                                    </div>
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
                                                    <span className="font-medium">{label}</span>
                                                    {selected && <CheckCircle size={16} className="text-emerald-400" />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            ) : (
                                (!singleFieldMode && currentBatch.length > 1) ? (
                                    /* CASE B: GROUP VIEW */
                                    <div className="w-full flex flex-col justify-center gap-8">
                                        <div className="space-y-6">
                                            <div className="text-center space-y-2">
                                                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-mono mb-4">
                                                    <Sparkles size={12} />
                                                    <span>SMART GROUPING ACTIVE</span>
                                                </div>
                                                <h3 className="text-2xl font-bold text-white">
                                                    Thinking...
                                                </h3>
                                                <p className="text-white/50 text-lg">
                                                    Listening for multiple fields at once.
                                                </p>
                                            </div>

                                            {/* Group Fields Visualization */}
                                            <div className="grid grid-cols-1 gap-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                                                {currentBatch.map((field, idx) => {
                                                    const status = batchStatus[field.name] || 'pending';
                                                    const val = formData[field.name] || '';
                                                    const isFilled = status === 'filled' || !!val;

                                                    return (
                                                        <div
                                                            key={field.name}
                                                            className={`p-4 rounded-xl border transition-all ${isFilled
                                                                ? 'bg-emerald-500/10 border-emerald-500/30'
                                                                : 'bg-white/5 border-white/10'
                                                                }`}
                                                        >
                                                            <div className="flex items-center justify-between mb-1">
                                                                <span className={`text-sm font-mono ${isFilled ? 'text-emerald-400' : 'text-white/60'}`}>
                                                                    {field.label || field.name}
                                                                </span>
                                                                {isFilled && <CheckCircle size={14} className="text-emerald-400" />}
                                                            </div>
                                                            <div className="text-lg font-medium text-white truncate">
                                                                {val || <span className="text-white/20 italic">Waiting...</span>}
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    /* CASE C: SIRI ORB */
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

                                                {/* Suggestion chips for Voice Mode */}
                                                {!showTextInput && suggestions.length > 0 && (
                                                    <div className="w-full mt-4 px-4">
                                                        <div className="text-xs font-mono text-white/30 uppercase tracking-widest mb-2 text-center">Suggestions from history</div>
                                                        <div className="flex flex-wrap gap-2 justify-center">
                                                            {suggestions.map((suggestion, idx) => (
                                                                <button
                                                                    key={idx}
                                                                    onClick={() => {
                                                                        setTranscript(suggestion);
                                                                        processVoiceInput(suggestion, currentFieldIndex, false);
                                                                    }}
                                                                    className="px-4 py-2 bg-white/5 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/30 rounded-xl text-sm text-white/70 hover:text-white transition-all backdrop-blur-sm flex items-center gap-2"
                                                                >
                                                                    <Sparkles size={12} className="text-emerald-400" />
                                                                    {suggestion}
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Fallback to Keyboard */}
                                        {!showTextInput && (
                                            <button
                                                onClick={() => {
                                                    // Stop voice recognition and auto-submit
                                                    if (isListening) {
                                                        recognitionRef.current?.stop();
                                                        stopAudioAnalysis();
                                                        setIsListening(false);
                                                    }
                                                    clearTimeout(pauseTimeoutRef.current);

                                                    // Pre-fill with current transcript so user can edit it
                                                    setTextInputValue(transcript);
                                                    setShowTextInput(true);
                                                }}
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
                                                    onKeyDown={(e) => e.key === 'Enter' && textInputValue && processVoiceInput(textInputValue, currentFieldIndex, true)}
                                                    placeholder="Type your answer..."
                                                    className="w-full bg-black/40 backdrop-blur-xl border border-white/10 rounded-xl px-5 py-4 text-xl text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all font-light shadow-inner"
                                                />
                                                <button
                                                    onClick={() => textInputValue && processVoiceInput(textInputValue, currentFieldIndex, true)}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-emerald-500 rounded-lg text-black hover:bg-emerald-400 shadow-lg hover:shadow-emerald-500/20 transition-all"
                                                >
                                                    <Send size={18} />
                                                </button>

                                                {/* Suggestions chips */}
                                                {suggestions.length > 0 && (
                                                    <div className="mt-3 flex flex-wrap gap-2">
                                                        {suggestions.map((suggestion, idx) => (
                                                            <button
                                                                key={idx}
                                                                onClick={() => {
                                                                    setTextInputValue(suggestion);
                                                                    processVoiceInput(suggestion, currentFieldIndex, true);
                                                                }}
                                                                className="px-3 py-1.5 bg-white/5 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/30 rounded-full text-sm text-white/70 hover:text-white transition-all backdrop-blur-sm flex items-center gap-1.5"
                                                            >
                                                                <Sparkles size={12} className="text-emerald-400" />
                                                                {suggestion}
                                                            </button>
                                                        ))}
                                                    </div>
                                                )}

                                                <button
                                                    onClick={() => setShowTextInput(false)}
                                                    className="w-full flex justify-center py-2 mt-2 text-white/30 hover:text-white/60 text-sm transition-colors gap-2 items-center"
                                                >
                                                    <Mic size={14} /> Switch back to Voice
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))}
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
