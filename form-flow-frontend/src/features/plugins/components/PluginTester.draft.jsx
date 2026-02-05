import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mic, Play, Square, Loader2, Bot, User, RefreshCw, AlertCircle } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import { usePluginAPIKeys } from '@/hooks/usePluginQueries';

/**
 * PluginTester - Interactive playground for testing the plugin
 */
export function PluginTester({ plugin }) {
    const { isDark } = useTheme();

    // State
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]); // Array of { role: 'bot' | 'user', text: string }
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState('idle'); // idle, listening, processing, success, error
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState(null);
    const messagesEndRef = useRef(null);

    // Fetch API keys to use for testing
    const { data: apiKeys, isLoading: isLoadingKeys } = usePluginAPIKeys(plugin.id);
    const activeKey = apiKeys?.find(key => key.is_active && key.is_valid);

    // Scroll to bottom on new message
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Format time
    const formatTime = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Start Session
    const startSession = useCallback(async () => {
        if (!activeKey) {
            setError('No active API key found for this plugin. Please create one securely.');
            return;
        }

        setIsLoading(true);
        setError(null);
        setMessages([]);
        setProgress(0);

        try {
            const res = await fetch('http://localhost:8001/plugins/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': activeKey.api_key_preview || activeKey.key_prefix, // We need full key actually...
                    // Wait, api_key_preview IS NOT the full key. We can't use it. 
                    // We need the user to PASTE a key or use a dev-mode backdoor?
                    // The backend needs the full key validation.
                    // BUT, for the dashboard tester, maybe we can use a special "Dashboard Token" or similar?
                    // OR, better: We can't automatically test without the key.
                    // I'll ask the user to input the key.
                }
            });
            // ... API key logic problem ...
            // The `apiKeys` query only returns masked keys.
            // I need to prompt the user for the key.
        } catch (err) {
            setError(err.message);
        }
        setIsLoading(false);
    }, [activeKey, plugin.id]);

    // ...
    // Wait, I can't start the session without the full API key. This is a security feature.
    // I should create a "Test Mode" where the user can paste their key.

    // Let's modify the component to ask for an API key if not provided.

    return (
        <div className="h-full flex flex-col">
            {/* ... UI ... */}
        </div>
    );
}
