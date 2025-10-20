/**
 * Centralized text constants for SHIOL+ application
 * All user-facing text content organized by feature and component
 * 
 * Usage: window.AppTexts.modals.upgrade.title
 * Benefits: Easy maintenance, consistent copy, future i18n support
 */

window.AppTexts = {
    // Modal content and messaging
    modals: {
        upgrade: {
            title: "Unlock All AI Insights",
            subtitle: "Join {userCount} users maximizing their winning potential",
            limitedOffer: "🔥 LIMITED TIME OFFER",
            pricing: "$9.99",
            pricingPeriod: "per year",
            pricingSubtext: "🚀 Less than $0.83/month",
            validUntil: "Cancel anytime • Valid until {date}",
            cta: "UNLOCK NOW - ONLY $9.99/YEAR 🚀",
            features: {
                aiAlgorithm: "Advanced AI algorithm insights",
                allPredictions: "Access to all 200 ranked AI insights", 
                performanceTracking: "Historical performance tracking",
                mobileApp: "PWA mobile app access",
                customerSupport: "Priority customer support",
                realtimeUpdates: "Real-time AI insight updates"
            },
            scarcity: {
                spotsRemaining: "⚠️ Only {count} premium spots remaining this month!",
                conversionRate: "{rate}% of users upgrade to premium"
            },
            socialProof: {
                userCount: "{count}+",
                successRate: "85%",
                insightCount: "200"
            },
            overlay: {
                rankBadge: "Rank #{rank}",
                premiumContent: "Premium Content",
                socialProof: "🔥 <strong>Join 1,000+ users</strong> unlocking winning AI insights!",
                urgency: "⏰ LIMITED TIME OFFER",
                valueProp: "Advanced AI • 85% Success Rate • Full Access",
                ctaButton: "<strong>UNLOCK NOW</strong> - Only $9.99/year 🚀"
            }
        },
        register: {
            title: "Go Premium Access",
            subtitle: "Unlock all 200 AI insights instantly",
            createAccount: "Create Your Premium Account",
            pricing: "$9.99/YEAR",
            pricingSubtext: "That's just $0.83/month!",
            cta: "Upgrade to Premium – $9.99/year",
            comparison: {
                free: {
                    emoji: "🆓",
                    title: "1 AI Insight",
                    subtitle: "Guest Access"
                },
                premium: {
                    emoji: "🔥", 
                    title: "200 AI Insights",
                    subtitle: "Advanced AI"
                }
            },
            benefits: [
                "Instant access to all AI insights",
                "Cancel anytime"
            ],
            footer: {
                hasAccount: "Already have an account?",
                loginLink: "Login here",
                disclaimer: "🏆 Start with free access, upgrade to Premium for $9.99/year"
            }
        },
        login: {
            title: "Login to SHIOL+",
            subtitle: "Access your premium AI insights",
            cta: "Login",
            footer: {
                noAccount: "Don't have an account?",
                registerLink: "Register here"
            }
        },
        common: {
            securityNote: "Secure payment · 200 AI insights · Cancel anytime",
            cancelAnytime: "Cancel anytime",
            loading: "Loading...",
            close: "Close"
        }
    },

    // Hero section texts
    hero: {
        tryFree: "Try Free",
        unlockPremium: "Unlock Premium - $9.99/year",
        viewMyInsights: "View My Insights",
        viewLatestInsights: "View Latest Insights",
        premiumActive: "✓ Premium Active",
        rememberMe: "Remember me"
    },

    // Quota and day-based insights messaging
    quota: {
        premiumDay: {
            badge: "🎉 Premium Day",
            message: "Today is your Premium Day! {count} insights available",
            description: "Saturdays give you full access to 5 AI insights"
        },
        regularDay: {
            badge: "Regular Day",
            message: "1 insight today • Saturday Premium Day: 5 insights",
            description: "{day} draw – 1 insight available. Saturday: 5 insights!"
        },
        insightsRemaining: "{remaining}/{total} insights available",
        upgradePrompt: "Upgrade to Premium for 200 insights every draw",
        nextPremiumDay: "Next Premium Day: Saturday",
        saturdayBonus: "🎁 Saturday Bonus: 5 insights"
    },

    // Button labels and call-to-actions
    buttons: {
        // Ticket verification
        selectImage: "Select Ticket Image",
        verifyTicket: "Verify Ticket",
        previewNumbers: "Preview Numbers Detected",
        scanAnother: "Scan Another Ticket",
        
        // Authentication
        login: "Login",
        register: "Register",
        logout: "Logout",
        upgradeNow: "Upgrade Now",
        unlockPremium: "Unlock Premium",
        goPremium: "Go Premium",
        
        // General actions
        tryAgain: "Try Again",
        continue: "Continue",
        cancel: "Cancel",
        save: "Save",
        
        // Loading states
        processing: "Processing...",
        verifying: "Verifying...",
        loading: "Loading...",
        uploading: "Uploading..."
    },

    // Error messages and validation
    errors: {
        // File upload errors
        imageRequired: "Please select an image first",
        invalidFileType: "Please select a valid image file (JPG, PNG, etc.)",
        fileTooLarge: "File size too large. Please select a smaller image",
        imageOptimizationFailed: "Failed to optimize image. Please try a smaller image",
        
        // Network and API errors
        networkError: "Network error. Please check your connection",
        serverError: "Server error. Please try again later",
        tooManyRequests: "Too many requests. Please try again later",
        authenticationFailed: "Authentication failed. Please check your credentials",
        
        // Validation errors
        emailRequired: "Email is required",
        emailInvalid: "Please enter a valid email address",
        passwordRequired: "Password is required",
        passwordTooShort: "Password must be at least 6 characters",
        usernameRequired: "Username is required",
        usernameTooShort: "Username must be at least 3 characters",
        
        // General errors
        somethingWentWrong: "Something went wrong. Please try again",
        sessionExpired: "Your session has expired. Please login again",
        permissionDenied: "Permission denied. Please upgrade to premium"
    },

    // Success messages and confirmations
    success: {
        ticketVerified: "Ticket verified successfully!",
        numbersDetected: "Numbers detected with {confidence}% confidence",
        loginSuccessful: "Login successful! Welcome back",
        registrationSuccessful: "Registration successful! Welcome to SHIOL+",
        upgradeSuccessful: "Upgrade successful! You now have premium access",
        imageUploaded: "Image uploaded successfully",
        settingsSaved: "Settings saved successfully"
    },

    // Form labels and placeholders
    forms: {
        labels: {
            email: "Email Address",
            username: "Username", 
            password: "Password",
            confirmPassword: "Confirm Password"
        },
        placeholders: {
            email: "Enter your email",
            username: "Enter your username",
            password: "Enter your password",
            confirmPassword: "Confirm your password"
        }
    },

    // UI elements and navigation
    ui: {
        // Countdown and timing
        drawingInProgress: "Drawing in progress...",
        nextDrawing: "Next Drawing",
        timeRemaining: "Time Remaining",
        
        // Prediction display
        confidence: "Confidence",
        method: "Method",
        rank: "Rank #{rank}",
        premiumContent: "Premium Content",
        
        // Status indicators
        status: {
            idle: "Idle",
            running: "Running", 
            completed: "Completed",
            failed: "Failed",
            starting: "Starting"
        },
        
        // Loading states
        loadingPredictions: "Loading AI insights...",
        loadingStats: "Loading statistics...",
        updatingData: "Updating data...",
        
        // Premium features
        premiumBadge: "🏆 Premium",
        lockIcon: "🔒",
        upgradeMessage: "🔥 Join 1,000+ users unlocking winning AI insights!",
        urgencyBadge: "⏰ LIMITED TIME OFFER",
        valueProp: "Advanced AI • 85% Success Rate • Full Access"
    },

    // Date and time formatting
    dates: {
        drawDate: "Draw Date: {date}",
        lastUpdated: "Last updated: {time}",
        currentDate: "{month} {day}, {year}"
    },

    // Loading and processing messages
    loading: {
        optimizingImage: "Optimizing image for mobile...",
        verifying: "Verifying your ticket...",
        processing: "Processing..."
    },

    // Statistics and counters
    stats: {
        visits: "visits",
        installs: "installs", 
        premiumUsers: "premium users",
        totalPlays: "Total Plays",
        winningNumbers: "Winning Numbers",
        confidence: "Confidence: {percent}%"
    }
};

/**
 * Helper function to replace placeholders in text strings
 * @param {string} text - Text with placeholders like {key}
 * @param {object} replacements - Key-value pairs for replacement
 * @returns {string} - Text with placeholders replaced
 */
window.AppTexts.format = function(text, replacements = {}) {
    return text.replace(/\{(\w+)\}/g, (match, key) => {
        return replacements[key] !== undefined ? replacements[key] : match;
    });
};

/**
 * Convenience methods for common text operations
 */
window.AppTexts.get = {
    modalTitle: (modal) => window.AppTexts.modals[modal]?.title || '',
    buttonText: (button) => window.AppTexts.buttons[button] || '',
    errorMessage: (error) => window.AppTexts.errors[error] || '',
    successMessage: (success) => window.AppTexts.success[success] || ''
};

// Export for ES6 modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.AppTexts;
}