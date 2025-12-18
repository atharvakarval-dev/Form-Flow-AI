"use client"

import { useState } from "react"
import axios from "axios"
import { motion } from "framer-motion"
import { ArrowRightIcon, Loader2, LockIcon, MailIcon } from "lucide-react"

export function LoginForm() {
    const [formData, setFormData] = useState({ email: "", password: "" })
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleLogin = async (e) => {
        e.preventDefault()
        setIsLoading(true)
        setError(null)

        try {
            const form = new FormData()
            form.append('username', formData.email)
            form.append('password', formData.password)

            const response = await axios.post("http://localhost:8000/login", form)

            // Store token
            localStorage.setItem('token', response.data.access_token)
            localStorage.setItem('user_email', formData.email)

            // Redirect to Dashboard
            window.location.href = '/dashboard'

        } catch (err) {
            setError("Invalid email or password.")
        } finally {
            setIsLoading(false)
        }
    }

    const handleInputChange = (field, value) => {
        setFormData({ ...formData, [field]: value })
    }

    return (
        <div className="w-full min-h-screen flex items-center justify-center p-4 font-sans relative z-10 text-white">
            <div className="w-full max-w-md">

                {/* Window Container */}
                <div className="bg-black/40 border border-white/20 rounded-2xl backdrop-blur-2xl shadow-2xl relative overflow-hidden flex flex-col">

                    {/* Window Header */}
                    <div className="bg-white/5 p-4 flex items-center justify-between border-b border-white/10 shrink-0">
                        <div className="flex gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
                        </div>
                        <div className="text-xs font-semibold text-white/40 flex items-center gap-2 font-mono uppercase tracking-widest">
                            secure_login.exe
                        </div>
                        <div className="w-14"></div>
                    </div>

                    {/* Content */}
                    <div className="p-8 md:p-10 relative flex flex-col justify-center">
                        {/* Background decoration */}
                        <div className="absolute top-0 right-0 p-32 bg-green-500/10 blur-[100px] rounded-full pointer-events-none" />

                        <div className="space-y-6 relative z-10">
                            <div className="space-y-2 text-center">
                                <h2 className="text-3xl font-bold tracking-tight text-white drop-shadow-lg">
                                    Welcome Back
                                </h2>
                                <p className="text-white/60">Enter your credentials to access your history.</p>
                            </div>

                            <form onSubmit={handleLogin} className="space-y-5 mt-4">
                                <div className="space-y-5">
                                    <div className="space-y-2 group">
                                        <label className="text-xs text-white/50 uppercase font-semibold tracking-wider ml-1">Email</label>
                                        <div className="relative">
                                            <MailIcon className="absolute left-4 top-4 h-5 w-5 text-white/60 pointer-events-none" />
                                            <input
                                                type="email"
                                                required
                                                value={formData.email}
                                                onChange={(e) => handleInputChange("email", e.target.value)}
                                                placeholder="name@example.com"
                                                className="w-full h-12 bg-black/20 border border-white/10 rounded-xl pl-12 pr-5 text-white placeholder-white/20 focus:outline-none focus:border-green-500/50 focus:bg-black/40 focus:ring-1 focus:ring-green-500/20 transition-all"
                                            />
                                        </div>
                                    </div>

                                    <div className="space-y-2 group">
                                        <label className="text-xs text-white/50 uppercase font-semibold tracking-wider ml-1">Password</label>
                                        <div className="relative">
                                            <LockIcon className="absolute left-4 top-4 h-5 w-5 text-white/60 pointer-events-none" />
                                            <input
                                                type="password"
                                                required
                                                value={formData.password}
                                                onChange={(e) => handleInputChange("password", e.target.value)}
                                                placeholder="••••••••"
                                                className="w-full h-12 bg-black/20 border border-white/10 rounded-xl pl-12 pr-5 text-white placeholder-white/20 focus:outline-none focus:border-green-500/50 focus:bg-black/40 focus:ring-1 focus:ring-green-500/20 transition-all"
                                            />
                                        </div>
                                    </div>
                                </div>

                                {error && (
                                    <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-center justify-center gap-2">
                                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                                        {error}
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full h-12 rounded-xl bg-white text-black font-bold hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 group shadow-lg shadow-white/5 mt-2"
                                >
                                    {isLoading ? (
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                    ) : (
                                        <>
                                            Sign In
                                            <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                                        </>
                                    )}
                                </button>
                            </form>

                            <div className="text-center pt-2">
                                <a href="/register" className="text-sm text-white/40 hover:text-white transition-colors">
                                    Don't have an account? <span className="text-green-400 underline decoration-green-400/30 underline-offset-4">Sign up</span>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
