/**
 * Flow Engine API Service
 * 
 * Integrates with the backend WhisperFlow /voice/flow endpoint.
 * Handles voice processing with:
 * - Self-correction detection
 * - Snippet expansion
 * - Smart formatting
 * - Action detection (Calendar, Jira, Slack, Email)
 */

import api from './api';

// =============================================================================
// FLOW ENGINE
// =============================================================================

/**
 * Process voice input through the Flow Engine
 * 
 * @param {string} audioText - Raw voice transcription
 * @param {Object} appContext - Current app context (e.g., { view: 'DealPipeline' })
 * @param {string[]} vocabulary - Additional technical terms to recognize
 * @returns {Promise<FlowEngineResult>}
 */
export const processFlow = async (audioText, appContext = null, vocabulary = null) => {
    try {
        const response = await api.post('/voice/flow', {
            audio_text: audioText,
            app_context: appContext,
            vocabulary: vocabulary
        });
        return {
            success: true,
            ...response.data
        };
    } catch (error) {
        console.warn('[processFlow] Failed:', error.message);
        return {
            success: false,
            display_text: audioText,
            intent: 'typing',
            detected_apps: [],
            actions: [],
            corrections_applied: [],
            snippets_expanded: [],
            confidence: 0,
            error: error.message
        };
    }
};

// =============================================================================
// SNIPPETS CRUD
// =============================================================================

/**
 * Get all user snippets
 * @param {boolean} activeOnly - Only return active snippets
 */
export const getSnippets = async (activeOnly = false) => {
    try {
        const response = await api.get('/snippets', {
            params: { active_only: activeOnly }
        });
        return { success: true, snippets: response.data };
    } catch (error) {
        console.warn('[getSnippets] Failed:', error.message);
        return { success: false, snippets: [], error: error.message };
    }
};

/**
 * Create a new snippet
 * @param {string} triggerPhrase - Phrase that triggers expansion
 * @param {string} expansionValue - Text to expand to
 * @param {boolean} isActive - Whether snippet is active
 */
export const createSnippet = async (triggerPhrase, expansionValue, isActive = true) => {
    try {
        const response = await api.post('/snippets', {
            trigger_phrase: triggerPhrase,
            expansion_value: expansionValue,
            is_active: isActive
        });
        return { success: true, snippet: response.data };
    } catch (error) {
        console.warn('[createSnippet] Failed:', error.message);
        return { success: false, error: error.message };
    }
};

/**
 * Update an existing snippet
 * @param {number} snippetId - Snippet ID
 * @param {Object} updates - Fields to update
 */
export const updateSnippet = async (snippetId, updates) => {
    try {
        const response = await api.put(`/snippets/${snippetId}`, {
            trigger_phrase: updates.triggerPhrase,
            expansion_value: updates.expansionValue,
            is_active: updates.isActive
        });
        return { success: true, snippet: response.data };
    } catch (error) {
        console.warn('[updateSnippet] Failed:', error.message);
        return { success: false, error: error.message };
    }
};

/**
 * Delete a snippet
 * @param {number} snippetId - Snippet ID
 */
export const deleteSnippet = async (snippetId) => {
    try {
        await api.delete(`/snippets/${snippetId}`);
        return { success: true };
    } catch (error) {
        console.warn('[deleteSnippet] Failed:', error.message);
        return { success: false, error: error.message };
    }
};

export default {
    processFlow,
    getSnippets,
    createSnippet,
    updateSnippet,
    deleteSnippet
};
