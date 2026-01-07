/**
 * API Service Layer
 * Centralized axios instance and API calls
 */
import axios from 'axios';

// Base API configuration - uses environment variable with fallback
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with default config (no global timeout)
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    // No global timeout - form operations can take minutes
});

// Request interceptor to add auth token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        // Handle common errors
        if (error.response?.status === 401) {
            // Token expired - clear and redirect
            localStorage.removeItem('token');
            window.location.href = '/login';
        }

        // Log errors in development
        if (import.meta.env.DEV) {
            console.error('API Error:', error.response?.data || error.message);
        }

        return Promise.reject(error);
    }
);

/**
 * Scrape and parse a form URL (no timeout - can take time)
 */
export const scrapeForm = async (url) => {
    const response = await api.post('/scrape', { url });
    return response.data;
};

// ============ PDF/Document APIs ============

/**
 * Upload and parse a PDF form
 * @param {File} file - PDF file to upload
 * @returns {Promise<{success, pdf_id, file_name, total_pages, total_fields, fields}>}
 */
export const uploadPdf = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/pdf/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

/**
 * Upload and parse a Word document (.docx)
 * @param {File} file - Word document to upload
 * @returns {Promise<{success, docx_id, file_name, total_fields, fields}>}
 */
export const uploadDocx = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/docx/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

/**
 * Get AI subsystem health status
 * @returns {Promise<{mode, dependencies}>} - AI mode and dependency status  
 */
export const getAIHealth = async () => {
    try {
        const response = await api.get('/health/ai');
        return response.data;
    } catch (error) {
        return { mode: 'unknown', error: error.message };
    }
};

/**
 * Get CAPTCHA solver configuration status
 * @returns {Promise<{auto_solve, provider, mode}>}
 */
export const getCaptchaHealth = async () => {
    try {
        const response = await api.get('/health/captcha');
        return response.data;
    } catch (error) {
        return { auto_solve: false, mode: 'unknown', error: error.message };
    }
};

/**
 * Get parsed schema from an uploaded PDF
 * @param {string} pdfId - PDF ID from upload response
 * @returns {Promise<{pdf_id, file_name, fields, source}>}
 */
export const getPdfSchema = async (pdfId) => {
    const response = await api.get(`/pdf/schema/${pdfId}`);
    return response.data;
};

/**
 * Preview how data would be filled into PDF fields
 * @param {string} pdfId - PDF ID
 * @param {Object} data - Field name to value mapping
 * @returns {Promise<{success, preview}>}
 */
export const previewPdfFill = async (pdfId, data) => {
    const response = await api.post('/pdf/preview', {
        pdf_id: pdfId,
        data,
    });
    return response.data;
};

/**
 * Fill a PDF form with collected data
 * @param {string} pdfId - PDF ID
 * @param {Object} data - Field name to value mapping
 * @param {boolean} flatten - Make form fields non-editable
 * @returns {Promise<{success, download_id, fields_filled}>}
 */
export const fillPdf = async (pdfId, data, flatten = false) => {
    const response = await api.post('/pdf/fill', {
        pdf_id: pdfId,
        data,
        flatten,
    });
    return response.data;
};

/**
 * Get download URL for a filled PDF
 * @param {string} downloadId - Download ID from fill response
 * @returns {string} Full download URL
 */
export const getPdfDownloadUrl = (downloadId) => {
    return `${API_BASE_URL}/pdf/download/${downloadId}`;
};

/**
 * Parse Word document (converts to form fields)
 * Note: Word support requires additional backend processing
 * @param {File} file - Word document (.docx)
 * @returns {Promise<{success, fields}>}
 */
export const uploadWordDocument = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    // For now, Word documents use a generic document endpoint
    // This could be expanded with docx parsing
    const response = await api.post('/pdf/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

/**
 * Submit form data to the original website (no timeout - can take minutes)
 */
export const submitForm = async (url, formData, formSchema) => {
    const response = await api.post('/submit-form', {
        url,
        form_data: formData,
        form_schema: formSchema,
    });
    return response.data;
};

// ============ Auth APIs ============

/**
 * User login
 */
export const login = async (email, password) => {
    const form = new FormData();
    form.append('username', email);
    form.append('password', password);

    const response = await axios.post(`${API_BASE_URL}/login`, form);
    return response.data;
};

/**
 * User registration
 */
export const register = async (userData) => {
    const response = await api.post('/register', userData);
    return response.data;
};

// ============ Dashboard APIs ============

/**
 * Get user's form submission history
 */
export const getSubmissionHistory = async () => {
    const response = await api.get('/submissions/history');
    return response.data;
};

/**
 * Get dashboard analytics with charts and AI insights
 */
export const getAnalytics = async () => {
    const response = await api.get('/analytics/dashboard');
    return response.data;
};

// ============ Voice APIs ============

/**
 * Process voice input with AI
 */
export const processVoiceInput = async (payload) => {
    const response = await api.post('/process-voice', payload);
    return response.data;
};

/**
 * Get user profile data
 */
export const getUserProfile = async () => {
    const response = await api.get('/user/profile');
    return response.data;
};


// ============ Advanced Voice AI Features ============

/**
 * Advanced text refinement with confidence scoring and clarification
 * 
 * Features:
 * - Confidence scoring (0-100%)
 * - Clarification requests when uncertain
 * - Multiple suggestions
 * - Issue detection
 * 
 * @param {string} text - Raw transcript from speech recognition
 * @param {string} question - The question/field label being answered
 * @param {string} fieldType - Type hint: email, phone, name, date, address, text
 * @param {Array<{question: string, answer: string}>} qaHistory - Previous Q&A for context
 * @param {Object} formContext - Already filled form fields
 * @returns {Promise<{success, refined, confidence, needs_clarification, suggestions, detected_issues}>}
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
            needs_clarification: true,
            clarification_question: 'Could not process input, please try again.'
        };
    }
};

/**
 * Extract multiple entities from a single utterance
 * 
 * Example: "My name is John, email john@gmail.com, phone 555-1234"
 * Returns: { name: "John", email: "john@gmail.com", phone: "555-1234" }
 * 
 * @param {string} text - Full spoken utterance
 * @param {string[]} expectedFields - Optional list of fields to look for
 * @returns {Promise<{entities, confidence_scores, sensitive_data_detected}>}
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
 * Validate field value with AI-powered error detection
 * 
 * Catches:
 * - Common typos (.con → .com)
 * - Format errors (missing @)
 * - Cross-field inconsistencies
 * 
 * @param {string} value - Field value to validate
 * @param {string} fieldType - Type: email, phone, date, name
 * @param {Object} context - Form context for cross-validation
 * @returns {Promise<{is_valid, issues, suggestions, auto_corrected}>}
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
        return { is_valid: true, issues: [], suggestions: [] };
    }
};

/**
 * Parse semantic/relative dates to ISO format
 * 
 * Examples:
 * - "next Tuesday" → "2025-12-30"
 * - "in 2 weeks" → "2026-01-05"
 * - "tomorrow" → next day
 * 
 * @param {string} text - Natural language date
 * @returns {Promise<{parsed_date, needs_clarification, clarification, confidence}>}
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
 * 
 * Supported commands:
 * - "go back" / "previous" → previous_field
 * - "skip" / "next" → next_field
 * - "clear" / "reset" → clear_form
 * - "repeat" → repeat_question
 * 
 * @param {string} command - Voice command text
 * @param {string} currentField - Current field name
 * @param {Object} formState - Current form state
 * @returns {Promise<{action, params, message}>}
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
 * Get smart autocomplete suggestions
 * 
 * @param {string} partialText - Partial input
 * @param {string} fieldType - Field type
 * @param {Object} context - Form context (name for email suggestions, etc.)
 * @returns {Promise<{suggestions, based_on}>}
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
 * Batch process entire utterance - extract, validate, and fill multiple fields
 * 
 * This is the "speak once, fill many" feature.
 * 
 * @param {string} text - Full spoken utterance
 * @returns {Promise<{entities, validation_results, fields_extracted}>}
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

/**
 * Legacy refineText - now calls advancedRefine internally
 * Kept for backward compatibility
 */
export const refineText = async (text, question = '', fieldType = '', previousQA = []) => {
    const result = await advancedRefine(text, question, fieldType, previousQA);
    return result;
};

// ============ Conversation Agent APIs ============

/**
 * Start a new conversation session
 */
export const startConversationSession = async (formSchema, formUrl, initialData = {}, clientType = 'web') => {
    const response = await api.post('/conversation/session', {
        form_schema: formSchema,
        form_url: formUrl,
        initial_data: initialData,
        client_type: clientType
    });
    return response.data;
};

/**
 * Send a message to the conversation agent
 */
export const sendConversationMessage = async (sessionId, message) => {
    const response = await api.post('/conversation/message', {
        session_id: sessionId,
        message: message
    });
    return response.data;
};

/**
 * Confirm a low-confidence value
 */
export const confirmConversationValue = async (sessionId, fieldName, confirmedValue) => {
    const response = await api.post('/conversation/confirm', {
        session_id: sessionId,
        field_name: fieldName,
        confirmed_value: confirmedValue
    });
    return response.data;
};

// ============ Suggestion APIs ============

/**
 * Get real-time suggestions for a form field
 * 
 * @param {string} fieldName - Field name
 * @param {string} fieldLabel - Field label (optional)
 * @param {string} fieldType - Field type (optional)
 * @param {string} currentValue - Partial value for autocomplete (optional)
 * @param {number} nResults - Max suggestions to return
 * @returns {Promise<{suggestions: string[], field_name: string}>}
 */
export const getSuggestions = async (
    fieldName,
    fieldLabel = null,
    fieldType = 'text',
    currentValue = null,
    nResults = 5
) => {
    try {
        const response = await api.post('/suggestions', {
            field_name: fieldName,
            field_label: fieldLabel,
            field_type: fieldType,
            current_value: currentValue,
            n_results: nResults
        });
        return response.data;
    } catch (error) {
        console.warn('[getSuggestions] Failed:', error.message);
        return { suggestions: [], field_name: fieldName };
    }
};

/**
 * Get intelligent profile-based suggestions for a form field
 * 
 * This is the ChatGPT/Claude-level suggestion system that uses 
 * behavioral profiles to generate personalized suggestions.
 * 
 * Features:
 * - Tier 1 (Profile-Based): Uses full behavioral profile with LLM
 * - Tier 2 (Blended): Combines patterns with light profile context
 * - Tier 3 (Pattern-Only): Fast fallback for new users
 * 
 * @param {string} fieldName - Field name
 * @param {string} fieldLabel - Field label (optional)
 * @param {string} fieldType - Field type (optional)
 * @param {string} formPurpose - Purpose of the form (optional)
 * @param {Object} previousAnswers - Already answered fields in this form (optional)
 * @returns {Promise<{suggestions: Array, tier_used: string, profile_confidence: number}>}
 */
export const getSmartSuggestions = async (
    fieldName,
    fieldLabel = null,
    fieldType = 'text',
    formPurpose = 'General',
    previousAnswers = {}
) => {
    try {
        const response = await api.post('/smart-suggestions', {
            field_name: fieldName,
            field_label: fieldLabel,
            field_type: fieldType,
            form_purpose: formPurpose,
            previous_answers: previousAnswers
        });
        return response.data;
    } catch (error) {
        console.warn('[getSmartSuggestions] Failed:', error.message);
        return {
            suggestions: [],
            field_name: fieldName,
            tier_used: 'error',
            profile_confidence: null
        };
    }
};

export default api;


