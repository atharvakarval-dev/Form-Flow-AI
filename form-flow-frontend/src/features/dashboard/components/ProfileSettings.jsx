"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    User, Shield, Edit3, Trash2, ToggleLeft, ToggleRight,
    Save, X, AlertTriangle, CheckCircle, Brain, Loader2,
    Activity, TrendingUp, Target, MessageSquare, Zap, BookOpen,
    Layers, Search, Compass
} from "lucide-react"
import {
    getProfile, updateProfile, deleteProfile,
    getProfileStatus, optInProfiling, optOutProfiling
} from '@/services/api'
import { useTheme } from '@/context/ThemeProvider'

/**
 * ProfileSettings - Profile Management UI Component
 * 
 * Features:
 * - View behavioral profile (JSON Case Study or Legacy Text)
 * - Edit profile text (JSON aware)
 * - Toggle profiling on/off
 * - Delete profile (GDPR)
 */
export function ProfileSettings() {
    const { isDark } = useTheme()

    // State
    const [profile, setProfile] = useState(null)
    const [status, setStatus] = useState(null)
    const [loading, setLoading] = useState(true)
    const [editing, setEditing] = useState(false)
    const [editText, setEditText] = useState('')
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

    // Theme styles
    const cardBgClass = isDark
        ? "bg-black/40 border-white/10 backdrop-blur-xl"
        : "bg-white/60 border-zinc-200 backdrop-blur-xl shadow-lg"
    const textClass = isDark ? "text-white" : "text-zinc-900"
    const subTextClass = isDark ? "text-white/60" : "text-zinc-500"
    const accentClass = isDark ? "text-purple-400" : "text-purple-600"
    const inputClass = isDark
        ? "bg-black/40 border-white/20 text-white placeholder-white/30"
        : "bg-white border-zinc-300 text-zinc-900 placeholder-zinc-400"

    // Fetch data on mount
    useEffect(() => {
        fetchProfileData()
    }, [])

    const fetchProfileData = async () => {
        setLoading(true)
        try {
            const statusData = await getProfileStatus()
            setStatus(statusData)

            if (statusData.has_profile) {
                const profileData = await getProfile()
                setProfile(profileData)
                setEditText(profileData.profile_text)
            }
        } catch (err) {
            console.error("Profile fetch error:", err)
            if (err.response?.status !== 404) {
                setMessage({ type: 'error', text: 'Failed to load profile data' })
            }
        } finally {
            setLoading(false)
        }
    }

    const handleToggleProfiling = async () => {
        try {
            if (status?.profiling_enabled) {
                const result = await optOutProfiling()
                setStatus(prev => ({ ...prev, profiling_enabled: false }))
                setMessage({ type: 'success', text: result.message })
            } else {
                const result = await optInProfiling()
                setStatus(prev => ({ ...prev, profiling_enabled: true }))
                setMessage({ type: 'success', text: result.message })
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to update profiling preference' })
        }
    }

    const handleSaveEdit = async () => {
        setSaving(true)
        try {
            // For JSON, we validate it parses
            try {
                if (editText.trim().startsWith('{')) {
                    JSON.parse(editText)
                }
            } catch (e) {
                setMessage({ type: 'error', text: 'Invalid JSON format' })
                setSaving(false)
                return
            }

            // Allow larger size for JSON structure
            const wordCount = editText.trim().split(/\s+/).length
            if (wordCount > 1000) {
                setMessage({ type: 'error', text: `Profile exceeds limit (${wordCount} words)` })
                setSaving(false)
                return
            }

            const updated = await updateProfile(editText)
            setProfile(updated)
            setEditing(false)
            setMessage({ type: 'success', text: 'Profile updated successfully!' })
        } catch (err) {
            setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to save profile' })
        } finally {
            setSaving(false)
        }
    }

    const handleDelete = async () => {
        try {
            await deleteProfile()
            setProfile(null)
            setStatus(prev => ({ ...prev, has_profile: false }))
            setShowDeleteConfirm(false)
            setMessage({ type: 'success', text: 'Profile deleted successfully' })
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to delete profile' })
        }
    }

    // Clear message after 5s
    useEffect(() => {
        if (message) {
            const timer = setTimeout(() => setMessage(null), 5000)
            return () => clearTimeout(timer)
        }
    }, [message])

    // --- RENDER HELPERS ---

    const renderStructuredProfile = (jsonText) => {
        let data
        try {
            data = JSON.parse(jsonText)
        } catch (e) {
            return renderLegacyProfile(jsonText)
        }

        // Mapping sections to icons
        const Section = ({ title, icon: Icon, children }) => (
            <div className="mb-6 last:mb-0">
                <div className="flex items-center gap-2 mb-3">
                    <Icon className={`w-4 h-4 ${accentClass}`} />
                    <h4 className={`text-sm font-semibold uppercase tracking-wider ${subTextClass}`}>{title}</h4>
                </div>
                <div className="pl-6 border-l md:border-l-2 border-dashed border-white/10 ml-2">
                    {children}
                </div>
            </div>
        )

        return (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {/* Executive Summary */}
                <div className={`p-4 rounded-xl ${isDark ? 'bg-purple-900/10 border-purple-500/20' : 'bg-purple-50 border-purple-100'} border`}>
                    <h3 className={`font-serif text-lg leading-relaxed italic ${textClass}`}>
                        "{data.executive_summary}"
                    </h3>
                </div>

                {/* Case Study Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                    {/* Psychological Profile */}
                    <Section title="Psychological Profile" icon={Brain}>
                        <div className="space-y-4">
                            <div>
                                <span className={`text-xs uppercase ${subTextClass}`}>Archetype</span>
                                <div className={`font-bold text-lg ${accentClass}`}>{data.psychological_profile?.personality_archetype || 'Unknown'}</div>
                            </div>
                            <div>
                                <span className={`text-xs uppercase ${subTextClass}`}>Mindset Analysis</span>
                                <p className={`text-sm leading-relaxed ${textClass} mt-1`}>
                                    {data.psychological_profile?.mindset_analysis}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {data.psychological_profile?.core_traits?.map((trait, i) => (
                                    <span key={i} className={`px-2 py-1 rounded-md text-xs font-medium ${isDark ? 'bg-white/10 text-white' : 'bg-zinc-100 text-zinc-700'}`}>
                                        {trait}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </Section>

                    {/* Behavioral Patterns */}
                    <Section title="Behavioral Patterns" icon={Activity}>
                        <div className="space-y-4 text-sm">
                            <div className={`p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-50'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Compass className="w-3 h-3 text-blue-400" />
                                    <span className={`font-medium ${textClass}`}>Decision Making</span>
                                </div>
                                <p className={subTextClass}>{data.behavioral_patterns?.decision_making}</p>
                            </div>
                            <div className={`p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-50'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Shield className="w-3 h-3 text-green-400" />
                                    <span className={`font-medium ${textClass}`}>Risk Tolerance</span>
                                </div>
                                <p className={subTextClass}>{data.behavioral_patterns?.risk_tolerance}</p>
                            </div>
                            <div className={`p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-zinc-50'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <MessageSquare className="w-3 h-3 text-yellow-400" />
                                    <span className={`font-medium ${textClass}`}>Communication</span>
                                </div>
                                <p className={subTextClass}>{data.behavioral_patterns?.communication_style}</p>
                            </div>
                        </div>
                    </Section>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Motivation */}
                    <Section title="Motivation Matrix" icon={Zap}>
                        <div className="space-y-4">
                            <div>
                                <div className={`text-xs mb-2 ${subTextClass}`}>DRIVERS</div>
                                <ul className="space-y-1">
                                    {data.motivation_matrix?.underlying_drivers?.map((d, i) => (
                                        <li key={i} className="flex items-center gap-2 text-sm text-zinc-400">
                                            <Target className="w-3 h-3 text-red-400" />
                                            <span className={textClass}>{d}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="mt-4">
                                <span className={`text-xs ${subTextClass}`}>DEFINITION OF SUCCESS</span>
                                <p className={`text-sm italic mt-1 ${textClass} opacity-80`}>
                                    "{data.motivation_matrix?.success_metrics}"
                                </p>
                            </div>
                        </div>
                    </Section>

                    {/* Growth */}
                    <Section title="Growth Trajectory" icon={TrendingUp}>
                        <div className="space-y-4 text-sm">
                            <div>
                                <span className={`text-xs ${subTextClass}`}>CURRENT FOCUS</span>
                                <p className={`mt-1 font-medium ${textClass}`}>
                                    {data.growth_trajectory?.current_focus}
                                </p>
                            </div>
                            <div className={`p-3 rounded-lg border-l-2 border-yellow-500 ${isDark ? 'bg-yellow-500/5' : 'bg-yellow-50'}`}>
                                <span className="text-xs text-yellow-500 font-bold uppercase block mb-1">Blind Spots</span>
                                <ul className="list-disc list-inside space-y-1">
                                    {data.growth_trajectory?.potential_blind_spots?.map((bs, i) => (
                                        <li key={i} className={subTextClass}>{bs}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </Section>
                </div>

                {/* History / Evolution (if present) */}
                {data.interaction_history && (
                    <Section title="Interaction Analytics" icon={Layers}>
                        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-zinc-50 border-zinc-200'}`}>
                            <div className="flex items-start gap-4">
                                <div className="mt-1">
                                    <TrendingUp className="w-5 h-5 text-green-400" />
                                </div>
                                <div>
                                    <h5 className={`text-sm font-medium ${textClass}`}>Behavioral Evolution</h5>
                                    <p className={`text-sm mt-1 ${subTextClass}`}>
                                        {data.interaction_history?.behavioral_evolution}
                                    </p>
                                </div>
                            </div>
                            {data.interaction_history?.observation_log && (
                                <div className={`mt-4 pt-4 border-t ${isDark ? 'border-white/10' : 'border-zinc-200'} text-xs ${subTextClass}`}>
                                    <span className="font-semibold text-purple-400">Latest Observation:</span> {data.interaction_history?.observation_log}
                                </div>
                            )}
                        </div>
                    </Section>
                )}
            </div>
        )
    }

    const renderLegacyProfile = (text) => (
        <div className={`text-sm leading-relaxed whitespace-pre-wrap font-mono opacity-80 ${subTextClass}`}>
            {text}
        </div>
    )


    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin opacity-50" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isDark ? 'bg-purple-500/20' : 'bg-purple-100'}`}>
                        <BookOpen className={`w-5 h-5 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} />
                    </div>
                    <div>
                        <h2 className={`font-semibold ${textClass}`}>Personal Case Study</h2>
                        <p className={`text-xs ${subTextClass}`}>
                            Psychological analysis of your form interactions
                        </p>
                    </div>
                </div>
                <button
                    onClick={fetchProfileData}
                    className={`p-2 rounded-lg transition-all ${isDark ? 'hover:bg-white/10 text-white/60' : 'hover:bg-zinc-100 text-zinc-500'}`}
                    title="Refresh Profile"
                >
                    <Loader2 className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Message Toast */}
            <AnimatePresence>
                {message && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className={`p-3 rounded-xl flex items-center gap-2 text-sm ${message.type === 'success'
                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-red-500/20 text-red-400 border border-red-500/30'
                            }`}
                    >
                        {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                        {message.text}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Profiling Toggle & Status */}
            <div className={`rounded-2xl border p-4 flex items-center justify-between ${cardBgClass}`}>
                <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${status?.profiling_enabled ? 'bg-green-500/20' : 'bg-zinc-500/20'}`}>
                        <Activity className={`w-4 h-4 ${status?.profiling_enabled ? 'text-green-400' : 'text-zinc-400'}`} />
                    </div>

                    <div>
                        <div className="flex items-center gap-2">
                            <span className={`text-sm font-medium ${textClass}`}>Live Profiling</span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-bold ${status?.profiling_enabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-500/20 text-zinc-400'
                                }`}>
                                {status?.profiling_enabled ? 'Active' : 'Paused'}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {profile && (
                        <div className={`px-3 py-1.5 rounded-lg text-xs font-mono mr-2 ${isDark ? 'bg-white/5 text-white/40' : 'bg-zinc-100 text-zinc-500'}`}>
                            v{profile.version}
                        </div>
                    )}
                    <button
                        onClick={handleToggleProfiling}
                        className={`p-2 rounded-lg transition-all ${status?.profiling_enabled
                            ? 'hover:bg-green-500/10 text-green-400'
                            : 'hover:bg-zinc-500/10 text-zinc-400'
                            }`}
                    >
                        {status?.profiling_enabled ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                    </button>
                </div>
            </div>

            {/* Profile Content */}
            {profile ? (
                <div className={`rounded-2xl border p-6 md:p-8 ${cardBgClass}`}>
                    <div className="flex items-center justify-between mb-8 pb-4 border-b border-white/5">
                        <div className="flex items-center gap-3">
                            <div className="flex flex-col">
                                <span className={`text-xs uppercase tracking-widest ${subTextClass}`}>Subject ID</span>
                                <span className={`font-mono text-sm ${textClass}`}>USR-{profile.user_id.toString().padStart(4, '0')}</span>
                            </div>
                            <div className={`h-8 w-[1px] ${isDark ? 'bg-white/10' : 'bg-zinc-200'} mx-2`}></div>
                            <div className="flex flex-col">
                                <span className={`text-xs uppercase tracking-widest ${subTextClass}`}>Confidence</span>
                                <span className={`font-mono text-sm ${profile.confidence_score > 0.7 ? 'text-green-400' : 'text-yellow-400'}`}>
                                    {Math.round(profile.confidence_score * 100)}%
                                </span>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            {!editing && (
                                <>
                                    <button
                                        onClick={() => setEditing(true)}
                                        className={`p-2 rounded-lg transition-all ${isDark ? 'hover:bg-white/10 text-white/60 hover:text-white' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-900'}`}
                                        title="Edit raw data"
                                    >
                                        <Edit3 className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={() => setShowDeleteConfirm(true)}
                                        className="p-2 rounded-lg transition-all text-red-400 hover:bg-red-500/20"
                                        title="Delete profile"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </>
                            )}
                        </div>
                    </div>

                    {editing ? (
                        <div className="space-y-3">
                            <div className={`text-xs font-mono mb-2 ${subTextClass}`}>
                                EDIT MODE: You are editing the raw JSON profile data. syntax errors will prevent saving.
                            </div>
                            <textarea
                                value={editText}
                                onChange={(e) => setEditText(e.target.value)}
                                rows={20}
                                className={`w-full p-4 rounded-xl border font-mono text-xs resize-y focus:outline-none focus:ring-2 focus:ring-purple-500/50 ${inputClass}`}
                                placeholder="{ ... }"
                            />
                            <div className="flex items-center justify-end gap-2">
                                <button
                                    onClick={() => {
                                        setEditing(false)
                                        setEditText(profile.profile_text)
                                    }}
                                    className={`px-3 py-1.5 rounded-lg text-sm ${isDark ? 'bg-white/10 hover:bg-white/20' : 'bg-zinc-100 hover:bg-zinc-200'}`}
                                >
                                    <X className="w-4 h-4 inline mr-1" />
                                    Cancel
                                </button>
                                <button
                                    onClick={handleSaveEdit}
                                    disabled={saving}
                                    className="px-3 py-1.5 rounded-lg text-sm bg-purple-500 text-white hover:bg-purple-600 disabled:opacity-50"
                                >
                                    {saving ? <Loader2 className="w-4 h-4 animate-spin inline mr-1" /> : <Save className="w-4 h-4 inline mr-1" />}
                                    Save JSON
                                </button>
                            </div>
                        </div>
                    ) : (
                        renderStructuredProfile(profile.profile_text)
                    )}
                </div>
            ) : (
                <div className={`rounded-2xl border p-12 text-center border-dashed ${isDark ? 'border-white/10 bg-white/5' : 'border-zinc-300 bg-zinc-50'}`}>
                    <div className={`w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center ${isDark ? 'bg-white/5' : 'bg-white shadow-sm'}`}>
                        <Search className={`w-8 h-8 ${isDark ? 'text-white/20' : 'text-zinc-300'}`} />
                    </div>
                    <h3 className={`text-lg font-medium mb-2 ${textClass}`}>No Case Study Available</h3>
                    <p className={`text-sm max-w-xs mx-auto ${subTextClass}`}>
                        Complete more forms to let the AI analyze your behavioral patterns and generate a study.
                    </p>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {showDeleteConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm"
                        onClick={() => setShowDeleteConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95 }}
                            animate={{ scale: 1 }}
                            exit={{ scale: 0.95 }}
                            onClick={(e) => e.stopPropagation()}
                            className={`p-6 rounded-2xl max-w-sm mx-4 shadow-2xl ${isDark ? 'bg-zinc-900 border border-white/10' : 'bg-white border border-zinc-200'}`}
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                                    <AlertTriangle className="w-5 h-5 text-red-400" />
                                </div>
                                <h3 className={`font-semibold ${textClass}`}>Delete Case Study?</h3>
                            </div>
                            <p className={`text-sm mb-6 ${subTextClass}`}>
                                This will permanently delete your behavioral profile and analysis history.
                                This action cannot be undone.
                            </p>
                            <div className="flex gap-3">
                                <button
                                    onClick={() => setShowDeleteConfirm(false)}
                                    className={`flex-1 py-2 rounded-xl text-sm ${isDark ? 'bg-white/10 hover:bg-white/20' : 'bg-zinc-100 hover:bg-zinc-200'}`}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleDelete}
                                    className="flex-1 py-2 rounded-xl text-sm bg-red-500 text-white hover:bg-red-600"
                                >
                                    Delete
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
