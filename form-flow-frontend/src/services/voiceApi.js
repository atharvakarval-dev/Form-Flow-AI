/**
 * Advanced Voice AI API Service
 * 
 * Complete API integration for all voice features:
 * - Advanced refinement with confidence
 * - Entity extraction
 * - Validation with auto-correct
 * - Date parsing
 * - Voice commands
 * - Autocomplete
 * - Smart autofill
 * - Analytics tracking
 * - Multilingual processing
 * - Batch processing
 */

import api from './api';

// =============================================================================
// CORE VOICE PROCESSING
// =============================================================================

/**
 * Advanced text refinement with confidence scoring
 */
export const advancedRefine = async (text, question = '', fieldType = '', qaHistory = [], formContext = {}) => {
    try {
        const response = await api.post('/voice/refine', {
            text,
            question,
            field_type: fieldType,
            qa_history: qaHistory,
            form_context: formContext
        });
        return response.data;
    } catch (error) {
        console.warn('[advancedRefine] Failed:', error.message);
        return {
            success: false,
            refined: text,
            original: text,
            confidence: 0,
            needs_clarification: true
        };
    }
};

/**
 * Extract multiple entities from single utterance
 */
export const extractEntities = async (text, expectedFields = null) => {
    try {
        const response = await api.post('/voice/extract', {
            text,
            expected_fields: expectedFields
        });
        return response.data;
    } catch (error) {
        console.warn('[extractEntities] Failed:', error.message);
        return { success: false, entities: {}, confidence_scores: {} };
    }
};

/**
 * AI-powered field validation
 */
export const validateField = async (value, fieldType, context = {}) => {
    try {
        const response = await api.post('/voice/validate', {
            value,
            field_type: fieldType,
            context
        });
        return response.data;
    } catch (error) {
        console.warn('[validateField] Failed:', error.message);
        return {
            is_valid: false,
            issues: ['Validation service unavailable'],
            suggestions: []
        };
    }
};

/**
 * Parse semantic dates
 */
export const parseDate = async (text) => {
    try {
        const response = await api.post('/voice/parse-date', {
            text,
            current_date: new Date().toISOString().split('T')[0]
        });
        return response.data;
    } catch (error) {
        console.warn('[parseDate] Failed:', error.message);
        return { success: false, parsed_date: null, needs_clarification: true };
    }
};

/**
 * Process voice navigation commands
 */
export const processVoiceCommand = async (command, currentField, formState = {}) => {
    try {
        const response = await api.post('/voice/command', {
            command,
            current_field: currentField,
            form_state: formState
        });
        return response.data;
    } catch (error) {
        console.warn('[processVoiceCommand] Failed:', error.message);
        return { success: false, action: 'unknown' };
    }
};

/**
 * Smart autocomplete suggestions
 */
export const getAutocomplete = async (partialText, fieldType, context = {}) => {
    try {
        const response = await api.post('/voice/autocomplete', {
            partial_text: partialText,
            field_type: fieldType,
            context
        });
        return response.data;
    } catch (error) {
        console.warn('[getAutocomplete] Failed:', error.message);
        return { suggestions: [] };
    }
};

/**
 * Batch process entire utterance
 */
export const batchProcess = async (text) => {
    try {
        const response = await api.post('/voice/batch', { text });
        return response.data;
    } catch (error) {
        console.warn('[batchProcess] Failed:', error.message);
        return { success: false, entities: {} };
    }
};

// =============================================================================
// SMART AUTOFILL
// =============================================================================

/**
 * Get autofill suggestions from user history
 */
export const getAutofillSuggestions = async (userId, fieldName, fieldType = 'text', currentValue = '') => {
    try {
        const response = await api.post('/voice/autofill/suggestions', {
            user_id: userId,
            field_name: fieldName,
            field_type: fieldType,
            current_value: currentValue
        });
        return response.data;
    } catch (error) {
        console.warn('[getAutofillSuggestions] Failed:', error.message);
        return { success: false, suggestions: [] };
    }
};

/**
 * Learn from successful form submission
 */
export const learnFromSubmission = async (userId, formData, formId = null) => {
    try {
        const response = await api.post('/voice/autofill/learn', {
            user_id: userId,
            form_data: formData,
            form_id: formId
        });
        return response.data;
    } catch (error) {
        console.warn('[learnFromSubmission] Failed:', error.message);
        return { success: false };
    }
};

// =============================================================================
// ANALYTICS
// =============================================================================

/**
 * Track form analytics event
 */
export const trackAnalyticsEvent = async (type, formId, sessionId, fieldId = null, metadata = {}) => {
    try {
        await api.post('/voice/analytics/track', {
            type,
            form_id: formId,
            session_id: sessionId,
            field_id: fieldId,
            metadata
        });
    } catch (error) {
        // Silent fail - analytics shouldn't break the app
        console.debug('[analytics] Event tracking failed:', error.message);
    }
};

/**
 * Get form insights
 */
export const getFormInsights = async (formId, days = 30) => {
    try {
        const response = await api.get(`/voice/analytics/insights/${formId}?days=${days}`);
        return response.data;
    } catch (error) {
        console.warn('[getFormInsights] Failed:', error.message);
        return { success: false };
    }
};

// =============================================================================
// MULTILINGUAL
// =============================================================================

/**
 * Process multilingual voice input
 */
export const processMultilingual = async (text, targetLanguage = 'auto', fieldType = '') => {
    try {
        const response = await api.post('/voice/multilingual/process', {
            text,
            target_language: targetLanguage,
            field_type: fieldType
        });
        return response.data;
    } catch (error) {
        console.warn('[processMultilingual] Failed:', error.message);
        return {
            success: false,
            detected_language: 'en-US',
            processed: text,
            was_translated: false
        };
    }
};

/**
 * Detect input language
 */
export const detectLanguage = async (text) => {
    try {
        const response = await api.post('/voice/multilingual/detect', { text });
        return response.data;
    } catch (error) {
        console.warn('[detectLanguage] Failed:', error.message);
        return { success: false, language: 'en-US' };
    }
};

// =============================================================================
// COMBINED PIPELINE
// =============================================================================

/**
 * Full voice processing pipeline
 * 
 * Combines all features for seamless processing:
 * 1. Multilingual detection & translation
 * 2. Command detection
 * 3. Entity extraction (if multi-field)
 * 4. Refinement with context
 * 5. Validation with auto-correct
 * 6. Analytics tracking
 */
export const processVoiceInput = async ({
    text,
    fieldName,
    fieldType,
    question = '',
    formContext = {},
    qaHistory = [],
    userId = null,
    formId = null,
    sessionId = null
}) => {
    const startTime = Date.now();

    try {
        // 1. Check for voice commands first
        const commandResult = await processVoiceCommand(text, fieldName, formContext);
        if (commandResult.success && commandResult.action !== 'unknown') {
            return {
                type: 'command',
                action: commandResult.action,
                params: commandResult.params,
                message: commandResult.message
            };
        }

        // 2. Multilingual processing
        const multiResult = await processMultilingual(text, 'auto', fieldType);
        const processedText = multiResult.processed || text;

        // 3. Check if this looks like multi-field input
        const isMultiField = /(?:and|,)\s+(?:my|the)?\s*(?:email|phone|name|address)/i.test(processedText);

        if (isMultiField) {
            // Extract multiple entities
            const extraction = await batchProcess(processedText);
            if (extraction.success && extraction.fields_extracted > 1) {
                // Track analytics
                if (sessionId) {
                    trackAnalyticsEvent('batch_extraction', formId, sessionId, null, {
                        fields_extracted: extraction.fields_extracted
                    });
                }

                return {
                    type: 'batch',
                    entities: extraction.entities,
                    validation_results: extraction.validation_results,
                    confidence_scores: extraction.confidence_scores
                };
            }
        }

        // 4. Single field refinement
        const refineResult = await advancedRefine(
            processedText,
            question,
            fieldType,
            qaHistory,
            formContext
        );

        // 5. Validate the refined value
        let validationResult = null;
        if (refineResult.refined && fieldType) {
            validationResult = await validateField(refineResult.refined, fieldType, formContext);
        }

        // 6. Track analytics
        if (sessionId) {
            trackAnalyticsEvent('voice_input', formId, sessionId, fieldName, {
                duration: Date.now() - startTime,
                confidence: refineResult.confidence,
                was_translated: multiResult.was_translated,
                had_issues: (validationResult?.issues?.length || 0) > 0
            });
        }

        // 7. Build final result
        const finalValue = validationResult?.auto_corrected || refineResult.refined;

        return {
            type: 'single',
            value: finalValue,
            original: text,
            confidence: refineResult.confidence,
            needs_clarification: refineResult.needs_clarification,
            clarification_question: refineResult.clarification_question,
            suggestions: refineResult.suggestions || validationResult?.suggestions,
            issues: [...(refineResult.detected_issues || []), ...(validationResult?.issues || [])],
            was_translated: multiResult.was_translated,
            detected_language: multiResult.detected_language,
            was_auto_corrected: !!validationResult?.auto_corrected
        };

    } catch (error) {
        console.error('[processVoiceInput] Pipeline error:', error);
        return {
            type: 'error',
            value: text,
            error: error.message
        };
    }
};

export default {
    advancedRefine,
    extractEntities,
    validateField,
    parseDate,
    processVoiceCommand,
    getAutocomplete,
    batchProcess,
    getAutofillSuggestions,
    learnFromSubmission,
    trackAnalyticsEvent,
    getFormInsights,
    processMultilingual,
    detectLanguage,
    processVoiceInput
};
