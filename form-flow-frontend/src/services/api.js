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

// ============ Form APIs ============

/**
 * Scrape and parse a form URL (no timeout - can take time)
 */
export const scrapeForm = async (url) => {
    const response = await api.post('/scrape', { url });
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

export default api;
