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
  const [userProfile, setUserProfile] = useState(null); // User profile for auto-fill
  const [autoFilledFields, setAutoFilledFields] = useState({}); // Track auto-filled fields
  const [isProfileLoading, setIsProfileLoading] = useState(true); // Wait for profile load

  const [lastFilled, setLastFilled] = useState(null); // Track last answer

  // Field name mappings for auto-fill (form field names -> user profile keys)
  // ORDER MATTERS: Specific patterns first, generic patterns last.
  const fieldMappings = {
    // 1. Explicit Full Name (High priority)
    'fullname': 'fullname', 'full_name': 'fullname', 'yourname': 'fullname',

    // 2. Specific Name Parts
    'first_name': 'first_name', 'firstname': 'first_name', 'fname': 'first_name', 'given_name': 'first_name',
    'last_name': 'last_name', 'lastname': 'last_name', 'lname': 'last_name', 'surname': 'last_name', 'family_name': 'last_name',

    // 3. Contact Info
    'email': 'email', 'mail': 'email', 'e_mail': 'email', 'emailid': 'email', 'email_id': 'email',
    'elecadr': 'email', 'nelecadr': 'email', 'emailaddress': 'email', 'email_address': 'email',

    'mobile': 'mobile', 'phone': 'mobile', 'telephone': 'mobile', 'cell': 'mobile', // Removed 'contact' as it matches 'Contact Message'
    'mobile_number': 'mobile', 'phone_number': 'mobile', 'nphone': 'mobile', 'phonenumber': 'mobile',
    'tel': 'mobile', 'cellphone': 'mobile', 'mobilephone': 'mobile',

    // 4. Location
    'country': 'country', // Removed 'nation' as it matches 'designation', 'destination', etc.
    'state': 'state', 'province': 'state', 'region': 'state',
    'city': 'city', 'town': 'city',
    'pincode': 'pincode', 'zip': 'pincode', 'zipcode': 'pincode', 'postal_code': 'pincode', 'postalcode': 'pincode',

    // 5. Generic Name (Lowest priority - fallback)
    'name': 'fullname',
  };



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
        )) &&
        // Skip tick-box fields (Terms, Privacy, Subscribe) - handled silently by backend
        !['terms', 'privacy', 'policy', 'agree', 'subscribe', 'newsletter', 'consent', 'marketing'].some(kw =>
          (field.name || '').toLowerCase().includes(kw) ||
          (field.label || '').toLowerCase().includes(kw)
        )
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

  // Fetch user profile for auto-fill
  useEffect(() => {
    const fetchUserProfile = async () => {
      const token = localStorage.getItem('token');
      if (!token) {
        setIsProfileLoading(false);
        return;
      }

      try {
        const response = await axios.get('http://localhost:8000/users/me', {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUserProfile(response.data);
        console.log('📋 User profile loaded for auto-fill:', response.data);
      } catch (error) {
        // Silently fail if user not logged in or token expired - auto-fill is optional
        if (error.response?.status !== 401) {
          console.warn('Could not fetch user profile for auto-fill:', error);
        }
        setIsProfileLoading(false); // Only stop loading here on error
      }
    };

    fetchUserProfile();
  }, []);

  // Auto-fill matching fields from user profile
  useEffect(() => {
    if (!userProfile || allFields.length === 0) return;

    const autoFilled = {};

    // Create fullname from first_name + last_name
    const fullName = [userProfile.first_name, userProfile.last_name].filter(Boolean).join(' ');
    const profileWithFullName = { ...userProfile, fullname: fullName || null };

    allFields.forEach(field => {
      const fieldNameLower = field.name.toLowerCase().replace(/[-_\s]/g, '');
      const labelLower = (field.label || '').toLowerCase().replace(/[-_\s]/g, '');

      // Keywords to strictly exclude from name/personal auto-fill
      const EXCLUDE_KEYWORDS = ['university', 'college', 'school', 'institution', 'institute', 'company', 'organization', 'project', 'product', 'item', 'group'];

      const isExcluded = EXCLUDE_KEYWORDS.some(kw =>
        (fieldNameLower.includes(kw) || labelLower.includes(kw))
      );

      if (isExcluded) return; // Skip this field

      // Check if this field matches any user profile field
      for (const [pattern, profileKey] of Object.entries(fieldMappings)) {
        const patternClean = pattern.replace(/[-_\s]/g, '');

        if (fieldNameLower.includes(patternClean) || labelLower.includes(patternClean)) {
          const profileValue = profileWithFullName[profileKey];
          if (profileValue) {
            autoFilled[field.name] = profileValue;
            console.log(`✅ Auto-filled '${field.name}' with '${profileValue}' from '${profileKey}'`);
            break;
          }
        }
      }
    });

    if (Object.keys(autoFilled).length > 0) {
      setAutoFilledFields(autoFilled);
      setFormData(prev => ({ ...prev, ...autoFilled }));
      formDataRef.current = { ...formDataRef.current, ...autoFilled };
    }

    // Auto-fill calculation complete -> Unblock the UI
    // Add a small delay to ensure state propagation and prevent race conditions
    setTimeout(() => {
      setIsProfileLoading(false);
    }, 500);
  }, [userProfile, allFields]);

  // Effect to handle field changes: Update prompt and Play Audio ONCE
  // Skip auto-filled fields
  useEffect(() => {
    if (isProfileLoading) return;

    if (allFields.length > 0 && currentFieldIndex < allFields.length) {
      const field = allFields[currentFieldIndex];

      // Skip this field if it was auto-filled
      if (autoFilledFields[field.name]) {
        console.log(`⏭️ Skipping auto-filled field: ${field.name}`);
        setLastFilled({ label: field.label || field.name, value: autoFilledFields[field.name], auto: true });
        handleNextField(currentFieldIndex);
        return;
      }

      const prompt = field.smart_prompt || `Please provide ${field.label || field.name}`;
      setCurrentPrompt(prompt);

      // Auto-play audio for the field (once)
      playPrompt(field.name);

      // Start idle timer - repeat after 15s if no user action
      startIdleTimer(field.name);
    }
  }, [currentFieldIndex, allFields, autoFilledFields, isProfileLoading]);

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

  const playPrompt = async (fieldName) => {
    if (!fieldName) return;

    // Stop current audio if any
    if (audioRef.current) {
      if (typeof audioRef.current.pause === 'function') {
        try { audioRef.current.pause(); } catch (e) { }
      }
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }

    try {
      const audioUrl = `http://localhost:8000/speech/${fieldName}?t=${Date.now()}`;
      console.log(`🔊 Playing prompt from: ${audioUrl}`);

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      await audio.play();
    } catch (e) {
      console.error("Audio playback failed:", e);
    }
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

      // Normalize text: trim and collapse multiple spaces
      const normalizedText = text.trim().replace(/\s+/g, ' ');

      // Update State (for UI)
      setFormData(prev => ({ ...prev, [field.name]: normalizedText }));

      // Update Ref (for logic/submission safety)
      formDataRef.current = { ...formDataRef.current, [field.name]: normalizedText };

      setLastFilled({ label: field.label || field.name, value: normalizedText }); // Store last answer
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

  // Skip current field (only for non-required fields)
  const handleSkipField = () => {
    const field = allFields[currentFieldIndex];
    if (field && !field.required) {
      console.log(`⏭️ User skipped optional field: ${field.name}`);
      setLastFilled({ label: field.label || field.name, value: '(skipped)', skipped: true });
      handleNextField(currentFieldIndex);
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
          <div className="text-xs font-semibold text-white/40 font-mono uppercase tracking-widest">
            voice_interface.exe
          </div>
          {/* Debug/Status Info */}
          <div className="text-right">
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/30">
              {isProfileLoading ? (
                <span className="flex items-center gap-1 text-yellow-500/80"><span className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" /> Loading Profile...</span>
              ) : userProfile ? (
                <span className="flex items-center gap-1 text-green-500/60"><span className="w-1.5 h-1.5 rounded-full bg-green-500" /> User: {userProfile.first_name || 'Guest'}</span>
              ) : (
                <span className="text-white/20">Guest Mode (No Auto-fill)</span>
              )}
            </div>
            {Object.keys(autoFilledFields).length > 0 && (
              <div className="text-[10px] font-mono text-green-400/40 mt-0.5">
                ⚡ {Object.keys(autoFilledFields).length} fields auto-filled
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
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
                    <span>
                      {lastFilled.auto ? '🤖 Auto-filled: ' : lastFilled.skipped ? '⏭️ Skipped: ' : 'Captured: '}
                      <strong className="text-white">{lastFilled.value}</strong> for {lastFilled.label}
                    </span>
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
          <div className="mt-8 relative z-10 flex items-center gap-4">
            {/* Skip Button - only show for non-required fields */}
            {currentField && !currentField.required && (
              <button
                onClick={handleSkipField}
                className="px-4 py-2 rounded-full text-sm font-medium bg-white/5 border border-white/20 text-white/60 hover:bg-white/10 hover:text-white transition-all"
              >
                Skip
              </button>
            )}

            <button
              onClick={toggleListening}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl ${isListening
                ? 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30 shadow-[0_0_30px_rgba(239,68,68,0.3)]'
                : 'bg-green-500 text-black hover:scale-105 shadow-[0_0_30px_rgba(34,197,94,0.4)]'
                }`}
            >
              {isListening ? <MicOff size={32} /> : <Mic size={32} />}
            </button>

            {/* Spacer for symmetry when skip button is shown */}
            {currentField && !currentField.required && <div className="w-16" />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceFormFiller;