/**
 * FormFlow Plugin React Component
 * 
 * React wrapper for the FormFlow Plugin SDK.
 * 
 * Usage:
 *   import { FormFlowWidget } from '@formflow/plugin-sdk/react';
 *   
 *   <FormFlowWidget
 *     apiKey="YOUR_API_KEY"
 *     pluginId="YOUR_PLUGIN_ID"
 *     onComplete={(result) => console.log(result)}
 *   />
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';

// Types
export interface FormFlowWidgetProps {
    /** Plugin API key */
    apiKey: string;
    /** Plugin ID */
    pluginId: string;
    /** Custom API base URL */
    apiBase?: string;
    /** Widget title */
    title?: string;
    /** Widget subtitle */
    subtitle?: string;
    /** Voice recognition language (default: en-US) */
    language?: string;
    /** Called when session starts */
    onStart?: (session: SessionData) => void;
    /** Called when data collection completes */
    onComplete?: (result: CompletionResult) => void;
    /** Called on error */
    onError?: (error: Error) => void;
    /** Called on progress update */
    onProgress?: (progress: ProgressData) => void;
    /** Custom CSS class */
    className?: string;
    /** Custom inline styles */
    style?: React.CSSProperties;
}

export interface SessionData {
    session_id: string;
    current_question?: string;
    fields?: FieldInfo[];
}

export interface FieldInfo {
    column_name: string;
    column_type: string;
    question_text: string;
    is_required: boolean;
}

export interface CompletionResult {
    session_id: string;
    extracted_values: Record<string, any>;
    inserted_rows: number;
    status: 'success' | 'partial' | 'failed';
}

export interface ProgressData {
    progress: number;
    completed_fields: string[];
    remaining_fields: string[];
    next_question?: string;
}

// Widget state type
type WidgetState = 'idle' | 'listening' | 'processing' | 'success' | 'error';

/**
 * FormFlow Plugin Widget React Component
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
}: FormFlowWidgetProps): JSX.Element {
    const [state, setState] = useState<WidgetState>('idle');
    const [question, setQuestion] = useState('Press the microphone button to start...');
    const [transcript, setTranscript] = useState('');
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const sessionRef = useRef<SessionData | null>(null);
    const recognizerRef = useRef<SpeechRecognition | null>(null);
    const isListeningRef = useRef(false);

    // API request helper
    const apiRequest = useCallback(async (endpoint: string, options: RequestInit = {}) => {
        const url = `${apiBase}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey,
            'X-Plugin-ID': pluginId,
            ...options.headers as Record<string, string>
        };

        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.message || `HTTP ${response.status}`);
        }
        return response.json();
    }, [apiBase, apiKey, pluginId]);

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
            handleError(err as Error);
            throw err;
        }
    }, [apiRequest, onStart]);

    // Submit input
    const submitInput = useCallback(async (input: string) => {
        if (!sessionRef.current) return;

        try {
            setState('processing');
            const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;

            const response = await apiRequest(
                `/plugins/sessions/${sessionRef.current.session_id}/input`,
                {
                    method: 'POST',
                    body: JSON.stringify({ input, request_id: requestId })
                }
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
            handleError(err as Error);
        }
    }, [apiRequest, onProgress]);

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

            // Reset after delay
            setTimeout(() => {
                setState('idle');
                setQuestion('Press the microphone button to start...');
                sessionRef.current = null;
            }, 3000);
        } catch (err) {
            handleError(err as Error);
        }
    }, [apiRequest, onComplete]);

    // Handle error
    const handleError = useCallback((err: Error) => {
        console.error('[FormFlow]', err);
        setState('error');
        setError(err.message);
        onError?.(err);

        setTimeout(() => {
            setState('idle');
            setError(null);
        }, 3000);
    }, [onError]);

    // Initialize speech recognition
    useEffect(() => {
        const SpeechRecognition = (window as any).SpeechRecognition ||
            (window as any).webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('[FormFlow] Speech recognition not supported');
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = language;
        recognition.continuous = false;
        recognition.interimResults = true;

        recognition.onresult = (event: SpeechRecognitionEvent) => {
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

        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
            isListeningRef.current = false;
            handleError(new Error(event.error));
        };

        recognition.onend = () => {
            isListeningRef.current = false;
        };

        recognizerRef.current = recognition;

        return () => {
            recognition.abort();
        };
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
            // Start session if needed
            if (!sessionRef.current) {
                await startSession();
            }

            recognizerRef.current.start();
            isListeningRef.current = true;
            setState('listening');
        }
    }, [startSession, handleError]);

    // Button styles based on state
    const buttonStyles: React.CSSProperties = {
        width: 64,
        height: 64,
        borderRadius: '50%',
        border: 'none',
        backgroundColor: state === 'listening' ? '#dc2626' :
            state === 'processing' ? '#f59e0b' :
                state === 'success' ? '#10b981' :
                    state === 'error' ? '#dc2626' : '#4F46E5',
        color: '#fff',
        fontSize: 24,
        cursor: state === 'processing' ? 'wait' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '0 auto',
        transition: 'all 0.2s ease',
        boxShadow: '0 4px 12px rgba(79, 70, 229, 0.4)'
    };

    return (
        <div
            className={`formflow-widget ${className || ''}`}
            style={{
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                backgroundColor: '#ffffff',
                borderRadius: 16,
                boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                padding: 20,
                width: 320,
                ...style
            }}
        >
            {/* Header */}
            <div style={{ marginBottom: 16, textAlign: 'center' }}>
                <h3 style={{ margin: '0 0 4px 0', fontSize: 16, fontWeight: 600, color: '#1a1a1a' }}>
                    {title}
                </h3>
                <p style={{ margin: 0, fontSize: 13, color: '#666' }}>{subtitle}</p>
            </div>

            {/* Question */}
            <div style={{
                backgroundColor: '#f8f9fa',
                borderRadius: 12,
                padding: 16,
                marginBottom: 16,
                minHeight: 60,
                fontSize: 14,
                lineHeight: 1.5,
                color: '#333'
            }}>
                {question}
            </div>

            {/* Transcript */}
            {transcript && (
                <div style={{
                    minHeight: 40,
                    marginBottom: 16,
                    padding: 12,
                    backgroundColor: '#e8f4fd',
                    borderRadius: 8,
                    fontSize: 13,
                    color: '#0066cc'
                }}>
                    {transcript}
                </div>
            )}

            {/* Mic button */}
            <button
                onClick={toggleListening}
                disabled={state === 'processing'}
                style={buttonStyles}
            >
                {state === 'listening' ? '⏹' :
                    state === 'processing' ? '⏳' :
                        state === 'success' ? '✓' :
                            state === 'error' ? '✕' : '🎤'}
            </button>

            {/* Progress */}
            <div style={{
                marginTop: 16,
                height: 4,
                backgroundColor: '#e5e7eb',
                borderRadius: 2,
                overflow: 'hidden'
            }}>
                <div style={{
                    width: `${progress}%`,
                    height: '100%',
                    backgroundColor: '#4F46E5',
                    transition: 'width 0.3s ease'
                }} />
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    marginTop: 12,
                    padding: 12,
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    borderRadius: 8,
                    fontSize: 13
                }}>
                    {error}
                </div>
            )}
        </div>
    );
}

/**
 * Hook for programmatic SDK control
 */
export function useFormFlowPlugin(config: Omit<FormFlowWidgetProps, 'className' | 'style'>) {
    const [isReady, setIsReady] = useState(false);
    const pluginRef = useRef<any>(null);

    useEffect(() => {
        // Dynamic import of vanilla SDK
        const script = document.createElement('script');
        script.src = `${config.apiBase || 'https://api.formflow.io'}/sdk/formflow-plugin.min.js`;
        script.onload = () => {
            if ((window as any).FormFlowPlugin) {
                pluginRef.current = (window as any).FormFlowPlugin;
                setIsReady(true);
            }
        };
        document.head.appendChild(script);

        return () => {
            script.remove();
        };
    }, [config.apiBase]);

    const init = useCallback((container?: string | HTMLElement) => {
        if (pluginRef.current) {
            return pluginRef.current.init({
                ...config,
                container
            });
        }
    }, [config]);

    const destroy = useCallback(() => {
        if (pluginRef.current) {
            pluginRef.current.destroy();
        }
    }, []);

    return { isReady, init, destroy };
}

export default FormFlowWidget;
