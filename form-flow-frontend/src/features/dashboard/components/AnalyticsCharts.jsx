/**
 * AnalyticsCharts Component
 * 
 * Recharts-powered visualizations for form filling analytics.
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

// Chart color palette - Reference Style (Blue/Purple/Orange/Green)
const COLORS = ['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981', '#EC4899', '#6366F1'];

export function SubmissionTrendChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis
                        dataKey="date"
                        stroke={isDark ? '#52525b' : '#a1a1aa'}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                    />
                    <YAxis
                        stroke={isDark ? '#52525b' : '#a1a1aa'}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}`}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)'
                        }}
                        itemStyle={{ color: '#e4e4e7' }}
                        cursor={{ stroke: '#3f3f46', strokeWidth: 1, strokeDasharray: '4 4' }}
                    />
                    <Line
                        type="monotone"
                        dataKey="count"
                        stroke="#F59E0B"
                        strokeWidth={4}
                        dot={false}
                        activeDot={{ r: 6, fill: '#F59E0B', stroke: '#09090b', strokeWidth: 2 }}
                    />
                    {/* Mock second line for comparison visual if needed, or remove */}
                </LineChart>
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
        <div className="h-full w-full flex items-center">
            <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <Pie
                        data={data}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                    >
                        <Cell fill="#3B82F6" stroke="none" />
                        <Cell fill="#27272a" stroke="none" />
                        {/* Use dark gray for 'empty' part in reference style */}
                    </Pie>
                    <Tooltip
                        formatter={(value) => `${value}%`}
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff'
                        }}
                        itemStyle={{ color: '#e4e4e7' }}
                    />
                    <Legend
                        verticalAlign="middle"
                        align="right"
                        layout="vertical"
                        iconType="circle"
                        content={({ payload }) => (
                            <ul className="space-y-2">
                                {payload.map((entry, index) => (
                                    <li key={`item-${index}`} className="flex items-center gap-2 text-sm text-zinc-400">
                                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }}></span>
                                        <span className={isDark ? "text-zinc-300" : "text-zinc-600"}>{entry.value}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    />
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
}

// Stacked Bar Chart for Field Types (Reference: "Composition")
export function FieldTypesChart({ data }) {
    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                {/* Using BarChart to mimic the stacked look */}
                <BarChart data={[data.reduce((acc, curr) => ({ ...acc, [curr.name]: curr.value }), {})]} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" hide />
                    <Tooltip
                        cursor={{ fill: 'transparent' }}
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff'
                        }}
                    />
                    {data.map((entry, index) => (
                        <Bar
                            key={entry.name}
                            dataKey={entry.name}
                            stackId="a"
                            fill={COLORS[index % COLORS.length]}
                            radius={index === 0 ? [4, 0, 0, 4] : index === data.length - 1 ? [0, 4, 4, 0] : [0, 0, 0, 0]}
                        />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

export function FormTypeChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis
                        dataKey="type"
                        stroke={isDark ? '#52525b' : '#a1a1aa'}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                    />
                    <YAxis
                        stroke={isDark ? '#52525b' : '#a1a1aa'}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff'
                        }}
                        cursor={{ fill: isDark ? '#27272a' : '#f4f4f5' }}
                    />
                    <Bar dataKey="success" stackId="a" fill="#10B981" radius={[0, 0, 4, 4]} barSize={40} />
                    <Bar dataKey="fail" stackId="a" fill="#3B82F6" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

export function TopDomainsChart({ data }) {
    const { isDark } = useTheme();

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    layout="vertical"
                    data={data}
                    margin={{ top: 0, right: 10, left: 10, bottom: 0 }}
                >
                    <XAxis type="number" hide />
                    <YAxis
                        dataKey="name"
                        type="category"
                        width={100}
                        tick={{ fill: isDark ? '#a1a1aa' : '#52525b', fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                    />
                    <Tooltip
                        cursor={{ fill: isDark ? '#27272a' : '#f4f4f5' }}
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff'
                        }}
                    />
                    <Bar dataKey="value" fill="#8B5CF6" radius={[0, 4, 4, 0]} barSize={20} />
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
                        <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <XAxis
                        dataKey="hour"
                        stroke={isDark ? '#52525b' : '#a1a1aa'}
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        interval={3}
                        tickFormatter={(h) => `${h}h`}
                    />
                    <YAxis hide />
                    <Tooltip
                        labelFormatter={(h) => `${h}:00 - ${h}:59`}
                        contentStyle={{
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '12px',
                            color: '#fff'
                        }}
                    />
                    <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#3B82F6"
                        fillOpacity={1}
                        fill="url(#colorCount)"
                        strokeWidth={2}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}
