"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    Clock, ExternalLink, FileText, CheckCircle2, XCircle, TrendingUp,
    PieChart, BarChart3, User, Sparkles, Target, Zap, Activity,
    ArrowUpRight, Trophy, Flame, Calendar
} from "lucide-react"
import api, { getAnalytics } from '@/services/api'
import { ROUTES } from '@/constants'
import { useTheme } from '@/context/ThemeProvider'
import { SubmissionTrendChart, SuccessRateChart, FieldTypesChart, FormTypeChart, TopDomainsChart, ActivityHourlyChart } from './AnalyticsCharts'
import { AIInsights } from './AIInsights'
import { ProfileSettings } from './ProfileSettings'

const ITEMS_PER_PAGE = 5;

// Bento Card Component - Reusable with variants
function BentoCard({ children, className = "", size = "default", glow = false, accent = null }) {
    const { isDark } = useTheme();

    const baseClasses = `
        relative overflow-hidden rounded-2xl border transition-all duration-300
        ${isDark
            ? 'bg-zinc-900/70 border-white/[0.08] hover:border-white/[0.15]'
            : 'bg-white/70 border-zinc-200/80 hover:border-zinc-300 shadow-lg shadow-zinc-200/20'
        }
        backdrop-blur-xl
    `;

    const sizeClasses = {
        default: 'p-5',
        lg: 'p-6',
        xl: 'p-8',
        compact: 'p-4'
    };

    const glowEffect = glow && isDark ? 'shadow-[0_0_50px_-20px_rgba(139,92,246,0.3)]' : '';

    const accentStyles = {
        purple: 'before:absolute before:inset-0 before:bg-gradient-to-br before:from-purple-500/10 before:to-transparent before:pointer-events-none',
        blue: 'before:absolute before:inset-0 before:bg-gradient-to-br before:from-blue-500/10 before:to-transparent before:pointer-events-none',
        green: 'before:absolute before:inset-0 before:bg-gradient-to-br before:from-emerald-500/10 before:to-transparent before:pointer-events-none',
        amber: 'before:absolute before:inset-0 before:bg-gradient-to-br before:from-amber-500/10 before:to-transparent before:pointer-events-none',
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
            className={`${baseClasses} ${sizeClasses[size]} ${glowEffect} ${accent ? accentStyles[accent] : ''} ${className}`}
        >
            {children}
        </motion.div>
    );
}

// Stat Card with icon and trend
function StatCard({ icon: Icon, label, value, trend, color = "blue", delay = 0 }) {
    const { isDark } = useTheme();

    const colorStyles = {
        blue: { bg: 'bg-blue-500/10', text: 'text-blue-400', glow: 'shadow-blue-500/20' },
        green: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', glow: 'shadow-emerald-500/20' },
        purple: { bg: 'bg-purple-500/10', text: 'text-purple-400', glow: 'shadow-purple-500/20' },
        amber: { bg: 'bg-amber-500/10', text: 'text-amber-400', glow: 'shadow-amber-500/20' },
    };

    const style = colorStyles[color];

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay, duration: 0.4 }}
            className="flex items-center gap-4"
        >
            <div className={`w-12 h-12 rounded-xl ${style.bg} flex items-center justify-center shadow-lg ${style.glow}`}>
                <Icon className={`w-5 h-5 ${style.text}`} />
            </div>
            <div className="flex-1">
                <p className={`text-xs font-medium uppercase tracking-wider ${isDark ? 'text-white/40' : 'text-zinc-500'}`}>
                    {label}
                </p>
                <div className="flex items-baseline gap-2">
                    <span className={`text-2xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                        {value}
                    </span>
                    {trend && (
                        <span className={`text-xs font-medium flex items-center gap-0.5 ${trend > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            <ArrowUpRight className={`w-3 h-3 ${trend < 0 ? 'rotate-180' : ''}`} />
                            {Math.abs(trend)}%
                        </span>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

export function Dashboard() {
    const { isDark } = useTheme();
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(true)
    const [user, setUser] = useState(null)
    const [analytics, setAnalytics] = useState(null)
    const [analyticsLoading, setAnalyticsLoading] = useState(false)
    const [currentPage, setCurrentPage] = useState(1)
    const [activeTab, setActiveTab] = useState('analytics');

    const chartData = analytics?.charts || generateChartsFromHistory(history);

    // Calculate stats
    const successRate = analytics?.summary?.success_rate ||
        (history.length > 0 ? Math.round((history.filter(h => h.status === 'Success').length / history.length) * 100) : 0);
    const timeSaved = analytics?.summary?.avg_time_saved_seconds
        ? `${Math.round(analytics.summary.avg_time_saved_seconds / 60)}m`
        : `${history.length * 3}m`;
    const totalForms = analytics?.summary?.total_forms || history.length;
    const streakDays = analytics?.summary?.streak_days || 0;

    useEffect(() => {
        fetchHistory()
        fetchAnalytics()
    }, [])

    const fetchHistory = async () => {
        const token = localStorage.getItem('token')
        if (!token) {
            window.location.href = ROUTES.LOGIN
            return
        }

        try {
            const userRes = await api.get("/users/me")
            setUser(userRes.data)

            if (userRes.data.submissions) {
                const sorted = [...userRes.data.submissions].sort((a, b) => b.id - a.id);
                setHistory(sorted);
            }
        } catch (err) {
            console.error("Dashboard fetch error:", err);
            if (err.response && err.response.status === 401) {
                localStorage.removeItem('token')
                window.location.href = ROUTES.LOGIN
            }
        } finally {
            setLoading(false)
        }
    }

    const fetchAnalytics = async () => {
        setAnalyticsLoading(true)
        try {
            const data = await getAnalytics()
            setAnalytics(data)
        } catch (err) {
            console.error("Analytics fetch error:", err)
        } finally {
            setAnalyticsLoading(false)
        }
    }

    function generateChartsFromHistory(submissions) {
        if (!submissions || submissions.length === 0) return null;

        const today = new Date();
        const submissions_by_day = [];
        for (let i = 6; i >= 0; i--) {
            const day = new Date(today);
            day.setDate(day.getDate() - i);
            const dayStr = day.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const count = submissions.filter(s => {
                const subDate = new Date(s.timestamp);
                return subDate.toDateString() === day.toDateString();
            }).length;
            submissions_by_day.push({ date: dayStr, count });
        }

        const totalFields = submissions.length * 8;
        const field_types = [
            { name: "Text", value: Math.round(totalFields * 0.35) },
            { name: "Email", value: Math.round(totalFields * 0.15) },
            { name: "Phone", value: Math.round(totalFields * 0.12) },
            { name: "Select", value: Math.round(totalFields * 0.18) },
            { name: "Checkbox", value: Math.round(totalFields * 0.10) },
            { name: "Other", value: Math.round(totalFields * 0.10) },
        ];

        const success_by_type = [{
            type: "Standard",
            success: submissions.filter(s => s.status === 'Success').length,
            fail: submissions.filter(s => s.status !== 'Success').length
        }];

        const domainCounts = {};
        submissions.forEach(s => {
            try {
                const hostname = new URL(s.form_url).hostname.replace('www.', '');
                domainCounts[hostname] = (domainCounts[hostname] || 0) + 1;
            } catch (e) { }
        });
        const top_domains = Object.entries(domainCounts)
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 5);

        const hours = Array(24).fill(0).map((_, i) => ({ hour: i, count: 0 }));
        submissions.forEach(s => {
            const h = new Date(s.timestamp).getHours();
            if (hours[h]) hours[h].count++;
        });

        return { submissions_by_day, field_types, success_by_type, top_domains, activity_by_hour: hours };
    }

    const totalPages = Math.ceil(history.length / ITEMS_PER_PAGE);
    const paginatedHistory = history.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

    // Tab config
    const tabs = [
        { id: 'analytics', label: 'Analytics', icon: TrendingUp },
        { id: 'history', label: 'History', icon: FileText },
        { id: 'profile', label: 'Profile', icon: User },
    ];

    return (
        <div className={`w-full min-h-screen font-sans relative z-10 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
            {/* Subtle gradient background */}
            <div className="fixed inset-0 -z-10">
                <div className={`absolute inset-0 ${isDark ? 'bg-zinc-950' : 'bg-zinc-50'}`} />
                <div className={`absolute top-0 left-1/4 w-96 h-96 rounded-full blur-3xl opacity-20 ${isDark ? 'bg-purple-600' : 'bg-purple-200'}`} />
                <div className={`absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-3xl opacity-20 ${isDark ? 'bg-blue-600' : 'bg-blue-200'}`} />
            </div>

            <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">

                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col md:flex-row md:items-end md:justify-between gap-4"
                >
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <Sparkles className={`w-5 h-5 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} />
                            <span className={`text-sm font-medium ${isDark ? 'text-purple-400' : 'text-purple-600'}`}>
                                Welcome back
                            </span>
                        </div>
                        <h1 className="text-4xl font-bold tracking-tight">
                            {user?.first_name || 'User'}'s Dashboard
                        </h1>
                        <p className={`mt-2 ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>
                            Your form automation command center
                        </p>
                    </div>

                    {/* Tab Switcher */}
                    <div className={`
                        inline-flex items-center gap-1 p-1 rounded-xl
                        ${isDark ? 'bg-white/5 border border-white/10' : 'bg-zinc-100 border border-zinc-200'}
                    `}>
                        {tabs.map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`
                                    flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                                    ${activeTab === tab.id
                                        ? `${isDark
                                            ? 'bg-white/10 text-white shadow-lg'
                                            : 'bg-white text-zinc-900 shadow-md'
                                        }`
                                        : `${isDark
                                            ? 'text-white/50 hover:text-white/80'
                                            : 'text-zinc-500 hover:text-zinc-700'
                                        }`
                                    }
                                `}
                            >
                                <tab.icon className="w-4 h-4" />
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </motion.div>

                {/* Analytics Tab Content */}
                <AnimatePresence mode="wait">
                    {activeTab === 'analytics' && (
                        <motion.div
                            key="analytics"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            transition={{ duration: 0.3 }}
                            className="space-y-6"
                        >
                            {/* Top Stats Row - Bento Grid */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                <BentoCard accent="blue">
                                    <StatCard
                                        icon={Target}
                                        label="Total Forms"
                                        value={totalForms}
                                        trend={12}
                                        color="blue"
                                        delay={0}
                                    />
                                </BentoCard>

                                <BentoCard accent="green">
                                    <StatCard
                                        icon={CheckCircle2}
                                        label="Success Rate"
                                        value={`${successRate}%`}
                                        color="green"
                                        delay={0.1}
                                    />
                                </BentoCard>

                                <BentoCard accent="purple">
                                    <StatCard
                                        icon={Clock}
                                        label="Time Saved"
                                        value={timeSaved}
                                        color="purple"
                                        delay={0.2}
                                    />
                                </BentoCard>

                                <BentoCard accent="amber">
                                    <StatCard
                                        icon={Flame}
                                        label="Day Streak"
                                        value={streakDays || history.length}
                                        color="amber"
                                        delay={0.3}
                                    />
                                </BentoCard>
                            </div>

                            {/* Main Bento Grid */}
                            <div className="grid grid-cols-12 gap-4 auto-rows-[minmax(140px,auto)]">

                                {/* AI Insights - Featured Card */}
                                <BentoCard className="col-span-12 lg:col-span-5 row-span-2" size="lg" glow accent="purple">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center gap-3 mb-4">
                                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/25">
                                                <Sparkles className="w-5 h-5 text-white" />
                                            </div>
                                            <div>
                                                <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-zinc-900'}`}>AI Insights</h3>
                                                <p className={`text-xs ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>Powered by machine learning</p>
                                            </div>
                                        </div>
                                        <div className="flex-1 overflow-hidden">
                                            <AIInsights
                                                insights={analytics?.ai_insights}
                                                isLoading={analyticsLoading}
                                                onRefresh={fetchAnalytics}
                                            />
                                        </div>
                                    </div>
                                </BentoCard>

                                {/* Activity Trend Chart */}
                                <BentoCard className="col-span-12 lg:col-span-7 row-span-2" size="lg">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-10 h-10 rounded-xl ${isDark ? 'bg-amber-500/10' : 'bg-amber-50'} flex items-center justify-center`}>
                                                    <TrendingUp className="w-5 h-5 text-amber-500" />
                                                </div>
                                                <div>
                                                    <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-zinc-900'}`}>Activity Trend</h3>
                                                    <p className={`text-xs ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>Last 7 days</p>
                                                </div>
                                            </div>
                                            <div className={`px-3 py-1 rounded-full text-xs font-medium ${isDark ? 'bg-amber-500/10 text-amber-400' : 'bg-amber-50 text-amber-600'}`}>
                                                <Calendar className="w-3 h-3 inline mr-1" />
                                                Weekly
                                            </div>
                                        </div>
                                        <div className="flex-1 min-h-[200px]">
                                            <SubmissionTrendChart data={chartData?.submissions_by_day || []} />
                                        </div>
                                    </div>
                                </BentoCard>

                                {/* Success Rate Donut */}
                                <BentoCard className="col-span-6 lg:col-span-4 row-span-2" size="lg">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center gap-2 mb-2">
                                            <PieChart className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                                            <h3 className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-zinc-900'}`}>Success Rate</h3>
                                        </div>
                                        <div className="flex-1 min-h-[160px]">
                                            <SuccessRateChart successRate={successRate} />
                                        </div>
                                    </div>
                                </BentoCard>

                                {/* Hourly Activity */}
                                <BentoCard className="col-span-6 lg:col-span-4" size="compact">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center gap-2 mb-3">
                                            <Activity className={`w-4 h-4 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                                            <h3 className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-zinc-900'}`}>Peak Hours</h3>
                                        </div>
                                        <div className="flex-1 min-h-[100px]">
                                            <ActivityHourlyChart data={chartData?.activity_by_hour || []} />
                                        </div>
                                    </div>
                                </BentoCard>

                                {/* Field Composition */}
                                <BentoCard className="col-span-12 lg:col-span-4 row-span-2" size="lg">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center gap-2 mb-4">
                                            <BarChart3 className={`w-4 h-4 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} />
                                            <h3 className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-zinc-900'}`}>Field Types</h3>
                                        </div>
                                        <p className={`text-xs mb-4 ${isDark ? 'text-white/40' : 'text-zinc-500'}`}>
                                            Breakdown of all input types filled
                                        </p>
                                        <div className="flex-1 min-h-[120px]">
                                            <FieldTypesChart data={chartData?.field_types || []} />
                                        </div>
                                        {/* Legend */}
                                        <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-white/5">
                                            {(chartData?.field_types || []).slice(0, 6).map((type, i) => (
                                                <div key={type.name} className="flex items-center gap-1.5 text-[10px]">
                                                    <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: ['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981', '#EC4899', '#6366F1'][i] }} />
                                                    <span className={isDark ? 'text-white/60' : 'text-zinc-600'}>{type.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </BentoCard>

                                {/* Top Domains */}
                                <BentoCard className="col-span-12 lg:col-span-4" size="compact">
                                    <div className="h-full flex flex-col">
                                        <div className="flex items-center gap-2 mb-3">
                                            <ExternalLink className={`w-4 h-4 ${isDark ? 'text-pink-400' : 'text-pink-600'}`} />
                                            <h3 className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-zinc-900'}`}>Top Domains</h3>
                                        </div>
                                        <div className="flex-1 min-h-[100px]">
                                            <TopDomainsChart data={chartData?.top_domains || []} />
                                        </div>
                                    </div>
                                </BentoCard>

                            </div>
                        </motion.div>
                    )}

                    {/* History Tab Content */}
                    {activeTab === 'history' && (
                        <motion.div
                            key="history"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            transition={{ duration: 0.3 }}
                        >
                            <BentoCard size="lg" className="min-h-[500px]">
                                {/* Header */}
                                <div className="flex items-center justify-between mb-6">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-10 h-10 rounded-xl ${isDark ? 'bg-blue-500/10' : 'bg-blue-50'} flex items-center justify-center`}>
                                            <FileText className="w-5 h-5 text-blue-500" />
                                        </div>
                                        <div>
                                            <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-zinc-900'}`}>Submission History</h3>
                                            <p className={`text-xs ${isDark ? 'text-white/50' : 'text-zinc-500'}`}>
                                                {history.length} total submissions
                                            </p>
                                        </div>
                                    </div>
                                    {history.length > 0 && (
                                        <div className={`text-xs font-mono ${isDark ? 'text-white/40' : 'text-zinc-400'}`}>
                                            {(currentPage - 1) * ITEMS_PER_PAGE + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, history.length)} of {history.length}
                                        </div>
                                    )}
                                </div>

                                {loading ? (
                                    <div className={`p-12 text-center ${isDark ? 'text-white/40' : 'text-zinc-400'}`}>
                                        <div className="w-8 h-8 border-2 border-current border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                                        Loading history...
                                    </div>
                                ) : history.length === 0 ? (
                                    <div className="p-12 text-center flex flex-col items-center gap-4">
                                        <div className={`w-20 h-20 rounded-2xl flex items-center justify-center ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`}>
                                            <FileText className={`h-10 w-10 ${isDark ? 'text-white/20' : 'text-zinc-300'}`} />
                                        </div>
                                        <div>
                                            <p className={`font-medium ${isDark ? 'text-white/60' : 'text-zinc-600'}`}>No forms submitted yet</p>
                                            <p className={`text-sm mt-1 ${isDark ? 'text-white/40' : 'text-zinc-400'}`}>Your submission history will appear here</p>
                                        </div>
                                        <a href={ROUTES.HOME} className="mt-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 text-white text-sm font-medium hover:opacity-90 transition-opacity">
                                            Fill your first form
                                        </a>
                                    </div>
                                ) : (
                                    <>
                                        <div className={`divide-y ${isDark ? 'divide-white/5' : 'divide-zinc-100'}`}>
                                            {paginatedHistory.map((item, idx) => {
                                                const ratingEmojis = ["😔", "😕", "😐", "🙂", "😍"];
                                                const localFeedback = JSON.parse(localStorage.getItem('form_feedback_history') || '{}');
                                                const feedback = localFeedback[item.form_url];
                                                const emoji = feedback ? ratingEmojis[feedback.rating - 1] : null;

                                                return (
                                                    <motion.div
                                                        key={item.id}
                                                        initial={{ opacity: 0, x: -10 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        transition={{ delay: idx * 0.05 }}
                                                        className={`py-4 flex items-center justify-between transition-colors group ${isDark ? 'hover:bg-white/[0.02]' : 'hover:bg-zinc-50'} -mx-4 px-4 rounded-xl`}
                                                    >
                                                        <div className="flex items-center gap-4">
                                                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.status === 'Success'
                                                                    ? 'bg-emerald-500/10 text-emerald-400'
                                                                    : 'bg-red-500/10 text-red-400'
                                                                }`}>
                                                                {item.status === 'Success' ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
                                                            </div>
                                                            <div>
                                                                <div className={`font-medium group-hover:text-purple-400 transition-colors truncate max-w-[200px] md:max-w-[400px] flex items-center gap-2 ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                                                                    {item.form_url}
                                                                    {emoji && (
                                                                        <span title={`Rated: ${feedback.rating}/5`} className={`text-base w-6 h-6 rounded-lg flex items-center justify-center ${isDark ? 'bg-white/10' : 'bg-zinc-100'}`}>
                                                                            {emoji}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <div className={`text-xs flex items-center gap-2 mt-1 ${isDark ? 'text-white/40' : 'text-zinc-400'}`}>
                                                                    <Clock className="h-3 w-3" />
                                                                    {new Date(item.timestamp).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <a
                                                            href={item.form_url}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className={`p-2 rounded-lg transition-colors ${isDark ? 'hover:bg-white/10 text-white/40 hover:text-white' : 'hover:bg-zinc-100 text-zinc-400 hover:text-zinc-900'}`}
                                                        >
                                                            <ExternalLink className="h-5 w-5" />
                                                        </a>
                                                    </motion.div>
                                                );
                                            })}
                                        </div>

                                        {/* Pagination */}
                                        {history.length > ITEMS_PER_PAGE && (
                                            <div className="flex items-center justify-center gap-4 pt-6 mt-6 border-t border-white/5">
                                                <button
                                                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                                    disabled={currentPage === 1}
                                                    className={`px-4 py-2 text-sm font-medium rounded-xl transition-all ${isDark
                                                            ? 'bg-white/10 hover:bg-white/20 disabled:bg-white/5 disabled:text-white/30'
                                                            : 'bg-zinc-100 hover:bg-zinc-200 disabled:bg-zinc-50 disabled:text-zinc-300'
                                                        }`}
                                                >
                                                    Previous
                                                </button>
                                                <span className={`text-sm font-medium ${isDark ? 'text-white/60' : 'text-zinc-500'}`}>
                                                    {currentPage} / {totalPages}
                                                </span>
                                                <button
                                                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                                    disabled={currentPage === totalPages}
                                                    className={`px-4 py-2 text-sm font-medium rounded-xl transition-all ${isDark
                                                            ? 'bg-white/10 hover:bg-white/20 disabled:bg-white/5 disabled:text-white/30'
                                                            : 'bg-zinc-100 hover:bg-zinc-200 disabled:bg-zinc-50 disabled:text-zinc-300'
                                                        }`}
                                                >
                                                    Next
                                                </button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </BentoCard>
                        </motion.div>
                    )}

                    {/* Profile Tab Content */}
                    {activeTab === 'profile' && (
                        <motion.div
                            key="profile"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            transition={{ duration: 0.3 }}
                        >
                            <BentoCard size="xl">
                                <ProfileSettings />
                            </BentoCard>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}
