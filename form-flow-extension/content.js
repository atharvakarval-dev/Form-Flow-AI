/**
 * FormFlow AI - Content Script
 * 
 * Injected into web pages to:
 * - Detect forms and extract field schemas
 * - Inject "Fill with Voice" buttons
 * - Manage voice overlay UI
 * - Fill form fields with extracted values
 */

(function () {
    'use strict';

    console.log('FormFlow: Content script loaded (v3.2.0)');

    // Prevent multiple injections
    if (window.__formFlowInjected) return;
    window.__formFlowInjected = true;

    // =============================================================================
    // Configuration
    // =============================================================================

    const CONFIG = {
        MIN_FORM_FIELDS: 2,
        BUTTON_OFFSET: 10,
        OVERLAY_Z_INDEX: 2147483647
    };

    // =============================================================================
    // Form Detector
    // =============================================================================

    class FormDetector {
        constructor() {
            this.detectedForms = [];
            this.injectedButtons = new Set();
        }

        /**
         * Scan the page for forms and return their schemas
         */
        scanPage() {
            this.detectedForms = [];
            const forms = document.querySelectorAll('form');

            forms.forEach((form, index) => {
                const schema = this.extractFormSchema(form, index);
                if (schema.fields.length >= CONFIG.MIN_FORM_FIELDS) {
                    this.detectedForms.push(schema);
                }
            });

            // Also check for formless inputs (common in SPAs)
            const formlessSchema = this.extractFormlessInputs();
            if (formlessSchema.fields.length >= CONFIG.MIN_FORM_FIELDS) {
                this.detectedForms.push(formlessSchema);
            }

            console.log(`FormFlow: Detected ${this.detectedForms.length} forms`);
            return this.detectedForms;
        }

        /**
         * Extract schema from a form element
         */
        extractFormSchema(form, index) {
            const fields = [];
            const inputs = form.querySelectorAll('input, select, textarea, [role="combobox"]');

            inputs.forEach(input => {
                const field = this.extractFieldInfo(input);
                if (field) {
                    fields.push(field);
                }
            });

            return {
                id: form.id || `form_${index}`,
                action: form.action || window.location.href,
                method: form.method || 'POST',
                fields: fields
            };
        }

        /**
         * Extract formless inputs (not inside a form tag)
         */
        extractFormlessInputs() {
            const allInputs = document.querySelectorAll('input, select, textarea, [role="combobox"]');
            const formlessInputs = Array.from(allInputs).filter(input => !input.closest('form'));

            const fields = formlessInputs
                .map(input => this.extractFieldInfo(input))
                .filter(Boolean);

            return {
                id: 'formless_container',
                action: window.location.href,
                method: 'POST',
                fields: fields
            };
        }

        /**
         * Extract information about a single form field
         */
        extractFieldInfo(element) {
            const type = element.type || element.tagName.toLowerCase();
            const name = element.name || element.id || '';

            // Skip hidden, submit, and button fields
            if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) {
                return null;
            }

            // Skip if no identifiable name
            if (!name && !element.id && !element.placeholder) {
                return null;
            }

            // Find label
            let label = this.findLabel(element);

            // Build field info
            const field = {
                name: name || element.id || `field_${Date.now()}`,
                type: this.normalizeType(type),
                label: label || name || element.placeholder || '',
                required: element.required || element.hasAttribute('required'),
                placeholder: element.placeholder || '',
                value: element.value || '',
                selector: this.generateSelector(element)
            };

            // Add options for select elements
            if (element.tagName === 'SELECT') {
                field.options = Array.from(element.options).map(opt => ({
                    value: opt.value,
                    text: opt.text
                }));
            }

            // Add options for custom comboboxes (try to find associated listbox)
            if (element.getAttribute('role') === 'combobox') {
                field.type = 'select'; // Treat as select
                // Try to find options from aria-controls or standard patterns
                const listboxId = element.getAttribute('aria-controls');
                if (listboxId) {
                    const listbox = document.getElementById(listboxId);
                    if (listbox) {
                        const options = listbox.querySelectorAll('[role="option"]');
                        if (options.length) {
                            field.options = Array.from(options).map(opt => ({
                                value: opt.getAttribute('data-value') || opt.textContent.trim(),
                                text: opt.textContent.trim()
                            }));
                        }
                    }
                }
            }

            // Add options for radio/checkbox groups
            if (type === 'radio' || type === 'checkbox') {
                const groupName = element.name;
                if (groupName) {
                    const group = document.querySelectorAll(`input[name="${groupName}"]`);
                    field.options = Array.from(group).map(opt => ({
                        value: opt.value,
                        label: this.findLabel(opt) || opt.value
                    }));
                }
            }

            return field;
        }

        /**
         * Find the label for an input element
         */
        findLabel(element) {
            // Check for explicit label
            if (element.id) {
                const label = document.querySelector(`label[for="${element.id}"]`);
                if (label) return label.textContent.trim();
            }

            // Check for wrapping label
            const parentLabel = element.closest('label');
            if (parentLabel) {
                return parentLabel.textContent.replace(element.value, '').trim();
            }

            // Check for aria-label
            if (element.getAttribute('aria-label')) {
                return element.getAttribute('aria-label');
            }

            // Check for previous sibling label
            const prev = element.previousElementSibling;
            if (prev && prev.tagName === 'LABEL') {
                return prev.textContent.trim();
            }

            // Check parent for label-like elements
            const parent = element.parentElement;
            if (parent) {
                const labelEl = parent.querySelector('label, .label, [class*="label"]');
                if (labelEl) return labelEl.textContent.trim();
            }

            return '';
        }

        /**
         * Normalize input types
         */
        normalizeType(type) {
            const typeMap = {
                'text': 'text',
                'email': 'email',
                'tel': 'tel',
                'phone': 'tel',
                'number': 'number',
                'password': 'password',
                'url': 'url',
                'search': 'text',
                'date': 'date',
                'datetime-local': 'datetime',
                'time': 'time',
                'month': 'month',
                'week': 'week',
                'color': 'color',
                'file': 'file',
                'radio': 'radio',
                'checkbox': 'checkbox',
                'select': 'select',
                'select-one': 'select',
                'select-multiple': 'select',
                'textarea': 'textarea'
            };

            return typeMap[type.toLowerCase()] || 'text';
        }

        /**
         * Generate a unique CSS selector for an element
         */
        generateSelector(element) {
            if (element.id) {
                return `#${element.id}`;
            }

            if (element.name) {
                const tag = element.tagName.toLowerCase();
                return `${tag}[name="${element.name}"]`;
            }

            // Generate path-based selector
            const path = [];
            let current = element;

            while (current && current !== document.body) {
                let selector = current.tagName.toLowerCase();

                if (current.id) {
                    selector = `#${current.id}`;
                    path.unshift(selector);
                    break;
                }

                if (current.className) {
                    const classes = current.className.split(' ').filter(c => c && !c.includes('formflow'));
                    if (classes.length) {
                        selector += '.' + classes.slice(0, 2).join('.');
                    }
                }

                const siblings = current.parentElement?.querySelectorAll(`:scope > ${current.tagName.toLowerCase()}`);
                if (siblings && siblings.length > 1) {
                    const index = Array.from(siblings).indexOf(current) + 1;
                    selector += `:nth-child(${index})`;
                }

                path.unshift(selector);
                current = current.parentElement;
            }

            return path.join(' > ');
        }
    }


    // =============================================================================
    // Voice Overlay (Premium Design with Live Transcription)
    // =============================================================================

    const LOGO_URL = chrome.runtime.getURL('logo_black.jpg');

    const ICONS = {
        BOT: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>`,
        MIC: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>`,
        STOP: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>`,
        SEND: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>`,
        PAPERCLIP: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`,
        GLOBE: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`,
        BRAIN: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>`,
        CODE: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/></svg>`,
        X: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
        ARROW_DOWN: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>`,
        CORNER_DOWN_LEFT: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 10 4 15 9 20"/><path d="M20 4v7a4 4 0 0 1-4 4H4"/></svg>`
    };

    class VoiceOverlay {
        constructor(formDetector) {
            this.formDetector = formDetector;
            this.container = null;
            this.isExpanded = false;
            this.recognition = null;
            this.isListening = false;
            this.currentFormSchema = null;
            // Track all extracted values across the session
            this.allExtractedValues = {};
            this.isFormComplete = false;
            this.fillFormBtn = null;
        }

        create() {
            if (this.container) return;

            // Create container
            this.container = document.createElement('div');
            this.container.id = 'formflow-overlay-root';
            // CSS for container - Force bottom-right positioning with explicit resets
            this.container.style.cssText = `
                position: fixed !important;
                bottom: 30px !important;
                right: 30px !important;
                left: auto !important;
                top: auto !important;
                z-index: 2147483647 !important;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: flex-end !important;
                pointer-events: none !important;
                transform: none !important;
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
                background: transparent !important;
                width: auto !important;
                height: auto !important;
                box-shadow: none !important;
            `;

            const shadow = this.container.attachShadow({ mode: 'open' });

            // CSS (Design System) - Premium Chat Message List
            const styles = `
                :host {
                    --bg-dark: #1a1a1a;
                    --bg-panel: #0d0d0d;
                    --border-dark: #2a2a2a;
                    --text-primary: #f3f4f6;
                    --text-secondary: #9CA3AF;
                    --accent-blue: #1EAEDB;
                    --accent-purple: #8B5CF6;
                    --accent-orange: #F97316;
                    --danger: #ef4444;
                    --primary: #10b981;
                    --msg-ai-bg: #262626;
                    --msg-user-bg: #404040;
                }

                * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }

                /* Floating Trigger */
                .trigger-btn {
                    pointer-events: auto;
                    width: 56px;
                    height: 56px;
                    border-radius: 28px;
                    background: var(--bg-dark);
                    border: 1px solid var(--border-dark);
                    color: var(--text-primary);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }

                .trigger-btn:hover {
                    transform: scale(1.05);
                    box-shadow: 0 8px 30px rgba(0,0,0,0.5);
                    background: #2A2B2F;
                }

                /* Panel */
                .panel {
                   pointer-events: auto;
                   width: 500px;
                   max-width: 90vw;
                   height: 500px;
                   background: var(--bg-panel);
                   border: 1px solid var(--border-dark);
                   border-radius: 16px;
                   display: flex; 
                   flex-direction: column;
                   margin-bottom: 16px;
                   opacity: 0;
                   transform-origin: bottom right;
                   transform: scale(0.95) translateY(20px);
                   transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                   visibility: hidden;
                   overflow: hidden;
                   box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                }

                .panel.open {
                    opacity: 1;
                    transform: scale(1) translateY(0);
                    visibility: visible;
                }

                /* Chat History Container */
                .chat-container {
                    flex: 1;
                    overflow: hidden;
                    position: relative;
                }

                .chat-history {
                    height: 100%;
                    overflow-y: auto;
                    padding: 16px;
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                }
                
                .chat-history::-webkit-scrollbar { width: 6px; }
                .chat-history::-webkit-scrollbar-track { background: transparent; }
                .chat-history::-webkit-scrollbar-thumb { background: #444; border-radius: 3px; }
                .chat-history::-webkit-scrollbar-thumb:hover { background: #555; }

                /* Scroll to Bottom Button */
                .scroll-bottom-btn {
                    position: absolute;
                    bottom: 8px;
                    left: 50%;
                    transform: translateX(-50%);
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: var(--bg-dark);
                    border: 1px solid var(--border-dark);
                    color: var(--text-secondary);
                    cursor: pointer;
                    display: none;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    transition: all 0.2s;
                }
                .scroll-bottom-btn:hover { background: #333; color: var(--text-primary); }
                .scroll-bottom-btn.visible { display: flex; }

                /* Chat Bubble with Avatar */
                .chat-bubble {
                    display: flex;
                    gap: 10px;
                    max-width: 85%;
                    align-items: flex-end;
                    animation: fadeIn 0.3s ease;
                }
                
                .chat-bubble.ai { align-self: flex-start; }
                .chat-bubble.user { 
                    align-self: flex-end; 
                    flex-direction: row-reverse;
                }

                .avatar {
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    flex-shrink: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: 600;
                    overflow: hidden;
                }

                .avatar img {
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }

                /* Live Transcription Banner */
                .transcription-banner {
                    background: linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(220, 38, 38, 0.95));
                    padding: 12px 16px;
                    display: none;
                    align-items: center;
                    gap: 12px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    animation: slideDown 0.3s ease;
                }
                .transcription-banner.active { display: flex; }

                .transcription-icon {
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    animation: micPulse 1.5s ease-in-out infinite;
                }

                @keyframes micPulse {
                    0%, 100% { transform: scale(1); opacity: 1; }
                    50% { transform: scale(1.1); opacity: 0.8; }
                }

                @keyframes slideDown {
                    from { transform: translateY(-100%); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }

                .transcription-content {
                    flex: 1;
                    min-width: 0;
                }

                .transcription-label {
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    color: rgba(255, 255, 255, 0.9);
                    margin-bottom: 4px;
                }

                .transcription-text {
                    font-size: 14px;
                    color: white;
                    line-height: 1.4;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .transcription-text.interim {
                    opacity: 0.7;
                    font-style: italic;
                }

                .waveform {
                    display: flex;
                    align-items: center;
                    gap: 3px;
                    height: 24px;
                }

                .waveform-bar {
                    width: 3px;
                    background: white;
                    border-radius: 2px;
                    animation: waveAnimation 1.2s ease-in-out infinite;
                }

                .waveform-bar:nth-child(1) { animation-delay: 0s; }
                .waveform-bar:nth-child(2) { animation-delay: 0.1s; }
                .waveform-bar:nth-child(3) { animation-delay: 0.2s; }
                .waveform-bar:nth-child(4) { animation-delay: 0.3s; }
                .waveform-bar:nth-child(5) { animation-delay: 0.4s; }

                @keyframes waveAnimation {
                    0%, 100% { height: 8px; }
                    50% { height: 20px; }
                }

                .avatar.ai { 
                    background: linear-gradient(135deg, #ff6b6b, #ee5a24);
                    color: white;
                }
                .avatar.user { 
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }

                .msg-content {
                    padding: 12px 16px;
                    border-radius: 16px;
                    font-size: 14px;
                    line-height: 1.5;
                    color: var(--text-primary);
                    word-wrap: break-word;
                }
                
                .chat-bubble.ai .msg-content {
                    background: var(--msg-ai-bg);
                    border-top-left-radius: 4px;
                }
                
                .chat-bubble.user .msg-content {
                    background: var(--msg-user-bg);
                    border-top-right-radius: 4px;
                }

                /* Loading Dots Animation */
                .loading-dots {
                    display: flex;
                    gap: 4px;
                    padding: 4px 0;
                }

                .loading-dots span {
                    width: 8px;
                    height: 8px;
                    background: var(--text-secondary);
                    border-radius: 50%;
                    animation: bounce 1.4s ease-in-out infinite both;
                }

                .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
                .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
                .loading-dots span:nth-child(3) { animation-delay: 0s; }

                @keyframes bounce {
                    0%, 80%, 100% { transform: translateY(0); }
                    40% { transform: translateY(-6px); }
                }
                
                .fill-btn-inline {
                    margin-top: 8px;
                    padding: 6px 14px;
                    border-radius: 8px;
                    background: var(--primary);
                    color: white;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                    font-size: 13px;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.2s;
                }
                .fill-btn-inline:hover { opacity: 0.9; transform: scale(1.02); }
                .fill-btn-inline svg { width: 14px; height: 14px; }

                /* Sticky Fill Form Button */
                .fill-form-container {
                    padding: 12px 16px;
                    background: linear-gradient(180deg, transparent 0%, rgba(13, 13, 13, 0.95) 20%);
                    opacity: 0;
                    transform: translateY(20px);
                    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                }
                .fill-form-container.visible {
                    opacity: 1;
                    transform: translateY(0);
                }
                
                .fill-form-btn {
                    width: 100%;
                    padding: 14px 24px;
                    border-radius: 12px;
                    background: linear-gradient(135deg, var(--primary) 0%, #059669 100%);
                    color: white;
                    border: none;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 15px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 10px;
                    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);
                }
                .fill-form-btn:hover:not(:disabled) { 
                    transform: translateY(-2px); 
                    box-shadow: 0 8px 30px rgba(16, 185, 129, 0.4);
                }
                .fill-form-btn:active:not(:disabled) { 
                    transform: translateY(0); 
                }
                .fill-form-btn:disabled {
                    opacity: 0.7;
                    cursor: not-allowed;
                }
                .fill-form-btn svg { width: 20px; height: 20px; }

                /* Toast Notification */
                .notification {
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    padding: 10px 16px;
                    font-size: 13px;
                    font-weight: 500;
                    text-align: center;
                    opacity: 0;
                    transform: translateY(-100%);
                    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                }
                .notification.visible {
                    opacity: 1;
                    transform: translateY(0);
                }

                @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }


                /* Prompt Input Box (Redesigned) */
                .prompt-box {
                    background: var(--bg-dark);
                    border-top: 1px solid var(--border-dark);
                    padding: 24px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 16px;
                    transition: border-color 0.3s ease;
                    position: relative;
                    overflow: visible;
                }
                
                .prompt-box.recording { border-color: rgba(239, 68, 68, 0.4); }

                /* Floating Trigger Button */
                .trigger-btn {
                    position: fixed;
                    bottom: 24px;
                    right: 24px;
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    background: var(--primary);
                    border: none;
                    box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    z-index: 10000;
                    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
                }
                .trigger-btn:hover { transform: scale(1.1) rotate(10deg); }
                .trigger-btn svg { width: 32px; height: 32px; color: white; }

                /* Transcription Display */
                .transcription-display {
                    width: 100%;
                    position: relative;
                }

                .input-area {
                    width: 100%;
                    min-height: 40px;
                    max-height: 120px;
                    background: transparent;
                    border: none;
                    color: var(--text-primary);
                    font-size: 16px;
                    line-height: 1.6;
                    resize: none;
                    font-family: inherit;
                    text-align: center;
                    font-weight: 300;
                }
                .input-area::placeholder { color: #555; font-style: italic; }
                
                /* Hide scrollbars but allow scroll */
                .input-area::-webkit-scrollbar { display: none; }

                /* Actions Row Hidden but kept for any legacy references if needed */
                .actions-row { display: none; }

                /* New Voice Input Styling (Replica of React Component) */
                .voice-input-container {
                    width: 100%;
                    padding: 16px 0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 8px;
                }

                .voice-trigger-btn {
                    position: relative;
                    width: 64px;
                    height: 64px;
                    border-radius: 12px;
                    background: transparent;
                    border: none;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .voice-trigger-btn:hover {
                    background: rgba(255,255,255,0.1);
                }

                .mic-icon-wrapper {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 24px;
                    height: 24px;
                    color: rgba(255,255,255,0.9);
                    transition: opacity 0.3s;
                }

                .voice-trigger-btn.active .mic-icon-wrapper {
                    opacity: 0;
                    display: none;
                }

                .spinner-loader {
                    display: none;
                    width: 24px;
                    height: 24px;
                    background-color: #fff;
                    border-radius: 2px;
                    animation: spin 3s infinite linear;
                }

                .voice-trigger-btn.active .spinner-loader {
                    display: block;
                }

                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }

                .voice-timer {
                    font-family: 'Geist Mono', monospace;
                    font-size: 14px;
                    color: rgba(255,255,255,0.4);
                    transition: color 0.3s;
                }

                .voice-trigger-btn.active ~ .voice-timer {
                    color: rgba(255,255,255,0.9);
                }

                .voice-visualizer {
                    height: 16px;
                    width: 256px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 2px;
                }

                .bar {
                    width: 2px;
                    height: 4px;
                    background: rgba(255,255,255,0.2);
                    border-radius: 9999px;
                    transition: all 0.3s;
                }

                .voice-trigger-btn.active ~ .voice-visualizer .bar {
                    background: rgba(255,255,255,0.8);
                    animation: pulseBar 0.5s infinite ease-in-out;
                }
                
                @keyframes pulseBar {
                    0%, 100% { height: 4px; }
                    50% { height: 100%; }
                }

                .voice-status {
                    height: 16px;
                    font-size: 12px;
                    color: rgba(255,255,255,0.6);
                    margin: 0;
                }
            `;

            const styleSheet = document.createElement('style');
            styleSheet.textContent = styles;
            shadow.appendChild(styleSheet);

            const template = `
                <!-- Panel -->
                <div class="panel" id="panel">
                    <div class="chat-container">
                        <div class="chat-history" id="chatHistory">
                            <div class="chat-bubble ai">
                                <div class="avatar ai">
                                    <img src="${LOGO_URL}" alt="AI" />
                                </div>
                                <div class="msg-content">Hello! I'm ready to help you fill this form. Just speak about your information.</div>
                            </div>
                        </div>
                        <button class="scroll-bottom-btn" id="scrollBtn">${ICONS.ARROW_DOWN}</button>
                    </div>

                    <div class="prompt-box" id="promptBox">
                        <!-- Central Mic & Animation -->
                        <!-- New AI Voice Input -->
                        <div class="voice-input-container">
                            <!-- Mic Button -->
                            <button class="voice-trigger-btn" id="micBtn" type="button">
                                <div class="mic-icon-wrapper" id="micIconWrapper">
                                    ${ICONS.MIC}
                                </div>
                                <div class="spinner-loader" id="spinnerLoader"></div>
                            </button>

                            <!-- Timer -->
                            <span class="voice-timer" id="voiceTimer">00:00</span>

                            <!-- Visualizer -->
                            <div class="voice-visualizer" id="visualizer">
                                ${Array(48).fill(0).map(() => '<div class="bar"></div>').join('')}
                            </div>

                            <!-- Status Text -->
                            <p class="voice-status" id="voiceStatus">Click to speak</p>
                        </div>

                        <!-- Transcription Area (ReadOnly) -->
                        <div class="transcription-display">
                            <textarea class="input-area" id="inputArea" readonly placeholder="Tap the mic to start..."></textarea>
                        </div>
                        
                        <!-- Hidden Send Btn to maintain ref -->
                        <button id="sendBtn" style="display:none"></button>
                    </div>
                </div>

                <!-- Floating Trigger -->
                <button class="trigger-btn" id="triggerBtn">${ICONS.BOT}</button>
            `;

            const wrapper = document.createElement('div');
            wrapper.innerHTML = template;
            shadow.appendChild(wrapper);

            // References
            this.root = shadow;
            this.panel = shadow.getElementById('panel');
            this.triggerBtn = shadow.getElementById('triggerBtn');
            this.inputArea = shadow.getElementById('inputArea');
            this.micBtn = shadow.getElementById('micBtn');
            this.micIconWrapper = shadow.getElementById('micIconWrapper');
            this.spinnerLoader = shadow.getElementById('spinnerLoader');
            this.voiceTimer = shadow.getElementById('voiceTimer');
            this.visualizer = shadow.getElementById('visualizer');
            this.voiceStatus = shadow.getElementById('voiceStatus');
            this.visualizerBars = Array.from(this.visualizer.querySelectorAll('.bar'));

            this.sendBtn = shadow.getElementById('sendBtn');
            this.chatHistory = shadow.getElementById('chatHistory');
            this.promptBox = shadow.getElementById('promptBox');
            this.scrollBtn = shadow.getElementById('scrollBtn');

            this.timerInterval = null;
            this.startTime = 0;

            // Events
            this.triggerBtn.onclick = () => this.togglePanel();
            this.micBtn.onclick = () => this.toggleMic();
            this.sendBtn.onclick = () => this.handleSend();

            this.inputArea.oninput = () => {
                this.autoResizeInput();
                this.updateSendButtonState();
            };

            this.inputArea.onkeydown = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.handleSend();
                }
            };

            // Scroll button functionality
            this.scrollBtn.onclick = () => this.scrollToBottom();
            this.chatHistory.onscroll = () => this.checkScrollPosition();

            this.initSpeechRecognition();
            (document.documentElement || document.body).appendChild(this.container);
        }

        togglePanel() {
            this.isExpanded = !this.isExpanded;
            if (this.isExpanded) {
                this.panel.classList.add('open');
                this.triggerBtn.innerHTML = ICONS.X;
                this.inputArea.focus();
                this.scrollToBottom();

                // Auto-detect
                if (!this.currentFormSchema && this.formDetector) {
                    const detected = this.formDetector.scanPage();
                    if (detected && detected.length > 0) this.currentFormSchema = detected;
                }
            } else {
                this.panel.classList.remove('open');
                this.triggerBtn.innerHTML = ICONS.BOT;
            }
        }

        autoResizeInput() {
            this.inputArea.style.height = 'auto';
            this.inputArea.style.height = Math.min(this.inputArea.scrollHeight, 120) + 'px';
        }

        updateSendButtonState() {
            const text = this.inputArea.value.trim();
            if (text.length > 0) {
                this.sendBtn.classList.add('active');
            } else {
                this.sendBtn.classList.remove('active');
            }
        }

        toggleMic() {
            if (this.isListening) {
                this.stopListening();
            } else {
                this.startListening();
            }
        }

        handleSend() {
            const text = this.inputArea.value.trim();
            if (text.length > 0) {
                this.addMessage(text, 'user');
                this.inputArea.value = '';
                this.autoResizeInput();
                this.updateSendButtonState();
                this.processUserSpeech(text);
            }
        }

        scrollToBottom() {
            this.chatHistory.scrollTo({
                top: this.chatHistory.scrollHeight,
                behavior: 'smooth'
            });
        }

        checkScrollPosition() {
            const { scrollTop, scrollHeight, clientHeight } = this.chatHistory;
            const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

            if (isAtBottom) {
                this.scrollBtn.classList.remove('visible');
            } else {
                this.scrollBtn.classList.add('visible');
            }
        }

        addMessage(text, type = 'ai', isLoading = false) {
            const bubble = document.createElement('div');
            bubble.className = `chat-bubble ${type}`;

            const avatar = document.createElement('div');
            avatar.className = `avatar ${type}`;
            if (type === 'ai') {
                // Use the constant LOGO_URL
                avatar.innerHTML = `<img src="${LOGO_URL}" alt="AI" />`;
            } else {
                // Consistent User Avatar
                avatar.textContent = 'U';
            }

            const content = document.createElement('div');
            content.className = 'msg-content';

            if (isLoading) {
                content.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
            } else {
                content.textContent = text;
            }

            bubble.appendChild(avatar);
            bubble.appendChild(content);
            this.chatHistory.appendChild(bubble);
            this.scrollToBottom();

            return bubble;
        }

        initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                console.error('FormFlow: SpeechRecognition API not available in this browser');
                return;
            }

            console.log('FormFlow: Initializing SpeechRecognition...');
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onstart = () => {
                console.log('FormFlow: Speech recognition started');
            };

            this.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }

                console.log('FormFlow: Transcription -', { interim: interimTranscript, final: finalTranscript });

                // Update live transcription display
                if (interimTranscript) {
                    this.updateTranscription(interimTranscript, false);
                }

                if (finalTranscript) {
                    this.updateTranscription(finalTranscript, true);
                    this.addMessage(finalTranscript, 'user');
                    this.processUserSpeech(finalTranscript);
                    this.stopListening();
                }
            };

            this.recognition.onerror = (event) => {
                console.error('FormFlow: Speech recognition error:', event.error, event);

                // Show error to user
                let errorMessage = 'Voice input error: ';
                switch (event.error) {
                    case 'not-allowed':
                        errorMessage += 'Microphone access denied. Please allow microphone permission.';
                        break;
                    case 'no-speech':
                        errorMessage += 'No speech detected. Please try again.';
                        break;
                    case 'network':
                        errorMessage += 'Network error. Speech recognition requires internet.';
                        break;
                    case 'audio-capture':
                        errorMessage += 'No microphone found. Please check your audio settings.';
                        break;
                    case 'aborted':
                        errorMessage += 'Voice input was aborted.';
                        break;
                    default:
                        errorMessage += event.error || 'Unknown error occurred.';
                }

                // Update UI to show error
                this.updateTranscription(errorMessage, true);
                this.stopListening();
            };

            this.recognition.onend = () => {
                console.log('FormFlow: Speech recognition ended');
                if (this.isListening) this.stopListening();
                this.updateMicButtonState();
            };

            console.log('FormFlow: SpeechRecognition initialized successfully');
        }

        updateMicButtonState() {
            if (this.isListening) {
                this.micBtn.classList.add('active');
                this.voiceStatus.textContent = "Listening...";
                this.startTimer();
                this.startVisualizer();
            } else {
                this.micBtn.classList.remove('active');
                this.voiceStatus.textContent = "Click to speak";
                this.stopTimer();
                this.stopVisualizer();
            }
        }

        startTimer() {
            this.startTime = Date.now();
            this.voiceTimer.textContent = "00:00";
            clearInterval(this.timerInterval);

            this.timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
                const secs = (elapsed % 60).toString().padStart(2, '0');
                this.voiceTimer.textContent = `${mins}:${secs} `;
            }, 1000);
        }

        stopTimer() {
            clearInterval(this.timerInterval);
            this.voiceTimer.textContent = "00:00";
        }

        startVisualizer() {
            this.visualizerBars.forEach((bar, i) => {
                bar.style.animationDelay = `${i * 0.05} s`;
                bar.style.height = `${20 + Math.random() * 80}% `;
            });
        }

        stopVisualizer() {
            this.visualizerBars.forEach(bar => {
                bar.style.animationDelay = '0s';
                bar.style.height = '4px';
            });
        }

        updateTranscription(text, isFinal) {
            if (this.inputArea) {
                this.inputArea.value = text || (this.isListening ? 'Listening...' : '');

                // Auto-scroll textarea if needed
                this.inputArea.scrollTop = this.inputArea.scrollHeight;
            }
        }

        startListening() {
            if (!this.recognition) return;
            this.isListening = true;
            this.recognition.start();
            this.updateMicButtonState();
        }

        stopListening() {
            this.isListening = false;
            if (this.recognition) this.recognition.stop();
            this.updateMicButtonState();
        }

        async processUserSpeech(text) {
            // Add loading bubble with animated dots
            const loadingBubble = this.addMessage('', 'ai', true);

            if (!this.currentFormSchema && this.formDetector) {
                const detected = this.formDetector.scanPage();
                if (detected && detected.length > 0) this.currentFormSchema = detected;
            }

            try {
                const statusResponse = await chrome.runtime.sendMessage({ type: 'GET_SESSION_STATUS' });
                if (!statusResponse.hasSession && this.currentFormSchema) {
                    await chrome.runtime.sendMessage({
                        type: 'START_SESSION',
                        formSchema: this.currentFormSchema,
                        formUrl: window.location.href
                    });
                }

                const response = await chrome.runtime.sendMessage({
                    type: 'SEND_MESSAGE',
                    text: text
                });

                // Remove loading bubble
                loadingBubble.remove();

                if (response.success) {
                    this.addMessage(response.response, 'ai');

                    // Accumulate extracted values across the session
                    if (response.extractedValues && Object.keys(response.extractedValues).length > 0) {
                        Object.assign(this.allExtractedValues, response.extractedValues);
                        console.log('FormFlow: Accumulated values:', this.allExtractedValues);

                        // Show extraction notification
                        const extractedCount = Object.keys(this.allExtractedValues).length;
                        this.showNotification(`✓ ${extractedCount} field${extractedCount > 1 ? 's' : ''} collected`);
                    }

                    // Check if form is complete - show sticky Fill Form button
                    if (response.isComplete) {
                        this.isFormComplete = true;
                        this.showFillFormButton();
                        this.showNotification('🎉 All fields collected! Ready to fill form.');
                    }


                } else {
                    this.addMessage("Error: " + response.error, 'ai');
                }
            } catch (e) {
                console.error(e);
                loadingBubble.remove();
                this.addMessage("Connection error (Backend might be down)", 'ai');
            }
        }

        showFillFormButton() {
            // Only create if not already present
            if (this.fillFormBtn) return;

            // Get the shadow root
            const shadow = this.container.shadowRoot;
            if (!shadow) return;

            // Create sticky button container
            const btnContainer = document.createElement('div');
            btnContainer.className = 'fill-form-container';
            btnContainer.innerHTML = `
                <button class="fill-form-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>
                    </svg>
                    <span>Fill Form (${Object.keys(this.allExtractedValues).length} fields)</span>
                </button>
            `;

            // Insert before the prompt box
            const promptBox = shadow.querySelector('.prompt-box');
            if (promptBox) {
                promptBox.parentNode.insertBefore(btnContainer, promptBox);
            }

            this.fillFormBtn = btnContainer;

            // Add click handler
            btnContainer.querySelector('button').onclick = async () => {
                btnContainer.querySelector('button').disabled = true;
                btnContainer.querySelector('span').textContent = 'Filling...';
                await this.autoFill(this.allExtractedValues);
                btnContainer.querySelector('span').textContent = '✓ Done!';
                setTimeout(() => {
                    btnContainer.remove();
                    this.fillFormBtn = null;
                }, 1500);
            };

            // Add animation
            setTimeout(() => btnContainer.classList.add('visible'), 50);
        }

        showNotification(message) {
            const shadow = this.container?.shadowRoot;
            if (!shadow) return;

            // Create notification element
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.textContent = message;

            // Insert at top of panel
            const panel = shadow.querySelector('.panel');
            if (panel) {
                panel.insertBefore(notification, panel.firstChild);

                // Animate in
                setTimeout(() => notification.classList.add('visible'), 10);

                // Remove after delay
                setTimeout(() => {
                    notification.classList.remove('visible');
                    setTimeout(() => notification.remove(), 300);
                }, 2500);
            }
        }

        async autoFill(data) {
            const formFiller = new FormFiller();
            const filledCount = await formFiller.fillFields(data, this.currentFormSchema);
            this.addMessage(`✅ Form filled! (${filledCount} fields updated)`, 'ai');
        }

        hide() {
            if (this.isExpanded) this.togglePanel();
        }
    }

    // =============================================================================
    // Form Filler
    // =============================================================================

    class FormFiller {
        async fillFields(data, formSchema) {
            let filled = 0;

            for (const [fieldName, value] of Object.entries(data)) {
                // Find the field in schema
                const fieldInfo = this.findFieldInSchema(fieldName, formSchema);
                if (!fieldInfo) continue;

                // Find element using selector
                const element = document.querySelector(fieldInfo.selector);
                if (!element) continue;

                // Fill based on type
                const success = await this.fillField(element, value, fieldInfo.type);
                if (success) filled++;
            }

            return filled;
        }

        findFieldInSchema(fieldName, formSchema) {
            for (const form of formSchema) {
                const field = form.fields.find(f => f.name === fieldName);
                if (field) return field;
            }
            return null;
        }

        async fillField(element, value, type) {
            try {
                // Focus the element
                element.focus();

                switch (type) {
                    case 'text':
                    case 'email':
                    case 'tel':
                    case 'number':
                    case 'password':
                    case 'url':
                    case 'date':
                    case 'textarea':
                        return this.fillTextInput(element, value);

                    case 'select':
                        if (element.getAttribute('role') === 'combobox') {
                            return this.fillCombobox(element, value);
                        }
                        return this.fillSelect(element, value);

                    case 'radio':
                    case 'checkbox':
                        return this.fillCheckbox(element, value);

                    case 'file':
                        // File inputs cannot be filled programmatically for security reasons
                        console.log('FormFlow: Skipping file input - cannot fill programmatically');
                        return false;

                    default:
                        // Check if it's a file input by element type (safety check)
                        if (element.type === 'file') {
                            console.log('FormFlow: Skipping file input - cannot fill programmatically');
                            return false;
                        }
                        if (element.getAttribute('role') === 'combobox') {
                            return this.fillCombobox(element, value);
                        }
                        return this.fillTextInput(element, value);
                }
            } catch (error) {
                console.error('FormFlow: Error filling field:', error);
                return false;
            }
        }

        fillTextInput(element, value) {
            // Clear existing value
            element.value = '';

            // Type character by character for human-like behavior
            element.value = value;

            // Dispatch events
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));

            // Highlight briefly
            this.highlightField(element);

            return true;
        }

        fillSelect(element, value) {
            // Find matching option
            const option = Array.from(element.options).find(opt =>
                opt.value.toLowerCase() === value.toLowerCase() ||
                opt.text.toLowerCase().includes(value.toLowerCase())
            );

            if (option) {
                element.value = option.value;
                element.dispatchEvent(new Event('change', { bubbles: true }));
                this.highlightField(element);
                return true;
            }

            return false;
        }

        async fillCombobox(element, value) {
            // Click to open
            element.click();
            await new Promise(r => setTimeout(r, 300));

            // Try to find listbox
            const listboxId = element.getAttribute('aria-controls');
            let options = [];

            if (listboxId) {
                const listbox = document.getElementById(listboxId);
                if (listbox) options = Array.from(listbox.querySelectorAll('[role="option"]'));
            } else {
                // Fallback: look for nearby visible options
                options = Array.from(document.querySelectorAll('[role="option"]')).filter(opt => {
                    const rect = opt.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
            }

            // Find matching option
            const option = options.find(opt => {
                const text = opt.textContent.trim().toLowerCase();
                const val = (opt.getAttribute('data-value') || '').toLowerCase();
                const target = value.toLowerCase();
                return text.includes(target) || val === target;
            });

            if (option) {
                option.click();
                this.highlightField(element);
                return true;
            }

            return false;
        }

        fillCheckbox(element, value) {
            const shouldCheck = ['yes', 'true', '1', 'check', 'checked'].includes(
                String(value).toLowerCase()
            );

            if (element.checked !== shouldCheck) {
                element.click();
            }

            this.highlightField(element);
            return true;
        }

        highlightField(element) {
            const originalBorder = element.style.border;
            const originalBoxShadow = element.style.boxShadow;

            element.style.border = '2px solid #10b981';
            element.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.5)';

            setTimeout(() => {
                element.style.border = originalBorder;
                element.style.boxShadow = originalBoxShadow;
            }, 1000);
        }
    }

    // =============================================================================
    // Initialize
    // =============================================================================

    const formDetector = new FormDetector();
    const overlay = new VoiceOverlay(formDetector);

    // Create overlay immediately
    if (document.readyState === 'complete') {
        overlay.create();
    } else {
        window.addEventListener('load', () => {
            overlay.create();
        });
    }

    console.log('FormFlow: Initialized successfully');

})();