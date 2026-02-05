/**
 * Plugin API Service
 * Handles all plugin-related API calls with error handling and request cancellation
 */
import api from './api';

/**
 * Plugin API endpoints
 */
export const pluginApi = {
    /**
     * List plugins with pagination and search
     * @param {Object} params - { page, limit, search, is_active }
     * @param {AbortSignal} signal - For request cancellation
     */
    list: async (params = {}, signal) => {
        const { page = 1, limit = 10, search = '', is_active } = params;
        const queryParams = new URLSearchParams({
            skip: ((page - 1) * limit).toString(),
            limit: limit.toString(),
        });
        if (search) queryParams.append('search', search);
        if (is_active !== undefined) queryParams.append('is_active', is_active);

        const response = await api.get(`/plugins?${queryParams}`, { signal });
        return response.data;
    },

    /**
     * Get single plugin by ID
     * @param {string|number} pluginId
     * @param {AbortSignal} signal
     */
    get: async (pluginId, signal) => {
        const response = await api.get(`/plugins/${pluginId}`, { signal });
        return response.data;
    },

    /**
     * Create new plugin
     * @param {Object} data - Plugin creation data
     */
    create: async (data) => {
        const response = await api.post('/plugins', data);
        return response.data;
    },

    /**
     * Update plugin
     * @param {string|number} pluginId
     * @param {Object} data - Update payload
     */
    update: async (pluginId, data) => {
        const response = await api.put(`/plugins/${pluginId}`, data);
        return response.data;
    },

    /**
     * Delete plugin
     * @param {string|number} pluginId
     */
    delete: async (pluginId) => {
        const response = await api.delete(`/plugins/${pluginId}`);
        return response.data;
    },

    /**
     * Test database connection
     * @param {string|number} pluginId
     */
    testConnection: async (pluginId) => {
        const response = await api.post(`/plugins/${pluginId}/test-connection`);
        return response.data;
    },

    // ============ API Key Management ============

    apiKeys: {
        /**
         * List API keys for a plugin
         */
        list: async (pluginId, signal) => {
            const response = await api.get(`/plugins/${pluginId}/api-keys`, { signal });
            return response.data;
        },

        /**
         * Create new API key
         * @param {string|number} pluginId
         * @param {Object} data - { name, expires_at }
         */
        create: async (pluginId, data) => {
            const response = await api.post(`/plugins/${pluginId}/api-keys`, data);
            return response.data;
        },

        /**
         * Revoke (delete) API key
         */
        revoke: async (pluginId, keyId) => {
            const response = await api.delete(`/plugins/${pluginId}/api-keys/${keyId}`);
            return response.data;
        },

        /**
         * Rotate API key (revoke old, create new)
         */
        rotate: async (pluginId, keyId) => {
            const response = await api.post(`/plugins/${pluginId}/api-keys/${keyId}/rotate`);
            return response.data;
        },
    },

    // ============ Session Management ============

    sessions: {
        /**
         * List sessions for a plugin
         */
        list: async (pluginId, params = {}, signal) => {
            const { page = 1, limit = 20 } = params;
            const queryParams = new URLSearchParams({
                skip: ((page - 1) * limit).toString(),
                limit: limit.toString(),
            });
            const response = await api.get(`/plugins/${pluginId}/sessions?${queryParams}`, { signal });
            return response.data;
        },

        /**
         * Get session details
         */
        get: async (sessionId, signal) => {
            const response = await api.get(`/plugins/sessions/${sessionId}`, { signal });
            return response.data;
        },
    },

    // ============ Analytics ============

    analytics: {
        /**
         * Get plugin analytics
         */
        get: async (pluginId, params = {}, signal) => {
            const { days = 30 } = params;
            const response = await api.get(`/plugins/${pluginId}/analytics?days=${days}`, { signal });
            return response.data;
        },
    },
};

export default pluginApi;
