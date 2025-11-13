/**
 * Account Settings Modal
 * Handles user account management: password change, email update, account deletion
 */

class AccountSettingsModal {
    constructor() {
        this.modal = null;
        this.init();
    }

    init() {
        // Create modal structure
        this.createModal();
        // Attach event listeners
        this.attachEventListeners();
    }

    createModal() {
        const modalHTML = `
            <div id="account-settings-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
                <div class="bg-[#1a1f2e] rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-white/10 shadow-2xl">
                    <!-- Header -->
                    <div class="flex items-center justify-between p-6 border-b border-white/10">
                        <div>
                            <h3 class="text-2xl font-bold text-white">Account Settings</h3>
                            <p class="text-sm text-white/60 mt-1">Manage your account preferences and security</p>
                        </div>
                        <button onclick="accountSettings.close()" class="text-white/40 hover:text-white transition-colors">
                            <i class="fas fa-times text-xl"></i>
                        </button>
                    </div>

                    <!-- Content -->
                    <div class="p-6 space-y-6">
                        <!-- Change Password Section -->
                        <div class="bg-[#0d1117] p-5 rounded-lg border border-white/5">
                            <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                <i class="fas fa-lock text-cyan-400"></i>
                                Change Password
                            </h4>
                            <form id="change-password-form" class="space-y-4">
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">Current Password</label>
                                    <input type="password" id="current-password" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white focus:border-cyan-400 focus:outline-none transition-colors"
                                        placeholder="Enter current password" required>
                                </div>
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">New Password</label>
                                    <input type="password" id="new-password" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white focus:border-cyan-400 focus:outline-none transition-colors"
                                        placeholder="Enter new password (min 8 characters)" required minlength="8">
                                    <p class="text-xs text-white/40 mt-1">Use at least 8 characters with a mix of letters and numbers</p>
                                </div>
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">Confirm New Password</label>
                                    <input type="password" id="confirm-password" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white focus:border-cyan-400 focus:outline-none transition-colors"
                                        placeholder="Confirm new password" required minlength="8">
                                </div>
                                <div id="password-error" class="hidden text-sm text-red-400"></div>
                                <div id="password-success" class="hidden text-sm text-green-400"></div>
                                <button type="submit" class="w-full px-4 py-2 bg-gradient-to-r from-cyan-500 to-pink-500 text-white font-semibold rounded-lg hover:opacity-90 transition-opacity">
                                    Update Password
                                </button>
                            </form>
                        </div>

                        <!-- Update Email Section -->
                        <div class="bg-[#0d1117] p-5 rounded-lg border border-white/5">
                            <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                <i class="fas fa-envelope text-pink-400"></i>
                                Update Email Address
                            </h4>
                            <form id="update-email-form" class="space-y-4">
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">Current Email</label>
                                    <input type="email" id="current-email" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white/50 cursor-not-allowed"
                                        disabled>
                                </div>
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">New Email Address</label>
                                    <input type="email" id="new-email" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white focus:border-pink-400 focus:outline-none transition-colors"
                                        placeholder="Enter new email address" required>
                                </div>
                                <div>
                                    <label class="block text-sm text-white/70 mb-2">Confirm Password</label>
                                    <input type="password" id="email-password" 
                                        class="w-full px-4 py-2 bg-[#1a1f2e] border border-white/10 rounded-lg text-white focus:border-pink-400 focus:outline-none transition-colors"
                                        placeholder="Enter your password to confirm" required>
                                </div>
                                <div id="email-error" class="hidden text-sm text-red-400"></div>
                                <div id="email-success" class="hidden text-sm text-green-400"></div>
                                <button type="submit" class="w-full px-4 py-2 bg-gradient-to-r from-cyan-500 to-pink-500 text-white font-semibold rounded-lg hover:opacity-90 transition-opacity">
                                    Update Email
                                </button>
                            </form>
                        </div>

                        <!-- Delete Account Section -->
                        <div class="bg-[#0d1117] p-5 rounded-lg border border-red-500/20">
                            <h4 class="text-lg font-semibold text-red-400 mb-4 flex items-center gap-2">
                                <i class="fas fa-exclamation-triangle"></i>
                                Danger Zone
                            </h4>
                            <p class="text-sm text-white/60 mb-4">
                                Once you delete your account, there is no going back. This action is permanent and cannot be undone.
                            </p>
                            <button onclick="accountSettings.confirmDelete()" 
                                class="w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors">
                                Delete Account
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Delete Confirmation Modal -->
            <div id="delete-confirm-modal" class="fixed inset-0 bg-black/90 backdrop-blur-sm z-[60] hidden flex items-center justify-center p-4">
                <div class="bg-[#1a1f2e] rounded-2xl max-w-md w-full border border-red-500/30 shadow-2xl">
                    <div class="p-6">
                        <div class="text-center mb-6">
                            <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                                <i class="fas fa-exclamation-triangle text-3xl text-red-400"></i>
                            </div>
                            <h3 class="text-xl font-bold text-white mb-2">Delete Account?</h3>
                            <p class="text-sm text-white/60">
                                This will permanently delete your account, all your data, and generated insights. This action cannot be undone.
                            </p>
                        </div>
                        <form id="delete-account-form" class="space-y-4">
                            <div>
                                <label class="block text-sm text-white/70 mb-2">Enter your password to confirm</label>
                                <input type="password" id="delete-password" 
                                    class="w-full px-4 py-2 bg-[#0d1117] border border-white/10 rounded-lg text-white focus:border-red-400 focus:outline-none transition-colors"
                                    placeholder="Enter your password" required>
                            </div>
                            <div id="delete-error" class="hidden text-sm text-red-400"></div>
                            <div class="flex gap-3">
                                <button type="button" onclick="accountSettings.cancelDelete()" 
                                    class="flex-1 px-4 py-2 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-lg transition-colors">
                                    Cancel
                                </button>
                                <button type="submit" 
                                    class="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors">
                                    Delete Forever
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('account-settings-modal');
    }

    attachEventListeners() {
        // Change Password Form
        document.getElementById('change-password-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handlePasswordChange();
        });

        // Update Email Form
        document.getElementById('update-email-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleEmailUpdate();
        });

        // Delete Account Form
        document.getElementById('delete-account-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleAccountDeletion();
        });

        // Close modal on outside click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });
    }

    async open() {
        // Load current user data
        try {
            const response = await fetch('/api/v1/auth/me', {
                credentials: 'include'
            });
            if (response.ok) {
                const user = await response.json();
                document.getElementById('current-email').value = user.email;
                
                // Apply demo mode protections if available
                if (window.DemoMode) {
                    window.DemoMode.protectDemoUserAccount(user);
                }
            }
        } catch (error) {
            console.error('Failed to load user data:', error);
        }

        this.modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    close() {
        this.modal.classList.add('hidden');
        document.body.style.overflow = '';
        this.resetForms();
    }

    resetForms() {
        document.getElementById('change-password-form').reset();
        document.getElementById('update-email-form').reset();
        document.getElementById('delete-account-form').reset();
        this.hideMessages();
    }

    hideMessages() {
        ['password-error', 'password-success', 'email-error', 'email-success', 'delete-error'].forEach(id => {
            document.getElementById(id).classList.add('hidden');
        });
    }

    async handlePasswordChange() {
        this.hideMessages();

        const currentPassword = document.getElementById('current-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;

        // Validate passwords match
        if (newPassword !== confirmPassword) {
            this.showError('password-error', 'New passwords do not match');
            return;
        }

        // Validate password strength
        if (newPassword.length < 8) {
            this.showError('password-error', 'Password must be at least 8 characters');
            return;
        }

        try {
            const response = await fetch('/api/v1/auth/user/password', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess('password-success', 'Password updated successfully!');
                document.getElementById('change-password-form').reset();
            } else {
                this.showError('password-error', data.detail || 'Failed to update password');
            }
        } catch (error) {
            this.showError('password-error', 'Network error. Please try again.');
        }
    }

    async handleEmailUpdate() {
        this.hideMessages();

        const newEmail = document.getElementById('new-email').value;
        const password = document.getElementById('email-password').value;

        // Validate email format
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(newEmail)) {
            this.showError('email-error', 'Please enter a valid email address');
            return;
        }

        try {
            const response = await fetch('/api/v1/auth/user/email', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    new_email: newEmail,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess('email-success', 'Email updated successfully!');
                document.getElementById('current-email').value = newEmail;
                document.getElementById('update-email-form').reset();
            } else {
                this.showError('email-error', data.detail || 'Failed to update email');
            }
        } catch (error) {
            this.showError('email-error', 'Network error. Please try again.');
        }
    }

    confirmDelete() {
        document.getElementById('delete-confirm-modal').classList.remove('hidden');
    }

    cancelDelete() {
        document.getElementById('delete-confirm-modal').classList.add('hidden');
        document.getElementById('delete-account-form').reset();
        this.hideMessages();
    }

    async handleAccountDeletion() {
        this.hideMessages();

        const password = document.getElementById('delete-password').value;

        try {
            const response = await fetch('/api/v1/auth/user/account', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ password: password })
            });

            const data = await response.json();

            if (response.ok) {
                // Account deleted successfully - redirect to home
                alert('Your account has been permanently deleted. You will be logged out.');
                window.location.href = '/';
            } else {
                this.showError('delete-error', data.detail || 'Failed to delete account');
            }
        } catch (error) {
            this.showError('delete-error', 'Network error. Please try again.');
        }
    }

    showError(elementId, message) {
        const element = document.getElementById(elementId);
        element.textContent = message;
        element.classList.remove('hidden');
    }

    showSuccess(elementId, message) {
        const element = document.getElementById(elementId);
        element.textContent = message;
        element.classList.remove('hidden');
    }
}

// Initialize account settings modal and make it globally accessible
window.accountSettings = null;
document.addEventListener('DOMContentLoaded', () => {
    window.accountSettings = new AccountSettingsModal();
    console.log('Account Settings Modal initialized');
});
