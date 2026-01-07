/**
 * FormFlow AI - Google Forms Specific Handler
 * 
 * Handles:
 * 1. Authentication detection
 * 2. Sticky "Please Sign In" banner
 * 3. Specific Google Forms DOM manipulation for filling
 */

(function () {
    'use strict';

    console.log('FormFlow: Google Forms handler loaded');

    class GoogleFormHandler {
        constructor() {
            this.isAuthenticated = this.checkAuthentication();
            this.init();
        }

        init() {
            if (!this.isAuthenticated) {
                this.showAuthenticationPrompt();
            } else {
                this.notifyBackend();
                this.setupMessageListener();
            }
        }

        checkAuthentication() {
            // Google Forms usually shows a profile picture or account info when logged in.
            // When not logged in, there's often a "Sign in" button or specific text.

            // Look for common logged-in indicators
            // 1. Aria-label containing "Google Account" (common in top-right)
            const profileElement = document.querySelector('[aria-label*="Google Account"]');

            // 2. "Sign in" link/button presence (indication of NOT logged in)
            // Be careful, sometimes "Sign in" is present even if logged in (e.g. "Switch account")
            // A strong indicator of NOT being logged in on a form page is the absence of the form itself 
            // OR a large "Sign in to continue" message.

            // However, for the specific requirement of "Organization restricted", 
            // if we are seeing the form, we are likely okay. 
            // If we are blocked, we usually see a generic "You need permission" or "Sign in" page.

            // Let's rely on the profile element for now as a positive signal.
            // If we are on a login page, the URL usually contains 'accounts.google.com' or 'ServiceLogin'.
            // But this script runs on `docs.google.com/forms/*`.

            // If we are on the form page but not logged in (public form), we might still want to fill it?
            // The user requirement says "Restrict to organization" block automation. 
            // If it's restricted, the user MUST be logged in to even SEE the form.

            // So if we can see the form fields, we are good to go? 
            // Not necessarily, we want to ensure the USER context is used.

            return !!profileElement || this.isFormVisible();
        }

        isFormVisible() {
            return document.querySelector('form') !== null;
        }

        showAuthenticationPrompt() {
            // Only show if we really think they need to login. 
            // If the form is visible, maybe let them proceed?
            // But the user specifically wants to handle the "Required sign-in" case.

            if (this.isFormVisible()) {
                console.log('Form is visible, assuming authenticated or public form.');
                return;
            }

            console.log('Authentication required or form not accessible.');

            const banner = document.createElement('div');
            banner.style.cssText = `
                position: fixed; 
                top: 20px; 
                left: 50%; 
                transform: translateX(-50%);
                background: #ea4335; 
                color: white; 
                padding: 16px 24px; 
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3); 
                z-index: 10000;
                font-family: 'Google Sans', Roboto, sans-serif;
                display: flex;
                align-items: center;
                gap: 12px;
                animation: slideDown 0.5s ease;
            `;

            banner.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                </svg>
                <div>
                    <div style="font-weight: bold; margin-bottom: 4px;">Authentication Required</div>
                    <div style="font-size: 14px;">Please sign in to Google to access this form.</div>
                </div>
                <a href="https://accounts.google.com/ServiceLogin" target="_blank" 
                   style="background: white; color: #ea4335; padding: 6px 12px; 
                          border-radius: 4px; text-decoration: none; font-weight: 500; margin-left: 12px;">
                   Sign In
                </a>
            `;

            // Styles for animation
            const style = document.createElement('style');
            style.textContent = `
                @keyframes slideDown {
                    from { transform: translate(-50%, -100%); opacity: 0; }
                    to { transform: translate(-50%, 0); opacity: 1; }
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(banner);
        }

        notifyBackend() {
            // Send message to background script
            chrome.runtime.sendMessage({
                type: 'GOOGLE_FORM_DETECTED',
                url: window.location.href
            });
        }

        setupMessageListener() {
            chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
                if (request.type === 'FILL_FORM') {
                    console.log('Received FILL_FORM request:', request.data);
                    this.fillForm(request.data)
                        .then(() => sendResponse({ success: true }))
                        .catch(err => sendResponse({ success: false, error: err.message }));
                    return true; // async response
                }
            });
        }

        async fillForm(formData) {
            console.log('Filling Google Form with data:', formData);

            // formData is expected to be { "Question Label": "Answer Value", ... }
            // Google Forms specific structures:
            // Text inputs: input[type="text"] (often hidden mostly), usually textarea or input.
            // They often use ARIA labels matching the question title.

            for (const [question, answer] of Object.entries(formData)) {
                await this.fillField(question, answer);
            }
        }

        async fillField(question, answer) {
            // Strategy: Find the container with the question text, then find the input within it.
            // Google Forms structure is usually: [Role="listitem"] -> [Role="heading"] (question) -> Input structure

            // 1. Find all potential question containers
            const items = document.querySelectorAll('[role="listitem"]');
            let targetItem = null;

            for (const item of items) {
                if (item.innerText.includes(question)) {
                    targetItem = item;
                    break;
                }
            }

            if (!targetItem) {
                console.warn(`Could not find question matching: "${question}"`);
                return;
            }

            console.log(`Found container for "${question}"`, targetItem);

            // 2. Identify input type and fill

            // Text Input (Short answer / Paragraph)
            const textInput = targetItem.querySelector('input[type="text"], textarea');
            if (textInput) {
                textInput.value = answer;
                textInput.dispatchEvent(new Event('input', { bubbles: true }));
                textInput.dispatchEvent(new Event('change', { bubbles: true }));
                // Sometimes also need 'focus' and 'blur' to trigger validation
                textInput.dispatchEvent(new Event('focus', { bubbles: true }));
                textInput.dispatchEvent(new Event('blur', { bubbles: true }));
                return;
            }

            // Radio Buttons
            const radios = targetItem.querySelectorAll('[role="radio"]');
            if (radios.length > 0) {
                for (const radio of radios) {
                    const label = radio.getAttribute('aria-label') || radio.innerText;
                    if (label && label.toLowerCase() === answer.toLowerCase()) {
                        radio.click();
                        return;
                    }
                    // Fallback: check surrounding text
                    if (radio.closest('label')?.innerText.toLowerCase().includes(answer.toLowerCase())) {
                        radio.click();
                        return;
                    }
                }
            }

            // Checkboxes
            const checkboxes = targetItem.querySelectorAll('[role="checkbox"]');
            if (checkboxes.length > 0) {
                // If answer is array, loop. If string, just assume one.
                const answers = Array.isArray(answer) ? answer : [answer];

                for (const checkbox of checkboxes) {
                    const label = checkbox.getAttribute('aria-label') || checkbox.innerText;
                    const matches = answers.some(a =>
                        (label && label.toLowerCase() === a.toLowerCase()) ||
                        (checkbox.closest('label')?.innerText.toLowerCase().includes(a.toLowerCase()))
                    );

                    if (matches) {
                        // Check if not already checked (aria-checked="true")
                        if (checkbox.getAttribute('aria-checked') !== 'true') {
                            checkbox.click();
                        }
                    }
                }
                return;
            }

            // Dropdown (ListBox)
            // Complex in Google Forms. usually has role="listbox".
            // Needs click to open, then click option.
            const listbox = targetItem.querySelector('[role="listbox"]');
            if (listbox) {
                // Click to open
                listbox.click();

                // Wait small delay for options to appear in DOM (they are often appended to body)
                await new Promise(r => setTimeout(r, 500));

                // Options are usually in a separate container, [role="option"]
                // We need to look globally or in the newly opened container
                const options = document.querySelectorAll('[role="option"]');
                for (const option of options) {
                    const text = option.innerText || option.getAttribute('data-value');
                    if (text && text.toLowerCase() === answer.toLowerCase()) {
                        option.click();
                        return;
                    }
                }

                // If failed, try to close?
                // document.body.click(); 
            }
        }
    }

    // Initialize
    new GoogleFormHandler();

})();
