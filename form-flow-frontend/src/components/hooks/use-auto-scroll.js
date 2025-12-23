import { useRef, useEffect, useState, useCallback } from "react";

export function useAutoScroll({ smooth = false, content }) {
    const scrollRef = useRef(null);
    const [isAtBottom, setIsAtBottom] = useState(true);
    const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);

    const scrollToBottom = useCallback(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({
                top: scrollRef.current.scrollHeight,
                behavior: smooth ? "smooth" : "auto",
            });
            setIsAtBottom(true);
            setAutoScrollEnabled(true);
        }
    }, [smooth]);

    const disableAutoScroll = useCallback(() => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            const bottomThreshold = 50;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < bottomThreshold;

            if (!isNearBottom) {
                setAutoScrollEnabled(false);
                setIsAtBottom(false);
            }
        }
    }, []);

    useEffect(() => {
        const scrollContainer = scrollRef.current;
        if (!scrollContainer) return;

        const handleScroll = () => {
            const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
            const bottomThreshold = 50;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < bottomThreshold;
            setIsAtBottom(isNearBottom);

            if (isNearBottom) {
                setAutoScrollEnabled(true);
            }
        };

        scrollContainer.addEventListener("scroll", handleScroll);
        return () => scrollContainer.removeEventListener("scroll", handleScroll);
    }, []);

    useEffect(() => {
        if (autoScrollEnabled) {
            scrollToBottom();
        }
    }, [content, autoScrollEnabled, scrollToBottom]);

    return {
        scrollRef,
        isAtBottom,
        autoScrollEnabled,
        scrollToBottom,
        disableAutoScroll,
    };
}
