import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, Smartphone, Globe, Zap, Layout, Keyboard, Sparkles, CheckCircle2, ShieldCheck } from "lucide-react";

const ANIMATION_EASE = [0.16, 1, 0.3, 1];

/**
 * Smart Auto-Fill Animation
 */
function AutoFillDemo() {
    const [text, setText] = useState("");
    const fullText = "Alexandra Chen";

    useEffect(() => {
        let index = 0;
        const interval = setInterval(() => {
            setText(fullText.slice(0, index + 1));
            index = (index + 1) % (fullText.length + 12);
        }, 150);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex items-center justify-center w-full h-full">
            <div className="bg-white rounded-xl border border-zinc-100 p-5 shadow-sm w-full max-w-[220px]">
                <div className="flex gap-2 mb-3">
                    <div className="w-8 h-8 rounded-full bg-zinc-100" />
                    <div className="space-y-1">
                        <div className="w-20 h-2 bg-zinc-100 rounded-full" />
                        <div className="w-12 h-2 bg-zinc-50 rounded-full" />
                    </div>
                </div>
                <div className="space-y-3">
                    <div>
                        <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Full Name</div>
                        <div className="flex items-center h-9 px-3 bg-zinc-50 rounded-md border border-zinc-100">
                            <span className="text-sm font-medium text-zinc-800">
                                {text}
                            </span>
                            <motion.div
                                animate={{ opacity: [1, 0] }}
                                transition={{ repeat: Infinity, duration: 0.8 }}
                                className="w-0.5 h-4 bg-emerald-500 ml-0.5"
                            />
                        </div>
                    </div>
                    <div className="opacity-40">
                        <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Email</div>
                        <div className="h-9 w-full bg-zinc-50 rounded-md border border-zinc-100" />
                    </div>
                </div>
            </div>
        </div>
    );
}

/**
 * Universal Form Support Animation
 */
function UniversalSupportAnim() {
    const [layout, setLayout] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setLayout((prev) => (prev + 1) % 3);
        }, 2800);
        return () => clearInterval(interval);
    }, []);

    const layouts = ["grid-cols-1", "grid-cols-2", "flex flex-col gap-2"];

    return (
        <div className="h-full flex items-center justify-center w-full">
            <motion.div
                className={`grid ${layout === 2 ? "" : layouts[layout]} gap-2 w-full max-w-[180px] p-4 bg-white rounded-xl border border-zinc-100 shadow-sm transition-all duration-500`}
                layout
                transition={{ duration: 0.6, ease: ANIMATION_EASE }}
            >
                <div className="col-span-full h-2 w-1/3 bg-zinc-100 rounded-full mb-1" />
                {[1, 2, 3].map((i) => (
                    <motion.div
                        key={i}
                        layout
                        className={`rounded-lg h-10 w-full border border-zinc-100 ${i === 1 ? "bg-emerald-50/50 border-emerald-100/50" : "bg-zinc-50/50"
                            }`}
                        transition={{ duration: 0.6, ease: ANIMATION_EASE }}
                    />
                ))}
                <motion.button
                    layout
                    className="col-span-full h-8 bg-zinc-900 rounded-lg mt-1"
                    transition={{ duration: 0.6, ease: ANIMATION_EASE }}
                />
            </motion.div>
        </div>
    );
}

/**
 * Speed Metric
 */
function SpeedMetric() {
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setProgress(0);
            setTimeout(() => setProgress(100), 100);
        }, 3000)
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center justify-center h-full w-full gap-6">
            <div className="relative">
                <svg className="w-24 h-24 -rotate-90">
                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-zinc-100" />
                    <motion.circle
                        cx="48" cy="48" r="40"
                        stroke="currentColor" strokeWidth="6"
                        fill="transparent"
                        className="text-emerald-500"
                        strokeLinecap="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: progress / 100 }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-zinc-900">0.2s</span>
                </div>
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium">
                <Zap className="w-3 h-3 fill-emerald-700" />
                <span>Instant Execution</span>
            </div>
        </div>
    );
}

/**
 * Enterprise Security Shield
 */
function SecurityShield() {
    return (
        <div className="flex items-center justify-center h-full w-full">
            <div className="relative">
                {/* Background Rings */}
                <div className="absolute inset-0 bg-emerald-500/10 blur-2xl rounded-full" />

                <div className="relative w-32 h-32 bg-white rounded-2xl border border-zinc-100 shadow-xl flex items-center justify-center overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(#e4e4e7_1px,transparent_1px)] [background-size:16px_16px] opacity-20" />

                    <motion.div
                        animate={{ scale: [1, 1.05, 1] }}
                        transition={{ duration: 3, repeat: Infinity }}
                    >
                        <ShieldCheck className="w-12 h-12 text-emerald-500" />
                    </motion.div>

                    {/* Animated Scan Line */}
                    <motion.div
                        className="absolute top-0 left-0 w-full h-1 bg-emerald-400/30 blur-[2px]"
                        animate={{ top: ["0%", "100%", "0%"] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                    />
                </div>

                {/* Floating Badges */}
                <motion.div
                    className="absolute -top-3 -right-3 bg-zinc-900 text-white text-[10px] font-bold px-2 py-1 rounded-md shadow-lg flex items-center gap-1"
                    animate={{ y: [0, -5, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                >
                    <Lock className="w-3 h-3" />
                    256-BIT
                </motion.div>
            </div>
        </div>
    );
}

/**
 * Cloud Sync / Global
 */
function CloudSyncAnim() {
    return (
        <div className="flex items-center justify-center h-full w-full relative">
            {/* Central Hub */}
            <div className="relative z-10 w-16 h-16 bg-white rounded-2xl border border-zinc-100 shadow-lg flex items-center justify-center">
                <Globe className="w-8 h-8 text-zinc-900" />
            </div>

            {/* Orbiting Browsers */}
            {[0, 120, 240].map((deg, i) => (
                <motion.div
                    key={i}
                    className="absolute w-full h-full flex items-center justify-center"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 20, repeat: Infinity, ease: "linear", delay: -i * 10 }}
                >
                    <motion.div
                        className="w-10 h-10 bg-white rounded-xl border border-zinc-100 shadow-md flex items-center justify-center absolute -top-8"
                        animate={{ rotate: -360 }} // Counter-rotate to keep icon upright
                        transition={{ duration: 20, repeat: Infinity, ease: "linear", delay: -i * 10 }}
                    >
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                    </motion.div>
                </motion.div>
            ))}

            <div className="absolute inset-0 border border-dashed border-zinc-200 rounded-full scale-150 opacity-50" />
        </div>
    );
}

/**
 * Mobile/Voice Command Demo
 */
function VoiceCommandAnim() {
    return (
        <div className="flex items-center justify-center h-full w-full">
            <div className="relative">
                {/* Phone Frame */}
                <div className="relative w-[140px] h-[240px] bg-white rounded-[2rem] border-[6px] border-zinc-900 shadow-2xl overflow-hidden z-10">
                    {/* Notch */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-16 h-4 bg-zinc-900 rounded-b-xl z-20" />

                    {/* Screen Content */}
                    <div className="pt-8 px-4 flex flex-col h-full bg-zinc-50">
                        <div className="flex items-center gap-2 mb-6">
                            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center">
                                <div className="w-4 h-4 bg-emerald-500 rounded-full" />
                            </div>
                            <div className="space-y-1">
                                <div className="w-12 h-1.5 bg-zinc-200 rounded-full" />
                                <div className="w-20 h-1.5 bg-zinc-100 rounded-full" />
                            </div>
                        </div>

                        {/* Voice Visualizer */}
                        <div className="mt-auto mb-8 flex flex-col items-center">
                            <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-3">Listening...</div>
                            <div className="flex items-end gap-1 h-8">
                                {[1, 2, 3, 4, 3, 2, 1].map((h, i) => (
                                    <motion.div
                                        key={i}
                                        className="w-1 bg-zinc-900 rounded-full"
                                        animate={{ height: [8, 24, 12, 32, 16][i % 5] }}
                                        transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.1 }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Decoration Blob */}
                <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-2xl" />
            </div>
        </div>
    )
}

function FeatureCard({ children, className, title, description, icon: Icon, delay = 0 }) {
    return (
        <motion.div
            className={`
                group relative bg-white rounded-3xl p-1 overflow-hidden
                border border-zinc-100 hover:border-zinc-200 hover:shadow-xl hover:shadow-zinc-200/50 
                transition-all duration-500
                ${className}
            `}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ delay, duration: 0.5, ease: "easeOut" }}
            whileHover={{ y: -4 }}
        >
            <div className="absolute inset-0 bg-gradient-to-br from-zinc-50/50 via-white to-white opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <div className="relative h-full flex flex-col rounded-[1.3rem] overflow-hidden bg-white">
                {/* Content Container */}
                <div className="flex-1 min-h-[180px] bg-zinc-50/30 flex items-center justify-center p-6 border-b border-zinc-50">
                    {children}
                </div>

                {/* Bottom Text */}
                <div className="p-8 bg-white">
                    <div className="flex items-start justify-between mb-3">
                        <div className="p-2.5 bg-zinc-50 rounded-xl group-hover:bg-emerald-50 transition-colors duration-300">
                            <Icon className="w-5 h-5 text-zinc-900 group-hover:text-emerald-600 transition-colors duration-300" />
                        </div>
                    </div>
                    <h3 className="text-xl font-semibold text-zinc-900 mb-2">{title}</h3>
                    <p className="text-sm text-zinc-500 leading-relaxed font-medium">{description}</p>
                </div>
            </div>
        </motion.div>
    );
}

function FeaturesGrid() {
    return (
        <section className="bg-white px-4 md:px-6 py-32 flex items-center justify-center relative overflow-hidden">
            <div className="max-w-[1400px] w-full mx-auto relative z-10">

                {/* Header Section */}
                <div className="mb-24 flex flex-col md:flex-row md:items-end justify-between gap-8 md:gap-20">
                    <div className="max-w-2xl">
                        <motion.div
                            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 border border-zinc-200 text-zinc-600 text-xs font-semibold uppercase tracking-wider mb-6"
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                        >
                            <Sparkles className="w-3 h-3 fill-zinc-400 text-zinc-400" />
                            Capabilities
                        </motion.div>

                        <motion.h2
                            className="text-4xl md:text-6xl font-semibold text-zinc-900 tracking-tight leading-[1.1]"
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                        >
                            Built for speed and <span className="text-zinc-400">precision.</span>
                        </motion.h2>
                    </div>

                    <motion.p
                        className="text-lg text-zinc-500 max-w-md leading-relaxed mb-1"
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.2 }}
                    >
                        Our intelligent agents analyze, adapt, and execute form submissions with human-like accuracy at machine speeds.
                    </motion.p>
                </div>

                {/* Bento Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                    {/* Row 1 */}
                    <FeatureCard
                        className="md:col-start-1"
                        title="Smart Auto-Fill"
                        description="Our agents type naturally, detecting fields contextually to fill widely different forms accurately."
                        icon={Keyboard}
                        delay={0.1}
                    >
                        <AutoFillDemo />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-start-2"
                        title="Adaptive Layouts"
                        description="Intelligent DOM parsing allows our system to adapt to any form structure instantly."
                        icon={Layout}
                        delay={0.2}
                    >
                        <UniversalSupportAnim />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-start-3"
                        title="Lightning Fast"
                        description="Optimized execution pipeline ensures submissions happen in milliseconds, not seconds."
                        icon={Zap}
                        delay={0.3}
                    >
                        <SpeedMetric />
                    </FeatureCard>

                    {/* Row 2 - Wide Cards */}
                    <FeatureCard
                        className="md:col-span-2"
                        title="Enterprise Security"
                        description="End-to-end encryption with zero-retention policy. Your data is processed securely in isolated environments and wiped immediately after submission. GDPR & CCPA compliant."
                        icon={Lock}
                        delay={0.4}
                    >
                        <SecurityShield />
                    </FeatureCard>

                    <FeatureCard
                        className="md:col-span-1"
                        title="Browser Agnostic"
                        description="Seamless operation across Chrome, Firefox, and Edge via our cloud pool."
                        icon={Globe}
                        delay={0.5}
                    >
                        <CloudSyncAnim />
                    </FeatureCard>

                    {/* Row 3 - Full Width Feature */}
                    <motion.div
                        className="md:col-span-3 bg-zinc-900 rounded-[2.5rem] p-8 md:p-12 overflow-hidden relative group"
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.6 }}
                    >
                        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[120px] pointer-events-none" />

                        <div className="relative z-10 flex flex-col md:flex-row items-center gap-12 md:gap-24">
                            <div className="flex-1 text-center md:text-left">
                                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-800 border border-zinc-700 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-6">
                                    <Smartphone className="w-3 h-3" />
                                    Voice Control
                                </div>
                                <h3 className="text-3xl md:text-4xl font-semibold text-white mb-6">"Fill this form for me."</h3>
                                <p className="text-lg text-zinc-400 leading-relaxed max-w-xl">
                                    Just say the word. Our voice agent parses your intent from natural language and executes complex form filling tasks hands-free.
                                </p>

                                <div className="mt-8 flex flex-col md:flex-row items-center gap-4 text-sm font-medium text-zinc-300">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        <span>High Accuracy ASR</span>
                                    </div>
                                    <div className="hidden md:block w-1 h-1 bg-zinc-700 rounded-full" />
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        <span>Context Awareness</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 flex justify-center md:justify-end">
                                <VoiceCommandAnim />
                            </div>
                        </div>
                    </motion.div>

                </div>
            </div>
        </section>
    );
}

export default FeaturesGrid;
