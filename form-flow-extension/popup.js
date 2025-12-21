
/**
 * FormFlow AI - Emerald Slate Controller
 * v2.1.0 React Port
 */

document.addEventListener('DOMContentLoaded', async () => {
    // UI References
    const ui = {
        logs: document.getElementById('terminalLogs'),
        statusText: document.getElementById('statusText'),
        statusBadge: document.getElementById('statusBadge'),
        progressBar: document.getElementById('progressBar'),
        percentText: document.getElementById('percentText'),
        actionText: document.getElementById('actionText'),
        runBtn: document.getElementById('runBtn')
    };

    let isConnected = false;

    // =========================================================================
    // REACT STATE SIMULATION
    // =========================================================================

    const State = {
        logs: [],
        progress: 0,

        addLog: (message, type = 'SYS') => {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-US', { hour12: false });

            // Create DOM Element
            const row = document.createElement('div');
            row.className = 'log-entry';

            let typeColorClass = 'type-sys'; // default text-emerald-600
            if (type === 'NET') typeColorClass = 'type-net'; // text-emerald-500
            if (type === 'ERR') typeColorClass = 'type-err';

            row.innerHTML = `
                <span class="log-ts">[${timeStr}]</span>
                <span class="log-type ${typeColorClass}">${type}</span>
                <svg class="w-4 h-4 text-emerald-500" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                <span class="log-msg">${message}</span>
            `;

            ui.logs.appendChild(row);
            row.scrollIntoView({ behavior: 'smooth' });
        },

        setProgress: (value) => {
            State.progress = value;
            ui.progressBar.style.width = `${value}%`;
            ui.percentText.textContent = `${Math.round(value)}%`;
        },

        setStatus: (text, online = true) => {
            ui.statusText.textContent = text;
            if (online) {
                ui.statusBadge.style.background = 'var(--emerald-100)';
                ui.statusBadge.querySelector('.status-dot').style.background = 'var(--emerald-500)';
            } else {
                ui.statusBadge.style.background = '#fef2f2';
                ui.statusBadge.querySelector('.status-dot').style.background = '#ef4444';
            }
        }
    };

    // =========================================================================
    // BOOT SEQUENCE (Matches User's React Code)
    // =========================================================================

    const systemLogs = [
        { type: 'SYS', message: 'Terminal initialized successfully.', delay: 200 },
        { type: 'SYS', message: 'Mounting file system...', delay: 600 },
        { type: 'SYS', message: 'Loading neural interface v1.0...', delay: 1000 },
        { type: 'NET', message: 'Establishing secure local uplink...', delay: 1500 }
    ];

    async function runBootSequence() {
        // Run simulated logs
        for (let i = 0; i < systemLogs.length; i++) {
            const log = systemLogs[i];
            setTimeout(() => {
                State.addLog(log.message, log.type);
                // Update progress based on logs
                const p = ((i + 1) / (systemLogs.length + 2)) * 100; // +2 for real connection steps
                State.setProgress(p);
            }, log.delay);
        }

        // Check Real Connection after delay
        setTimeout(() => checkConnection(), 2000);
    }

    async function checkConnection() {
        try {
            const response = await chrome.runtime.sendMessage({ type: 'CHECK_BACKEND' });

            if (response && (response.healthy || response.success)) {
                isConnected = true;
                State.addLog('Uplink established :: Latency <10ms', 'NET');
                State.addLog(`Backend version ${response.version || '1.0.0'} active`, 'SYS');
                State.setStatus('Online', true);
                State.setProgress(100);

                ui.runBtn.disabled = false;
                ui.actionText.textContent = "SYSTEM READY";

            } else {
                throw new Error('Connection refused');
            }
        } catch (err) {
            isConnected = false;
            State.addLog(`Connection Failed: ${err.message}`, 'ERR');
            State.setStatus('Offline', false);
            ui.actionText.textContent = "SYSTEM ERROR";

            // Allow retry via run button (change icon behavior?)
            // For now just log
        }
    }

    // =========================================================================
    // INTERACTIONS
    // =========================================================================

    ui.runBtn.addEventListener('click', async () => {
        if (!isConnected) return;

        State.addLog('Executing voice command injection...', 'SYS');
        State.setProgress(0);
        ui.actionText.textContent = "INJECTING...";

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    const btn = document.querySelector('.formflow-voice-btn');
                    if (btn) btn.click();
                }
            });

            State.setProgress(100);
            State.addLog('Voice overlay activated.', 'SYS');
            setTimeout(() => window.close(), 1000);

        } catch (err) {
            State.addLog(`Injection Error: ${err.message}`, 'ERR');
        }
    });

    // Start
    runBootSequence();
});
