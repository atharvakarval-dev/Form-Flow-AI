/**
 * useVoiceFlow - WhisperFlow Voice Processing Hook
 * 
 * Connects to the FlowEngine backend for intelligent voice processing:
 * - Self-correction handling ("wait, no", "actually")
 * - User snippet expansion
 * - Smart formatting (lists, tech terms)
 * - Action detection (Calendar, Jira, Slack, Email)
 * 
 * Usage:
 *   const {
 *     isListening,
 *     isProcessing,
 *     result,
 *     startListening,
 *     stopListening,
 *     processText
 *   } = useVoiceFlow({
 *     appContext: { view: 'DealPipeline' },
 *     onResult: (result) => console.log(result.display_text),
 *     onAction: (action) => console.log('Action:', action)
 *   });
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import flowApi from '../services/flowApi';
import { useActionDispatcher } from './useActionDispatcher';

// =============================================================================
// HOOK
// =============================================================================

const useVoiceFlow = ({
    appContext = null,
    vocabulary = null,
    language = 'en-US',
    onResult = null,
    onAction = null,
    onError = null,
    // Action handlers (passed to ActionDispatcher)
    onCalendarAction = null,
    onJiraAction = null,
    onSlackAction = null,
    onEmailAction = null,
    // Auto-dispatch actions or just notify
    autoDispatchActions = true
} = {}) => {
    // State
    const [isListening, setIsListening] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [interimTranscript, setInterimTranscript] = useState('');
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    // Refs
    const recognitionRef = useRef(null);

    // Action dispatcher
    const actionDispatcher = useActionDispatcher({
        onCalendarAction,
        onJiraAction,
        onSlackAction,
        onEmailAction
    });

    // Initialize speech recognition
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            setError('Speech recognition not supported in this browser');
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = language;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            setIsListening(true);
            setError(null);
            setInterimTranscript('');
        };

        recognition.onend = () => {
            setIsListening(false);
        };

        recognition.onerror = (event) => {
            console.warn('Speech recognition error:', event.error);
            setIsListening(false);

            if (event.error !== 'no-speech' && event.error !== 'aborted') {
                const errorMsg = `Recognition error: ${event.error}`;
                setError(errorMsg);
                onError?.(errorMsg);
            }
        };

        recognition.onresult = async (event) => {
            const results = event.results;
            const lastResult = results[results.length - 1];

            if (lastResult.isFinal) {
                const finalTranscript = lastResult[0].transcript;
                setTranscript(finalTranscript);
                setInterimTranscript('');

                // Process through Flow Engine
                await processText(finalTranscript);
            } else {
                setInterimTranscript(lastResult[0].transcript);
            }
        };

        recognitionRef.current = recognition;

        return () => {
            recognition.abort();
        };
    }, [language]);

    /**
     * Process text through the Flow Engine
     */
    const processText = useCallback(async (text) => {
        if (!text?.trim()) return null;

        setIsProcessing(true);
        setError(null);

        try {
            const flowResult = await flowApi.processFlow(text, appContext, vocabulary);

            setResult(flowResult);

            // Handle based on intent
            if (flowResult.intent === 'command' && flowResult.actions?.length > 0) {
                // Dispatch actions
                if (autoDispatchActions) {
                    const dispatchResults = actionDispatcher.dispatchAll(flowResult.actions, {
                        displayText: flowResult.display_text,
                        confidence: flowResult.confidence
                    });

                    // Notify about each action
                    flowResult.actions.forEach((action, index) => {
                        onAction?.(action, dispatchResults[index]);
                    });
                } else {
                    // Just notify, don't dispatch
                    flowResult.actions.forEach(action => {
                        onAction?.(action, { handled: false });
                    });
                }
            }

            // Always call onResult with the processed text
            onResult?.(flowResult);

            return flowResult;

        } catch (err) {
            console.error('Flow Engine error:', err);
            const errorMsg = err.message || 'Flow processing failed';
            setError(errorMsg);
            onError?.(errorMsg);
            return null;
        } finally {
            setIsProcessing(false);
        }
    }, [appContext, vocabulary, autoDispatchActions, actionDispatcher, onResult, onAction, onError]);

    /**
     * Start listening for voice input
     */
    const startListening = useCallback(() => {
        if (recognitionRef.current && !isListening) {
            try {
                recognitionRef.current.start();
            } catch (err) {
                console.warn('Could not start recognition:', err);
            }
        }
    }, [isListening]);

    /**
     * Stop listening
     */
    const stopListening = useCallback(() => {
        if (recognitionRef.current && isListening) {
            recognitionRef.current.stop();
        }
    }, [isListening]);

    /**
     * Reset state
     */
    const reset = useCallback(() => {
        setTranscript('');
        setInterimTranscript('');
        setResult(null);
        setError(null);
    }, []);

    return {
        // State
        isListening,
        isProcessing,
        transcript,
        interimTranscript,
        result,
        error,

        // Computed
        displayText: result?.display_text || '',
        intent: result?.intent || 'typing',
        detectedApps: result?.detected_apps || [],
        actions: result?.actions || [],
        corrections: result?.corrections_applied || [],
        snippetsExpanded: result?.snippets_expanded || [],
        confidence: result?.confidence || 0,

        // Actions
        startListening,
        stopListening,
        processText,
        reset,

        // Action dispatcher access
        registerActionHandler: actionDispatcher.registerHandler,
        unregisterActionHandler: actionDispatcher.unregisterHandler
    };
};

export default useVoiceFlow;
