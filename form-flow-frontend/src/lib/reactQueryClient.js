/**
 * React Query Client Configuration
 * Centralized caching, retry logic, and stale time management
 * 
 * note: Renamed from queryClient.js to fix CI build casing issues
 */
import { QueryClient } from '@tanstack/react-query';

/**
 * Global QueryClient instance with production-optimized defaults
 */
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            // Data considered fresh for 30 seconds
            staleTime: 30 * 1000,
            // Cache persists for 5 minutes
            gcTime: 5 * 60 * 1000,
            // Retry failed requests 3 times with exponential backoff
            retry: 3,
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
            // Refetch on window focus for real-time data
            refetchOnWindowFocus: true,
            // Don't refetch on mount if data is fresh
            refetchOnMount: 'always',
        },
        mutations: {
            // Retry mutations once
            retry: 1,
            retryDelay: 1000,
        },
    },
});

// Make queryClient globally accessible for cache clearing on logout
if (typeof window !== 'undefined') {
    window.queryClient = queryClient;
}

/**
 * Query keys factory for type-safe cache invalidation
 */
export const queryKeys = {
    plugins: {
        all: ['plugins'],
        list: (params) => ['plugins', 'list', params],
        detail: (id) => ['plugins', 'detail', id],
        apiKeys: (pluginId) => ['plugins', pluginId, 'api-keys'],
        sessions: (pluginId) => ['plugins', pluginId, 'sessions'],
        analytics: (pluginId) => ['plugins', pluginId, 'analytics'],
    },
};

export default queryClient;