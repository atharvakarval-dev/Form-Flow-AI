/**
 * State Persistence Manager
 * 
 * Manages session state across page reloads and navigation
 * Stores conversation history, filled fields, and user preferences
 */

class StateManager {
    constructor() {
        this.sessionId = null;
        this.state = {
            conversationHistory: [],
            filledFields: new Map(),
            extractedValues: {},
            undoStack: [],
            redoStack: [],
            formSchema: null,
            formUrl: null,
            createdAt: null,
            lastActivity: null
        };
        
        this.storageKey = 'formflow_session_state';
        this.ttl = 3600000; // 1 hour
    }

    /**
     * Initialize and restore state if available
     */
    async init() {
        this.sessionId = this.generateSessionId();
        await this.restoreState();
        
        // Auto-save on changes
        this.startAutoSave();
        
        // Clean up old sessions
        this.cleanupOldSessions();
        
        console.log('StateManager initialized:', this.sessionId);
    }

    /**
     * Save current state to storage
     */
    async persistState() {
        try {
            const stateData = {
                sessionId: this.sessionId,
                state: {
                    ...this.state,
                    filledFields: Array.from(this.state.filledFields.entries()),
                    lastActivity: Date.now()
                },
                timestamp: Date.now()
            };
            
            await chrome.storage.local.set({
                [this.storageKey]: JSON.stringify(stateData)
            });
            
            console.log('✓ State persisted');
            return true;
        } catch (error) {
            console.error('Failed to persist state:', error);
            return false;
        }
    }

    /**
     * Restore state from storage
     */
    async restoreState() {
        try {
            const result = await chrome.storage.local.get(this.storageKey);
            
            if (result[this.storageKey]) {
                const stateData = JSON.parse(result[this.storageKey]);
                
                // Check if state is still valid (not expired)
                const age = Date.now() - stateData.timestamp;
                if (age < this.ttl) {
                    this.sessionId = stateData.sessionId;
                    this.state = {
                        ...stateData.state,
                        filledFields: new Map(stateData.state.filledFields)
                    };
                    
                    console.log('✓ State restored from storage');
                    return true;
                } else {
                    console.log('Stored state expired, starting fresh');
                    await this.clearState();
                }
            }
            
            return false;
        } catch (error) {
            console.error('Failed to restore state:', error);
            return false;
        }
    }

    /**
     * Update conversation history
     */
    addToConversation(message, type = 'user') {
        this.state.conversationHistory.push({
            message: message,
            type: type,
            timestamp: Date.now()
        });
        
        // Keep only last 50 messages
        if (this.state.conversationHistory.length > 50) {
            this.state.conversationHistory = this.state.conversationHistory.slice(-50);
        }
        
        this.persistState();
    }

    /**
     * Update filled fields
     */
    updateFilledField(fieldName, value, selector) {
        this.state.filledFields.set(fieldName, {
            value: value,
            selector: selector,
            timestamp: Date.now()
        });
        
        this.persistState();
    }

    /**
     * Update extracted values
     */
    updateExtractedValues(values) {
        this.state.extractedValues = {
            ...this.state.extractedValues,
            ...values
        };
        
        this.persistState();
    }

    /**
     * Add undo action
     */
    addUndoAction(action) {
        this.state.undoStack.push({
            ...action,
            timestamp: Date.now()
        });
        
        // Clear redo stack when new action is added
        this.state.redoStack = [];
        
        // Keep only last 20 actions
        if (this.state.undoStack.length > 20) {
            this.state.undoStack = this.state.undoStack.slice(-20);
        }
        
        this.persistState();
    }

    /**
     * Undo last action
     */
    undo() {
        if (this.state.undoStack.length === 0) {
            return null;
        }
        
        const action = this.state.undoStack.pop();
        this.state.redoStack.push(action);
        
        this.persistState();
        return action;
    }

    /**
     * Redo last undone action
     */
    redo() {
        if (this.state.redoStack.length === 0) {
            return null;
        }
        
        const action = this.state.redoStack.pop();
        this.state.undoStack.push(action);
        
        this.persistState();
        return action;
    }

    /**
     * Set form schema
     */
    setFormSchema(schema, url) {
        this.state.formSchema = schema;
        this.state.formUrl = url;
        this.state.createdAt = Date.now();
        
        this.persistState();
    }

    /**
     * Get current state
     */
    getState() {
        return {
            ...this.state,
            sessionId: this.sessionId,
            age: Date.now() - (this.state.createdAt || Date.now())
        };
    }

    /**
     * Clear current state
     */
    async clearState() {
        this.state = {
            conversationHistory: [],
            filledFields: new Map(),
            extractedValues: {},
            undoStack: [],
            redoStack: [],
            formSchema: null,
            formUrl: null,
            createdAt: null,
            lastActivity: null
        };
        
        await chrome.storage.local.remove(this.storageKey);
        console.log('✓ State cleared');
    }

    /**
     * Export state for debugging
     */
    exportState() {
        return JSON.stringify({
            sessionId: this.sessionId,
            state: {
                ...this.state,
                filledFields: Array.from(this.state.filledFields.entries())
            }
        }, null, 2);
    }

    /**
     * Import state from JSON
     */
    importState(jsonString) {
        try {
            const data = JSON.parse(jsonString);
            this.sessionId = data.sessionId;
            this.state = {
                ...data.state,
                filledFields: new Map(data.state.filledFields)
            };
            
            this.persistState();
            console.log('✓ State imported');
            return true;
        } catch (error) {
            console.error('Failed to import state:', error);
            return false;
        }
    }

    /**
     * Start auto-save interval
     */
    startAutoSave() {
        // Save every 30 seconds if there's activity
        setInterval(() => {
            if (this.state.lastActivity) {
                const timeSinceActivity = Date.now() - this.state.lastActivity;
                if (timeSinceActivity < 60000) { // Active in last minute
                    this.persistState();
                }
            }
        }, 30000);
    }

    /**
     * Clean up old sessions from storage
     */
    async cleanupOldSessions() {
        try {
            const result = await chrome.storage.local.get(null);
            const now = Date.now();
            
            for (const [key, value] of Object.entries(result)) {
                if (key.startsWith('formflow_session_')) {
                    try {
                        const data = JSON.parse(value);
                        const age = now - data.timestamp;
                        
                        if (age > this.ttl) {
                            await chrome.storage.local.remove(key);
                            console.log(`Cleaned up old session: ${key}`);
                        }
                    } catch (e) {
                        // Invalid data, remove it
                        await chrome.storage.local.remove(key);
                    }
                }
            }
        } catch (error) {
            console.error('Cleanup failed:', error);
        }
    }

    /**
     * Generate unique session ID
     */
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Check if session is valid
     */
    isValid() {
        if (!this.state.createdAt) return false;
        
        const age = Date.now() - this.state.createdAt;
        return age < this.ttl;
    }

    /**
     * Refresh session (extend TTL)
     */
    refresh() {
        this.state.lastActivity = Date.now();
        this.persistState();
    }
}

// Export for use in content script
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StateManager;
}
