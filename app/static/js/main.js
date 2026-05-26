/**
 * Blue.AI — main.js
 * Protecting the Lungs of Our Coastline
 * Core client-side functionality for the Blue.AI platform.
 */

'use strict';

/* ==========================================================================
   1. Navbar Scroll Effect
   ========================================================================== */
(function initNavbarScroll() {
    const nav = document.getElementById('mainNav');
    if (!nav) return;

    let lastScrollY = window.scrollY;

    function onScroll() {
        const currentScrollY = window.scrollY;

        if (currentScrollY > 60) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }

        lastScrollY = currentScrollY;
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // run once on load
})();

/* ==========================================================================
   2. Auto-dismiss Flash Messages
   ========================================================================== */
(function initFlashMessages() {
    const DISMISS_DELAY = 5000; // 5 seconds

    function dismissAlert(alertEl) {
        alertEl.classList.remove('show');
        alertEl.classList.add('fade');
        setTimeout(() => alertEl.remove(), 300);
    }

    function scheduleAutoDismiss() {
        const alerts = document.querySelectorAll('#flash-container .alert');
        alerts.forEach((alert) => {
            if (alert.dataset.autoDismissScheduled) return;
            alert.dataset.autoDismissScheduled = 'true';
            setTimeout(() => dismissAlert(alert), DISMISS_DELAY);
        });
    }

    // Run on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scheduleAutoDismiss);
    } else {
        scheduleAutoDismiss();
    }
})();

/* ==========================================================================
   3. Animated Counter
   ========================================================================== */

/**
 * Animate a numeric counter from 0 to `target`.
 * @param {HTMLElement} element  - The DOM element whose text will be updated.
 * @param {number}      target   - The final value to count to.
 * @param {number}      duration - Animation duration in milliseconds.
 * @param {string}      [suffix] - Optional suffix (e.g. '+', '%', 'K').
 */
function animateCounter(element, target, duration, suffix) {
    if (!element) return;

    const start      = 0;
    const startTime  = performance.now();
    const numericSuffix = suffix || element.dataset.suffix || '';
    const decimals   = parseInt(element.dataset.decimals || '0', 10);

    // Ease-out cubic
    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    function tick(currentTime) {
        const elapsed  = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased    = easeOutCubic(progress);
        const current  = start + (target - start) * eased;

        element.textContent = current.toFixed(decimals) + numericSuffix;

        if (progress < 1) {
            requestAnimationFrame(tick);
        } else {
            element.textContent = target.toFixed(decimals) + numericSuffix;
        }
    }

    requestAnimationFrame(tick);
}

/* ==========================================================================
   4. IntersectionObserver — Trigger Counters When In Viewport
   ========================================================================== */
(function initCounterObserver() {
    if (typeof IntersectionObserver === 'undefined') return;

    const observerOptions = {
        root:       null,
        rootMargin: '0px 0px -80px 0px',
        threshold:  0.2,
    };

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;

            const el = entry.target;
            const target   = parseFloat(el.dataset.target || el.textContent);
            const duration = parseInt(el.dataset.duration || '1800', 10);
            const suffix   = el.dataset.suffix || '';

            animateCounter(el, target, duration, suffix);
            obs.unobserve(el); // only animate once
        });
    }, observerOptions);

    function attachObservers() {
        const counters = document.querySelectorAll('[data-counter]');
        counters.forEach((el) => observer.observe(el));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachObservers);
    } else {
        attachObservers();
    }
})();

/* ==========================================================================
   5. Donation Amount Button Selector
   ========================================================================== */
(function initAmountSelector() {
    function setup() {
        const containers = document.querySelectorAll('.amount-selector');

        containers.forEach((container) => {
            const hiddenInput = document.getElementById(
                container.dataset.target || 'donation_amount'
            );
            const buttons = container.querySelectorAll('.amount-btn');

            buttons.forEach((btn) => {
                btn.addEventListener('click', () => {
                    // Deactivate all siblings
                    buttons.forEach((b) => b.classList.remove('active'));
                    // Activate clicked
                    btn.classList.add('active');
                    // Update hidden input
                    if (hiddenInput) {
                        hiddenInput.value = btn.dataset.value || btn.textContent.trim().replace(/[^0-9.]/g, '');
                        // Dispatch change event so other listeners can react
                        hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
            });

            // Pre-select if hidden input already has a value
            if (hiddenInput && hiddenInput.value) {
                buttons.forEach((btn) => {
                    const btnVal = btn.dataset.value || btn.textContent.trim().replace(/[^0-9.]/g, '');
                    if (btnVal === hiddenInput.value) {
                        btn.classList.add('active');
                    }
                });
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

/* ==========================================================================
   6. Firebase Client-Side Auth Helper
   ========================================================================== */

/**
 * Sign in with email and password using Firebase, then submit the form
 * with the returned ID token so the Flask backend can verify it.
 *
 * Usage in a login form:
 *   <form id="loginForm" onsubmit="handleFirebaseLogin(event)">
 *     ...
 *     <input type="hidden" name="id_token" id="id_token">
 *   </form>
 *
 * @param {string} email
 * @param {string} password
 * @param {string} [formId] - ID of the form to submit after auth (default: 'loginForm')
 * @returns {Promise<void>}
 */
async function loginWithEmailPassword(email, password, formId) {
    const auth   = window._firebaseAuth;
    const signIn = window._firebaseSignIn;

    if (!auth || !signIn) {
        console.error('Firebase is not initialised. Check that firebase_config is passed to the template.');
        throw new Error('Firebase not available');
    }

    try {
        const userCredential = await signIn(auth, email, password);
        const idToken        = await userCredential.user.getIdToken();

        const targetFormId = formId || 'loginForm';
        const form         = document.getElementById(targetFormId);

        if (!form) {
            throw new Error(`Form #${targetFormId} not found in DOM.`);
        }

        // Inject the id_token into the hidden input
        let tokenInput = form.querySelector('input[name="id_token"]');
        if (!tokenInput) {
            tokenInput      = document.createElement('input');
            tokenInput.type = 'hidden';
            tokenInput.name = 'id_token';
            form.appendChild(tokenInput);
        }
        tokenInput.value = idToken;

        form.submit();
    } catch (error) {
        console.error('Firebase sign-in error:', error.code, error.message);
        throw error; // re-throw so the calling UI can handle it
    }
}

/**
 * Convenience handler for form submit events.
 * Attach to a form's onsubmit:
 *   <form onsubmit="handleFirebaseLogin(event)">
 *
 * @param {SubmitEvent} event
 */
async function handleFirebaseLogin(event) {
    event.preventDefault();

    const form         = event.target;
    const emailInput   = form.querySelector('input[type="email"], input[name="email"]');
    const passwordInput = form.querySelector('input[type="password"], input[name="password"]');
    const submitBtn    = form.querySelector('[type="submit"]');
    const errorEl      = document.getElementById('loginError');

    if (!emailInput || !passwordInput) {
        console.error('Could not find email/password inputs in the form.');
        return;
    }

    const email    = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        showFormError(errorEl, 'Please enter your email and password.');
        return;
    }

    // Show loading state
    const originalText = setButtonLoading(submitBtn, 'Signing in...');

    try {
        await loginWithEmailPassword(email, password, form.id);
    } catch (error) {
        const message = firebaseErrorToMessage(error.code);
        showFormError(errorEl, message);
        restoreButton(submitBtn, originalText);
    }
}

/**
 * Map Firebase error codes to user-friendly messages.
 * @param {string} code - Firebase error code (e.g. 'auth/wrong-password')
 * @returns {string}
 */
function firebaseErrorToMessage(code) {
    const messages = {
        'auth/user-not-found':      'No account found with this email address.',
        'auth/wrong-password':      'Incorrect password. Please try again.',
        'auth/invalid-email':       'Please enter a valid email address.',
        'auth/user-disabled':       'This account has been disabled. Contact support.',
        'auth/too-many-requests':   'Too many failed attempts. Please try again later.',
        'auth/network-request-failed': 'Network error. Check your connection and try again.',
        'auth/invalid-credential':  'Invalid email or password.',
    };
    return messages[code] || 'Sign-in failed. Please try again.';
}

/* ==========================================================================
   7. Form Validation Helpers
   ========================================================================== */

/**
 * Display an error message in a designated error element.
 * @param {HTMLElement|null} el      - The element to write the error into.
 * @param {string}           message
 */
function showFormError(el, message) {
    if (!el) {
        console.warn('showFormError: no error element provided. Message:', message);
        return;
    }
    el.textContent = message;
    el.style.display = 'block';
    el.setAttribute('role', 'alert');
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Clear a form error element.
 * @param {HTMLElement|null} el
 */
function clearFormError(el) {
    if (!el) return;
    el.textContent = '';
    el.style.display = 'none';
    el.removeAttribute('role');
}

/**
 * Mark a field as valid or invalid and show a feedback message.
 * @param {HTMLElement} field
 * @param {boolean}     isValid
 * @param {string}      [message] - Feedback message (for invalid state).
 */
function setFieldValidity(field, isValid, message) {
    field.classList.toggle('is-valid',   isValid);
    field.classList.toggle('is-invalid', !isValid);

    // Update adjacent .invalid-feedback if present
    const feedback = field.parentElement && field.parentElement.querySelector('.invalid-feedback');
    if (feedback && message) {
        feedback.textContent = message;
    }
}

/**
 * Simple email format validator.
 * @param {string} email
 * @returns {boolean}
 */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

/**
 * Real-time input validation bootstrap for a form.
 * Attaches blur listeners to all required inputs.
 * @param {HTMLFormElement} form
 */
function initLiveValidation(form) {
    if (!form) return;

    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');

    inputs.forEach((input) => {
        input.addEventListener('blur', () => {
            if (!input.value.trim()) {
                setFieldValidity(input, false, 'This field is required.');
            } else if (input.type === 'email' && !isValidEmail(input.value)) {
                setFieldValidity(input, false, 'Please enter a valid email address.');
            } else {
                setFieldValidity(input, true);
            }
        });

        // Clear error on new input
        input.addEventListener('input', () => {
            if (input.classList.contains('is-invalid')) {
                input.classList.remove('is-invalid');
            }
        });
    });
}

/* ==========================================================================
   8. Smooth Scroll to Sections
   ========================================================================== */
(function initSmoothScroll() {
    function setup() {
        document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
            anchor.addEventListener('click', (e) => {
                const href = anchor.getAttribute('href');
                if (!href || href === '#') return;

                const target = document.querySelector(href);
                if (!target) return;

                e.preventDefault();

                const navHeight = document.getElementById('mainNav')
                    ? document.getElementById('mainNav').offsetHeight
                    : 70;

                const top = target.getBoundingClientRect().top + window.scrollY - navHeight - 16;

                window.scrollTo({ top, behavior: 'smooth' });

                // Update URL hash without triggering jump
                history.pushState(null, '', href);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

/* ==========================================================================
   9. Report Generation — Loading State
   ========================================================================== */

/**
 * Set a button into a loading state (spinner + text).
 * @param {HTMLElement} btn           - The button element.
 * @param {string}      [loadingText] - Text to show while loading.
 * @returns {string} The original button HTML (for restoration).
 */
function setButtonLoading(btn, loadingText) {
    if (!btn) return '';
    const original = btn.innerHTML;
    btn.disabled   = true;
    btn.innerHTML  =
        `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
         ${loadingText || 'Loading...'}`;
    return original;
}

/**
 * Restore a button from loading state.
 * @param {HTMLElement} btn
 * @param {string}      originalHTML
 */
function restoreButton(btn, originalHTML) {
    if (!btn) return;
    btn.disabled  = false;
    btn.innerHTML = originalHTML;
}

/**
 * Attach loading state to all buttons with `data-loading-text` attribute.
 * Useful for report generation, form submission, etc.
 * Usage: <button data-loading-text="Generating Report...">Generate</button>
 */
(function initLoadingButtons() {
    function setup() {
        document.querySelectorAll('[data-loading-text]').forEach((btn) => {
            const form = btn.closest('form');
            if (!form) return;

            form.addEventListener('submit', () => {
                setButtonLoading(btn, btn.dataset.loadingText);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

/* ==========================================================================
   10. Global Spinner Overlay Helper
   ========================================================================== */

/**
 * Show or hide the full-page spinner overlay.
 * Requires a `.spinner-overlay` element in the DOM.
 * @param {boolean} show
 * @param {string}  [message]
 */
function toggleSpinner(show, message) {
    let overlay = document.querySelector('.spinner-overlay');

    if (show && !overlay) {
        // Create overlay on-the-fly if not present in template
        overlay = document.createElement('div');
        overlay.className = 'spinner-overlay';
        overlay.innerHTML =
            `<div class="spinner-box">
                <div class="spinner-border" role="status"></div>
                <p>${message || 'Please wait...'}</p>
             </div>`;
        document.body.appendChild(overlay);
        // Trigger reflow before adding active class
        void overlay.offsetWidth;
    }

    if (!overlay) return;

    if (show) {
        if (message) {
            const p = overlay.querySelector('p');
            if (p) p.textContent = message;
        }
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    } else {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/* ==========================================================================
   11. Scroll-Reveal Animation Helper (Fade-In on Scroll)
   ========================================================================== */
(function initScrollReveal() {
    if (typeof IntersectionObserver === 'undefined') return;

    const options = {
        root:       null,
        rootMargin: '0px 0px -60px 0px',
        threshold:  0.1,
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                entry.target.style.opacity = '1';
                observer.unobserve(entry.target);
            }
        });
    }, options);

    function setup() {
        document.querySelectorAll('[data-reveal]').forEach((el) => {
            el.style.opacity = '0';
            observer.observe(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

/* ==========================================================================
   12. Expose Public API
   ========================================================================== */
window.BlueAI = {
    animateCounter,
    loginWithEmailPassword,
    handleFirebaseLogin,
    showFormError,
    clearFormError,
    setFieldValidity,
    isValidEmail,
    initLiveValidation,
    setButtonLoading,
    restoreButton,
    toggleSpinner,
};
