
/**
 * FormFlow AI - Clean Lab Controller
 * v1.3.1 - Reverted to Clean Theme
 */

document.addEventListener('DOMContentLoaded', async () => {
    // UI References
    const ui = {
        logs: document.getElementById('terminalLogs'),
        statusText: document.getElementById('statusText'),
        statusDot: document.getElementById('statusDot'),
        retryBtn: document.getElementById('retryBtn'),
        startBtn: document.getElementById('startBtn'),
        autoDetect: document.getElementById('autoDetect'),
        showOverlay: document.getElementById('showOverlay')
    };

    let isConnected = false;

    // =========================================================================
    // LOGGER SYSTEM (Light Theme)
    // =========================================================================

    const Logger = {
        add: (msg, type = 'info') => {
            const row = document.createElement('div');
            row.className = 'log-entry';

            // Timestamp
            const now = new Date();
            const ts = now.toLocaleTimeString('en-US', { hour12: false });

            // Icon/Arrow color based on type
            let colorClass = '';
            if (type === 'error') colorClass = 'error';

            row.innerHTML = `
                <span class="ts">${ts}</span>
                <span class="arrow">➜</span>
                <span class="msg ${colorClass}">${msg}</span>
            `;

            ui.logs.appendChild(row);
            // Smooth scroll to bottom
            row.scrollIntoView({ behavior: 'smooth' });
        },

        setStatus: (status, state) => {
            ui.statusText.textContent = status;
            if (state === 'online') {
                ui.statusDot.classList.add('online');
                ui.statusText.style.color = 'var(--accent-green)';
            } else {
                ui.statusDot.classList.remove('online');
                ui.statusText.style.color = 'var(--text-sub)';
            }
        }
    };

    // =========================================================================
    // INITIALIZATION & CONNECTION
    // =========================================================================

    // Load Settings
    loadSettings();

    // Boot Sequence Simulation
    runBootSequence();

    async function runBootSequence() {
        Logger.add('Restoring Clean Lab Interface...');
        await wait(200);
        Logger.add('Calibrating neural inputs...');
        await wait(200);
        await checkConnection();
    }

    async function checkConnection() {
        ui.retryBtn.style.display = 'none';
        Logger.add('Pinging backend server...');

        try {
            const response = await chrome.runtime.sendMessage({ type: 'CHECK_BACKEND' });

            if (response && (response.healthy || response.success)) {
                isConnected = true;
                Logger.setStatus('System Online', 'online');
                Logger.add(`Connected to Core v${response.version || '1.0'}`);

                ui.startBtn.disabled = false;

            } else {
                throw new Error('Non-healthy response');
            }
        } catch (err) {
            isConnected = false;
            Logger.setStatus('Connection Failed', 'offline');
            Logger.add(`Error: ${err.message || 'Server Unreachable'}`, 'error');

            ui.retryBtn.style.display = 'block';
            ui.startBtn.disabled = true;
        }
    }

    // =========================================================================
    // INTERACTION HANDLERS
    // =========================================================================

    ui.startBtn.addEventListener('click', async () => {
        if (!isConnected) return;

        Logger.add('Initiating session...');

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    const btn = document.querySelector('.formflow-voice-btn');
                    if (btn) btn.click();
                }
            });

            Logger.add('Voice agent injected.');
            setTimeout(() => window.close(), 1000);

        } catch (err) {
            Logger.add(`Error: ${err.message}`, 'error');
        }
    });

    ui.retryBtn.addEventListener('click', () => {
        Logger.add('Retrying...');
        checkConnection();
    });

    // Settings
    ui.autoDetect.addEventListener('change', saveSettings);
    ui.showOverlay.addEventListener('change', saveSettings);

    async function loadSettings() {
        const result = await chrome.storage.local.get('settings');
        const settings = result.settings || { autoDetectForms: true, showOverlay: true };
        ui.autoDetect.checked = settings.autoDetectForms;
        ui.showOverlay.checked = settings.showOverlay;
    }

    async function saveSettings() {
        const settings = {
            autoDetectForms: ui.autoDetect.checked,
            showOverlay: ui.showOverlay.checked
        };
        chrome.storage.local.set({ settings });
    }

    function wait(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
});
