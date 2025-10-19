/**
 * AuthManager - Authentication and upgrade management system
 * Handles user authentication state and upgrade modal functionality
 */

// IIFE wrapper with class redeclaration guard
(function() {
    'use strict';
    
    // Prevent class redeclaration
    if (window.AuthManager) {
        console.warn('AuthManager class already declared, skipping redeclaration');
        return;
    }

class AuthManager {
    constructor() {
        // Singleton pattern: return existing instance if available
        if (window.__authManager) {
            console.warn('AuthManager singleton already exists, returning existing instance');
            return window.__authManager;
        }
        
        this.user = null;
        this.isAuthenticated = false;
        this.isPremium = false;
        this.isRegisteringFromUpgrade = false; // Track if user is registering from upgrade modal
        this.init();
    }

    /**
     * Initialize AuthManager and attach to window
     */
    init() {
        // Attach to window for global access (singleton reference)
        window.__authManager = this;
        // Also maintain backward compatibility reference
        window.authManager = this;
        
        // Check authentication status on load
        this.checkAuthStatus();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize premium stats on page load
        this.initializePremiumStats();
        
        console.log('AuthManager initialized');
    }

    /**
     * Initialize premium stats on page load and set up periodic updates
     */
    initializePremiumStats() {
        // Initial load of premium stats
        this.fetchPremiumStats();
        
        // Set up periodic refresh every 2 minutes
        setInterval(() => {
            this.fetchPremiumStats();
        }, 120000);
    }

    /**
     * Fetch premium stats independently (used on page load and periodic updates)
     */
    async fetchPremiumStats() {
        try {
            const response = await fetch('/api/v1/auth/stats', {
                credentials: 'include'  // Include credentials in case endpoint requires auth
            });
            
            if (response.ok) {
                const stats = await response.json();
                this.updatePremiumStats(stats);
                this.updateFooterCounters(stats);
            } else {
                console.log('Premium stats endpoint not accessible, using defaults');
            }
        } catch (error) {
            console.log('Could not fetch premium stats:', error.message);
        }
    }

    /**
     * Check current authentication status
     */
    async checkAuthStatus() {
        try {
            const response = await fetch('/api/v1/auth/status', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.isAuthenticated = data.is_authenticated || false;
                this.isPremium = data.user?.is_premium || false;
                this.updateAuthUI();
                this.renderHeroCTAs();
            } else {
                // User not authenticated - render guest hero
                this.renderHeroCTAs();
            }
        } catch (error) {
            console.log('User not authenticated or error checking status');
            // Render guest hero on error
            this.renderHeroCTAs();
        }
    }

    /**
     * Update authentication UI based on current state
     */
    updateAuthUI() {
        const guestState = document.getElementById('guest-state');
        const loggedInState = document.getElementById('logged-in-state');
        const usernameDisplay = document.getElementById('username-display');
        
        if (this.isAuthenticated) {
            // Show logged-in state
            if (guestState) guestState.classList.add('hidden');
            if (loggedInState) loggedInState.classList.remove('hidden');
            
            // Update username
            if (usernameDisplay && this.user?.username) {
                usernameDisplay.textContent = this.user.username;
            }
        } else {
            // Show guest state
            if (guestState) guestState.classList.remove('hidden');
            if (loggedInState) loggedInState.classList.add('hidden');
        }
    }

    /**
     * Get user tier (guest, free, or premium)
     * @returns {string} - User tier: 'guest', 'free', or 'premium'
     */
    getUserTier() {
        if (!this.isAuthenticated) return 'guest';
        if (this.user?.plan_tier) return this.user.plan_tier;
        return this.isPremium ? 'premium' : 'free';
    }

    /**
     * Get insights quota information
     * @returns {Object} - {remaining: number, total: number}
     */
    getInsightsQuota() {
        const remaining = this.user?.insights_remaining || 0;
        const total = this.user?.insights_total || 1;
        return { remaining, total };
    }

    /**
     * Render hero CTAs based on user tier
     * - Guest: Show both [Try Free] and [Unlock Premium]
     * - Free: Show [Unlock Premium] + "View My Insights" link
     * - Premium: Show "✓ Premium Active" badge + [View Latest Insights]
     */
    renderHeroCTAs() {
        const container = document.getElementById('hero-cta-container');
        if (!container) {
            console.warn('Hero CTA container not found');
            return;
        }

        const tier = this.getUserTier();
        const quota = this.getInsightsQuota();
        
        let html = '';
        
        if (tier === 'guest') {
            // Guest: Both buttons
            html = `
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <button
                        id="hero-cta-free"
                        class="bg-canvas-surface border-2 border-canvas-accent hover:bg-canvas-accent/10 text-white text-base px-6 py-3 rounded-lg transition-all duration-200 font-semibold"
                    >
                        <i class="fas fa-play-circle mr-2"></i>
                        ${window.AppTexts?.hero?.tryFree || 'Try Free'}
                    </button>
                    <button
                        id="hero-cta-premium"
                        class="bg-gradient-to-r from-canvas-accent to-canvas-accent2 hover:opacity-90 text-white text-base px-6 py-3 rounded-lg transition-all duration-200 font-semibold shadow-lg"
                    >
                        <i class="fas fa-crown mr-2"></i>
                        ${window.AppTexts?.hero?.unlockPremium || 'Unlock Premium'}
                    </button>
                </div>
            `;
        } else if (tier === 'free') {
            // Free: Upgrade button + View Insights link + contextual quota message
            const isPremiumDay = this.user?.is_premium_day || false;
            const nextDrawDay = this.user?.next_draw_day || 'Saturday';
            
            // Build contextual quota message
            let quotaMessage = '';
            if (isPremiumDay) {
                quotaMessage = window.AppTexts?.quota?.premiumDay?.message?.replace('{count}', quota.total) || 
                              `Today is your Premium Day! ${quota.total} insights available`;
            } else {
                quotaMessage = window.AppTexts?.quota?.regularDay?.message || 
                              `1 insight today • Saturday Premium Day: 5 insights`;
            }
            
            html = `
                <div class="flex flex-col gap-4 items-center">
                    <button
                        id="hero-cta-premium"
                        class="bg-gradient-to-r from-canvas-accent to-canvas-accent2 hover:opacity-90 text-white text-base px-6 py-3 rounded-lg transition-all duration-200 font-semibold shadow-lg"
                    >
                        <i class="fas fa-crown mr-2"></i>
                        ${window.AppTexts?.hero?.unlockPremium || 'Unlock Premium'}
                    </button>
                    <div class="text-center">
                        <a
                            href="#predictions-section"
                            class="text-white/70 hover:text-canvas-accent text-sm font-medium transition-colors block"
                        >
                            <i class="fas fa-chart-line mr-1"></i>
                            ${window.AppTexts?.hero?.viewMyInsights || 'View My Insights'}
                        </a>
                        <p class="text-white/50 text-xs mt-1">
                            ${quotaMessage}
                        </p>
                    </div>
                </div>
            `;
        } else {
            // Premium: Badge + View Latest Insights button
            html = `
                <div class="flex flex-col gap-4 items-center">
                    <div class="inline-flex items-center px-4 py-2 rounded-full bg-gradient-to-r from-canvas-accent to-canvas-accent2 text-white text-sm font-semibold">
                        <i class="fas fa-check-circle mr-2"></i>
                        ${window.AppTexts?.hero?.premiumActive || '✓ Premium Active'}
                    </div>
                    <button
                        id="hero-cta-view-insights"
                        class="bg-canvas-surface border-2 border-canvas-accent hover:bg-canvas-accent/10 text-white text-base px-6 py-3 rounded-lg transition-all duration-200 font-semibold"
                    >
                        <i class="fas fa-chart-line mr-2"></i>
                        ${window.AppTexts?.hero?.viewLatestInsights || 'View Latest Insights'}
                    </button>
                </div>
            `;
        }
        
        // Update container with smooth transition
        container.style.opacity = '0';
        setTimeout(() => {
            container.innerHTML = html;
            container.style.opacity = '1';
            
            // Re-attach event listeners
            this.attachHeroCTAListeners();
        }, 150);
    }

    /**
     * Attach event listeners to hero CTA buttons
     */
    attachHeroCTAListeners() {
        const heroCTAFree = document.getElementById('hero-cta-free');
        const heroCTAPremium = document.getElementById('hero-cta-premium');
        const heroCTAViewInsights = document.getElementById('hero-cta-view-insights');
        
        if (heroCTAFree) {
            heroCTAFree.addEventListener('click', () => {
                this.handleUpgradeClick();
            });
        }
        
        if (heroCTAPremium) {
            heroCTAPremium.addEventListener('click', () => {
                this.handleUpgradeClick();
            });
        }
        
        if (heroCTAViewInsights) {
            heroCTAViewInsights.addEventListener('click', () => {
                document.getElementById('predictions-section')?.scrollIntoView({ behavior: 'smooth' });
            });
        }
    }

    /**
     * Setup event listeners for modal interactions
     */
    setupEventListeners() {
        // Login and Register button event listeners
        const loginBtn = document.getElementById('login-btn');
        const registerBtn = document.getElementById('register-btn');
        
        if (loginBtn) {
            loginBtn.addEventListener('click', () => {
                console.log('Login button clicked');
                this.showLoginModal();
            });
        }
        
        if (registerBtn) {
            registerBtn.addEventListener('click', () => {
                console.log('Register button clicked - opening upgrade modal with register view');
                this.trackEvent('register_button_clicked');
                this.showUpgradeModal({ view: 'register' });
            });
        }

        // Modal close buttons
        const loginClose = document.getElementById('login-close');
        const registerClose = document.getElementById('register-close');
        
        if (loginClose) {
            loginClose.addEventListener('click', () => this.hideLoginModal());
        }
        
        // Legacy: register-close button support - now rare since register-modal is removed
        if (registerClose) {
            registerClose.addEventListener('click', () => this.hideRegisterModal());
        }

        // Modal switching
        const switchToRegister = document.getElementById('switch-to-register');
        const switchToLogin = document.getElementById('switch-to-login');
        
        if (switchToRegister) {
            switchToRegister.addEventListener('click', () => {
                this.hideLoginModal();
                this.showUpgradeModal({ view: 'register' });
            });
        }
        
        // Updated: switch-to-login now works within the upgrade modal
        if (switchToLogin) {
            switchToLogin.addEventListener('click', () => {
                console.log('Switch to login clicked from upgrade modal register view');
                this.hideUpgradeModal();
                this.showLoginModal();
            });
        }

        // Form submissions
        const loginForm = document.getElementById('login-form');
        
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }
        
        // Registration buttons (two separate flows)
        const registerPremiumBtn = document.getElementById('register-premium-btn');
        const registerFreeBtn = document.getElementById('register-free-btn');
        
        if (registerPremiumBtn) {
            registerPremiumBtn.addEventListener('click', (e) => this.handlePremiumRegister(e));
        }
        
        if (registerFreeBtn) {
            registerFreeBtn.addEventListener('click', (e) => this.handleFreeRegister(e));
        }

        // User menu
        const userMenuBtn = document.getElementById('user-menu-btn');
        const logoutBtn = document.getElementById('logout-btn');
        
        if (userMenuBtn) {
            userMenuBtn.addEventListener('click', () => this.toggleUserDropdown());
        }
        
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.handleLogout());
        }

        // System Status link
        const systemStatusLink = document.getElementById('system-status-link');
        if (systemStatusLink) {
            systemStatusLink.addEventListener('click', (e) => this.handleSystemStatusClick(e));
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#user-menu-btn') && !e.target.closest('#user-dropdown')) {
                this.hideUserDropdown();
            }
        });

        // Close modals when clicking outside
        const loginModal = document.getElementById('login-modal');
        const registerModal = document.getElementById('register-modal');
        const upgradeModal = document.getElementById('upgrade-modal');
        
        if (loginModal) {
            loginModal.addEventListener('click', (e) => {
                if (e.target.id === 'login-modal') this.hideLoginModal();
            });
        }
        
        // Legacy register modal support - fallback if it still exists
        if (registerModal) {
            registerModal.addEventListener('click', (e) => {
                if (e.target.id === 'register-modal') this.hideRegisterModal();
            });
        }
        
        if (upgradeModal) {
            upgradeModal.addEventListener('click', (e) => {
                if (e.target === upgradeModal) {
                    this.hideUpgradeModal();
                }
            });
        }

        // Close modal with Escape key - now unified to upgrade modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideUpgradeModal();
                this.hideLoginModal();
                // hideRegisterModal is now handled by hideUpgradeModal for unified modal
            }
        });
    }

    /**
     * Show upgrade modal with pricing and CTAs
     * @param {Object} options - Configuration options
     * @param {string} options.view - Initial view: 'offer' (default) or 'register'
     */
    showUpgradeModal(options = {}) {
        console.log('Opening upgrade modal...', options);
        
        const modal = document.getElementById('upgrade-modal');
        if (!modal) {
            console.error('Upgrade modal not found in DOM');
            return;
        }

        // Set initial view - default to 'offer'
        const initialView = options.view || 'offer';
        this.setUpgradeModalView(initialView);

        // Add dynamic content
        this.updateModalContent();
        
        // Show modal with animation
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        
        // Trigger animation
        setTimeout(() => {
            const modalContent = modal.querySelector('.modal-content');
            if (modalContent) {
                modalContent.style.transform = 'scale(1)';
                modalContent.style.opacity = '1';
            }
        }, 10);

        // Track modal open event
        this.trackEvent('upgrade_modal_opened', { initialView });
    }

    /**
     * Set the internal view of the upgrade modal
     * @param {string} view - View to show: 'offer' or 'register'
     */
    setUpgradeModalView(view) {
        console.log(`Switching upgrade modal to ${view} view`);
        
        const offerView = document.getElementById('upgrade-offer-view');
        const registerView = document.getElementById('upgrade-register-view');
        
        // Defensive guards - fallback if elements not found
        if (!offerView || !registerView) {
            console.warn('Upgrade modal views not found - using fallback behavior');
            // Try to find and use old register-modal as fallback
            const fallbackModal = document.getElementById('register-modal');
            if (fallbackModal && view === 'register') {
                fallbackModal.classList.remove('hidden');
                return;
            }
            return;
        }
        
        // Hide both views first
        offerView.classList.add('hidden');
        registerView.classList.add('hidden');
        
        // Show requested view
        if (view === 'register') {
            registerView.classList.remove('hidden');
            this.trackEvent('upgrade_modal_register_view_shown');
        } else {
            offerView.classList.remove('hidden');
            this.trackEvent('upgrade_modal_offer_view_shown');
        }
    }

    /**
     * Show login modal
     * @param {Object} options - Modal options
     * @param {string} options.context - Context for login (e.g., 'admin_required')
     */
    showLoginModal(options = {}) {
        console.log('Opening login modal...', options);
        
        const modal = document.getElementById('login-modal');
        const adminContextDiv = document.getElementById('login-admin-context');
        
        // Store context for post-login handling
        this.loginContext = options.context || null;
        
        // Show/hide admin context message
        if (adminContextDiv) {
            if (options.context === 'admin_required') {
                adminContextDiv.classList.remove('hidden');
            } else {
                adminContextDiv.classList.add('hidden');
            }
        }
        
        if (modal) {
            modal.classList.remove('hidden');
        }
    }

    /**
     * Hide login modal
     */
    hideLoginModal() {
        const modal = document.getElementById('login-modal');
        const adminContextDiv = document.getElementById('login-admin-context');
        
        if (modal) {
            modal.classList.add('hidden');
            this.clearLoginForm();
        }
        
        // Hide admin context message
        if (adminContextDiv) {
            adminContextDiv.classList.add('hidden');
        }
        
        // Clear login context
        this.loginContext = null;
    }

    /**
     * Show register modal (Legacy compatibility - redirects to upgrade modal register view)
     */
    showRegisterModal() {
        console.log('Legacy showRegisterModal called - redirecting to upgrade modal register view');
        this.showUpgradeModal({ view: 'register' });
    }

    /**
     * Legacy compatibility shim for openRegisterModal calls
     * Redirects to unified upgrade modal with register view
     */
    openRegisterModal() {
        console.log('Legacy openRegisterModal called - redirecting to upgrade modal register view');
        this.showUpgradeModal({ view: 'register' });
    }

    /**
     * Hide register modal (Legacy compatibility - now closes upgrade modal)
     */
    hideRegisterModal() {
        console.log('Legacy hideRegisterModal called - closing upgrade modal');
        // Try to find legacy register modal first for compatibility
        const legacyModal = document.getElementById('register-modal');
        if (legacyModal) {
            legacyModal.classList.add('hidden');
            this.clearRegisterForm();
            return;
        }
        
        // If no legacy modal, close the upgrade modal instead
        this.hideUpgradeModal();
    }

    /**
     * Clear login form
     */
    clearLoginForm() {
        const form = document.getElementById('login-form');
        const error = document.getElementById('login-error');
        if (form) form.reset();
        if (error) error.classList.add('hidden');
    }

    /**
     * Clear register form
     */
    clearRegisterForm() {
        const form = document.getElementById('register-form');
        const error = document.getElementById('register-error');
        if (form) form.reset();
        if (error) error.classList.add('hidden');
    }

    /**
     * Toggle user dropdown menu
     */
    toggleUserDropdown() {
        const dropdown = document.getElementById('user-dropdown');
        if (dropdown) {
            dropdown.classList.toggle('hidden');
        }
    }

    /**
     * Hide user dropdown menu
     */
    hideUserDropdown() {
        const dropdown = document.getElementById('user-dropdown');
        if (dropdown) {
            dropdown.classList.add('hidden');
        }
    }

    /**
     * Handle System Status link click with admin verification
     */
    async handleSystemStatusClick(e) {
        e.preventDefault();
        
        // Check if user is authenticated
        if (!this.isAuthenticated) {
            // Not logged in - show login modal with admin context
            this.showLoginModal({ context: 'admin_required' });
            return;
        }
        
        // User is logged in - check if admin
        const isAdmin = this.user?.is_admin || false;
        
        if (isAdmin) {
            // Admin user - redirect to status page
            window.location.href = '/status';
        } else {
            // Not admin - show error message
            this.showAdminRequiredMessage();
        }
    }

    /**
     * Show admin required message
     */
    showAdminRequiredMessage() {
        // Create toast notification or alert
        const message = 'Administrator access only. Your account does not have administrator permissions.';
        
        // Simple alert for now - can be enhanced with toast notification
        alert(message);
    }

    /**
     * Handle login form submission
     */
    async handleLogin(e) {
        e.preventDefault();
        
        const submitBtn = document.getElementById('login-submit');
        const submitText = document.getElementById('login-submit-text');
        const spinner = document.getElementById('login-spinner');
        const errorDiv = document.getElementById('login-error');
        
        // Show loading state
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = window.AppTexts.buttons.verifying;
        if (spinner) spinner.classList.remove('hidden');
        if (errorDiv) errorDiv.classList.add('hidden');
        
        try {
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const rememberMe = document.getElementById('login-remember-me')?.checked || false;
            
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ 
                    login: email, 
                    password,
                    remember_me: rememberMe
                }),
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.user = data.user;
                this.isAuthenticated = true;
                this.isPremium = data.user?.is_premium || false;
                this.updateAuthUI();
                this.renderHeroCTAs();
                
                // Check if login was for admin access to system status
                if (this.loginContext === 'admin_required') {
                    const isAdmin = data.user?.is_admin || false;
                    
                    if (isAdmin) {
                        // Admin user - redirect to status page
                        this.hideLoginModal();
                        window.location.href = '/status';
                        return;
                    } else {
                        // Not admin - show error in modal
                        this.hideLoginModal();
                        this.showAdminRequiredMessage();
                        return;
                    }
                }
                
                // Normal login flow
                this.hideLoginModal();
                
                // Refresh predictions after successful login
                this.refreshPredictionsData();
            } else {
                if (errorDiv) {
                    errorDiv.textContent = data.message || window.AppTexts.errors.authenticationFailed;
                    errorDiv.classList.remove('hidden');
                }
            }
        } catch (error) {
            if (errorDiv) {
                errorDiv.textContent = window.AppTexts.errors.networkError;
                errorDiv.classList.remove('hidden');
            }
        } finally {
            // Reset loading state
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = window.AppTexts.buttons.login;
            if (spinner) spinner.classList.add('hidden');
        }
    }

    /**
     * Handle premium registration - Register + Stripe Checkout flow
     */
    async handlePremiumRegister(e) {
        e.preventDefault();
        
        // Validate form first
        const form = document.getElementById('register-form');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        const submitBtn = document.getElementById('register-premium-btn');
        const submitText = document.getElementById('register-premium-text');
        const spinner = document.getElementById('register-premium-spinner');
        const errorDiv = document.getElementById('register-error');
        
        // Show loading state
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = 'Creating account...';
        if (spinner) spinner.classList.remove('hidden');
        if (errorDiv) errorDiv.classList.add('hidden');
        
        try {
            const email = document.getElementById('register-email').value;
            const username = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;
            
            const response = await fetch('/api/v1/auth/register-and-upgrade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    email,
                    username,
                    password,
                    success_url: `${window.location.origin}/payment-success`,
                    cancel_url: window.location.origin
                }),
            });
            
            const data = await response.json();
            
            if (data.success && data.checkout_url) {
                // Account created and checkout session ready - redirect to Stripe
                console.log('Account created, redirecting to Stripe checkout...');
                window.location.href = data.checkout_url;
            } else if (data.success && !data.checkout_url) {
                // Account created but checkout failed - fallback to regular registration
                console.log('Account created but checkout failed, logging in...');
                this.user = data.user;
                this.isAuthenticated = true;
                this.isPremium = false;
                this.updateAuthUI();
                this.hideUpgradeModal();
                this.refreshPredictionsData();
                
                this.showToast(
                    data.message || 'Account created! Please try upgrading from your account.',
                    'warning',
                    5000
                );
            } else {
                if (errorDiv) {
                    errorDiv.textContent = data.message || 'Registration failed. Please try again.';
                    errorDiv.classList.remove('hidden');
                }
            }
        } catch (error) {
            console.error('Premium registration error:', error);
            if (errorDiv) {
                errorDiv.textContent = 'Network error. Please check your connection and try again.';
                errorDiv.classList.remove('hidden');
            }
        } finally {
            // Reset loading state
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = '🚀 CREATE PREMIUM ACCOUNT - $9.99/YEAR';
            if (spinner) spinner.classList.add('hidden');
        }
    }

    /**
     * Handle free registration - Standard registration flow
     */
    async handleFreeRegister(e) {
        e.preventDefault();
        
        // Validate form first
        const form = document.getElementById('register-form');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        const submitBtn = document.getElementById('register-free-btn');
        const submitText = document.getElementById('register-free-text');
        const spinner = document.getElementById('register-free-spinner');
        const errorDiv = document.getElementById('register-error');
        
        // Show loading state
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = 'Creating account...';
        if (spinner) spinner.classList.remove('hidden');
        if (errorDiv) errorDiv.classList.add('hidden');
        
        try {
            const email = document.getElementById('register-email').value;
            const username = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;
            
            const response = await fetch('/api/v1/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ email, username, password }),
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.user = data.user;
                this.isAuthenticated = true;
                this.isPremium = data.user?.is_premium || false;
                this.updateAuthUI();
                this.renderHeroCTAs();
                this.hideUpgradeModal();
                
                this.showToast(
                    'Free account created successfully! You can now access 5 predictions.',
                    'success',
                    5000
                );
                
                // Refresh predictions after successful registration
                this.refreshPredictionsData();
            } else {
                if (errorDiv) {
                    errorDiv.textContent = data.message || 'Registration failed. Please try again.';
                    errorDiv.classList.remove('hidden');
                }
            }
        } catch (error) {
            console.error('Free registration error:', error);
            if (errorDiv) {
                errorDiv.textContent = 'Network error. Please check your connection and try again.';
                errorDiv.classList.remove('hidden');
            }
        } finally {
            // Reset loading state
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = 'Create Free Account (5 predictions)';
            if (spinner) spinner.classList.add('hidden');
        }
    }

    /**
     * Refresh predictions data after login/logout
     */
    refreshPredictionsData() {
        try {
            // Reload AI predictions for next drawing
            if (typeof loadPredictions === 'function') {
                console.log('Refreshing AI predictions after authentication change...');
                loadPredictions();
            } else if (typeof window.loadPredictions === 'function') {
                console.log('Refreshing AI predictions after authentication change...');
                window.loadPredictions();
            } else {
                console.log('AI predictions refresh not available, page may need manual refresh');
            }
        } catch (error) {
            console.error('Error refreshing AI predictions:', error);
        }
    }
    
    /**
     * Handle logout
     */
    async handleLogout() {
        try {
            await fetch('/api/v1/auth/logout', {
                method: 'POST',
                credentials: 'include',
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        
        this.user = null;
        this.isAuthenticated = false;
        this.isPremium = false;
        this.updateAuthUI();
        this.renderHeroCTAs();
        this.hideUserDropdown();
        
        // Refresh predictions after logout to show free user view
        this.refreshPredictionsData();
    }

    /**
     * Hide upgrade modal
     */
    hideUpgradeModal() {
        const modal = document.getElementById('upgrade-modal');
        if (!modal) return;

        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.style.transform = 'scale(0.95)';
            modalContent.style.opacity = '0';
        }

        setTimeout(() => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }, 200);
    }

    /**
     * Update modal content with dynamic information
     */
    updateModalContent() {
        // Simplified - minimalist modal doesn't need dynamic content updates
        console.log('Modal content updated (minimalist mode)');
    }

    /**
     * Update user count and premium stats with real data from APIs
     * Note: Simplified for minimalist modal
     */
    async updateUserCount() {
        // No longer needed for minimalist modal
    }

    /**
     * Update premium user statistics and scarcity indicators
     * Note: Simplified for minimalist modal
     */
    updatePremiumStats(stats) {
        // Keep footer counter update only
        this.updateFooterCounters(stats);
    }

    /**
     * Update footer counters separately to avoid dependencies
     */
    updateFooterCounters(stats) {
        const footerPremiumElement = document.getElementById('premium-counter');
        if (footerPremiumElement && typeof stats.premium_users === 'number' && stats.premium_users >= 0) {
            footerPremiumElement.textContent = stats.premium_users.toLocaleString();
            footerPremiumElement.classList.add('counter-updated');
            setTimeout(() => footerPremiumElement.classList.remove('counter-updated'), 500);
        }
    }

    /**
     * Handle upgrade button click
     * Verifies auth status from server in real-time before proceeding
     */
    async handleUpgradeClick() {
        console.log('Upgrade button clicked');
        
        // Track upgrade intent
        this.trackEvent('upgrade_button_clicked');
        
        // Find all upgrade buttons and show loading state
        const upgradeButtons = document.querySelectorAll('[data-upgrade-action="start"], .unlock-premium-btn');
        const originalButtonStates = new Map();
        
        upgradeButtons.forEach(btn => {
            if (btn) {
                originalButtonStates.set(btn, {
                    disabled: btn.disabled,
                    innerHTML: btn.innerHTML
                });
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Verifying...';
            }
        });
        
        let isAuthenticatedNow = false;
        
        try {
            // Verify authentication status from server in real-time
            console.log('Verifying authentication status from server...');
            const response = await fetch('/api/v1/auth/status', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update local state with fresh server data
                this.isAuthenticated = data.is_authenticated || false;
                this.user = data.user || null;
                this.isPremium = data.user?.is_premium || false;
                isAuthenticatedNow = this.isAuthenticated;
                
                console.log('Auth status verified:', {
                    isAuthenticated: this.isAuthenticated,
                    isPremium: this.isPremium,
                    username: this.user?.username
                });
            } else {
                console.log('Auth status check failed, treating as not authenticated');
                this.isAuthenticated = false;
                this.user = null;
                this.isPremium = false;
                isAuthenticatedNow = false;
            }
        } catch (error) {
            console.error('Error verifying auth status:', error);
            // On error, fall back to not authenticated (safer)
            this.isAuthenticated = false;
            isAuthenticatedNow = false;
        } finally {
            // Restore button states
            upgradeButtons.forEach(btn => {
                const originalState = originalButtonStates.get(btn);
                if (btn && originalState) {
                    btn.disabled = originalState.disabled;
                    btn.innerHTML = originalState.innerHTML;
                }
            });
        }
        
        // Now decide what to do based on verified auth status
        if (!isAuthenticatedNow) {
            console.log('User not authenticated - showing register modal');
            this.isRegisteringFromUpgrade = true;
            this.showUpgradeModal({ view: 'register' });
            return;
        }

        // User is authenticated - go directly to Stripe (NO modal)
        console.log('User is authenticated - redirecting directly to Stripe checkout');
        await this.startUpgradeProcess();
    }

    /**
     * Start upgrade process for authenticated users
     */
    async startUpgradeProcess() {
        console.log('Starting upgrade process...');
        
        try {
            // Disable upgrade button to prevent double-clicks
            const upgradeBtn = document.querySelector('[data-upgrade-action="start"]');
            if (upgradeBtn) {
                upgradeBtn.disabled = true;
                upgradeBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
            }
            
            // Track upgrade attempt
            this.trackEvent('upgrade_process_started');
            
            // Generate idempotency key for safe retries
            const idempotencyKey = this.generateIdempotencyKey();
            
            // Create checkout session
            const response = await fetch('/api/v1/billing/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Idempotency-Key': idempotencyKey
                },
                credentials: 'include',
                body: JSON.stringify({
                    success_url: `${window.location.origin}/payment-success`,
                    cancel_url: window.location.origin
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to create checkout session');
            }
            
            const data = await response.json();
            
            // Redirect to Stripe Checkout
            console.log('Redirecting to Stripe Checkout:', data.checkout_url);
            window.location.href = data.checkout_url;
            
        } catch (error) {
            console.error('Upgrade process error:', error);
            
            // Re-enable button
            const upgradeBtn = document.querySelector('[data-upgrade-action="start"]');
            if (upgradeBtn) {
                upgradeBtn.disabled = false;
                upgradeBtn.innerHTML = '🚀 GO PREMIUM - $9.99/YEAR';
            }
            
            // Show error message
            this.showToast(
                `Upgrade failed: ${error.message}`,
                'error',
                5000
            );
            
            this.trackEvent('upgrade_process_failed', { error: error.message });
        }
    }
    
    /**
     * Generate unique idempotency key for API requests
     */
    generateIdempotencyKey() {
        const timestamp = Date.now();
        const random = Math.random().toString(36).substring(2);
        return `shiol-upgrade-${timestamp}-${random}`;
    }

    /**
     * Track events for analytics
     */
    trackEvent(event, data = {}) {
        console.log(`Event tracked: ${event}`, data);
        
        // Here you would integrate with analytics service
        // Example: gtag('event', event, data);
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `fixed top-5 right-5 bg-${type === 'success' ? 'green' : 'blue'}-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, duration);
    }
}

// Export AuthManager class to window (single declaration)
window.AuthManager = AuthManager;

// Initialize AuthManager with singleton protection
document.addEventListener('DOMContentLoaded', () => {
    // Singleton protection: prevent multiple instances
    if (window.__authManager) {
        console.log('🔐 AuthManager singleton already exists, skipping initialization');
        return;
    }
    
    console.log('🔐 Initializing AuthManager singleton...');
    window.__authManager = new AuthManager();
});

// Global legacy compatibility function for openRegisterModal
window.openRegisterModal = () => {
    console.log('Legacy global openRegisterModal called');
    
    // Robust retry mechanism for early calls before AuthManager is initialized
    const attemptOpenModal = () => {
        if (window.authManager && typeof window.authManager.showUpgradeModal === 'function') {
            window.authManager.showUpgradeModal({ view: 'register' });
            return true;
        }
        return false;
    };
    
    // Try immediately first
    if (attemptOpenModal()) {
        return;
    }
    
    // If not available, wait for DOM and AuthManager initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Give AuthManager time to initialize after DOM load
            setTimeout(() => {
                if (!attemptOpenModal()) {
                    console.warn('AuthManager still not available after DOM load, cannot open register modal');
                }
            }, 100);
        });
    } else {
        // DOM already loaded, try again after short delay
        setTimeout(() => {
            if (!attemptOpenModal()) {
                console.warn('AuthManager instance not available, cannot open register modal');
            }
        }, 100);
    }
};

})(); // Close IIFE