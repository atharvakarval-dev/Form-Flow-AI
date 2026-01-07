"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    User, Shield, Edit3, Trash2, ToggleLeft, ToggleRight,
    Save, X, AlertTriangle, CheckCircle, Brain, Loader2
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
 * - View behavioral profile
 * - Edit profile text
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
            const wordCount = editText.trim().split(/\s+/).length
            if (wordCount > 500) {
                setMessage({ type: 'error', text: `Profile exceeds 500 word limit (${wordCount} words)` })
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
            <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isDark ? 'bg-purple-500/20' : 'bg-purple-100'}`}>
                    <Brain className={`w-5 h-5 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} />
                </div>
                <div>
                    <h2 className={`font-semibold ${textClass}`}>Behavioral Profile</h2>
                    <p className={`text-xs ${subTextClass}`}>
                        AI-generated insights from your form interactions
                    </p>
                </div>
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

            {/* Profiling Toggle Card */}
            <div className={`rounded-2xl border p-5 ${cardBgClass}`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Shield className={`w-5 h-5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                        <div>
                            <div className={`font-medium ${textClass}`}>AI Profiling</div>
                            <div className={`text-xs ${subTextClass}`}>
                                {status?.profiling_enabled
                                    ? 'Your form interactions are analyzed to personalize suggestions'
                                    : 'Profiling is disabled - suggestions use patterns only'}
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={handleToggleProfiling}
                        className={`p-2 rounded-lg transition-all ${status?.profiling_enabled
                                ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                                : 'bg-zinc-500/20 text-zinc-400 hover:bg-zinc-500/30'
                            }`}
                    >
                        {status?.profiling_enabled ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                    </button>
                </div>
            </div>

            {/* Profile Content Card */}
            {profile ? (
                <div className={`rounded-2xl border p-5 ${cardBgClass}`}>
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <User className={`w-4 h-4 ${subTextClass}`} />
                            <span className={`text-sm font-medium ${textClass}`}>Your Profile</span>
                            <span className={`px-2 py-0.5 rounded-full text-xs ${profile.confidence_level === 'high' ? 'bg-green-500/20 text-green-400' :
                                    profile.confidence_level === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                        'bg-zinc-500/20 text-zinc-400'
                                }`}>
                                {Math.round(profile.confidence_score * 100)}% confidence
                            </span>
                        </div>
                        <div className="flex gap-2">
                            {!editing && (
                                <>
                                    <button
                                        onClick={() => setEditing(true)}
                                        className={`p-2 rounded-lg transition-all ${isDark ? 'hover:bg-white/10 text-white/60 hover:text-white' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-900'}`}
                                        title="Edit profile"
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
                            <textarea
                                value={editText}
                                onChange={(e) => setEditText(e.target.value)}
                                rows={8}
                                className={`w-full p-3 rounded-xl border resize-none focus:outline-none focus:ring-2 focus:ring-purple-500/50 ${inputClass}`}
                                placeholder="Your behavioral profile..."
                            />
                            <div className="flex items-center justify-between">
                                <span className={`text-xs ${subTextClass}`}>
                                    {editText.trim().split(/\s+/).length}/500 words
                                </span>
                                <div className="flex gap-2">
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
                                        Save
                                    </button>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${subTextClass}`}>
                            {profile.profile_text}
                        </div>
                    )}

                    {/* Profile metadata */}
                    <div className={`mt-4 pt-4 border-t ${isDark ? 'border-white/10' : 'border-zinc-200'} flex gap-4 text-xs ${subTextClass}`}>
                        <span>Version {profile.version}</span>
                        <span>•</span>
                        <span>{profile.form_count} forms analyzed</span>
                        {profile.updated_at && (
                            <>
                                <span>•</span>
                                <span>Updated {new Date(profile.updated_at).toLocaleDateString()}</span>
                            </>
                        )}
                    </div>
                </div>
            ) : (
                <div className={`rounded-2xl border p-8 text-center ${cardBgClass}`}>
                    <div className={`w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`}>
                        <User className={`w-8 h-8 ${isDark ? 'text-white/20' : 'text-zinc-300'}`} />
                    </div>
                    <p className={subTextClass}>No profile yet</p>
                    <p className={`text-xs mt-1 ${subTextClass}`}>Complete some forms to generate your behavioral profile</p>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {showDeleteConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
                        onClick={() => setShowDeleteConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95 }}
                            animate={{ scale: 1 }}
                            exit={{ scale: 0.95 }}
                            onClick={(e) => e.stopPropagation()}
                            className={`p-6 rounded-2xl max-w-sm mx-4 ${isDark ? 'bg-zinc-900 border border-white/10' : 'bg-white border border-zinc-200 shadow-xl'}`}
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                                    <AlertTriangle className="w-5 h-5 text-red-400" />
                                </div>
                                <h3 className={`font-semibold ${textClass}`}>Delete Profile?</h3>
                            </div>
                            <p className={`text-sm mb-6 ${subTextClass}`}>
                                This will permanently delete your behavioral profile.
                                A new profile will be generated as you continue using the app.
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
