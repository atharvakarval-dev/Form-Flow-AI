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
            const inputs = form.querySelectorAll('input, select, textarea');

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
            const allInputs = document.querySelectorAll('input, select, textarea');
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
    // Voice Overlay
    // =============================================================================

    class VoiceOverlay {
        constructor() {
            this.container = null;
            this.isVisible = false;
            this.recognition = null;
            this.isListening = false;
            this.currentFormSchema = null;
        }

        /**
         * Create and inject the overlay into the page
         */
        create() {
            if (this.container) return;

            // Create shadow DOM for style isolation
            this.container = document.createElement('div');
            this.container.id = 'formflow-overlay-root';
            this.container.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: ${CONFIG.OVERLAY_Z_INDEX};
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      `;

            const shadow = this.container.attachShadow({ mode: 'open' });

            shadow.innerHTML = `
        <style>
          * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
          }
          
          .overlay {
            width: 360px;
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.95), rgba(5, 150, 105, 0.95));
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            overflow: hidden;
            transform: translateY(20px);
            opacity: 0;
            transition: all 0.3s ease;
          }
          
          .overlay.visible {
            transform: translateY(0);
            opacity: 1;
          }
          
          .header {
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
          }
          
          .logo {
            display: flex;
            align-items: center;
            gap: 8px;
            color: white;
            font-weight: 600;
            font-size: 16px;
          }
          
          .logo-icon {
            width: 28px;
            height: 28px;
            background: white;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
          }
          
          .close-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
          }
          
          .close-btn:hover {
            background: rgba(255, 255, 255, 0.3);
          }
          
          .content {
            padding: 16px;
            max-height: 300px;
            overflow-y: auto;
          }
          
          .message {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 12px;
            color: white;
            font-size: 14px;
            line-height: 1.5;
          }
          
          .message.user {
            background: rgba(0, 0, 0, 0.2);
            margin-left: 40px;
          }
          
          .transcript {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 10px;
            color: rgba(255, 255, 255, 0.8);
            font-size: 13px;
            font-style: italic;
            min-height: 40px;
          }
          
          .transcript.listening {
            animation: pulse 1.5s infinite;
          }
          
          @keyframes pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
          }
          
          .controls {
            padding: 16px;
            display: flex;
            gap: 10px;
            border-top: 1px solid rgba(255, 255, 255, 0.2);
          }
          
          .mic-btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s;
          }
          
          .mic-btn.start {
            background: white;
            color: #059669;
          }
          
          .mic-btn.start:hover {
            background: #f0fdf4;
          }
          
          .mic-btn.stop {
            background: #ef4444;
            color: white;
          }
          
          .mic-btn.stop:hover {
            background: #dc2626;
          }
          
          .fill-btn {
            padding: 12px 20px;
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 12px;
            color: white;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
          }
          
          .fill-btn:hover {
            background: rgba(255, 255, 255, 0.3);
          }
          
          .fill-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          
          .progress {
            padding: 0 16px 16px;
          }
          
          .progress-bar {
            height: 4px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
            overflow: hidden;
          }
          
          .progress-fill {
            height: 100%;
            background: white;
            border-radius: 2px;
            transition: width 0.3s ease;
          }
          
          .progress-text {
            color: rgba(255, 255, 255, 0.8);
            font-size: 12px;
            margin-top: 6px;
            text-align: center;
          }
        </style>
        
        <div class="overlay" id="overlay">
          <div class="header">
            <div class="logo">
              <span class="logo-icon">🎤</span>
              FormFlow AI
            </div>
            <button class="close-btn" id="closeBtn">✕</button>
          </div>
          
          <div class="content" id="content">
            <div class="message" id="agentMessage">
              Hi! I'll help you fill out this form. Click the microphone button to start speaking.
            </div>
            <div class="transcript" id="transcript">
              Click "Start Listening" to begin...
            </div>
          </div>
          
          <div class="progress">
            <div class="progress-bar">
              <div class="progress-fill" id="progressFill" style="width: 0%"></div>
            </div>
            <div class="progress-text" id="progressText">0 of 0 fields completed</div>
          </div>
          
          <div class="controls">
            <button class="mic-btn start" id="micBtn">
              🎤 Start Listening
            </button>
            <button class="fill-btn" id="fillBtn" disabled>
              Fill Form
            </button>
          </div>
        </div>
      `;

            document.body.appendChild(this.container);

            // Get elements
            const shadowRoot = this.container.shadowRoot;
            this.overlay = shadowRoot.getElementById('overlay');
            this.agentMessage = shadowRoot.getElementById('agentMessage');
            this.transcript = shadowRoot.getElementById('transcript');
            this.micBtn = shadowRoot.getElementById('micBtn');
            this.fillBtn = shadowRoot.getElementById('fillBtn');
            this.progressFill = shadowRoot.getElementById('progressFill');
            this.progressText = shadowRoot.getElementById('progressText');

            // Bind events
            shadowRoot.getElementById('closeBtn').onclick = () => this.hide();
            this.micBtn.onclick = () => this.toggleListening();
            this.fillBtn.onclick = () => this.fillForm();

            // Initialize speech recognition
            this.initSpeechRecognition();
        }

        /**
         * Initialize Web Speech API
         */
        initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (!SpeechRecognition) {
                console.warn('FormFlow: Speech recognition not supported');
                return;
            }

            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

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

                // Update UI
                this.transcript.textContent = finalTranscript || interimTranscript || 'Listening...';

                if (finalTranscript) {
                    this.processUserSpeech(finalTranscript);
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.transcript.textContent = `Error: ${event.error}. Click to retry.`;
                this.stopListening();
            };

            this.recognition.onend = () => {
                if (this.isListening) {
                    // Auto-restart if still supposed to be listening
                    this.recognition.start();
                }
            };
        }

        /**
         * Toggle listening state
         */
        toggleListening() {
            if (this.isListening) {
                this.stopListening();
            } else {
                this.startListening();
            }
        }

        startListening() {
            if (!this.recognition) {
                this.transcript.textContent = 'Speech recognition not supported in this browser.';
                return;
            }

            this.isListening = true;
            this.recognition.start();

            this.micBtn.textContent = '⏹️ Stop Listening';
            this.micBtn.classList.remove('start');
            this.micBtn.classList.add('stop');
            this.transcript.textContent = 'Listening...';
            this.transcript.classList.add('listening');
        }

        stopListening() {
            this.isListening = false;
            if (this.recognition) {
                this.recognition.stop();
            }

            this.micBtn.textContent = '🎤 Start Listening';
            this.micBtn.classList.remove('stop');
            this.micBtn.classList.add('start');
            this.transcript.classList.remove('listening');
        }

        /**
         * Process user speech and send to backend
         */
        async processUserSpeech(text) {
            console.log('FormFlow: Processing speech:', text);

            // Add user message to UI
            const userMsg = document.createElement('div');
            userMsg.className = 'message user';
            userMsg.textContent = text;
            this.agentMessage.parentElement.insertBefore(userMsg, this.transcript);

            // Send to background script
            try {
                const response = await chrome.runtime.sendMessage({
                    type: 'SEND_MESSAGE',
                    text: text
                });

                if (response.success) {
                    this.agentMessage.textContent = response.response;
                    this.updateProgress(response);

                    if (Object.keys(response.extractedValues || {}).length > 0) {
                        this.fillBtn.disabled = false;
                    }

                    // Auto-fill if enabled and complete
                    if (response.isComplete) {
                        this.stopListening();
                        this.agentMessage.textContent += '\n\n✅ All fields collected! Click "Fill Form" to complete.';
                    }
                } else {
                    this.agentMessage.textContent = `Sorry, there was an error: ${response.error}`;
                }
            } catch (error) {
                console.error('FormFlow: Error processing speech:', error);
                this.agentMessage.textContent = 'Sorry, I had trouble processing that. Please try again.';
            }
        }

        /**
         * Update progress indicator
         */
        updateProgress(response) {
            const filled = Object.keys(response.extractedValues || {}).length;
            const total = filled + (response.remainingCount || 0);
            const percentage = total > 0 ? (filled / total) * 100 : 0;

            this.progressFill.style.width = `${percentage}%`;
            this.progressText.textContent = `${filled} of ${total} fields completed`;
        }

        /**
         * Fill the form with extracted values
         */
        async fillForm() {
            this.fillBtn.disabled = true;
            this.fillBtn.textContent = 'Filling...';

            try {
                const response = await chrome.runtime.sendMessage({
                    type: 'GET_EXTRACTED_DATA'
                });

                if (response.success && response.data) {
                    const formFiller = new FormFiller();
                    const filled = await formFiller.fillFields(response.data, this.currentFormSchema);

                    this.agentMessage.textContent = `✅ Filled ${filled} fields! Please review and submit.`;
                    this.fillBtn.textContent = 'Filled!';
                }
            } catch (error) {
                console.error('FormFlow: Error filling form:', error);
                this.agentMessage.textContent = 'Error filling form. Please try manually.';
                this.fillBtn.textContent = 'Fill Form';
                this.fillBtn.disabled = false;
            }
        }

        /**
         * Show the overlay with a greeting
         */
        async show(formSchema, greeting) {
            this.create();
            this.currentFormSchema = formSchema;

            // Update UI
            if (greeting) {
                this.agentMessage.textContent = greeting;
            }

            const total = formSchema.reduce((sum, f) => sum + f.fields.length, 0);
            this.progressText.textContent = `0 of ${total} fields completed`;

            // Animate in
            setTimeout(() => {
                this.overlay.classList.add('visible');
            }, 50);

            this.isVisible = true;
        }

        /**
         * Hide the overlay
         */
        async hide() {
            if (this.overlay) {
                this.overlay.classList.remove('visible');
            }

            this.stopListening();

            // End session
            await chrome.runtime.sendMessage({ type: 'END_SESSION' });

            setTimeout(() => {
                if (this.container) {
                    this.container.remove();
                    this.container = null;
                }
            }, 300);

            this.isVisible = false;
        }
    }

    // =============================================================================
    // Form Filler
    // =============================================================================

    class FormFiller {
        /**
         * Fill form fields with extracted values
         */
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
                        return this.fillSelect(element, value);

                    case 'radio':
                    case 'checkbox':
                        return this.fillCheckbox(element, value);

                    default:
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
    // Button Injector
    // =============================================================================

    class ButtonInjector {
        constructor(formDetector, overlay) {
            this.formDetector = formDetector;
            this.overlay = overlay;
            this.injectedButtons = new Set();
        }

        /**
         * Inject "Fill with Voice" buttons on detected forms
         */
        injectButtons() {
            const forms = this.formDetector.scanPage();

            forms.forEach((formSchema, index) => {
                const formElement = this.findFormElement(formSchema);
                if (!formElement || this.injectedButtons.has(formElement)) return;

                this.createButton(formElement, formSchema);
                this.injectedButtons.add(formElement);
            });
        }

        findFormElement(formSchema) {
            if (formSchema.id === 'formless_container') {
                // Find a container for formless inputs
                const firstField = formSchema.fields[0];
                if (firstField?.selector) {
                    const element = document.querySelector(firstField.selector);
                    return element?.closest('div, section, main') || document.body;
                }
                return null;
            }

            return document.getElementById(formSchema.id) ||
                document.querySelector(`form[action="${formSchema.action}"]`) ||
                document.querySelectorAll('form')[parseInt(formSchema.id.replace('form_', ''))];
        }

        createButton(formElement, formSchema) {
            const button = document.createElement('button');
            button.className = 'formflow-voice-btn';
            button.innerHTML = '🎤 Fill with Voice';
            button.type = 'button';

            button.style.cssText = `
        position: fixed;
        bottom: 80px;
        right: 20px;
        z-index: 2147483646;
        padding: 12px 20px;
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        border: none;
        border-radius: 25px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        transition: all 0.3s ease;
      `;

            button.onmouseenter = () => {
                button.style.transform = 'scale(1.05)';
                button.style.boxShadow = '0 6px 20px rgba(16, 185, 129, 0.5)';
            };

            button.onmouseleave = () => {
                button.style.transform = 'scale(1)';
                button.style.boxShadow = '0 4px 15px rgba(16, 185, 129, 0.4)';
            };

            button.onclick = async (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Hide button when overlay opens
                button.style.display = 'none';

                // Start session
                const schemas = this.formDetector.detectedForms;
                const response = await chrome.runtime.sendMessage({
                    type: 'START_SESSION',
                    formSchema: schemas,
                    formUrl: window.location.href
                });

                if (response.success) {
                    this.overlay.show(schemas, response.greeting);
                } else {
                    alert('Failed to start FormFlow session. Is the backend running?');
                    button.style.display = 'block';
                }
            };

            document.body.appendChild(button);
        }
    }

    // =============================================================================
    // Initialize
    // =============================================================================

    const formDetector = new FormDetector();
    const overlay = new VoiceOverlay();
    const buttonInjector = new ButtonInjector(formDetector, overlay);

    // Wait for page to fully load
    if (document.readyState === 'complete') {
        buttonInjector.injectButtons();
    } else {
        window.addEventListener('load', () => {
            buttonInjector.injectButtons();
        });
    }

    // Re-scan on dynamic content changes (for SPAs)
    const observer = new MutationObserver((mutations) => {
        // Debounce
        clearTimeout(window.__formFlowRescanTimeout);
        window.__formFlowRescanTimeout = setTimeout(() => {
            buttonInjector.injectButtons();
        }, 1000);
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log('FormFlow AI content script loaded');

})();
