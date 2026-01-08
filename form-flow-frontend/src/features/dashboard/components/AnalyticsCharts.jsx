/**
 * AnalyticsCharts Component - Premium Redesign
 * 
 * Recharts-powered visualizations with enhanced aesthetics for Bento dashboard.
 */

import {
    LineChart, Line,
    PieChart, Pie, Cell,
    BarChart, Bar,
    AreaChart, Area,
    XAxis, YAxis,
    CartesianGrid, Tooltip,
    ResponsiveContainer, Legend
} from 'recharts';
import { useTheme } from '@/context/ThemeProvider';

// Premium color palette with gradients
const COLORS = {
    primary: ['#6366F1', '#8B5CF6'], // Indigo to Purple
    success: ['#10B981', '#34D399'], // Emerald
    warning: ['#F59E0B', '#FBBF24'], // Amber
    info: ['#3B82F6', '#60A5FA'],    // Blue
    danger: ['#EF4444', '#F87171'],  // Red
    pink: ['#EC4899', '#F472B6'],    // Pink
};

const CHART_COLORS = ['#10B981', '#14B8A6', '#22C55E', '#84CC16', '#34D399', '#6EE7B7'];

// Custom tooltip style
const getTooltipStyle = (isDark) => ({
    backgroundColor: isDark ? 'rgba(9, 9, 11, 0.95)' : 'rgba(255, 255, 255, 0.95)',
    border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
    borderRadius: '12px',
    color: isDark ? '#fff' : '#18181b',
    boxShadow: isDark
        ? '0 4px 20px rgba(0, 0, 0, 0.5)'
        : '0 4px 20px rgba(0, 0, 0, 0.1)',
    padding: '12px 16px',
    backdropFilter: 'blur(8px)',
});

export function SubmissionTrendChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                        <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                            <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <XAxis
                        dataKey="date"
                        stroke={isDark ? '#3f3f46' : '#d4d4d8'}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                        tick={{ fill: isDark ? '#71717a' : '#a1a1aa' }}
                    />
                    <YAxis
                        stroke={isDark ? '#3f3f46' : '#d4d4d8'}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: isDark ? '#71717a' : '#a1a1aa' }}
                        tickFormatter={(value) => `${value}`}
                    />
                    <Tooltip
                        contentStyle={getTooltipStyle(isDark)}
                        itemStyle={{ color: isDark ? '#fbbf24' : '#d97706' }}
                        cursor={{ stroke: isDark ? '#3f3f46' : '#e4e4e7', strokeWidth: 1, strokeDasharray: '4 4' }}
                    />
                    <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#10B981"
                        strokeWidth={3}
                        fill="url(#trendGradient)"
                        dot={false}
                        activeDot={{
                            r: 6,
                            fill: '#10B981',
                            stroke: isDark ? '#09090b' : '#fff',
                            strokeWidth: 3,
                            filter: 'drop-shadow(0 0 8px rgba(16, 185, 129, 0.5))'
                        }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}

export function SuccessRateChart({ successRate }) {
    const { isDark } = useTheme();
    const data = [
        { name: 'Success', value: successRate },
        { name: 'Failed', value: 100 - successRate },
    ];

    return (
        <div className="h-full w-full flex items-center justify-center relative">
            {/* Center percentage display */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                <div className="text-center">
                    <div className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>
                        {successRate}%
                    </div>
                    <div className={`text-xs ${isDark ? 'text-white/40' : 'text-zinc-500'}`}>
                        Success
                    </div>
                </div>
            </div>

            <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <defs>
                        <linearGradient id="successGradient" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stopColor="#10B981" />
                            <stop offset="100%" stopColor="#34D399" />
                        </linearGradient>
                    </defs>
                    <Pie
                        data={data}
                        cx="50%"
                        cy="50%"
                        innerRadius="65%"
                        outerRadius="85%"
                        paddingAngle={4}
                        dataKey="value"
                        startAngle={90}
                        endAngle={-270}
                    >
                        <Cell fill="url(#successGradient)" stroke="none" />
                        <Cell fill={isDark ? '#27272a' : '#e4e4e7'} stroke="none" />
                    </Pie>
                    <Tooltip
                        formatter={(value) => `${value}%`}
                        contentStyle={getTooltipStyle(isDark)}
                    />
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
}

// Horizontal stacked bar for Field Types (Composition)
export function FieldTypesChart({ data }) {
    const { isDark } = useTheme();

    if (!data || data.length === 0) {
        return (
            <div className={`h-full w-full flex items-center justify-center ${isDark ? 'text-white/30' : 'text-zinc-300'}`}>
                No data available
            </div>
        );
    }

    return (
        <div className="h-full w-full flex flex-col justify-center">
            {/* Stacked horizontal bar visualization */}
            <div className="h-12 w-full rounded-xl overflow-hidden flex shadow-inner">
                {data.map((entry, index) => {
                    const total = data.reduce((sum, d) => sum + d.value, 0);
                    const percentage = total > 0 ? (entry.value / total) * 100 : 0;

                    return (
                        <div
                            key={entry.name}
                            className="h-full transition-all duration-500 hover:opacity-80 relative group"
                            style={{
                                width: `${percentage}%`,
                                backgroundColor: CHART_COLORS[index % CHART_COLORS.length],
                                minWidth: percentage > 0 ? '8px' : 0
                            }}
                            title={`${entry.name}: ${entry.value} (${percentage.toFixed(1)}%)`}
                        >
                            {/* Tooltip on hover */}
                            <div className="absolute -top-10 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap bg-black/90 text-white text-xs px-2 py-1 rounded pointer-events-none z-20">
                                {entry.name}: {entry.value}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export function FormTypeChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                        <linearGradient id="successBarGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#10B981" />
                            <stop offset="100%" stopColor="#059669" />
                        </linearGradient>
                        <linearGradient id="failBarGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#EF4444" />
                            <stop offset="100%" stopColor="#DC2626" />
                        </linearGradient>
                    </defs>
                    <XAxis
                        dataKey="type"
                        stroke={isDark ? '#3f3f46' : '#d4d4d8'}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                        tick={{ fill: isDark ? '#71717a' : '#a1a1aa' }}
                    />
                    <YAxis
                        stroke={isDark ? '#3f3f46' : '#d4d4d8'}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: isDark ? '#71717a' : '#a1a1aa' }}
                    />
                    <Tooltip
                        contentStyle={getTooltipStyle(isDark)}
                        cursor={{ fill: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }}
                    />
                    <Bar dataKey="success" stackId="a" fill="url(#successBarGradient)" radius={[0, 0, 4, 4]} barSize={40} />
                    <Bar dataKey="fail" stackId="a" fill="url(#failBarGradient)" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

export function TopDomainsChart({ data }) {
    const { isDark } = useTheme();

    if (!data || data.length === 0) {
        return (
            <div className={`h-full w-full flex items-center justify-center ${isDark ? 'text-white/30' : 'text-zinc-300'}`}>
                No domains yet
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    layout="vertical"
                    data={data}
                    margin={{ top: 0, right: 10, left: 10, bottom: 0 }}
                >
                    <defs>
                        <linearGradient id="domainGradient" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#14B8A6" />
                            <stop offset="100%" stopColor="#10B981" />
                        </linearGradient>
                    </defs>
                    <XAxis type="number" hide />
                    <YAxis
                        dataKey="name"
                        type="category"
                        width={100}
                        tick={{ fill: isDark ? '#a1a1aa' : '#52525b', fontSize: 10 }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => value.length > 15 ? value.substring(0, 15) + '...' : value}
                    />
                    <Tooltip
                        cursor={{ fill: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }}
                        contentStyle={getTooltipStyle(isDark)}
                    />
                    <Bar
                        dataKey="value"
                        fill="url(#domainGradient)"
                        radius={[0, 6, 6, 0]}
                        barSize={16}
                    />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

export function ActivityHourlyChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                        <linearGradient id="hourlyGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#14B8A6" stopOpacity={0.4} />
                            <stop offset="95%" stopColor="#14B8A6" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <XAxis
                        dataKey="hour"
                        stroke={isDark ? '#3f3f46' : '#d4d4d8'}
                        fontSize={9}
                        tickLine={false}
                        axisLine={false}
                        interval={5}
                        tickFormatter={(h) => `${h}h`}
                        tick={{ fill: isDark ? '#52525b' : '#a1a1aa' }}
                    />
                    <YAxis hide />
                    <Tooltip
                        labelFormatter={(h) => `${h}:00 - ${h}:59`}
                        contentStyle={getTooltipStyle(isDark)}
                    />
                    <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#14B8A6"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#hourlyGradient)"
                        dot={false}
                        activeDot={{
                            r: 4,
                            fill: '#14B8A6',
                            stroke: isDark ? '#09090b' : '#fff',
                            strokeWidth: 2
                        }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}
