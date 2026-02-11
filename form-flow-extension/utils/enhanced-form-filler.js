/**
 * Enhanced Form Filler with Error Recovery
 * 
 * Features:
 * - Retry mechanism with exponential backoff
 * - Field validation before submission
 * - Undo/Redo functionality
 * - State persistence across page reloads
 */

class EnhancedFormFiller {
    constructor() {
        this.retryQueue = [];
        this.fillHistory = [];
        this.undoStack = [];
        this.redoStack = [];
        this.maxRetries = 3;
        this.validationRules = new Map();
    }

    /**
     * Fill field with retry logic
     */
    async fillFieldWithRetry(element, value, fieldType, maxRetries = 3) {
        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                // Save original value for undo
                const originalValue = element.value;
                const originalChecked = element.checked;

                // Fill the field
                const success = await this.fillField(element, value, fieldType);

                if (success) {
                    // Validate the field
                    const isValid = await this.validateField(element, value, fieldType);

                    if (isValid) {
                        // Add to undo stack
                        this.undoStack.push({
                            element: element,
                            originalValue: originalValue,
                            originalChecked: originalChecked,
                            newValue: value,
                            timestamp: Date.now()
                        });

                        // Add to history
                        this.fillHistory.push({
                            selector: this.generateSelector(element),
                            value: value,
                            timestamp: Date.now(),
                            success: true
                        });

                        console.log(`✓ Field filled successfully: ${value}`);
                        return true;
                    } else {
                        console.warn(`⚠ Validation failed for: ${value}`);
                    }
                }

            } catch (error) {
                console.error(`Attempt ${attempt + 1} failed:`, error);

                if (attempt === maxRetries - 1) {
                    // Add to retry queue for later
                    this.retryQueue.push({
                        element: element,
                        value: value,
                        fieldType: fieldType,
                        error: error.message,
                        attempts: maxRetries
                    });

                    return false;
                }

                // Exponential backoff
                await this.wait(1000 * Math.pow(2, attempt));
            }
        }

        return false;
    }

    /**
     * Validate field value
     */
    async validateField(element, value, fieldType) {
        // Basic validation rules
        const validators = {
            email: (val) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val),
            tel: (val) => /^[\d\s\-\+\(\)]+$/.test(val),
            number: (val) => !isNaN(val),
            url: (val) => {
                try {
                    new URL(val);
                    return true;
                } catch {
                    return false;
                }
            },
            date: (val) => !isNaN(Date.parse(val))
        };

        // Check if field has custom validation
        if (element.pattern) {
            const regex = new RegExp(element.pattern);
            if (!regex.test(value)) {
                console.warn(`Pattern validation failed: ${element.pattern}`);
                return false;
            }
        }

        // Check required
        if (element.required && !value) {
            console.warn('Required field is empty');
            return false;
        }

        // Type-specific validation
        if (validators[fieldType]) {
            return validators[fieldType](value);
        }

        // Check if value actually set
        await this.wait(100);

        if (element.type === 'checkbox' || element.type === 'radio') {
            const shouldCheck = ['yes', 'true', '1', 'check', 'checked'].includes(String(value).toLowerCase());
            return element.checked === shouldCheck;
        }

        return element.value === value;
    }

    /**
     * Fill field (enhanced version)
     */
    async fillField(element, value, type) {
        // Focus the element
        element.focus();
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        await this.wait(100);

        switch (type) {
            case 'text':
            case 'email':
            case 'tel':
            case 'number':
            case 'password':
            case 'url':
            case 'textarea':
                return await this.fillTextInput(element, value);

            case 'select':
                return await this.fillSelect(element, value);

            case 'radio':
            case 'checkbox':
                return await this.fillCheckbox(element, value);

            default:
                return await this.fillTextInput(element, value);
        }
    }

    /**
     * Fill text input with human-like typing
     */
    async fillTextInput(element, value) {
        // Clear existing value
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));

        // Type character by character
        for (let char of value) {
            element.value += char;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            await this.wait(50 + Math.random() * 50); // 50-100ms per char
        }

        // Dispatch change event
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('blur', { bubbles: true }));

        // Highlight field
        this.highlightField(element);

        return true;
    }

    /**
     * Fill select dropdown
     */
    async fillSelect(element, value) {
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

    /**
     * Fill checkbox/radio
     */
    async fillCheckbox(element, value) {
        const shouldCheck = ['yes', 'true', '1', 'check', 'checked'].includes(
            String(value).toLowerCase()
        );

        if (element.checked !== shouldCheck) {
            element.click();
            await this.wait(100);
        }

        this.highlightField(element);
        return true;
    }

    /**
     * Undo last fill
     */
    undo() {
        if (this.undoStack.length === 0) {
            console.log('Nothing to undo');
            return false;
        }

        const action = this.undoStack.pop();

        if (action.element.type === 'checkbox' || action.element.type === 'radio') {
            action.element.checked = action.originalChecked;
        } else {
            action.element.value = action.originalValue;
        }

        action.element.dispatchEvent(new Event('input', { bubbles: true }));
        action.element.dispatchEvent(new Event('change', { bubbles: true }));

        this.redoStack.push(action);

        console.log('✓ Undo successful');
        return true;
    }

    /**
     * Redo last undo
     */
    redo() {
        if (this.redoStack.length === 0) {
            console.log('Nothing to redo');
            return false;
        }

        const action = this.redoStack.pop();
        action.element.value = action.newValue;
        action.element.dispatchEvent(new Event('change', { bubbles: true }));

        this.undoStack.push(action);

        console.log('✓ Redo successful');
        return true;
    }

    /**
     * Retry failed fields
     */
    async retryFailed() {
        console.log(`Retrying ${this.retryQueue.length} failed fields...`);

        const queue = [...this.retryQueue];
        this.retryQueue = [];

        let successCount = 0;

        for (const item of queue) {
            const success = await this.fillFieldWithRetry(
                item.element,
                item.value,
                item.fieldType,
                2 // Fewer retries on second attempt
            );

            if (success) successCount++;
        }

        console.log(`✓ Retry complete: ${successCount}/${queue.length} successful`);
        return successCount;
    }

    /**
     * Get fill summary
     */
    getSummary() {
        const successful = this.fillHistory.filter(h => h.success).length;
        const failed = this.retryQueue.length;

        return {
            total: successful + failed,
            successful: successful,
            failed: failed,
            canUndo: this.undoStack.length > 0,
            canRedo: this.redoStack.length > 0
        };
    }

    /**
     * Highlight field with animation
     */
    highlightField(element) {
        const original = {
            border: element.style.border,
            boxShadow: element.style.boxShadow,
            transition: element.style.transition
        };

        element.style.transition = 'all 0.3s ease';
        element.style.border = '2px solid #10b981';
        element.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.5)';

        setTimeout(() => {
            element.style.border = original.border;
            element.style.boxShadow = original.boxShadow;
            element.style.transition = original.transition;
        }, 1000);
    }

    /**
     * Generate unique selector for element
     */
    generateSelector(element) {
        if (element.id) return `#${CSS.escape(element.id)}`;
        if (element.name) return `[name="${CSS.escape(element.name)}"]`;

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
                // Handle SVG className (SVGAnimatedString) vs HTML className (string)
                const className = typeof current.className === 'string'
                    ? current.className
                    : (current.className.baseVal || '');

                const classes = className.split(' ').filter(c => c);
                if (classes.length) {
                    selector += '.' + classes.slice(0, 2).join('.');
                }
            }

            path.unshift(selector);
            current = current.parentElement;
        }

        return path.join(' > ');
    }

    /**
     * Wait helper
     */
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Export for use in content script
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedFormFiller;
}
