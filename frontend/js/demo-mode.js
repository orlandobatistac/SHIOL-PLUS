/**
 * Demo Mode Configuration and Restrictions
 * Protects sensitive data and actions when demo user is logged in
 */

const DEMO_CONFIG = {
    // Demo user identifiers
    demoUsers: ['demo@shiolplus.com', 'demo'],
    
    // Admin users to protect/hide
    adminUsers: ['admin', 'orlando', 'orlandobatistac'],
    
    // Elements to hide completely
    hideSelectors: [
        '#commit-url',           // GitHub commit link
        '.github-link',          // Any other GitHub links
        '#commit-hash',          // Commit hash element
        '#commit-link',          // Commit link wrapper
    ],
    
    // Buttons to disable
    disableSelectors: [
        '#run-pipeline-btn',     // Pipeline execution button
    ],
    
    // Tooltips for disabled elements
    tooltips: {
        disabled: 'This action is disabled in demo mode',
        protected: 'Demo user cannot be modified',
        adminProtected: 'Admin user cannot be modified in demo mode',
    }
};

/**
 * Check if current user is a demo user
 */
function isDemoUser(user) {
    if (!user) return false;
    return DEMO_CONFIG.demoUsers.includes(user.email) || 
           DEMO_CONFIG.demoUsers.includes(user.username);
}

/**
 * Apply demo mode restrictions to the page
 */
function applyDemoRestrictions(currentUser) {
    if (!isDemoUser(currentUser)) {
        console.log('Not a demo user - no restrictions applied');
        return;
    }
    
    console.log('Demo mode activated - applying restrictions');
    
    // Hide sensitive elements
    DEMO_CONFIG.hideSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            if (el) {
                el.style.display = 'none';
                console.log(`Hidden: ${selector}`);
            }
        });
    });
    
    // Replace commit hash with placeholder and remove link
    const commitHashElement = document.getElementById('commit-hash');
    if (commitHashElement) {
        commitHashElement.textContent = 'XXXXXXX';
        commitHashElement.removeAttribute('href');
        commitHashElement.removeAttribute('target');
        commitHashElement.removeAttribute('title');
        commitHashElement.style.cursor = 'default';
        commitHashElement.style.pointerEvents = 'none';
        console.log('Commit hash replaced with placeholder');
    }
    
    // Hide commit message (may contain sensitive info)
    const commitMessageElement = document.getElementById('commit-message');
    if (commitMessageElement) {
        commitMessageElement.textContent = 'Hidden in demo mode';
        console.log('Commit message hidden');
    }
    
    // Disable action buttons
    DEMO_CONFIG.disableSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(btn => {
            if (btn) {
                btn.disabled = true;
                btn.title = DEMO_CONFIG.tooltips.disabled;
                btn.classList.add('opacity-50', 'cursor-not-allowed');
                // Remove click handlers
                btn.onclick = (e) => {
                    e.preventDefault();
                    alert(DEMO_CONFIG.tooltips.disabled);
                };
                console.log(`Disabled: ${selector}`);
            }
        });
    });
    
    // Protect demo user in admin panel - wait for functions to be defined and table to render
    setTimeout(() => {
        protectDemoUserInAdminPanel(currentUser);
    }, 100);
    
    // Wait longer for user table to fully render before hiding admin users
    setTimeout(() => {
        hideAdminUsersFromTable();
    }, 1500);
}

/**
 * Protect demo user from admin actions
 */
function protectDemoUserInAdminPanel(currentUser) {
    console.log('Protecting demo user in admin panel...');
    
    // Override resetPassword function
    if (typeof window.resetPassword === 'function') {
        const originalResetPassword = window.resetPassword;
        window.resetPassword = function(userId, username) {
            if (DEMO_CONFIG.demoUsers.includes(username)) {
                alert(DEMO_CONFIG.tooltips.protected);
                console.log('Blocked reset password for demo user');
                return;
            }
            if (DEMO_CONFIG.adminUsers.includes(username.toLowerCase())) {
                alert(DEMO_CONFIG.tooltips.adminProtected);
                console.log('Blocked reset password for admin user');
                return;
            }
            return originalResetPassword(userId, username);
        };
        console.log('resetPassword protected');
    } else {
        console.warn('resetPassword function not found');
    }
    
    // Override deleteUser function
    if (typeof window.deleteUser === 'function') {
        const originalDeleteUser = window.deleteUser;
        window.deleteUser = function(userId, username) {
            if (DEMO_CONFIG.demoUsers.includes(username)) {
                alert(DEMO_CONFIG.tooltips.protected);
                console.log('Blocked delete user for demo user');
                return;
            }
            if (DEMO_CONFIG.adminUsers.includes(username.toLowerCase())) {
                alert(DEMO_CONFIG.tooltips.adminProtected);
                console.log('Blocked delete user for admin user');
                return;
            }
            return originalDeleteUser(userId, username);
        };
        console.log('deleteUser protected');
    } else {
        console.warn('deleteUser function not found');
    }
    
    // Override togglePremium function
    if (typeof window.togglePremium === 'function') {
        const originalTogglePremium = window.togglePremium;
        window.togglePremium = function(userId, username) {
            if (DEMO_CONFIG.demoUsers.includes(username)) {
                alert(DEMO_CONFIG.tooltips.protected);
                console.log('Blocked toggle premium for demo user');
                return;
            }
            if (DEMO_CONFIG.adminUsers.includes(username.toLowerCase())) {
                alert(DEMO_CONFIG.tooltips.adminProtected);
                console.log('Blocked toggle premium for admin user');
                return;
            }
            return originalTogglePremium(userId, username);
        };
        console.log('togglePremium protected');
    } else {
        console.warn('togglePremium function not found');
    }
}

/**
 * Hide admin users from the user management table
 */
function hideAdminUsersFromTable() {
    console.log('Hiding admin users from table...');
    
    // Find all table rows
    const userTable = document.querySelector('#user-management table tbody');
    if (!userTable) {
        console.warn('User table not found');
        return;
    }
    
    const rows = userTable.querySelectorAll('tr');
    let hiddenCount = 0;
    
    rows.forEach(row => {
        const usernameCell = row.querySelector('td:first-child');
        if (usernameCell) {
            const username = usernameCell.textContent.trim().toLowerCase();
            if (DEMO_CONFIG.adminUsers.includes(username)) {
                row.style.display = 'none';
                hiddenCount++;
                console.log(`Hidden admin user: ${username}`);
            }
        }
    });
    
    console.log(`Hidden ${hiddenCount} admin user(s) from table`);
}

/**
 * Disable account deletion for demo user
 */
function protectDemoUserAccount(currentUser) {
    if (!isDemoUser(currentUser)) return;
    
    // Disable delete account button in account settings
    const deleteBtn = document.querySelector('[onclick*="confirmDelete"]');
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.title = DEMO_CONFIG.tooltips.protected;
        deleteBtn.classList.add('opacity-50', 'cursor-not-allowed');
        deleteBtn.onclick = (e) => {
            e.preventDefault();
            alert('Demo account cannot be deleted. All changes are reset on page refresh.');
        };
    }
}

// Export for use in other scripts
window.DemoMode = {
    isDemoUser,
    applyDemoRestrictions,
    protectDemoUserAccount,
    DEMO_CONFIG
};

console.log('Demo Mode module loaded');
