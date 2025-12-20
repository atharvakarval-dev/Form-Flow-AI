"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { CheckIcon, ArrowRightIcon, Loader2 } from "lucide-react"
import { register } from '@/services/api'

const steps = [
    { id: 1, label: "Identity", fields: ["first_name", "last_name"], placeholders: ["First Name", "Last Name"] },
    { id: 2, label: "Contact", fields: ["email", "mobile"], placeholders: ["Email Address", "Mobile Number"] },
    { id: 3, label: "Your Location", fields: ["country", "state", "city", "pincode"], placeholders: ["Country", "State", "City", "Pincode"] },
    { id: 4, label: "Security", fields: ["password"], placeholders: ["Create Password"] },
]

export function RegistrationForm() {
    const [currentStep, setCurrentStep] = useState(0)
    const [formData, setFormData] = useState({})
    const [isComplete, setIsComplete] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleNext = async () => {
        if (currentStep < steps.length - 1) {
            setCurrentStep(currentStep + 1)
        } else {
            setIsLoading(true)
            setError(null)
            try {
                await register(formData)
                setIsComplete(true)
            } catch (err) {
                setError(err.response?.data?.detail || "Registration failed. Please try again.")
            } finally {
                setIsLoading(false)
            }
        }
    }

    const handleInputChange = (field, value) => {
        setFormData({ ...formData, [field]: value })
    }

    const currentStepData = steps[currentStep]

    const isStepValid = () => {
        return currentStepData.fields.every(field => formData[field] && formData[field].trim() !== "")
    }

    if (isComplete) {
        return (
            <div className="w-full max-w-md mx-auto min-h-screen flex items-center justify-center p-4">
                {/* Success Card */}
                <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-black/40 p-12 backdrop-blur-xl w-full shadow-2xl">
                    {/* Window Header */}
                    <div className="absolute top-0 left-0 right-0 bg-white/5 p-3 flex items-center border-b border-white/5">
                        <div className="flex gap-2 ml-2">
                            <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
                        </div>
                    </div>

                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(120,119,198,0.1),transparent_50%)]" />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="relative flex flex-col items-center gap-6 text-center mt-4"
                    >
                        <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-green-500/20 bg-green-500/10">
                            <CheckIcon
                                className="h-10 w-10 text-green-500"
                                strokeWidth={2.5}
                            />
                        </div>
                        <div className="space-y-2">
                            <h2 className="text-2xl font-semibold tracking-tight text-white">Welcome, {formData.first_name}!</h2>
                            <p className="text-white/60">Your profile has been created successfully.</p>
                        </div>
                        <button
                            onClick={() => window.location.href = '/'}
                            className="mt-4 px-6 py-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors backdrop-blur-md border border-white/10"
                        >
                            Go to Dashboard
                        </button>
                    </motion.div>
                </div>
            </div>
        )
    }

    return (
        <div className="w-full min-h-screen flex items-center justify-center p-4 font-sans relative z-10 text-white">
            <div className="w-full max-w-4xl">

                {/* Form Container as a Window */}
                <div className="bg-black/40 border border-white/20 rounded-2xl backdrop-blur-2xl shadow-2xl relative overflow-hidden flex flex-col min-h-[600px]">

                    {/* Window Header */}
                    <div className="bg-white/5 p-4 flex items-center justify-between border-b border-white/10 shrink-0">
                        <div className="flex gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-400/80"></div>
                            <div className="w-3 h-3 rounded-full bg-green-400/80"></div>
                        </div>
                        <div className="text-xs font-semibold text-white/40 flex items-center gap-2 font-mono uppercase tracking-widest">
                            user_registration.exe
                        </div>
                        <div className="w-14"></div> {/* Spacer */}
                    </div>

                    <div className="flex flex-1 flex-col md:flex-row h-full">
                        {/* Sidebar / Progress */}
                        <div className="w-full md:w-1/3 bg-black/20 p-8 border-r border-white/10 flex flex-col justify-between">
                            <div>
                                <h1 className="text-xl font-bold text-white mb-2">Create Account</h1>
                                <p className="text-white/40 text-sm mb-8">Setup your persistent profile for auto-filling.</p>

                                <div className="flex flex-col gap-6 relative">
                                    {/* Connecting Line */}
                                    <div className="absolute left-[19px] top-4 bottom-4 w-0.5 bg-white/10 z-0 hidden md:block">
                                        <motion.div
                                            className="w-full bg-white/50 origin-top"
                                            initial={{ height: 0 }}
                                            animate={{ height: `${(currentStep / (steps.length - 1)) * 100}%` }}
                                            transition={{ duration: 0.5 }}
                                        />
                                    </div>

                                    {steps.map((step, index) => (
                                        <div key={step.id} className="flex items-center gap-4 relative z-10">
                                            <div
                                                className={`relative flex h-10 w-10 items-center justify-center rounded-full transition-all duration-500 border z-10
                                    ${index < currentStep ? "bg-[#09090b] border-green-500/30 text-green-400" : ""}
                                    ${index === currentStep ? "bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.3)] border-transparent scale-110" : ""}
                                    ${index > currentStep ? "bg-[#09090b] border-white/10 text-white/20" : ""}
                                    `}
                                            >
                                                {index < currentStep ? (
                                                    <CheckIcon className="h-5 w-5" strokeWidth={2.5} />
                                                ) : (
                                                    <span className="text-sm font-bold">{step.id}</span>
                                                )}
                                            </div>
                                            <div className={`flex flex-col transition-opacity duration-300 ${index === currentStep ? "opacity-100" : "opacity-50"}`}>
                                                <span className="text-sm font-medium text-white">{step.label}</span>
                                                {index === currentStep && <span className="text-xs text-green-400 font-mono mt-0.5">In Progress</span>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="text-xs text-white/20 mt-8 font-mono">
                                SECURED CONNECTION<br />
                                v2.4.0-stable
                            </div>
                        </div>

                        {/* Main Content */}
                        <div className="flex-1 p-8 md:p-12 relative flex flex-col justify-center bg-transparent">
                            {/* Background decoration */}
                            <div className="absolute top-0 right-0 p-32 bg-green-500/10 blur-[100px] rounded-full pointer-events-none" />

                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={currentStep}
                                    initial={{ opacity: 0, y: 10, filter: "blur(10px)" }}
                                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                                    exit={{ opacity: 0, y: -10, filter: "blur(10px)" }}
                                    transition={{ duration: 0.4 }}
                                    className="space-y-8 relative z-10"
                                >
                                    <div className="space-y-2">
                                        <h2 className="text-4xl font-bold tracking-tight text-white drop-shadow-lg">
                                            {currentStepData.label}
                                        </h2>
                                        <p className="text-white/60 text-lg">Please enter details for {currentStepData.label.toLowerCase()} verification.</p>
                                    </div>

                                    <div className="grid gap-5">
                                        {currentStepData.fields.map((field, idx) => (
                                            <div key={field} className="space-y-2 group">
                                                <label className="text-xs text-white/50 uppercase font-semibold tracking-wider ml-1 group-focus-within:text-green-400 transition-colors">
                                                    {currentStepData.placeholders[idx]}
                                                </label>
                                                <input
                                                    type={field.includes('password') ? 'password' : field === 'email' ? 'email' : 'text'}
                                                    value={formData[field] || ""}
                                                    onChange={(e) => handleInputChange(field, e.target.value)}
                                                    placeholder={`Enter ${currentStepData.placeholders[idx]}...`}
                                                    className="w-full h-14 bg-white/5 border border-white/10 rounded-xl px-5 text-white placeholder-white/20 focus:outline-none focus:border-green-500/50 focus:bg-white/5 focus:ring-1 focus:ring-green-500/20 transition-all text-lg backdrop-blur-sm"
                                                    autoFocus={idx === 0}
                                                />
                                            </div>
                                        ))}
                                    </div>

                                    {error && (
                                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-center gap-3">
                                            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                                            {error}
                                        </div>
                                    )}

                                    <div className="pt-8 flex gap-4">
                                        {currentStep > 0 && (
                                            <button
                                                onClick={() => setCurrentStep(currentStep - 1)}
                                                className="h-14 px-8 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-all backdrop-blur-sm border border-white/5"
                                            >
                                                Back
                                            </button>
                                        )}
                                        <button
                                            onClick={handleNext}
                                            disabled={!isStepValid() || isLoading}
                                            className="flex-1 h-14 rounded-xl bg-white text-black font-bold hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-3 group shadow-lg shadow-white/5"
                                        >
                                            {isLoading ? (
                                                <Loader2 className="h-5 w-5 animate-spin" />
                                            ) : (
                                                <>
                                                    {currentStep === steps.length - 1 ? "Complete Registration" : "Continue"}
                                                    <ArrowRightIcon className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </motion.div>
                            </AnimatePresence>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
