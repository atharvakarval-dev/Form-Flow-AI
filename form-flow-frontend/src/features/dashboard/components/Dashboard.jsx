"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Clock, ExternalLink, FileText, CheckCircle2, XCircle } from "lucide-react"
import api from '@/services/api'
import { ROUTES } from '@/constants'

export function Dashboard() {
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(true)
    const [user, setUser] = useState(null)

    useEffect(() => {
        fetchHistory()
    }, [])

    const fetchHistory = async () => {
        const token = localStorage.getItem('token')
        if (!token) {
            window.location.href = ROUTES.LOGIN
            return
        }

        try {
            // Fetch User Info (includes submissions now)
            const userRes = await api.get("/users/me")
            setUser(userRes.data)

            // Use submissions from user profile if available, otherwise default to empty
            if (userRes.data.submissions) {
                // Sort by ID descending (newest first) since timestamp might be same string
                const sorted = [...userRes.data.submissions].sort((a, b) => b.id - a.id);
                setHistory(sorted);
            }
        } catch (err) {
            console.error("Dashboard fetch error:", err);
            // Only logout on auth error
            if (err.response && err.response.status === 401) {
                localStorage.removeItem('token')
                window.location.href = ROUTES.LOGIN
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="w-full min-h-screen p-6 md:p-12 font-sans relative z-10 text-white">
            <div className="max-w-5xl mx-auto space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
                        <p className="text-white/60 mt-1">
                            Welcome back, {user?.first_name || 'User'}
                        </p>
                    </div>
                </div>

                {/* Stats / Overview */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-xl">
                        <div className="text-white/40 text-sm font-medium uppercase tracking-wider mb-2">Total Forms</div>
                        <div className="text-4xl font-bold">{history.length}</div>
                    </div>
                    <div className="bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-xl">
                        <div className="text-white/40 text-sm font-medium uppercase tracking-wider mb-2">Success Rate</div>
                        <div className="text-4xl font-bold text-green-400">
                            {history.length > 0
                                ? Math.round((history.filter(h => h.status === 'Success').length / history.length) * 100)
                                : 0}%
                        </div>
                    </div>
                </div>

                {/* History List */}
                <div className="bg-black/40 border border-white/20 rounded-3xl backdrop-blur-2xl shadow-2xl overflow-hidden min-h-[400px]">
                    {/* Window Header */}
                    <div className="bg-white/5 p-4 flex items-center border-b border-white/10 shrink-0 gap-4">
                        <div className="flex gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
                        </div>
                        <div className="text-xs font-semibold text-white/40 font-mono uppercase tracking-widest">
                            submission_history.log
                        </div>
                    </div>

                    <div className="p-0">
                        {loading ? (
                            <div className="p-12 text-center text-white/40">Loading history...</div>
                        ) : history.length === 0 ? (
                            <div className="p-12 text-center flex flex-col items-center gap-4">
                                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                                    <FileText className="h-8 w-8 text-white/20" />
                                </div>
                                <p className="text-white/40">No forms submitted yet.</p>
                                <a href={ROUTES.HOME} className="text-green-400 hover:underline">Fill your first form</a>
                            </div>
                        ) : (
                            <div className="divide-y divide-white/5">
                                {history.map((item) => (
                                    <motion.div
                                        key={item.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="p-5 flex items-center justify-between hover:bg-white/5 transition-colors group"
                                    >
                                        <div className="flex items-center gap-4">
                                            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${item.status === 'Success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                                                }`}>
                                                {item.status === 'Success' ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
                                            </div>
                                            <div>
                                                <div className="font-medium text-white group-hover:text-green-200 transition-colors truncate max-w-[300px] md:max-w-[500px]">
                                                    {item.form_url}
                                                </div>
                                                <div className="text-xs text-white/40 flex items-center gap-2 mt-1">
                                                    <Clock className="h-3 w-3" />
                                                    {new Date(item.timestamp).toLocaleString(undefined, {
                                                        dateStyle: 'medium',
                                                        timeStyle: 'short'
                                                    })}
                                                </div>
                                            </div>
                                        </div>

                                        <a
                                            href={item.form_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="p-2 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
                                            title="Open Form URL"
                                        >
                                            <ExternalLink className="h-5 w-5" />
                                        </a>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
