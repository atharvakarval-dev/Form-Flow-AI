/**
 * FormFlow AI - Popup Script
 * 
 * Handles popup UI interactions and settings management
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Elements
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const startBtn = document.getElementById('startBtn');
    const helpBtn = document.getElementById('helpBtn');
    const autoDetect = document.getElementById('autoDetect');
    const showOverlay = document.getElementById('showOverlay');
    const recentForms = document.getElementById('recentForms');
    const recentList = document.getElementById('recentList');
    const docsLink = document.getElementById('docsLink');

    // Check backend health
    await checkBackendHealth();

    // Load settings
    loadSettings();

    // Load recent forms
    loadRecentForms();

    // Event listeners
    startBtn.onclick = startOnCurrentPage;
    helpBtn.onclick = showHelp;
    autoDetect.onchange = saveSettings;
    showOverlay.onchange = saveSettings;
    docsLink.onclick = openDocs;

    /**
     * Check if backend is running
     */
    async function checkBackendHealth() {
        try {
            const response = await chrome.runtime.sendMessage({ type: 'CHECK_BACKEND' });

            if (response.success && response.healthy) {
                statusDot.classList.add('connected');
                statusText.textContent = `Connected (v${response.version})`;
                startBtn.disabled = false;
            } else {
                statusDot.classList.remove('connected');
                statusText.textContent = 'Backend not running. Start the server.';
                startBtn.disabled = true;
            }
        } catch (error) {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Error connecting to backend';
            startBtn.disabled = true;
        }
    }

    /**
     * Start FormFlow on the current tab
     */
    async function startOnCurrentPage() {
        try {
            // Get current tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            if (!tab) {
                alert('No active tab found');
                return;
            }

            // Inject content script if needed and trigger form detection
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    // Trigger button click if already injected
                    const btn = document.querySelector('.formflow-voice-btn');
                    if (btn) {
                        btn.click();
                    } else {
                        // Force re-scan
                        window.__formFlowInjected = false;
                    }
                }
            });

            // Close popup
            window.close();

        } catch (error) {
            console.error('Error starting FormFlow:', error);
            alert('Could not start FormFlow on this page. Make sure you\'re on a page with forms.');
        }
    }

    /**
     * Show help/instructions
     */
    function showHelp() {
        const helpContent = `
How to use FormFlow AI:

1. Navigate to a webpage with a form
2. Click the "🎤 Fill with Voice" button that appears
3. Grant microphone permission when asked
4. Start speaking naturally: "My name is John Smith, email john@example.com"
5. FormFlow will extract and fill the fields
6. Review and submit!

Tips:
- Speak clearly and at a normal pace
- You can say multiple fields at once
- Say "email" or "phone" before those values for clarity
- Click "Fill Form" when ready to complete
    `;

        alert(helpContent);
    }

    /**
     * Load settings from storage
     */
    async function loadSettings() {
        const result = await chrome.storage.local.get('settings');
        const settings = result.settings || {
            autoDetectForms: true,
            showOverlay: true
        };

        autoDetect.checked = settings.autoDetectForms;
        showOverlay.checked = settings.showOverlay;
    }

    /**
     * Save settings to storage
     */
    async function saveSettings() {
        const settings = {
            autoDetectForms: autoDetect.checked,
            showOverlay: showOverlay.checked,
            voiceSpeed: 1.0,
            language: 'en-US'
        };

        await chrome.storage.local.set({ settings });
    }

    /**
     * Load recent form submissions
     */
    async function loadRecentForms() {
        const result = await chrome.storage.local.get('recentForms');
        const forms = result.recentForms || [];

        if (forms.length === 0) {
            recentForms.style.display = 'none';
            return;
        }

        recentForms.style.display = 'block';
        recentList.innerHTML = '';

        forms.slice(0, 3).forEach(form => {
            const item = document.createElement('div');
            item.className = 'recent-item';
            item.innerHTML = `
        <span class="recent-icon">📝</span>
        <div class="recent-info">
          <div class="recent-url">${new URL(form.url).hostname}</div>
          <div class="recent-fields">${form.fieldsCount} fields filled</div>
        </div>
      `;
            recentList.appendChild(item);
        });
    }

    /**
     * Open documentation
     */
    function openDocs(e) {
        e.preventDefault();
        chrome.tabs.create({ url: 'https://github.com/your-repo/formflow-ai#readme' });
    }
});
