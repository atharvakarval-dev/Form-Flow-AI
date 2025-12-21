import React, { useState } from "react"
import { cn } from "@/lib/utils"

const ratingData = [
    { emoji: "😔", label: "Terrible", color: "from-red-400 to-red-500", shadowColor: "shadow-red-500/30" },
    { emoji: "😕", label: "Poor", color: "from-orange-400 to-orange-500", shadowColor: "shadow-orange-500/30" },
    { emoji: "😐", label: "Okay", color: "from-yellow-400 to-yellow-500", shadowColor: "shadow-yellow-500/30" },
    { emoji: "🙂", label: "Good", color: "from-lime-400 to-lime-500", shadowColor: "shadow-lime-500/30" },
    { emoji: "😍", label: "Amazing", color: "from-emerald-400 to-emerald-500", shadowColor: "shadow-emerald-500/30" },
]

export function RatingInteraction({ onChange, className }) {
    const [rating, setRating] = useState(0)
    const [hoverRating, setHoverRating] = useState(0)

    const handleClick = (value) => {
        setRating(value)
        if (onChange) {
            onChange(value)
        }
    }

    const displayRating = hoverRating || rating

    return (
        <div className={cn("flex flex-col items-center gap-6", className)}>
            {/* Emoji rating buttons */}
            <div className="flex items-center gap-3">
                {ratingData.map((item, i) => {
                    const value = i + 1
                    const isActive = value <= displayRating

                    return (
                        <button
                            key={value}
                            onClick={() => handleClick(value)}
                            onMouseEnter={() => setHoverRating(value)}
                            onMouseLeave={() => setHoverRating(0)}
                            className="group relative focus:outline-none"
                            aria-label={`Rate ${value}: ${item.label}`}
                        >
                            <div
                                className={cn(
                                    "relative flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300 ease-out",
                                    isActive ? "scale-110" : "scale-100 group-hover:scale-105",
                                )}
                            >
                                {/* Emoji with smooth grayscale transition */}
                                <span
                                    className={cn(
                                        "text-3xl transition-all duration-300 ease-out select-none",
                                        isActive
                                            ? "grayscale-0 drop-shadow-lg"
                                            : "grayscale opacity-40 group-hover:opacity-70 group-hover:grayscale-[0.3]",
                                    )}
                                >
                                    {item.emoji}
                                </span>
                            </div>
                        </button>
                    )
                })}
            </div>

            <div className="relative h-7 w-32">
                {/* Default "Rate us" text */}
                <div
                    className={cn(
                        "absolute inset-0 flex items-center justify-center transition-all duration-300 ease-out",
                        displayRating > 0 ? "opacity-0 blur-md scale-95" : "opacity-100 blur-0 scale-100",
                    )}
                >
                    <span className="text-sm font-medium text-white/50">Rate experience</span>
                </div>

                {/* Rating labels with blur in/out effect */}
                {ratingData.map((item, i) => (
                    <div
                        key={i}
                        className={cn(
                            "absolute inset-0 flex items-center justify-center transition-all duration-300 ease-out",
                            displayRating === i + 1 ? "opacity-100 blur-0 scale-100" : "opacity-0 blur-md scale-105",
                        )}
                    >
                        <span className="text-sm font-semibold tracking-wide text-white">{item.label}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}
