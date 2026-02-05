/**
 * FormFlow Plugin SDK
 * 
 * Embeddable widget for voice-driven data collection.
 * Single script tag integration with automatic initialization.
 * 
 * Usage:
 *   <script src="https://cdn.formflow.io/plugin-sdk.min.js"
 *           data-api-key="YOUR_API_KEY"
 *           data-plugin-id="YOUR_PLUGIN_ID">
 *   </script>
 * 
 * Or programmatic:
 *   FormFlowPlugin.init({
 *     apiKey: 'YOUR_API_KEY',
 *     pluginId: 'YOUR_PLUGIN_ID',
 *     container: '#formflow-widget'
 *   });
 */

(function (global, factory) {
    // UMD wrapper
    typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() :
        typeof define === 'function' && define.amd ? define(factory) :
            (global = global || self, global.FormFlowPlugin = factory());
}(this, function () {
    'use strict';

    // =========================================================================
    // Configuration & Constants
    // =========================================================================

    const VERSION = '1.0.0';
    const DEFAULT_API_BASE = 'https://api.formflow.io/v1';
    const DEFAULT_STYLES = {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: '999999'
    };

    // Widget states
    const WidgetState = {
        IDLE: 'idle',
        LISTENING: 'listening',
        PROCESSING: 'processing',
        SUCCESS: 'success',
        ERROR: 'error'
    };

    // =========================================================================
    // Utilities
    // =========================================================================

    function createElement(tag, attrs, children) {
        const el = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(key => {
                if (key === 'style' && typeof attrs[key] === 'object') {
                    Object.assign(el.style, attrs[key]);
                } else if (key.startsWith('on') && typeof attrs[key] === 'function') {
                    el.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
                } else if (key === 'className') {
                    el.className = attrs[key];
                } else {
                    el.setAttribute(key, attrs[key]);
                }
            });
        }
        if (children) {
            if (Array.isArray(children)) {
                children.forEach(child => {
                    if (typeof child === 'string') {
                        el.appendChild(document.createTextNode(child));
                    } else if (child) {
                        el.appendChild(child);
                    }
                });
            } else if (typeof children === 'string') {
                el.textContent = children;
            } else {
                el.appendChild(children);
            }
        }
        return el;
    }

    function generateId() {
        return 'ff_' + Math.random().toString(36).substr(2, 9);
    }

    // =========================================================================
    // API Client
    // =========================================================================

    class APIClient {
        constructor(config) {
            this.apiKey = config.apiKey;
            this.pluginId = config.pluginId;
            this.baseUrl = config.apiBase || DEFAULT_API_BASE;
        }

        async request(endpoint, options = {}) {
            const url = `${this.baseUrl}${endpoint}`;
            const headers = {
                'Content-Type': 'application/json',
                'X-API-Key': this.apiKey,
                'X-Plugin-ID': this.pluginId,
                ...options.headers
            };

            try {
                const response = await fetch(url, {
                    ...options,
                    headers,
                    body: options.body ? JSON.stringify(options.body) : undefined
                });

                if (!response.ok) {
                    const error = await response.json().catch(() => ({}));
                    throw new Error(error.message || `HTTP ${response.status}`);
                }

                return response.json();
            } catch (error) {
                console.error('[FormFlow] API Error:', error);
                throw error;
            }
        }

        // Start a new data collection session
        async startSession(metadata = {}) {
            return this.request('/plugins/sessions', {
                method: 'POST',
                body: { metadata }
            });
        }

        // Submit user input (voice transcription or text)
        async submitInput(sessionId, input, requestId) {
            return this.request(`/plugins/sessions/${sessionId}/input`, {
                method: 'POST',
                body: { input, request_id: requestId }
            });
        }

        // Complete the session and trigger database population
        async completeSession(sessionId) {
            return this.request(`/plugins/sessions/${sessionId}/complete`, {
                method: 'POST'
            });
        }

        // Get session status
        async getSession(sessionId) {
            return this.request(`/plugins/sessions/${sessionId}`);
        }
    }

    // =========================================================================
    // Voice Recognition
    // =========================================================================

    class VoiceRecognizer {
        constructor(onResult, onError, options = {}) {
            this.onResult = onResult;
            this.onError = onError;
            this.isListening = false;
            this.recognition = null;
            this.options = {
                language: options.language || 'en-US',
                continuous: options.continuous || false,
                interimResults: options.interimResults || true
            };
        }

        isSupported() {
            return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
        }

        start() {
            if (!this.isSupported()) {
                this.onError(new Error('Speech recognition not supported'));
                return false;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();

            this.recognition.lang = this.options.language;
            this.recognition.continuous = this.options.continuous;
            this.recognition.interimResults = this.options.interimResults;

            this.recognition.onresult = (event) => {
                const results = Array.from(event.results);
                const transcript = results.map(r => r[0].transcript).join(' ');
                const isFinal = results.some(r => r.isFinal);
                this.onResult(transcript, isFinal);
            };

            this.recognition.onerror = (event) => {
                this.isListening = false;
                this.onError(new Error(event.error));
            };

            this.recognition.onend = () => {
                this.isListening = false;
            };

            this.recognition.start();
            this.isListening = true;
            return true;
        }

        stop() {
            if (this.recognition) {
                this.recognition.stop();
                this.isListening = false;
            }
        }
    }

    // =========================================================================
    // Widget UI
    // =========================================================================

    class Widget {
        constructor(container, options) {
            this.container = typeof container === 'string'
                ? document.querySelector(container)
                : container;
            this.options = options;
            this.state = WidgetState.IDLE;
            this.elements = {};
            this.listeners = [];
        }

        render() {
            // Main widget container
            this.elements.root = createElement('div', {
                className: 'formflow-widget',
                style: {
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    backgroundColor: '#ffffff',
                    borderRadius: '16px',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                    padding: '20px',
                    width: '320px',
                    transition: 'all 0.3s ease'
                }
            });

            // Header
            this.elements.header = createElement('div', {
                style: { marginBottom: '16px', textAlign: 'center' }
            }, [
                createElement('h3', {
                    style: {
                        margin: '0 0 4px 0',
                        fontSize: '16px',
                        fontWeight: '600',
                        color: '#1a1a1a'
                    }
                }, this.options.title || 'Voice Assistant'),
                createElement('p', {
                    style: {
                        margin: '0',
                        fontSize: '13px',
                        color: '#666'
                    }
                }, this.options.subtitle || 'Tap to speak')
            ]);

            // Question display
            this.elements.question = createElement('div', {
                className: 'formflow-question',
                style: {
                    backgroundColor: '#f8f9fa',
                    borderRadius: '12px',
                    padding: '16px',
                    marginBottom: '16px',
                    minHeight: '60px',
                    fontSize: '14px',
                    lineHeight: '1.5',
                    color: '#333'
                }
            }, 'Press the microphone button to start...');

            // Transcript display
            this.elements.transcript = createElement('div', {
                className: 'formflow-transcript',
                style: {
                    minHeight: '40px',
                    marginBottom: '16px',
                    padding: '12px',
                    backgroundColor: '#e8f4fd',
                    borderRadius: '8px',
                    fontSize: '13px',
                    color: '#0066cc',
                    display: 'none'
                }
            });

            // Mic button
            this.elements.micButton = createElement('button', {
                className: 'formflow-mic-button',
                style: {
                    width: '64px',
                    height: '64px',
                    borderRadius: '50%',
                    border: 'none',
                    backgroundColor: '#4F46E5',
                    color: '#fff',
                    fontSize: '24px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 4px 12px rgba(79, 70, 229, 0.4)'
                },
                onClick: () => this.emit('micClick')
            }, '🎤');

            // Progress bar
            this.elements.progress = createElement('div', {
                style: {
                    marginTop: '16px',
                    height: '4px',
                    backgroundColor: '#e5e7eb',
                    borderRadius: '2px',
                    overflow: 'hidden'
                }
            }, [
                createElement('div', {
                    className: 'formflow-progress-fill',
                    style: {
                        width: '0%',
                        height: '100%',
                        backgroundColor: '#4F46E5',
                        transition: 'width 0.3s ease'
                    }
                })
            ]);

            // Error display
            this.elements.error = createElement('div', {
                className: 'formflow-error',
                style: {
                    display: 'none',
                    marginTop: '12px',
                    padding: '12px',
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    borderRadius: '8px',
                    fontSize: '13px'
                }
            });

            // Assemble
            this.elements.root.appendChild(this.elements.header);
            this.elements.root.appendChild(this.elements.question);
            this.elements.root.appendChild(this.elements.transcript);
            this.elements.root.appendChild(this.elements.micButton);
            this.elements.root.appendChild(this.elements.progress);
            this.elements.root.appendChild(this.elements.error);

            // Append to container
            if (this.container) {
                this.container.appendChild(this.elements.root);
            } else {
                // Create floating container
                const floating = createElement('div', {
                    style: DEFAULT_STYLES
                });
                floating.appendChild(this.elements.root);
                document.body.appendChild(floating);
            }

            return this;
        }

        setState(state) {
            this.state = state;

            const micBtn = this.elements.micButton;

            switch (state) {
                case WidgetState.LISTENING:
                    micBtn.style.backgroundColor = '#dc2626';
                    micBtn.style.animation = 'formflow-pulse 1.5s infinite';
                    micBtn.textContent = '⏹';
                    break;
                case WidgetState.PROCESSING:
                    micBtn.style.backgroundColor = '#f59e0b';
                    micBtn.style.animation = 'none';
                    micBtn.textContent = '⏳';
                    micBtn.disabled = true;
                    break;
                case WidgetState.SUCCESS:
                    micBtn.style.backgroundColor = '#10b981';
                    micBtn.textContent = '✓';
                    break;
                case WidgetState.ERROR:
                    micBtn.style.backgroundColor = '#dc2626';
                    micBtn.textContent = '✕';
                    break;
                default:
                    micBtn.style.backgroundColor = '#4F46E5';
                    micBtn.style.animation = 'none';
                    micBtn.textContent = '🎤';
                    micBtn.disabled = false;
            }
        }

        setQuestion(text) {
            this.elements.question.textContent = text;
        }

        setTranscript(text, show = true) {
            this.elements.transcript.textContent = text;
            this.elements.transcript.style.display = show ? 'block' : 'none';
        }

        setProgress(percent) {
            const fill = this.elements.progress.querySelector('.formflow-progress-fill');
            if (fill) {
                fill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
            }
        }

        showError(message) {
            this.elements.error.textContent = message;
            this.elements.error.style.display = 'block';
            setTimeout(() => {
                this.elements.error.style.display = 'none';
            }, 5000);
        }

        on(event, callback) {
            this.listeners.push({ event, callback });
        }

        emit(event, data) {
            this.listeners
                .filter(l => l.event === event)
                .forEach(l => l.callback(data));
        }

        destroy() {
            if (this.elements.root && this.elements.root.parentNode) {
                this.elements.root.parentNode.removeChild(this.elements.root);
            }
            this.listeners = [];
        }
    }

    // =========================================================================
    // Main Plugin Controller
    // =========================================================================

    class FormFlowPluginController {
        constructor(config) {
            this.config = {
                apiKey: config.apiKey,
                pluginId: config.pluginId,
                apiBase: config.apiBase,
                container: config.container,
                language: config.language || 'en-US',
                title: config.title,
                subtitle: config.subtitle,
                onStart: config.onStart || (() => { }),
                onComplete: config.onComplete || (() => { }),
                onError: config.onError || (() => { }),
                onProgress: config.onProgress || (() => { })
            };

            this.api = new APIClient(this.config);
            this.widget = null;
            this.recognizer = null;
            this.session = null;
            this.isActive = false;
        }

        async init() {
            // Create widget
            this.widget = new Widget(this.config.container, this.config);
            this.widget.render();

            // Initialize voice recognizer
            this.recognizer = new VoiceRecognizer(
                (transcript, isFinal) => this.handleTranscript(transcript, isFinal),
                (error) => this.handleError(error),
                { language: this.config.language }
            );

            // Wire up events
            this.widget.on('micClick', () => this.toggleListening());

            // Inject CSS animations
            this.injectStyles();

            console.log('[FormFlow] SDK initialized v' + VERSION);
            return this;
        }

        injectStyles() {
            if (document.getElementById('formflow-styles')) return;

            const style = document.createElement('style');
            style.id = 'formflow-styles';
            style.textContent = `
        @keyframes formflow-pulse {
          0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.7); }
          70% { transform: scale(1.05); box-shadow: 0 0 0 15px rgba(220, 38, 38, 0); }
          100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
        }
        .formflow-widget * { box-sizing: border-box; }
        .formflow-mic-button:hover { transform: scale(1.05); }
        .formflow-mic-button:active { transform: scale(0.95); }
      `;
            document.head.appendChild(style);
        }

        async toggleListening() {
            if (this.recognizer.isListening) {
                this.stopListening();
            } else {
                await this.startListening();
            }
        }

        async startListening() {
            try {
                // Start session if not active
                if (!this.session) {
                    this.widget.setState(WidgetState.PROCESSING);
                    this.session = await this.api.startSession();
                    this.widget.setQuestion(this.session.current_question || 'Please speak...');
                    this.config.onStart(this.session);
                }

                // Start voice recognition
                this.recognizer.start();
                this.widget.setState(WidgetState.LISTENING);
                this.isActive = true;
            } catch (error) {
                this.handleError(error);
            }
        }

        stopListening() {
            this.recognizer.stop();
            this.widget.setState(WidgetState.IDLE);
        }

        async handleTranscript(transcript, isFinal) {
            this.widget.setTranscript(transcript, true);

            if (isFinal && transcript.trim()) {
                this.stopListening();
                await this.submitInput(transcript);
            }
        }

        async submitInput(input) {
            if (!this.session) return;

            try {
                this.widget.setState(WidgetState.PROCESSING);

                const requestId = generateId();
                const response = await this.api.submitInput(
                    this.session.session_id,
                    input,
                    requestId
                );

                // Update UI with response
                if (response.is_complete) {
                    await this.complete();
                } else {
                    this.widget.setQuestion(response.next_question || 'Continue speaking...');
                    this.widget.setProgress(response.progress || 0);
                    this.widget.setState(WidgetState.IDLE);
                    this.config.onProgress(response);
                }
            } catch (error) {
                this.handleError(error);
            }
        }

        async complete() {
            try {
                this.widget.setState(WidgetState.PROCESSING);
                const result = await this.api.completeSession(this.session.session_id);

                this.widget.setState(WidgetState.SUCCESS);
                this.widget.setQuestion('Thank you! Data collected successfully.');
                this.widget.setProgress(100);
                this.widget.setTranscript('', false);

                this.config.onComplete(result);
                this.session = null;
                this.isActive = false;

                // Reset after delay
                setTimeout(() => {
                    this.widget.setState(WidgetState.IDLE);
                    this.widget.setQuestion('Press the microphone button to start...');
                }, 3000);
            } catch (error) {
                this.handleError(error);
            }
        }

        handleError(error) {
            console.error('[FormFlow] Error:', error);
            this.widget.setState(WidgetState.ERROR);
            this.widget.showError(error.message || 'An error occurred');
            this.config.onError(error);

            // Reset after delay
            setTimeout(() => {
                this.widget.setState(WidgetState.IDLE);
            }, 3000);
        }

        destroy() {
            if (this.recognizer) {
                this.recognizer.stop();
            }
            if (this.widget) {
                this.widget.destroy();
            }
            this.session = null;
        }
    }

    // =========================================================================
    // Auto-initialization from script tag
    // =========================================================================

    function autoInit() {
        const scripts = document.querySelectorAll('script[data-api-key][data-plugin-id]');
        scripts.forEach(script => {
            const config = {
                apiKey: script.getAttribute('data-api-key'),
                pluginId: script.getAttribute('data-plugin-id'),
                apiBase: script.getAttribute('data-api-base'),
                container: script.getAttribute('data-container'),
                language: script.getAttribute('data-language'),
                title: script.getAttribute('data-title'),
                subtitle: script.getAttribute('data-subtitle')
            };

            if (config.apiKey && config.pluginId) {
                FormFlowPlugin.init(config);
            }
        });
    }

    // =========================================================================
    // Public API
    // =========================================================================

    const FormFlowPlugin = {
        version: VERSION,
        instance: null,

        init: function (config) {
            if (this.instance) {
                this.instance.destroy();
            }
            this.instance = new FormFlowPluginController(config);
            return this.instance.init();
        },

        destroy: function () {
            if (this.instance) {
                this.instance.destroy();
                this.instance = null;
            }
        },

        // Expose classes for advanced usage
        APIClient: APIClient,
        Widget: Widget,
        VoiceRecognizer: VoiceRecognizer
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    return FormFlowPlugin;
}));
