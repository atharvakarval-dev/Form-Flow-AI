/**
 * Plugin React Query Hooks
 * Server state management with caching, mutations, and optimistic updates
 */
import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import pluginApi from '@/services/pluginApi';
import toast from 'react-hot-toast';

// ============ Plugin Queries ============

/**
 * Fetch all plugins with pagination
 * @param {Object} params - { page, limit, search, is_active }
 */
export const usePlugins = (params = {}) => {
    return useQuery({
        queryKey: queryKeys.plugins.list(params),
        queryFn: ({ signal }) => pluginApi.list(params, signal),
        staleTime: 30000,
        select: (data) => ({
            plugins: data.plugins || data,
            total: data.total || data.length,
            page: params.page || 1,
        }),
    });
};

/**
 * Fetch single plugin by ID
 * @param {string|number} pluginId
 * @param {Object} options - Additional query options
 */
export const usePlugin = (pluginId, options = {}) => {
    return useQuery({
        queryKey: queryKeys.plugins.detail(pluginId),
        queryFn: ({ signal }) => pluginApi.get(pluginId, signal),
        enabled: !!pluginId,
        staleTime: 60000,
        ...options,
    });
};

/**
 * Prefetch plugin detail (for hover/link preloading)
 */
export const usePrefetchPlugin = () => {
    const queryClient = useQueryClient();
    return (pluginId) => {
        queryClient.prefetchQuery({
            queryKey: queryKeys.plugins.detail(pluginId),
            queryFn: ({ signal }) => pluginApi.get(pluginId, signal),
            staleTime: 60000,
        });
    };
};

// ============ Plugin Mutations ============

/**
 * Create new plugin with cache invalidation
 */
export const useCreatePlugin = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data) => pluginApi.create(data),
        onSuccess: (newPlugin) => {
            // Invalidate plugin list to refetch
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.all });
            toast.success(`Plugin "${newPlugin.name}" created successfully!`);
        },
        onError: (error) => {
            toast.error(error.response?.data?.detail || 'Failed to create plugin');
        },
    });
};

/**
 * Update plugin with optimistic update
 */
export const useUpdatePlugin = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pluginId, data }) => pluginApi.update(pluginId, data),
        onMutate: async ({ pluginId, data }) => {
            // Cancel outgoing refetches
            await queryClient.cancelQueries({ queryKey: queryKeys.plugins.detail(pluginId) });

            // Snapshot previous value
            const previousPlugin = queryClient.getQueryData(queryKeys.plugins.detail(pluginId));

            // Optimistically update
            if (previousPlugin) {
                queryClient.setQueryData(queryKeys.plugins.detail(pluginId), {
                    ...previousPlugin,
                    ...data,
                });
            }

            return { previousPlugin };
        },
        onError: (error, { pluginId }, context) => {
            // Rollback on error
            if (context?.previousPlugin) {
                queryClient.setQueryData(queryKeys.plugins.detail(pluginId), context.previousPlugin);
            }
            toast.error(error.response?.data?.detail || 'Failed to update plugin');
        },
        onSettled: (_, __, { pluginId }) => {
            // Refetch to ensure consistency
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.detail(pluginId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.all });
        },
        onSuccess: () => {
            toast.success('Plugin updated successfully!');
        },
    });
};

/**
 * Delete plugin with confirmation
 */
export const useDeletePlugin = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (pluginId) => pluginApi.delete(pluginId),
        onSuccess: (_, pluginId) => {
            // Remove from cache
            queryClient.removeQueries({ queryKey: queryKeys.plugins.detail(pluginId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.all });
            toast.success('Plugin deleted successfully!');
        },
        onError: (error) => {
            toast.error(error.response?.data?.detail || 'Failed to delete plugin');
        },
    });
};

/**
 * Test database connection
 */
export const useTestConnection = () => {
    return useMutation({
        mutationFn: (pluginId) => pluginApi.testConnection(pluginId),
        onSuccess: () => {
            toast.success('Connection successful!');
        },
        onError: (error) => {
            toast.error(error.response?.data?.detail || 'Connection failed');
        },
    });
};

// ============ API Key Hooks ============

/**
 * Fetch API keys for a plugin
 */
export const useAPIKeys = (pluginId, options = {}) => {
    return useQuery({
        queryKey: queryKeys.plugins.apiKeys(pluginId),
        queryFn: ({ signal }) => pluginApi.apiKeys.list(pluginId, signal),
        enabled: !!pluginId,
        staleTime: 30000,
        ...options,
    });
};

/**
 * Create API key
 */
export const useCreateAPIKey = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pluginId, data }) => pluginApi.apiKeys.create(pluginId, data),
        onSuccess: (result, { pluginId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.apiKeys(pluginId) });
            // Don't show toast here - let component handle showing the key
        },
        onError: (error) => {
            toast.error(error.response?.data?.detail || 'Failed to create API key');
        },
    });
};

/**
 * Revoke API key
 */
export const useRevokeAPIKey = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pluginId, keyId }) => pluginApi.apiKeys.revoke(pluginId, keyId),
        onSuccess: (_, { pluginId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.plugins.apiKeys(pluginId) });
            toast.success('API key revoked');
        },
        onError: (error) => {
            toast.error(error.response?.data?.detail || 'Failed to revoke API key');
        },
    });
};

// ============ Session Hooks ============

/**
 * Fetch sessions for a plugin
 */
export const useSessions = (pluginId, params = {}, options = {}) => {
    return useQuery({
        queryKey: queryKeys.plugins.sessions(pluginId),
        queryFn: ({ signal }) => pluginApi.sessions.list(pluginId, params, signal),
        enabled: !!pluginId,
        staleTime: 15000, // Sessions change frequently
        ...options,
    });
};

// ============ Analytics Hooks ============

/**
 * Fetch plugin analytics
 */
export const usePluginAnalytics = (pluginId, params = {}, options = {}) => {
    return useQuery({
        queryKey: queryKeys.plugins.analytics(pluginId),
        queryFn: ({ signal }) => pluginApi.analytics.get(pluginId, params, signal),
        enabled: !!pluginId,
        staleTime: 60000, // Analytics can be cached longer
        ...options,
    });
};

export default {
    usePlugins,
    usePlugin,
    usePrefetchPlugin,
    useCreatePlugin,
    useUpdatePlugin,
    useDeletePlugin,
    useTestConnection,
    useAPIKeys,
    useCreateAPIKey,
    useRevokeAPIKey,
    useSessions,
    usePluginAnalytics,
};
