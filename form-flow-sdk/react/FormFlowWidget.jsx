/**
 * FormFlow Plugin React Component
 * 
 * React wrapper for the FormFlow Plugin SDK.
 * 
 * @example
 * import { FormFlowWidget } from '@formflow/plugin-sdk/react';
 * 
 * <FormFlowWidget
 *   apiKey="YOUR_API_KEY"
 *   pluginId="YOUR_PLUGIN_ID"
 *   onComplete={(result) => console.log(result)}
 * />
 * 
 * @typedef {Object} FormFlowWidgetProps
 * @property {string} apiKey - Plugin API key
 * @property {string} pluginId - Plugin ID
 * @property {string} [apiBase] - Custom API base URL
 * @property {string} [title] - Widget title
 * @property {string} [subtitle] - Widget subtitle
 * @property {string} [language] - Voice recognition language
 * @property {Function} [onStart] - Session start callback
 * @property {Function} [onComplete] - Completion callback
 * @property {Function} [onError] - Error callback
 * @property {Function} [onProgress] - Progress callback
 * @property {string} [className] - Custom CSS class
 * @property {Object} [style] - Custom inline styles
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';

/**
 * FormFlow Plugin Widget React Component
 * @param {FormFlowWidgetProps} props
 */
export function FormFlowWidget({
    apiKey,
    pluginId,
    apiBase = 'https://api.formflow.io/v1',
    title = 'Voice Assistant',
    subtitle = 'Tap to speak',
    language = 'en-US',
    onStart,
    onComplete,
    onError,
    onProgress,
    className,
    style
}) {
    const [state, setState] = useState('idle');
    const [question, setQuestion] = useState('Press the microphone button to start...');
    const [transcript, setTranscript] = useState('');
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState(null);

    const sessionRef = useRef(null);
    const recognizerRef = useRef(null);
    const isListeningRef = useRef(false);

    // API request helper
    const apiRequest = useCallback(async (endpoint, options = {}) => {
        const url = `${apiBase}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey,
            'X-Plugin-ID': pluginId,
            ...options.headers
        };

        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.message || `HTTP ${response.status}`);
        }
        return response.json();
    }, [apiBase, apiKey, pluginId]);

    // Handle error
    const handleError = useCallback((err) => {
        console.error('[FormFlow]', err);
        setState('error');
        setError(err.message);
        onError?.(err);
        setTimeout(() => { setState('idle'); setError(null); }, 3000);
    }, [onError]);

    // Start session
    const startSession = useCallback(async () => {
        try {
            setState('processing');
            const session = await apiRequest('/plugins/sessions', {
                method: 'POST',
                body: JSON.stringify({})
            });
            sessionRef.current = session;
            setQuestion(session.current_question || 'Please speak...');
            onStart?.(session);
            return session;
        } catch (err) {
            handleError(err);
            throw err;
        }
    }, [apiRequest, onStart, handleError]);

    // Complete session
    const completeSession = useCallback(async () => {
        if (!sessionRef.current) return;
        try {
            setState('processing');
            const result = await apiRequest(
                `/plugins/sessions/${sessionRef.current.session_id}/complete`,
                { method: 'POST' }
            );
            setState('success');
            setQuestion('Thank you! Data collected successfully.');
            setProgress(100);
            setTranscript('');
            onComplete?.(result);
            setTimeout(() => {
                setState('idle');
                setQuestion('Press the microphone button to start...');
                sessionRef.current = null;
            }, 3000);
        } catch (err) {
            handleError(err);
        }
    }, [apiRequest, onComplete, handleError]);

    // Submit input
    const submitInput = useCallback(async (input) => {
        if (!sessionRef.current) return;
        try {
            setState('processing');
            const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;
            const response = await apiRequest(
                `/plugins/sessions/${sessionRef.current.session_id}/input`,
                { method: 'POST', body: JSON.stringify({ input, request_id: requestId }) }
            );
            if (response.is_complete) {
                await completeSession();
            } else {
                setQuestion(response.next_question || 'Continue speaking...');
                setProgress(response.progress || 0);
                setState('idle');
                onProgress?.(response);
            }
        } catch (err) {
            handleError(err);
        }
    }, [apiRequest, onProgress, completeSession, handleError]);

    // Initialize speech recognition
    useEffect(() => {
        const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognitionClass) {
            console.warn('[FormFlow] Speech recognition not supported');
            return;
        }
        const recognition = new SpeechRecognitionClass();
        recognition.lang = language;
        recognition.continuous = false;
        recognition.interimResults = true;

        recognition.onresult = (event) => {
            const results = Array.from(event.results);
            const text = results.map(r => r[0].transcript).join(' ');
            const isFinal = results.some(r => r.isFinal);
            setTranscript(text);
            if (isFinal && text.trim()) {
                isListeningRef.current = false;
                setState('processing');
                submitInput(text);
            }
        };

        recognition.onerror = (event) => {
            isListeningRef.current = false;
            handleError(new Error(event.error));
        };

        recognition.onend = () => { isListeningRef.current = false; };
        recognizerRef.current = recognition;
        return () => { recognition.abort(); };
    }, [language, submitInput, handleError]);

    // Toggle listening
    const toggleListening = useCallback(async () => {
        if (!recognizerRef.current) {
            handleError(new Error('Speech recognition not available'));
            return;
        }
        if (isListeningRef.current) {
            recognizerRef.current.stop();
            isListeningRef.current = false;
            setState('idle');
        } else {
            if (!sessionRef.current) await startSession();
            recognizerRef.current.start();
            isListeningRef.current = true;
            setState('listening');
        }
    }, [startSession, handleError]);

    const buttonBg = state === 'listening' ? '#dc2626' :
        state === 'processing' ? '#f59e0b' :
            state === 'success' ? '#10b981' :
                state === 'error' ? '#dc2626' : '#4F46E5';

    const buttonIcon = state === 'listening' ? '⏹' :
        state === 'processing' ? '⏳' :
            state === 'success' ? '✓' :
                state === 'error' ? '✕' : '🎤';

    return React.createElement('div', {
        className: `formflow-widget ${className || ''}`,
        style: {
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            backgroundColor: '#ffffff', borderRadius: 16,
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)', padding: 20, width: 320, ...style
        }
    },
        // Header
        React.createElement('div', { style: { marginBottom: 16, textAlign: 'center' } },
            React.createElement('h3', { style: { margin: '0 0 4px 0', fontSize: 16, fontWeight: 600, color: '#1a1a1a' } }, title),
            React.createElement('p', { style: { margin: 0, fontSize: 13, color: '#666' } }, subtitle)
        ),
        // Question
        React.createElement('div', {
            style: { backgroundColor: '#f8f9fa', borderRadius: 12, padding: 16, marginBottom: 16, minHeight: 60, fontSize: 14, lineHeight: 1.5, color: '#333' }
        }, question),
        // Transcript
        transcript && React.createElement('div', {
            style: { minHeight: 40, marginBottom: 16, padding: 12, backgroundColor: '#e8f4fd', borderRadius: 8, fontSize: 13, color: '#0066cc' }
        }, transcript),
        // Mic button
        React.createElement('button', {
            onClick: toggleListening, disabled: state === 'processing',
            style: {
                width: 64, height: 64, borderRadius: '50%', border: 'none', backgroundColor: buttonBg,
                color: '#fff', fontSize: 24, cursor: state === 'processing' ? 'wait' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto',
                transition: 'all 0.2s ease', boxShadow: '0 4px 12px rgba(79, 70, 229, 0.4)'
            }
        }, buttonIcon),
        // Progress
        React.createElement('div', {
            style: { marginTop: 16, height: 4, backgroundColor: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }
        },
            React.createElement('div', {
                style: { width: `${progress}%`, height: '100%', backgroundColor: '#4F46E5', transition: 'width 0.3s ease' }
            })
        ),
        // Error
        error && React.createElement('div', {
            style: { marginTop: 12, padding: 12, backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: 8, fontSize: 13 }
        }, error)
    );
}

/**
 * Hook for programmatic SDK control
 * @param {Object} config - Configuration options
 */
export function useFormFlowPlugin(config) {
    const [isReady, setIsReady] = useState(false);
    const pluginRef = useRef(null);

    useEffect(() => {
        const script = document.createElement('script');
        script.src = `${config.apiBase || 'https://api.formflow.io'}/sdk/formflow-plugin.min.js`;
        script.onload = () => {
            if (window.FormFlowPlugin) {
                pluginRef.current = window.FormFlowPlugin;
                setIsReady(true);
            }
        };
        document.head.appendChild(script);
        return () => { script.remove(); };
    }, [config.apiBase]);

    const init = useCallback((container) => {
        if (pluginRef.current?.init) {
            return pluginRef.current.init({ ...config, container });
        }
    }, [config]);

    const destroy = useCallback(() => {
        pluginRef.current?.destroy?.();
    }, []);

    return { isReady, init, destroy };
}

export default FormFlowWidget;
