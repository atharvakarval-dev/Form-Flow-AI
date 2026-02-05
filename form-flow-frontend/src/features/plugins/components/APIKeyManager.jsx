/**
 * API Key Manager Component
 * Manage API keys for a plugin: create, copy, revoke
 */
import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
    Key, Plus, Copy, Check, Trash2, Clock, AlertTriangle, X, Eye, EyeOff
} from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import { useAPIKeys, useCreateAPIKey, useRevokeAPIKey } from '@/hooks/usePluginQueries';
import { apiKeyCreateSchema } from '../schemas/pluginSchemas';
import { ConfirmDialog } from './ConfirmDialog';
import toast from 'react-hot-toast';

/**
 * APIKeyManager - Full API key management UI
 */
export function APIKeyManager({ plugin, onClose }) {
    const { isDark } = useTheme();
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);
    const [keyToRevoke, setKeyToRevoke] = useState(null);
    const [copiedKeyId, setCopiedKeyId] = useState(null);

    const { data: apiKeys, isLoading, error, refetch } = useAPIKeys(plugin.id);
    const createAPIKey = useCreateAPIKey();
    const revokeAPIKey = useRevokeAPIKey();

    // Copy to clipboard
    const copyToClipboard = useCallback(async (text, keyId) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedKeyId(keyId);
            toast.success('Copied to clipboard!');
            setTimeout(() => setCopiedKeyId(null), 2000);
        } catch (err) {
            toast.error('Failed to copy');
        }
    }, []);

    // Create new key
    const handleCreateKey = async (data) => {
        try {
            const result = await createAPIKey.mutateAsync({
                pluginId: plugin.id,
                data,
            });
            // Show the newly created key (only shown once!)
            setNewlyCreatedKey(result.api_key);
            setShowCreateForm(false);
            toast.success('API key created!');
        } catch (error) {
            // Error handled by mutation
        }
    };

    // Revoke key
    const handleRevokeKey = async () => {
        if (!keyToRevoke) return;
        try {
            await revokeAPIKey.mutateAsync({
                pluginId: plugin.id,
                keyId: keyToRevoke.id,
            });
            setKeyToRevoke(null);
        } catch (error) {
            // Error handled by mutation
        }
    };

    const inputClasses = `
    w-full px-4 py-3 rounded-xl border transition-colors
    ${isDark
            ? 'bg-white/5 border-white/10 text-white placeholder:text-white/30 focus:border-emerald-500/50'
            : 'bg-white border-zinc-200 text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-500'
        }
    focus:outline-none focus:ring-2 focus:ring-emerald-500/20
  `;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                        API Keys
                    </h3>
                    <p className={`text-sm ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>
                        Manage API keys for {plugin.name}
                    </p>
                </div>
                {onClose && (
                    <button
                        onClick={onClose}
                        className={`p-2 rounded-lg ${isDark ? 'hover:bg-white/10' : 'hover:bg-zinc-100'}`}
                        aria-label="Close"
                    >
                        <X className="w-5 h-5" />
                    </button>
                )}
            </div>

            {/* Newly created key warning - Immersive Hero Style */}
            {newlyCreatedKey && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={`
                        p-10 rounded-[3rem] text-center relative overflow-hidden
                        ${isDark ? 'bg-amber-500/10 border border-amber-500/20' : 'bg-amber-50/50 border border-amber-200'}
                    `}
                >
                    <div className="relative z-10 flex flex-col items-center">
                        <div className="w-16 h-16 bg-amber-500 rounded-[1.5rem] flex items-center justify-center mb-6 shadow-2xl shadow-amber-500/40">
                            <AlertTriangle className="w-8 h-8 text-white" />
                        </div>
                        <h4 className={`text-2xl font-black tracking-tighter mb-2 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                            Copy Secure Identity
                        </h4>
                        <p className={`text-xs font-black uppercase tracking-[0.2em] mb-8 opacity-60 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                            This key will only be shown once
                        </p>

                        <div className="flex gap-3 w-full">
                            <code className={`
                                flex-1 px-6 py-5 rounded-[1.5rem] text-lg font-mono tracking-wider truncate
                                ${isDark ? 'bg-black/40 text-amber-200' : 'bg-white text-amber-600 shadow-inner'}
                            `}>
                                {newlyCreatedKey}
                            </code>
                            <button
                                onClick={() => copyToClipboard(newlyCreatedKey, 'new')}
                                className="px-8 py-5 rounded-[1.5rem] bg-amber-500 text-white font-black uppercase tracking-widest text-[10px] shadow-2xl shadow-amber-500/20 hover:scale-105 transition-all"
                            >
                                {copiedKeyId === 'new' ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                            </button>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* Create new key form */}
            <AnimatePresence>
                {showCreateForm && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                    >
                        <CreateKeyForm
                            onSubmit={handleCreateKey}
                            onCancel={() => setShowCreateForm(false)}
                            isLoading={createAPIKey.isPending}
                            isDark={isDark}
                            inputClasses={inputClasses}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* API Keys List */}
            {isLoading ? (
                <div className="space-y-3">
                    {[1, 2].map((i) => (
                        <div key={i} className={`p-4 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`}>
                            <div className={`h-4 w-32 rounded ${isDark ? 'bg-white/10' : 'bg-zinc-200'}`} />
                            <div className={`h-3 w-48 rounded mt-2 ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                        </div>
                    ))}
                </div>
            ) : error ? (
                <div className={`p-4 rounded-xl text-center ${isDark ? 'bg-red-500/10' : 'bg-red-50'}`}>
                    <p className="text-red-500 text-sm">{error.message}</p>
                    <button onClick={() => refetch()} className="text-sm text-red-500 underline mt-2">
                        Retry
                    </button>
                </div>
            ) : apiKeys?.length > 0 ? (
                <div className="space-y-3">
                    {apiKeys.map((key) => (
                        <APIKeyItem
                            key={key.id}
                            apiKey={key}
                            isDark={isDark}
                            copiedKeyId={copiedKeyId}
                            onCopy={copyToClipboard}
                            onRevoke={() => setKeyToRevoke(key)}
                        />
                    ))}
                </div>
            ) : (
                <div className={`py-8 text-center ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>
                    <Key className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No API keys yet</p>
                    <p className="text-sm mt-1">Create one to start using this plugin</p>
                </div>
            )}

            {/* Create button - Premium Pulsing Style */}
            {!showCreateForm && (
                <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => setShowCreateForm(true)}
                    className={`
                        w-full py-6 rounded-[2.5rem] flex items-center justify-center gap-4 transition-all shadow-2xl
                        ${isDark
                            ? 'bg-emerald-500 text-white shadow-emerald-500/10 hover:shadow-emerald-500/30'
                            : 'bg-zinc-900 text-white shadow-zinc-900/10 hover:shadow-zinc-900/20'
                        }
                    `}
                >
                    <Plus className="w-5 h-5" />
                    <span className="text-[11px] font-black uppercase tracking-[0.3em]">Issue New Credential</span>
                </motion.button>
            )}

            {/* Revoke confirmation */}
            <ConfirmDialog
                isOpen={!!keyToRevoke}
                onClose={() => setKeyToRevoke(null)}
                onConfirm={handleRevokeKey}
                title="Revoke API Key?"
                message={`This will permanently revoke "${keyToRevoke?.name}". Any applications using this key will stop working immediately.`}
                confirmText="Revoke Key"
                variant="danger"
                isLoading={revokeAPIKey.isPending}
            />
        </div>
    );
}

/**
 * CreateKeyForm - Form for creating new API key
 */
function CreateKeyForm({ onSubmit, onCancel, isLoading, isDark, inputClasses }) {
    const { register, handleSubmit, formState: { errors } } = useForm({
        resolver: zodResolver(apiKeyCreateSchema),
        defaultValues: { name: '' },
    });

    return (
        <form onSubmit={handleSubmit(onSubmit)} className={`
      p-4 rounded-xl border space-y-4
      ${isDark ? 'bg-white/[0.02] border-white/10' : 'bg-zinc-50 border-zinc-200'}
    `}>
            <div>
                <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-white/70' : 'text-zinc-700'}`}>
                    Key Name <span className="text-red-500">*</span>
                </label>
                <input
                    {...register('name')}
                    placeholder="e.g., Production Key"
                    className={inputClasses}
                    disabled={isLoading}
                />
                {errors.name && (
                    <p className="text-xs text-red-500 mt-1">{errors.name.message}</p>
                )}
            </div>

            <div className="flex gap-3">
                <button
                    type="button"
                    onClick={onCancel}
                    disabled={isLoading}
                    className={`
            flex-1 py-2.5 rounded-xl font-medium transition-colors
            ${isDark ? 'bg-white/10 hover:bg-white/20 text-white' : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'}
          `}
                >
                    Cancel
                </button>
                <button
                    type="submit"
                    disabled={isLoading}
                    className="flex-1 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium flex items-center justify-center gap-2"
                >
                    {isLoading ? (
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                        <>
                            <Key className="w-4 h-4" /> Create Key
                        </>
                    )}
                </button>
            </div>
        </form>
    );
}

/**
 * APIKeyItem - Single API key display
 */
function APIKeyItem({ apiKey, isDark, copiedKeyId, onCopy, onRevoke }) {
    const [showPrefix, setShowPrefix] = useState(false);

    // Format date
    const formatDate = (dateStr) => {
        if (!dateStr) return 'Never';
        const date = new Date(dateStr);
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    };

    // Check if expired
    const isExpired = apiKey.expires_at && new Date(apiKey.expires_at) < new Date();

    return (
        <div className={`
      p-4 rounded-xl border transition-colors
      ${isDark ? 'bg-white/[0.02] border-white/10' : 'bg-white border-zinc-200'}
      ${isExpired || !apiKey.is_active ? 'opacity-60' : ''}
    `}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className={`
            w-8 h-8 rounded-lg flex items-center justify-center
            ${isDark ? 'bg-emerald-500/10' : 'bg-emerald-50'}
          `}>
                        <Key className="w-4 h-4 text-emerald-500" />
                    </div>
                    <div>
                        <h4 className={`font-medium ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                            {apiKey.name}
                        </h4>
                        <div className="flex items-center gap-2 text-xs mt-1">
                            <code className={`
                px-2 py-0.5 rounded font-mono
                ${isDark ? 'bg-white/5 text-white/50' : 'bg-zinc-100 text-zinc-500'}
              `}>
                                {showPrefix ? apiKey.key_prefix || 'ffp_***' : '••••••••'}
                            </code>
                            <button
                                onClick={() => setShowPrefix(!showPrefix)}
                                className={isDark ? 'text-white/40 hover:text-white/60' : 'text-zinc-400 hover:text-zinc-600'}
                            >
                                {showPrefix ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                            </button>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Status badges */}
                    {isExpired && (
                        <span className={`
              px-2 py-1 rounded-full text-xs font-medium
              ${isDark ? 'bg-red-500/10 text-red-400' : 'bg-red-50 text-red-600'}
            `}>
                            Expired
                        </span>
                    )}
                    {!apiKey.is_active && !isExpired && (
                        <span className={`
              px-2 py-1 rounded-full text-xs font-medium
              ${isDark ? 'bg-zinc-500/10 text-zinc-400' : 'bg-zinc-100 text-zinc-600'}
            `}>
                            Revoked
                        </span>
                    )}

                    {/* Actions */}
                    {apiKey.is_active && (
                        <button
                            onClick={onRevoke}
                            className={`
                p-2 rounded-lg transition-colors
                ${isDark ? 'hover:bg-red-500/10 text-red-400' : 'hover:bg-red-50 text-red-500'}
              `}
                            aria-label="Revoke key"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </div>

            {/* Meta */}
            <div className={`flex gap-4 mt-3 pt-3 border-t text-xs ${isDark ? 'border-white/5 text-white/40' : 'border-zinc-100 text-zinc-500'}`}>
                <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Created {formatDate(apiKey.created_at)}
                </span>
                {apiKey.expires_at && (
                    <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Expires {formatDate(apiKey.expires_at)}
                    </span>
                )}
                {apiKey.last_used_at && (
                    <span>Last used {formatDate(apiKey.last_used_at)}</span>
                )}
            </div>
        </div>
    );
}

export default APIKeyManager;
