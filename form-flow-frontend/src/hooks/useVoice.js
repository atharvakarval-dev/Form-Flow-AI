/**
 * useVoice Hook
 * 
 * Manages voice recording state, audio analysis for volume levels,
 * and speech recognition integration for FormFlow AI.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for voice input with real-time audio visualization
 * 
 * @returns {Object} Voice state and controls
 * @property {boolean} isListening - Whether actively listening
 * @property {boolean} isProcessing - Whether processing audio
 * @property {number} volumeLevel - Current volume level (0-1)
 * @property {string} transcript - Final transcript text
 * @property {string} interimTranscript - In-progress transcript
 * @property {string|null} error - Error message if any
 * @property {Function} startListening - Start voice capture
 * @property {Function} stopListening - Stop voice capture
 * @property {Function} toggleListening - Toggle voice capture
 * @property {Function} resetTranscript - Clear transcript
 */
export default function useVoice() {
    const [isListening, setIsListening] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [volumeLevel, setVolumeLevel] = useState(0);
    const [transcript, setTranscript] = useState('');
    const [interimTranscript, setInterimTranscript] = useState('');
    const [error, setError] = useState(null);

    const recognitionRef = useRef(null);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const micStreamRef = useRef(null);
    const animationFrameRef = useRef(null);

    // Initialize Speech Recognition
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            setError('Speech recognition not supported in this browser');
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let interim = '';
            let final = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcriptText = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += transcriptText;
                } else {
                    interim += transcriptText;
                }
            }

            if (final) {
                setTranscript(prev => prev + ' ' + final);
                setInterimTranscript('');
            } else {
                setInterimTranscript(interim);
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error !== 'no-speech') {
                setError(`Voice error: ${event.error}`);
            }
        };

        recognition.onend = () => {
            // Auto-restart if still supposed to be listening
            if (isListening && recognitionRef.current) {
                try {
                    recognitionRef.current.start();
                } catch (e) {
                    // Already started
                }
            }
        };

        recognitionRef.current = recognition;

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        };
    }, [isListening]);

    // Audio analysis for volume visualization
    const startAudioAnalysis = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            micStreamRef.current = stream;

            const audioContext = new AudioContext();
            audioContextRef.current = audioContext;

            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8;
            analyserRef.current = analyser;

            const source = audioContext.createMediaStreamSource(stream);
            source.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);

            const updateVolume = () => {
                if (!analyserRef.current) return;

                analyserRef.current.getByteFrequencyData(dataArray);

                // Calculate RMS volume
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) {
                    sum += dataArray[i] * dataArray[i];
                }
                const rms = Math.sqrt(sum / dataArray.length);

                // Normalize to 0-1 range with some amplification
                const normalizedVolume = Math.min(1, rms / 128);
                setVolumeLevel(normalizedVolume);

                animationFrameRef.current = requestAnimationFrame(updateVolume);
            };

            updateVolume();
        } catch (err) {
            console.error('Error accessing microphone:', err);
            setError('Could not access microphone');
        }
    }, []);

    const stopAudioAnalysis = useCallback(() => {
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }

        if (micStreamRef.current) {
            micStreamRef.current.getTracks().forEach(track => track.stop());
            micStreamRef.current = null;
        }

        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        analyserRef.current = null;
        setVolumeLevel(0);
    }, []);

    const startListening = useCallback(() => {
        if (!recognitionRef.current) {
            setError('Speech recognition not available');
            return;
        }

        setError(null);
        setIsListening(true);

        try {
            recognitionRef.current.start();
            startAudioAnalysis();
        } catch (err) {
            console.error('Error starting recognition:', err);
        }
    }, [startAudioAnalysis]);

    const stopListening = useCallback(() => {
        setIsListening(false);

        if (recognitionRef.current) {
            recognitionRef.current.stop();
        }

        stopAudioAnalysis();
    }, [stopAudioAnalysis]);

    const toggleListening = useCallback(() => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    }, [isListening, startListening, stopListening]);

    const resetTranscript = useCallback(() => {
        setTranscript('');
        setInterimTranscript('');
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopAudioAnalysis();
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        };
    }, [stopAudioAnalysis]);

    return {
        isListening,
        isProcessing,
        volumeLevel,
        transcript,
        interimTranscript,
        error,
        startListening,
        stopListening,
        toggleListening,
        resetTranscript,
    };
}
