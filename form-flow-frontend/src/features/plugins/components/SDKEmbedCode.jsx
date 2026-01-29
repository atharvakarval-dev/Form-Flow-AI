/**
 * SDK Embed Code Component
 * Generate and display embed code for different frameworks
 */
import { useState, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Copy, Check, Code, ExternalLink } from 'lucide-react';
import { useTheme } from '@/context/ThemeProvider';
import toast from 'react-hot-toast';

// Simple syntax highlighting for code blocks
const highlightCode = (code, language) => {
  // Add basic syntax highlighting classes
  return code
    .replace(/(const|let|var|function|import|export|from|return|async|await)/g, '<span class="text-purple-400">$1</span>')
    .replace(/('.*?'|".*?"|`.*?`)/g, '<span class="text-emerald-400">$1</span>')
    .replace(/(\{|\}|\(|\)|\[|\])/g, '<span class="text-zinc-400">$1</span>')
    .replace(/(\/\/.*$)/gm, '<span class="text-zinc-500">$1</span>');
};

/**
 * SDKEmbedCode - Code snippet generator with multiple framework support
 */
export function SDKEmbedCode({ plugin, apiKey }) {
  const { isDark } = useTheme();
  const [activeTab, setActiveTab] = useState('html');
  const [copied, setCopied] = useState(false);

  // Generate code examples
  const codeExamples = useMemo(() => ({
    html: `<!-- Add FormFlow Voice Widget -->
<script src="https://cdn.formflow.ai/v1/sdk.min.js"></script>
<div id="formflow-widget"></div>

<script>
  FormFlow.init({
    apiKey: '${apiKey || 'YOUR_API_KEY'}',
    pluginId: '${plugin.id}',
    theme: 'auto', // 'light', 'dark', or 'auto'
    onComplete: (data) => {
      console.log('Data collected:', data);
      // Handle collected data
    },
    onError: (error) => {
      console.error('Error:', error);
    }
  });
</script>`,

    react: `import { FormFlowWidget, useFormFlowPlugin } from '@formflow/react';

function MyForm() {
  const { isReady, startSession, data, error } = useFormFlowPlugin({
    apiKey: '${apiKey || 'YOUR_API_KEY'}',
    pluginId: '${plugin.id}',
    onComplete: (collectedData) => {
      console.log('Data collected:', collectedData);
      // Save to your backend
    },
  });

  return (
    <FormFlowWidget
      theme="auto"
      position="bottom-right"
      welcomeMessage="Hi! Let me help you fill this form."
    />
  );
}

export default MyForm;`,

    vanilla: `// Vanilla JavaScript integration
const formflow = new FormFlow({
  apiKey: '${apiKey || 'YOUR_API_KEY'}',
  pluginId: '${plugin.id}',
  container: document.getElementById('formflow-widget'),
});

// Start a voice session
formflow.start();

// Listen for events
formflow.on('complete', (data) => {
  console.log('Data collected:', data);
  
  // Submit to your API
  fetch('/api/submit', {
    method: 'POST',
    body: JSON.stringify(data),
  });
});

formflow.on('error', (error) => {
  console.error('FormFlow error:', error);
});`,

    curl: `# Test your plugin API
curl -X POST https://api.formflow.ai/v1/session/start \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${apiKey || 'YOUR_API_KEY'}" \\
  -d '{
    "plugin_id": "${plugin.id}",
    "metadata": {
      "user_agent": "curl/test"
    }
  }'

# Response:
# {
#   "session_id": "sess_xxx",
#   "questions": [...]
# }`,
  }), [plugin.id, apiKey]);

  // Copy to clipboard
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(codeExamples[activeTab]);
      setCopied(true);
      toast.success('Copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error('Failed to copy');
    }
  }, [codeExamples, activeTab]);

  const tabs = [
    { id: 'html', label: 'HTML' },
    { id: 'react', label: 'React' },
    { id: 'vanilla', label: 'Vanilla JS' },
    { id: 'curl', label: 'cURL' },
  ];

  return (
    <div className="space-y-4">
      {/* Header - Fluid Hero Style */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${isDark ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-500 shadow-sm'}`}>
            <Code className="w-6 h-6" />
          </div>
          <div>
            <h4 className={`text-xl font-black tracking-tighter ${isDark ? 'text-white' : 'text-zinc-900'}`}>
              Integration
            </h4>
            <p className={`text-[10px] font-black uppercase tracking-[0.2em] opacity-40 ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Deploy your voice interface
            </p>
          </div>
        </div>
        <a
          href="https://docs.formflow.ai/sdk"
          target="_blank"
          rel="noopener noreferrer"
          className={`
                        px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest transition-all
                        ${isDark ? 'text-emerald-400 hover:text-emerald-300 hover:bg-white/5' : 'text-emerald-600 hover:text-emerald-700 hover:bg-zinc-50'}
                    `}
        >
          Docs <ExternalLink className="w-3 h-3 inline ml-1" />
        </a>
      </div>

      {/* Tab Switcher - Premium Pill Style */}
      <div className={`
                inline-flex items-center gap-1 p-1.5 rounded-full border mb-4
                ${isDark ? 'bg-zinc-900/50 border-white/[0.05]' : 'bg-zinc-100/50 border-zinc-200/50'}
            `}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
                            relative px-6 py-2.5 rounded-full text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-500
                            ${activeTab === tab.id
                ? isDark ? 'text-black' : 'text-white'
                : isDark ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'
              }
                        `}
          >
            {activeTab === tab.id && (
              <motion.div
                layoutId="embed-tab-bg"
                className={`absolute inset-0 rounded-full z-0 ${isDark ? 'bg-white' : 'bg-zinc-900 shadow-lg'}`}
                transition={{ type: "spring", bounce: 0.1, duration: 0.6 }}
              />
            )}
            <span className="relative z-10">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Code block - Ultra High-End IDE Aesthetic */}
      <div className="relative group">
        <div className={`
                    rounded-[2rem] overflow-hidden border transition-all duration-500
                    ${isDark
            ? 'bg-black/40 border-white/[0.05] group-hover:border-emerald-500/20'
            : 'bg-zinc-900 border-zinc-800 shadow-2xl shadow-zinc-900/40'
          }
                `}>
          {/* Code header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.05]">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-400/20 border border-red-400/40" />
              <div className="w-3 h-3 rounded-full bg-amber-400/20 border border-amber-400/40" />
              <div className="w-3 h-3 rounded-full bg-emerald-400/20 border border-emerald-400/40" />
              <span className="ml-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                {activeTab} source
              </span>
            </div>
            <button
              onClick={handleCopy}
              className={`
                                flex items-center gap-2 px-5 py-2 rounded-[1rem] text-[10px] font-black uppercase tracking-widest transition-all
                                ${copied
                  ? 'bg-emerald-500 text-white'
                  : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white'
                }
                            `}
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>

          {/* Code content */}
          <pre className="p-8 overflow-x-auto text-[13px] custom-scrollbar">
            <code
              className="text-zinc-400 font-mono leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: highlightCode(codeExamples[activeTab], activeTab)
              }}
            />
          </pre>
        </div>

        {/* API Key warning */}
        {!apiKey && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`
              mt-3 p-3 rounded-xl flex items-center gap-2 text-sm
              ${isDark ? 'bg-amber-500/10 text-amber-400' : 'bg-amber-50 text-amber-700'}
            `}
          >
            <span>⚠️</span>
            <span>Generate an API key above to get working embed code</span>
          </motion.div>
        )}
      </div>

      {/* Quick tips */}
      <div className={`
        p-4 rounded-xl space-y-2
        ${isDark ? 'bg-white/[0.02]' : 'bg-zinc-50'}
      `}>
        <h5 className={`text-sm font-medium ${isDark ? 'text-white/70' : 'text-zinc-700'}`}>
          Quick Tips
        </h5>
        <ul className={`text-sm space-y-1 ${isDark ? 'text-white/50' : 'text-zinc-600'}`}>
          <li>• Load the SDK in your page's <code className="px-1 rounded bg-white/10">&lt;head&gt;</code> or before closing <code className="px-1 rounded bg-white/10">&lt;body&gt;</code></li>
          <li>• The widget auto-detects mobile and adjusts its UI accordingly</li>
          <li>• Use <code className="px-1 rounded bg-white/10">theme: 'auto'</code> to match the user's system preference</li>
          <li>• Data is encrypted in transit and at rest</li>
        </ul>
      </div>
    </div>
  );
}

export default SDKEmbedCode;
