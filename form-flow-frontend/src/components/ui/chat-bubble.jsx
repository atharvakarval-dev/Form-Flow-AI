import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

// MessageLoading component
function MessageLoading() {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            className="text-foreground"
        >
            <circle cx="4" cy="12" r="2" fill="currentColor">
                <animate
                    id="spinner_qFRN"
                    begin="0;spinner_OcgL.end+0.25s"
                    attributeName="cy"
                    calcMode="spline"
                    dur="0.6s"
                    values="12;6;12"
                    keySplines=".33,.66,.66,1;.33,0,.66,.33"
                />
            </circle>
            <circle cx="12" cy="12" r="2" fill="currentColor">
                <animate
                    begin="spinner_qFRN.begin+0.1s"
                    attributeName="cy"
                    calcMode="spline"
                    dur="0.6s"
                    values="12;6;12"
                    keySplines=".33,.66,.66,1;.33,0,.66,.33"
                />
            </circle>
            <circle cx="20" cy="12" r="2" fill="currentColor">
                <animate
                    id="spinner_OcgL"
                    begin="spinner_qFRN.begin+0.2s"
                    attributeName="cy"
                    calcMode="spline"
                    dur="0.6s"
                    values="12;6;12"
                    keySplines=".33,.66,.66,1;.33,0,.66,.33"
                />
            </circle>
        </svg>
    );
}

// ChatBubble variants
const chatBubbleVariants = cva(
    "flex gap-2 max-w-[60%] items-end relative group",
    {
        variants: {
            variant: {
                received: "self-start",
                sent: "self-end flex-row-reverse",
            },
            layout: {
                default: "",
                ai: "max-w-full w-full items-center",
            },
        },
        defaultVariants: {
            variant: "received",
            layout: "default",
        },
    }
);

const ChatBubble = React.forwardRef(
    ({ className, variant, layout, children, ...props }, ref) => (
        <div
            className={cn(chatBubbleVariants({ variant, layout, className }))}
            ref={ref}
            {...props}
        >
            {children}
        </div>
    )
);
ChatBubble.displayName = "ChatBubble";

// ChatBubbleAvatar
const ChatBubbleAvatar = React.forwardRef(
    ({ className, src, fallback, ...props }, ref) => (
        <div
            ref={ref}
            className={cn(
                "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-muted text-sm font-medium overflow-hidden",
                className
            )}
            {...props}
        >
            {src ? (
                <img src={src} alt={fallback || "Avatar"} className="h-full w-full object-cover" />
            ) : (
                <span>{fallback}</span>
            )}
        </div>
    )
);
ChatBubbleAvatar.displayName = "ChatBubbleAvatar";

// ChatBubbleMessage variants
const chatBubbleMessageVariants = cva(
    "px-4 py-2 rounded-lg max-w-full whitespace-pre-wrap break-words",
    {
        variants: {
            variant: {
                received: "bg-secondary text-secondary-foreground",
                sent: "bg-primary text-primary-foreground",
            },
            layout: {
                default: "",
                ai: "border-t w-full rounded-none bg-transparent",
            },
        },
        defaultVariants: {
            variant: "received",
            layout: "default",
        },
    }
);

const ChatBubbleMessage = React.forwardRef(
    ({ className, variant, layout, isLoading = false, children, ...props }, ref) => (
        <div
            className={cn(chatBubbleMessageVariants({ variant, layout, className }))}
            ref={ref}
            {...props}
        >
            {isLoading ? <MessageLoading /> : children}
        </div>
    )
);
ChatBubbleMessage.displayName = "ChatBubbleMessage";

// ChatBubbleTimestamp
const ChatBubbleTimestamp = React.forwardRef(
    ({ className, timestamp, ...props }, ref) => (
        <div
            ref={ref}
            className={cn("text-xs text-muted-foreground mt-2 text-right", className)}
            {...props}
        >
            {timestamp}
        </div>
    )
);
ChatBubbleTimestamp.displayName = "ChatBubbleTimestamp";

export {
    ChatBubble,
    ChatBubbleAvatar,
    ChatBubbleMessage,
    ChatBubbleTimestamp,
    MessageLoading,
    chatBubbleVariants,
    chatBubbleMessageVariants,
};
