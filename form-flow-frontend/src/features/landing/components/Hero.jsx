import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import { Aurora } from "@/components/ui";
import { HERO_AURORA_COLORS, HERO_TITLES } from "@/constants";

function Hero({ url, setUrl, handleSubmit, loading }) {
    const [titleNumber, setTitleNumber] = useState(0);

    useEffect(() => {
        const timeoutId = setTimeout(() => {
            if (titleNumber === HERO_TITLES.length - 1) {
                setTitleNumber(0);
            } else {
                setTitleNumber(titleNumber + 1);
            }
        }, 2000);
        return () => clearTimeout(timeoutId);
    }, [titleNumber]);

    return (
        <div className="w-full min-h-screen flex items-center relative overflow-hidden">
            <Aurora colorStops={HERO_AURORA_COLORS} amplitude={1.2} blend={0.6} speed={0.3} />
            <div className="container mx-auto relative z-10">
                <div className="flex gap-8 py-20 lg:py-32 items-center justify-center flex-col">
                    <div className="flex gap-4 flex-col">
                        <h1 className="text-5xl md:text-7xl max-w-3xl tracking-tighter text-center font-semibold">
                            <span className="text-foreground">Form Completion with</span>
                            <span className="relative flex w-full justify-center overflow-hidden text-center md:pb-4 md:pt-1">
                                &nbsp;
                                {HERO_TITLES.map((title, index) => (
                                    <motion.span
                                        key={index}
                                        className="absolute font-bold text-primary"
                                        initial={{ opacity: 0, y: -100 }}
                                        transition={{ type: "spring", stiffness: 50 }}
                                        animate={
                                            titleNumber === index
                                                ? { y: 0, opacity: 1 }
                                                : { y: titleNumber > index ? -150 : 150, opacity: 0 }
                                        }
                                    >
                                        {title}
                                    </motion.span>
                                ))}
                            </span>
                        </h1>

                        <p className="text-lg md:text-xl leading-relaxed tracking-tight text-muted-foreground max-w-2xl text-center">
                            Revolutionizing online form completion with voice AI. Simply paste any form URL and let our intelligent assistant guide you through with natural conversation.
                        </p>
                    </div>

                    <div className="w-full max-w-2xl">
                        <PromptInputBox
                            onSend={(message) => {
                                setUrl(message);
                                handleSubmit({ preventDefault: () => { } }, message);
                            }}
                            isLoading={loading}
                            placeholder="Paste your form URL here..."
                        />
                    </div>
                </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-64 bg-gradient-to-b from-transparent to-background pointer-events-none" />
        </div>
    );
}

export { Hero };
export default Hero;
