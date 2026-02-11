/**
 * FormFlow AI - Vocabulary Manager Logic
 */

const API_BASE = 'http://localhost:8001'; // Adjust if backend port differs

// DOM Elements
const heardInput = document.getElementById('heardInput');
const correctInput = document.getElementById('correctInput');
const contextInput = document.getElementById('contextInput');
const addForm = document.getElementById('addForm');
const correctionsList = document.getElementById('correctionsList');
const emptyState = document.getElementById('emptyState');
const testInput = document.getElementById('testInput');
const testBtn = document.getElementById('testBtn');
const testResult = document.getElementById('testResult');
const testOutput = document.getElementById('testOutput');
const toast = document.getElementById('toast');

// State
let corrections = [];

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchCorrections();
});

// Event Listeners
if (addForm) {
    addForm.addEventListener('submit', addCorrection);
}
testBtn.addEventListener('click', testCorrection);

testInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') testCorrection();
});

// Functions

async function fetchCorrections() {
    try {
        const response = await fetch(`${API_BASE}/vocabulary/corrections`);
        if (!response.ok) throw new Error('Failed to fetch');

        corrections = await response.json();
        renderList();
    } catch (err) {
        console.error('Error fetching corrections:', err);
        showToast('Error connecting to backend', true);
    }
}

async function addCorrection(e) {
    if (e) e.preventDefault();

    const heard = heardInput.value.trim();
    const correct = correctInput.value.trim();
    const context = contextInput.value.trim();

    if (!heard || !correct) {
        showToast('Please fill in both fields', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/vocabulary/correction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                heard,
                correct,
                context
            })
        });

        if (!response.ok) throw new Error('Failed to add');

        // Clear inputs
        heardInput.value = '';
        correctInput.value = '';
        contextInput.value = '';

        // Refresh list
        await fetchCorrections();
        showToast('Correction added successfully');

    } catch (err) {
        console.error('Error adding correction:', err);
        showToast('Failed to save correction', true);
    }
}

async function deleteCorrection(id) {
    if (!confirm('Are you sure you want to delete this rule?')) return;

    try {
        const response = await fetch(`${API_BASE}/vocabulary/correction/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete');

        await fetchCorrections();
        showToast('Correction deleted');
    } catch (err) {
        console.error('Error deleting:', err);
        showToast('Failed to delete', true);
    }
}

async function testCorrection() {
    const text = testInput.value.trim();
    if (!text) return;

    try {
        const response = await fetch(`${API_BASE}/vocabulary/apply?text=${encodeURIComponent(text)}`, {
            method: 'POST'
        });

        const data = await response.json();

        testResult.style.display = 'block';
        testOutput.textContent = data.corrected;

        if (data.original !== data.corrected) {
            testOutput.style.color = 'var(--success)';
        } else {
            testOutput.style.color = 'var(--text-secondary)';
        }

    } catch (err) {
        console.error('Test failed:', err);
    }
}

function renderList() {
    correctionsList.innerHTML = '';

    if (corrections.length === 0) {
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';

    correctionsList.innerHTML = corrections.map(c => `
        <div class="correction-item">
            <div class="correction-info">
                <div class="correction-main">
                    <span class="heard-text">${escapeHtml(c.heard)}</span>
                    <svg class="arrow-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                    <span class="correct-text">${escapeHtml(c.correct)}</span>
                </div>
                <div class="correction-meta">
                    ${c.context ? `<span style="background:var(--muted); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border);">${escapeHtml(c.context)}</span> • ` : ''}
                    Used ${c.usage_count} times
                </div>
            </div>
            <button class="btn btn-ghost" onclick="deleteCorrection(${c.id})" title="Delete Rule">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
            </button>
        </div>
    `).join('');
}

function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = msg;
    // Use classList for styling instead of inline styles
    toast.className = isError ? 'toast show error' : 'toast show';

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expose delete function to window
window.deleteCorrection = deleteCorrection;
