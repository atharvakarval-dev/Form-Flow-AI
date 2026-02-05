/**
 * Plugin Card Component
 * Memoized card for displaying plugin info with actions
 */
import { memo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Database, Key, Trash2, Settings, Activity, CheckCircle2, XCircle } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';

/**
 * PluginCard - Displays single plugin with actions
 * Memoized to prevent unnecessary re-renders
 */
const PluginCard = memo(function PluginCard({
    plugin,
    onEdit,
    onAPIKeys,
    onTest,
    onDelete,
    onPrefetch,
}) {
    const { isDark } = useTheme();

    // Prefetch on mouse enter for faster navigation
    const handleMouseEnter = useCallback(() => {
        onPrefetch?.(plugin.id);
    }, [plugin.id, onPrefetch]);

    // Database type icon colors
    const dbColors = {
        postgresql: 'text-blue-400',
        mysql: 'text-orange-400',
        mongodb: 'text-green-400',
    };

    return (
        <motion.article
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            whileHover={{ scale: 1.02, y: -5 }}
            onMouseEnter={handleMouseEnter}
            role="article"
            aria-labelledby={`plugin-name-${plugin.id}`}
            className={`
                group relative p-8 rounded-[3rem] transition-all duration-500
                ${isDark
                    ? 'bg-zinc-900/40 hover:bg-zinc-900/60 shadow-[0_32px_64px_rgba(0,0,0,0.3)]'
                    : 'bg-white/70 hover:bg-white shadow-[0_32px_64px_rgba(31,38,135,0.05)]'
                }
            `}
        >
            {/* Hover Glow Effect - Ultra Soft */}
            <div className={`
                absolute inset-0 rounded-[3rem] opacity-0 group-hover:opacity-10 pointer-events-none transition-opacity duration-700
                ${isDark ? 'bg-emerald-500 blur-[80px]' : 'bg-emerald-400 blur-[80px]'}
            `} />

            {/* Header */}
            <div className="relative z-10 flex items-start justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className={`
                        w-12 h-12 rounded-2xl flex items-center justify-center border transition-all duration-500
                        ${isDark
                            ? 'bg-zinc-800/50 border-white/5 shadow-inner'
                            : 'bg-zinc-50 border-zinc-100 shadow-inner'
                        }
                    `}>
                        <Database className={`w-6 h-6 ${dbColors[plugin.database_type.toLowerCase()] || 'text-emerald-500'}`} />
                    </div>
                    <div>
                        <h3
                            id={`plugin-name-${plugin.id}`}
                            className={`text-lg font-bold tracking-tight truncate max-w-[160px] ${isDark ? 'text-white' : 'text-zinc-900'}`}
                        >
                            {plugin.name}
                        </h3>
                        <div className={`text-[10px] font-bold uppercase tracking-widest opacity-50 ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                            {plugin.database_type}
                        </div>
                    </div>
                </div>

                {/* Status Badge */}
                <div
                    className={`
                        flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest border
                        ${plugin.is_active
                            ? isDark
                                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                : 'bg-emerald-50 border-emerald-200 text-emerald-600'
                            : isDark
                                ? 'bg-red-500/10 border-red-500/20 text-red-400'
                                : 'bg-red-50 border-red-200 text-red-600'
                        }
                    `}
                    aria-label={`Status: ${plugin.is_active ? 'Active' : 'Inactive'}`}
                >
                    <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${plugin.is_active ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    {plugin.is_active ? 'Online' : 'Offline'}
                </div>
            </div>

            {/* Description */}
            {plugin.description && (
                <p className={`relative z-10 text-sm mb-6 line-clamp-2 leading-relaxed font-medium opacity-70 ${isDark ? 'text-zinc-300' : 'text-zinc-600'}`}>
                    {plugin.description}
                </p>
            )}

            {/* Stats Overlay */}
            <div className={`
                relative z-10 flex items-center justify-between p-4 rounded-2xl mb-6
                ${isDark ? 'bg-white/[0.03] border border-white/[0.05]' : 'bg-zinc-50 border border-zinc-100'}
            `}>
                <div className="flex flex-col items-center gap-1 flex-1 border-r border-white/5">
                    <span className={`text-xs font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{plugin.tables?.length || 0}</span>
                    <span className="text-[9px] uppercase tracking-wider opacity-50">Tables</span>
                </div>
                <div className="flex flex-col items-center gap-1 flex-1 border-r border-white/5">
                    <span className={`text-xs font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{plugin.api_key_count || 0}</span>
                    <span className="text-[9px] uppercase tracking-wider opacity-50">Keys</span>
                </div>
                <div className="flex flex-col items-center gap-1 flex-1">
                    <span className={`text-xs font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{plugin.session_count || 0}</span>
                    <span className="text-[9px] uppercase tracking-wider opacity-50">Sessions</span>
                </div>
            </div>

            {/* Actions */}
            <div className="relative z-10 flex items-center gap-2">
                <button
                    onClick={(e) => { e.stopPropagation(); onEdit?.(plugin); }}
                    aria-label={`Edit ${plugin.name}`}
                    className={`
                        flex-1 flex items-center justify-center gap-2 py-4 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] transition-all
                        ${isDark
                            ? 'bg-white/5 hover:bg-white/10 text-white/70 hover:text-white'
                            : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-500 hover:text-zinc-900'
                        }
                    `}
                >
                    <Settings className="w-3.5 h-3.5" />
                    Setup
                </button>

                <button
                    onClick={(e) => { e.stopPropagation(); onTest?.(plugin); }}
                    aria-label={`Test ${plugin.name}`}
                    className={`
                        flex-1 flex items-center justify-center gap-2 py-4 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] transition-all
                        ${isDark
                            ? 'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 shadow-lg shadow-blue-500/5'
                            : 'bg-blue-50 text-blue-600 hover:bg-blue-100 shadow-lg shadow-blue-500/5'
                        }
                    `}
                >
                    <Activity className="w-3.5 h-3.5" />
                    Test
                </button>

                <button
                    onClick={(e) => { e.stopPropagation(); onAPIKeys?.(plugin); }}
                    aria-label={`Manage API keys for ${plugin.name}`}
                    className={`
                        flex-1 flex items-center justify-center gap-2 py-4 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] transition-all
                        ${isDark
                            ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40'
                            : 'bg-zinc-900 text-white shadow-lg shadow-zinc-900/10 hover:shadow-zinc-900/30'
                        }
                    `}
                >
                    <Key className="w-3.5 h-3.5" />
                    Keys
                </button>

                <button
                    onClick={(e) => { e.stopPropagation(); onDelete?.(plugin); }}
                    aria-label={`Delete ${plugin.name}`}
                    className={`
                        p-3 rounded-xl transition-all
                        ${isDark
                            ? 'text-zinc-500 hover:text-red-400 hover:bg-red-500/10'
                            : 'text-zinc-400 hover:text-red-500 hover:bg-red-50'
                        }
                    `}
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>
        </motion.article>
    );
}, (prevProps, nextProps) => {
    // Only re-render if plugin data changed
    return (
        prevProps.plugin.id === nextProps.plugin.id &&
        prevProps.plugin.name === nextProps.plugin.name &&
        prevProps.plugin.is_active === nextProps.plugin.is_active &&
        prevProps.plugin.updated_at === nextProps.plugin.updated_at
    );
});

/**
 * PluginCardSkeleton - Loading placeholder
 */
export function PluginCardSkeleton() {
    const { isDark } = useTheme();

    return (
        <div className={`
      p-5 rounded-2xl border animate-pulse
      ${isDark ? 'bg-zinc-900/70 border-white/[0.08]' : 'bg-white/80 border-zinc-200'}
    `}>
            {/* Header skeleton */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />
                    <div>
                        <div className={`h-4 w-32 rounded ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />
                        <div className={`h-3 w-20 rounded mt-1 ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                    </div>
                </div>
                <div className={`h-6 w-16 rounded-full ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />
            </div>

            {/* Description skeleton */}
            <div className={`h-3 w-full rounded mb-2 ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
            <div className={`h-3 w-2/3 rounded mb-4 ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />

            {/* Stats skeleton */}
            <div className={`flex gap-4 mb-4 pb-4 border-b ${isDark ? 'border-white/5' : 'border-zinc-100'}`}>
                {[1, 2, 3].map((i) => (
                    <div key={i} className={`h-3 w-16 rounded ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                ))}
            </div>

            {/* Actions skeleton */}
            <div className="flex gap-2">
                <div className={`flex-1 h-9 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                <div className={`flex-1 h-9 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                <div className={`w-9 h-9 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
            </div>
        </div>
    );
}

export default PluginCard;
