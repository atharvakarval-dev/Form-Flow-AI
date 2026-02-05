/**
 * Plugin Dashboard - Main Plugin Management View
 * Features: plugin list, search, create, delete, API keys, embed code
 */
import { useState, useCallback, useMemo, lazy, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { QueryClientProvider } from '@tanstack/react-query';
import {
    Search, Plus, Filter, LayoutGrid, List, RefreshCw, Puzzle, ChevronLeft, X
} from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import queryClient from '@/lib/queryClient';
import { usePlugins, useDeletePlugin, usePrefetchPlugin } from '@/hooks/usePluginQueries';
import PluginCard, { PluginCardSkeleton } from './PluginCard';
import { EmptyState, ErrorState } from './EmptyState';
import { ConfirmDialog } from './ConfirmDialog';
import { CreatePluginModal } from './CreatePluginModal';
import { APIKeyManager } from './APIKeyManager';
import { SDKEmbedCode } from './SDKEmbedCode';
import { PluginTester } from './PluginTester';

// ============ Debounce Hook ============
function useDebounce(value, delay = 500) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useMemo(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
}

// ============ Plugin Dashboard Content ============
function PluginDashboardContent() {
    const { isDark } = useTheme();

    // UI State
    const [searchQuery, setSearchQuery] = useState('');
    const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'list'
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedPlugin, setSelectedPlugin] = useState(null);
    const [pluginToDelete, setPluginToDelete] = useState(null);
    const [showAPIKeys, setShowAPIKeys] = useState(false);
    const [showEmbedCode, setShowEmbedCode] = useState(false);
    const [showTester, setShowTester] = useState(false);

    // Debounced search
    const debouncedSearch = useDebounce(searchQuery, 500);

    // Queries
    const { data, isLoading, error, refetch, isFetching } = usePlugins({
        search: debouncedSearch,
        page: 1,
        limit: 50,
    });

    const deletePlugin = useDeletePlugin();
    const prefetchPlugin = usePrefetchPlugin();

    // Handlers
    const handleCreateSuccess = useCallback(() => {
        refetch();
    }, [refetch]);

    const handleDeleteConfirm = useCallback(async () => {
        if (!pluginToDelete) return;
        try {
            await deletePlugin.mutateAsync(pluginToDelete.id);
            setPluginToDelete(null);
        } catch (err) {
            // Error handled by mutation
        }
    }, [pluginToDelete, deletePlugin]);

    const handleEditPlugin = useCallback((plugin) => {
        setSelectedPlugin(plugin);
        setShowEmbedCode(true); // Changed to show Embed Code (Setup)
    }, []);

    const handleAPIKeysClick = useCallback((plugin) => {
        setSelectedPlugin(plugin);
        setShowAPIKeys(true);
    }, []);

    const handleTestPlugin = useCallback((plugin) => {
        setSelectedPlugin(plugin);
        setShowTester(true);
    }, []);

    const handleClosePanel = useCallback(() => {
        setShowAPIKeys(false);
        setShowEmbedCode(false);
        setShowTester(false);
        setSelectedPlugin(null);
    }, []);


    // Plugins data
    const plugins = data?.plugins || data || [];

    return (
        <div className="flex flex-col h-full">
            {/* Toast notifications */}
            <Toaster
                position="top-right"
                toastOptions={{
                    className: isDark ? '!bg-zinc-800 !text-white' : '',
                    duration: 3000,
                }}
            />

            {/* Dashboard Controls Row */}
            <div className="flex flex-col md:flex-row items-center gap-4 mb-10">
                {/* Search - Immersive Style */}
                <div className="relative flex-1 w-full">
                    <Search className={`absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors ${isDark ? 'text-zinc-600 group-focus-within:text-emerald-500' : 'text-zinc-300'}`} />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search your architecture..."
                        className={`
                            w-full pl-14 pr-6 py-4 rounded-[2rem] border-none text-sm font-medium transition-all duration-500
                            ${isDark
                                ? 'bg-zinc-900/50 text-white placeholder:text-zinc-700 focus:bg-zinc-900 focus:ring-4 focus:ring-emerald-500/10'
                                : 'bg-white text-zinc-900 placeholder:text-zinc-400 shadow-xl shadow-zinc-200/20 focus:ring-4 focus:ring-emerald-500/5'
                            }
                            focus:outline-none
                        `}
                    />
                    {isFetching && (
                        <div className="absolute right-6 top-1/2 -translate-y-1/2">
                            <RefreshCw className={`w-4 h-4 animate-spin ${isDark ? 'text-emerald-500/50' : 'text-emerald-500'}`} />
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-3 w-full md:w-auto">
                    {/* View Toggle - Pill */}
                    <div className={`
                        flex p-1.5 rounded-full backdrop-blur-xl border
                        ${isDark ? 'bg-zinc-900/50 border-white/[0.05]' : 'bg-white border-zinc-200/50 shadow-sm'}
                    `}>
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2.5 rounded-full transition-all duration-500 ${viewMode === 'grid' ? (isDark ? 'bg-white text-black shadow-lg' : 'bg-zinc-900 text-white shadow-lg') : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            <LayoutGrid className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2.5 rounded-full transition-all duration-500 ${viewMode === 'list' ? (isDark ? 'bg-white text-black shadow-lg' : 'bg-zinc-900 text-white shadow-lg') : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                            <List className="w-4 h-4" />
                        </button>
                    </div>

                    <motion.button
                        whileHover={{ scale: 1.02, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => setShowCreateModal(true)}
                        className={`
                            flex-1 md:flex-none px-8 py-4 rounded-[2rem] font-black uppercase tracking-[0.2em] text-[10px] transition-all shadow-2xl
                            ${isDark
                                ? 'bg-emerald-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/40'
                                : 'bg-zinc-900 text-white shadow-zinc-900/20 hover:shadow-zinc-900/40'
                            }
                            flex items-center justify-center gap-3
                        `}
                    >
                        <Plus className="w-4 h-4" />
                        Initialize
                    </motion.button>
                </div>
            </div>

            {/* Main content area */}
            <div className="flex-1 flex gap-6">
                {/* Plugin grid/list */}
                <div className={`flex-1 ${showAPIKeys || showEmbedCode ? 'hidden lg:block' : ''}`}>
                    {isLoading ? (
                        // Loading skeleton
                        <div className={`
              grid gap-4
              ${viewMode === 'grid' ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1'}
            `}>
                            {[1, 2, 3, 4, 5, 6].map((i) => (
                                <PluginCardSkeleton key={i} />
                            ))}
                        </div>
                    ) : error ? (
                        // Error state
                        <ErrorState
                            error={error}
                            onRetry={refetch}
                            title="Failed to load plugins"
                        />
                    ) : plugins.length === 0 ? (
                        // Empty state
                        <EmptyState
                            icon={Puzzle}
                            title={searchQuery ? 'No plugins found' : 'Create your first plugin'}
                            description={
                                searchQuery
                                    ? `No plugins match "${searchQuery}". Try a different search.`
                                    : 'Plugins let you collect voice-powered data directly into your database. Create one to get started!'
                            }
                            actionLabel={searchQuery ? 'Clear search' : 'Create Plugin'}
                            onAction={searchQuery ? () => setSearchQuery('') : () => setShowCreateModal(true)}
                        />
                    ) : (
                        // Plugin cards
                        <div className={`
              grid gap-4
              ${viewMode === 'grid' ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1'}
            `}>
                            <AnimatePresence mode="popLayout">
                                {plugins.map((plugin) => (
                                    <PluginCard
                                        key={plugin.id}
                                        plugin={plugin}
                                        onEdit={handleEditPlugin}
                                        onAPIKeys={handleAPIKeysClick}
                                        onTest={handleTestPlugin}
                                        onDelete={setPluginToDelete}
                                        onPrefetch={prefetchPlugin}
                                    />
                                ))}
                            </AnimatePresence>
                        </div>
                    )}
                </div>

                {/* Side panel - Floating Drawer Style */}
                <AnimatePresence>
                    {(showAPIKeys || showEmbedCode || showTester) && selectedPlugin && (
                        <div className="fixed inset-0 z-[500] flex justify-end overflow-hidden">
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                onClick={handleClosePanel}
                                className="absolute inset-0 bg-zinc-950/60 backdrop-blur-3xl"
                            />
                            <motion.div
                                initial={{ x: '100%', filter: 'blur(30px)' }}
                                animate={{ x: 0, filter: 'blur(0px)' }}
                                exit={{ x: '100%', filter: 'blur(30px)' }}
                                transition={{ type: "spring", damping: 35, stiffness: 350 }}
                                className={`
                                    relative z-10 w-full max-w-2xl h-full shadow-[-40px_0_80px_rgba(0,0,0,0.5)] overflow-visible border-l
                                    ${isDark ? 'bg-zinc-900/98 border-white/[0.05]' : 'bg-white/95 border-zinc-200/50 backdrop-blur-3xl'}
                                `}
                            >
                                {/* Floating Back Arrow - External to white area */}
                                <motion.button
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: 20 }}
                                    transition={{ delay: 0.3 }}
                                    onClick={handleClosePanel}
                                    className={`
                                        absolute -left-16 top-10 w-12 h-12 rounded-full flex items-center justify-center transition-all hover:scale-110 active:scale-95 z-20
                                        ${isDark
                                            ? 'bg-zinc-800/80 text-white hover:bg-zinc-700 border-white/10'
                                            : 'bg-white/80 text-zinc-900 hover:bg-white shadow-2xl border-zinc-200'
                                        }
                                        backdrop-blur-xl border
                                    `}
                                >
                                    <ChevronLeft className="w-6 h-6" />
                                </motion.button>

                                <div className="p-10 pt-16 h-full overflow-y-auto custom-scrollbar">
                                    <div className="flex justify-between items-center mb-8">
                                        <h2 className={`text-4xl font-black tracking-tighter ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                                            {showAPIKeys ? 'Credentials' : showTester ? 'Test Plugin' : 'Embed Code'}
                                        </h2>
                                    </div>
                                    {showAPIKeys && (
                                        <APIKeyManager plugin={selectedPlugin} onClose={handleClosePanel} />
                                    )}
                                    {showEmbedCode && (
                                        <SDKEmbedCode plugin={selectedPlugin} />
                                    )}
                                    {showTester && (
                                        <PluginTester plugin={selectedPlugin} />
                                    )}
                                </div>
                            </motion.div>
                        </div>
                    )}
                </AnimatePresence>
            </div>

            {/* Create plugin modal */}
            <CreatePluginModal
                isOpen={showCreateModal}
                onClose={() => setShowCreateModal(false)}
                onSuccess={handleCreateSuccess}
            />

            {/* Delete confirmation */}
            <ConfirmDialog
                isOpen={!!pluginToDelete}
                onClose={() => setPluginToDelete(null)}
                onConfirm={handleDeleteConfirm}
                title="Delete Plugin?"
                message={`This will permanently delete "${pluginToDelete?.name}" and all associated API keys and sessions. This action cannot be undone.`}
                confirmText="Delete Plugin"
                variant="danger"
                isLoading={deletePlugin.isPending}
            />
        </div>
    );
}

// ============ Main Export with QueryProvider ============
/**
 * PluginDashboard - Wrapped with React Query provider
 */
export function PluginDashboard() {
    return (
        <QueryClientProvider client={queryClient}>
            <PluginDashboardContent />
        </QueryClientProvider>
    );
}

export default PluginDashboard;
