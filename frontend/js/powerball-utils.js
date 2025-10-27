/**
 * SHIOL+ Powerball Utilities
 * ==========================
 * 
 * Reusable utilities and components for Powerball number display and formatting.
 * Implements the PowerballCard component with conditional rendering as specified.
 */

class PowerballUtils {
    /**
     * Create a PowerballCard component with conditional rendering
     * @param {Object} options - Configuration options
     * @param {Array} options.numbers - Array of 5 white ball numbers
     * @param {number} options.powerball - Powerball number
     * @param {string} options.type - 'prediction' or 'result'
     * @param {string} options.date - Date string for the card
     * @param {Object} options.metadata - Additional metadata (score, jackpot, etc.)
     * @param {boolean} options.featured - Whether this is a featured/highlighted card
     * @param {string} options.access_type - 'unlocked' or 'locked' (for freemium restrictions)
     * @param {number} options.rank - Prediction rank (1, 2, 3, ...)
     * @param {boolean} options.is_premium_only - Whether this prediction requires premium access
     * @returns {HTMLElement} - The created card element
     */
    static createPowerballCard(options) {
        const {
            numbers = [],
            powerball = 0,
            type = 'prediction',
            date = '',
            metadata = {},
            featured = false,
            access_type = 'unlocked',
            rank = null,
            is_premium_only = false
        } = options;

        // Create main card container
        const card = document.createElement('div');
        let cardClasses = `powerball-card ${featured ? 'featured-card' : 'history-card'} bg-white rounded-xl p-6 shadow-md transition-all duration-300 hover:shadow-lg`;
        
        // Add freemium styling classes based on access_type and rank
        if (access_type === 'locked') {
            cardClasses += ' locked-prediction';
        } else if (rank === 1 && !is_premium_only) {
            cardClasses += ' rank-1-unlocked';
        }
        
        card.className = cardClasses;

        // Create date badge if provided
        let dateBadge = '';
        if (date) {
            const badgeClass = type === 'prediction' ? 'bg-blue-600' : 'bg-gray-600';
            dateBadge = `
                <div class="date-badge ${badgeClass} text-white text-sm font-semibold px-3 py-1 rounded-full inline-block mb-4">
                    ${this.formatDate(date)}
                </div>
            `;
        }

        // Create numbers display
        const numbersHtml = this.createNumbersDisplay(numbers, powerball);

        // Create metadata section based on type
        let metadataHtml = '';
        if (type === 'prediction' && metadata.confidence_score) {
            metadataHtml = `
                <div class="mt-4 flex items-center justify-center space-x-4 text-sm text-gray-400">
                    <div class="flex items-center">
                        <i class="fas fa-chart-line text-[#00e0ff] mr-1"></i>
                        <span>Confidence: <span class="font-semibold">${(metadata.confidence_score * 100).toFixed(1)}%</span></span>
                    </div>
                    <div class="flex items-center">
                        <i class="fas fa-robot text-blue-600 mr-1"></i>
                        <span>Method: <span class="font-semibold">${metadata.method || 'AI'}</span></span>
                    </div>
                </div>
            `;
        } else if (type === 'result' && metadata.jackpot_amount) {
            metadataHtml = `
                <div class="mt-4 text-center">
                    <div class="jackpot-amount text-gray-300 font-bold text-lg">
                        Jackpot: ${metadata.jackpot_amount}
                    </div>
                    ${metadata.multiplier ? `<div class="text-sm text-gray-400 mt-1">Multiplier: ${metadata.multiplier}x</div>` : ''}
                </div>
            `;
        }

        // Assemble the card using safe DOM methods to prevent XSS
        // Clear any existing content
        card.textContent = '';
        
        // Add date badge if provided
        if (date) {
            const badgeContainer = document.createElement('div');
            const badge = document.createElement('div');
            badge.className = `date-badge ${type === 'prediction' ? 'bg-blue-600' : 'bg-gray-600'} text-white text-sm font-semibold px-3 py-1 rounded-full inline-block mb-4`;
            badge.textContent = this.formatDate(date);
            badgeContainer.appendChild(badge);
            card.appendChild(badgeContainer);
        }
        
        // Create center container
        const centerDiv = document.createElement('div');
        centerDiv.className = 'text-center';
        
        // Add numbers display safely
        const numbersContainer = this.createNumbersDisplaySafe(numbers, powerball);
        numbersContainer.className += ' numbers-container'; // Add class for blur targeting
        if (access_type === 'locked') {
            numbersContainer.className += ' blurred'; // Add blur effect for locked predictions
        }
        centerDiv.appendChild(numbersContainer);
        
        // Add metadata safely
        const metadataContainer = this.createMetadataSafe(type, metadata);
        if (metadataContainer) {
            metadataContainer.className += ' metadata-container'; // Add class for blur targeting
            centerDiv.appendChild(metadataContainer);
        }
        
        card.appendChild(centerDiv);
        
        // Add rank indicator if rank is provided
        if (Number.isFinite(rank) && rank > 0) {
            const rankIndicator = document.createElement('div');
            rankIndicator.className = 'rank-indicator';
            rankIndicator.textContent = `#${rank}`;
            card.appendChild(rankIndicator);
        }
        
        // Add premium badge for high-value unlocked predictions
        if (access_type === 'unlocked' && is_premium_only && Number.isFinite(rank) && rank <= 10) {
            const premiumBadge = document.createElement('div');
            premiumBadge.className = 'premium-prediction-badge';
            premiumBadge.innerHTML = '<i class="fas fa-crown mr-1"></i>Premium';
            card.appendChild(premiumBadge);
        }
        
        // Add upgrade overlay for locked predictions
        if (access_type === 'locked') {
            const overlay = this.createUpgradeOverlay(rank);
            card.appendChild(overlay);
        }

        return card;
    }

    /**
     * Create the numbers display component safely
     * @param {Array} numbers - Array of 5 white ball numbers
     * @param {number} powerball - Powerball number
     * @returns {HTMLElement} - Safe DOM element for numbers display
     */
    static createNumbersDisplaySafe(numbers, powerball) {
        const container = document.createElement('div');
        container.className = 'flex items-center justify-center space-x-3 mb-2';
        
        if (!numbers || numbers.length !== 5 || !powerball) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'text-gray-300';
            errorDiv.textContent = 'Invalid numbers';
            return errorDiv;
        }

        // Create white balls
        numbers.forEach(num => {
            const ball = document.createElement('div');
            ball.className = 'num-chip num-chip-main';
            ball.textContent = num.toString();
            container.appendChild(ball);
        });
        
        // Create separator
        const separator = document.createElement('div');
        separator.className = 'w-4 h-4 flex items-center justify-center';
        const dot = document.createElement('div');
        dot.className = 'w-2 h-2 bg-canvas-accent2 rounded-full';
        separator.appendChild(dot);
        container.appendChild(separator);
        
        // Create powerball
        const powerBall = document.createElement('div');
        powerBall.className = 'num-chip num-chip-power';
        powerBall.textContent = powerball.toString();
        container.appendChild(powerBall);
        
        return container;
    }

    /**
     * Create the numbers display component (legacy method - kept for backward compatibility)
     * @param {Array} numbers - Array of 5 white ball numbers
     * @param {number} powerball - Powerball number
     * @returns {string} - HTML string for numbers display
     */
    static createNumbersDisplay(numbers, powerball) {
        if (!numbers || numbers.length !== 5 || !powerball) {
            return '<div class="text-gray-300">Invalid numbers</div>';
        }

        const whiteBalls = numbers.map(num => 
            `<div class="num-chip num-chip-main">${num}</div>`
        ).join('');

        const powerBall = `<div class="num-chip num-chip-power">${powerball}</div>`;

        return `
            <div class="flex items-center justify-center space-x-3 mb-2">
                ${whiteBalls}
                <div class="w-4 h-4 flex items-center justify-center">
                    <div class="w-2 h-2 bg-canvas-accent2 rounded-full"></div>
                </div>
                ${powerBall}
            </div>
        `;
    }

    /**
     * Create metadata section safely
     * @param {string} type - Type of card ('prediction' or 'result')
     * @param {Object} metadata - Metadata object
     * @returns {HTMLElement|null} - Safe DOM element for metadata or null
     */
    static createMetadataSafe(type, metadata) {
        if (type === 'prediction' && metadata.confidence_score) {
            const container = document.createElement('div');
            container.className = 'mt-4 flex items-center justify-center space-x-4 text-sm text-gray-400';
            
            // Confidence section
            const confidenceDiv = document.createElement('div');
            confidenceDiv.className = 'flex items-center';
            
            const confidenceIcon = document.createElement('i');
            confidenceIcon.className = 'fas fa-chart-line text-[#00e0ff] mr-1';
            confidenceDiv.appendChild(confidenceIcon);
            
            const confidenceText = document.createElement('span');
            confidenceText.textContent = 'Confidence: ';
            const confidenceValue = document.createElement('span');
            confidenceValue.className = 'font-semibold';
            confidenceValue.textContent = `${(metadata.confidence_score * 100).toFixed(1)}%`;
            confidenceText.appendChild(confidenceValue);
            confidenceDiv.appendChild(confidenceText);
            
            container.appendChild(confidenceDiv);
            
            // Method section
            const methodDiv = document.createElement('div');
            methodDiv.className = 'flex items-center';
            
            const methodIcon = document.createElement('i');
            methodIcon.className = 'fas fa-robot text-blue-600 mr-1';
            methodDiv.appendChild(methodIcon);
            
            const methodText = document.createElement('span');
            methodText.textContent = 'Method: ';
            const methodValue = document.createElement('span');
            methodValue.className = 'font-semibold';
            methodValue.textContent = metadata.method || 'AI';
            methodText.appendChild(methodValue);
            methodDiv.appendChild(methodText);
            
            container.appendChild(methodDiv);
            
            return container;
            
        } else if (type === 'result' && metadata.jackpot_amount) {
            const container = document.createElement('div');
            container.className = 'mt-4 text-center';
            
            const jackpotDiv = document.createElement('div');
            jackpotDiv.className = 'jackpot-amount text-gray-300 font-bold text-lg';
            jackpotDiv.textContent = `Jackpot: ${metadata.jackpot_amount}`;
            container.appendChild(jackpotDiv);
            
            if (metadata.multiplier) {
                const multiplierDiv = document.createElement('div');
                multiplierDiv.className = 'text-sm text-gray-400 mt-1';
                multiplierDiv.textContent = `Multiplier: ${metadata.multiplier}x`;
                container.appendChild(multiplierDiv);
            }
            
            return container;
        }
        
        return null;
    }

    /**
     * Format date for display
     * @param {string|Date} date - Date to format
     * @returns {string} - Formatted date string
     */
    static formatDate(date) {
        try {
            const dateObj = typeof date === 'string' ? new Date(date) : date;
            const options = { 
                weekday: 'short', 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric' 
            };
            return dateObj.toLocaleDateString('en-US', options);
        } catch (error) {
            console.error('Error formatting date:', error);
            return date.toString();
        }
    }

    /**
     * Format date for next drawing display with countdown
     * @param {Object} drawingInfo - Drawing information object
     * @returns {string} - Formatted display text
     */
    static formatNextDrawingDate(drawingInfo) {
        try {
            if (typeof drawingInfo === 'string') {
                // Fallback for old format
                const dateObj = new Date(drawingInfo);
                const options = { 
                    weekday: 'long', 
                    month: 'short', 
                    day: 'numeric' 
                };
                return dateObj.toLocaleDateString('en-US', options);
            }

            // Use the display_text from the API if available
            if (drawingInfo.display_text) {
                return drawingInfo.display_text;
            }

            // Fallback to countdown calculation
            const countdownSeconds = drawingInfo.countdown_seconds || 0;
            if (countdownSeconds <= 0) {
                return 'Drawing in progress';
            }

            const days = Math.floor(countdownSeconds / (24 * 3600));
            const hours = Math.floor((countdownSeconds % (24 * 3600)) / 3600);
            const minutes = Math.floor((countdownSeconds % 3600) / 60);

            if (days > 0) {
                return `Drawing in ${days} day${days > 1 ? 's' : ''}`;
            } else if (hours > 0) {
                return `Drawing in ${hours} hour${hours > 1 ? 's' : ''}`;
            } else if (minutes > 0) {
                return `Drawing in ${minutes} minute${minutes > 1 ? 's' : ''}`;
            } else {
                return 'Drawing very soon';
            }
        } catch (error) {
            console.error('Error formatting next drawing date:', error);
            return 'Next drawing';
        }
    }

    /**
     * Format countdown time for display
     * @param {number} seconds - Countdown seconds
     * @returns {string} - Formatted countdown string
     */
    static formatCountdown(seconds) {
        if (seconds <= 0) {
            return 'Drawing time!';
        }

        const days = Math.floor(seconds / (24 * 3600));
        const hours = Math.floor((seconds % (24 * 3600)) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (days > 0) {
            return `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
    }

    /**
     * Validate Powerball numbers
     * @param {Array} numbers - Array of 5 white ball numbers
     * @param {number} powerball - Powerball number
     * @returns {boolean} - Whether numbers are valid
     */
    static validateNumbers(numbers, powerball) {
        // Check if we have exactly 5 white ball numbers
        if (!Array.isArray(numbers) || numbers.length !== 5) {
            return false;
        }

        // Check white ball range (1-69) and uniqueness
        const uniqueNumbers = new Set(numbers);
        if (uniqueNumbers.size !== 5) {
            return false; // Duplicate numbers
        }

        for (const num of numbers) {
            if (!Number.isInteger(num) || num < 1 || num > 69) {
                return false;
            }
        }

        // Check powerball range (1-26)
        if (!Number.isInteger(powerball) || powerball < 1 || powerball > 26) {
            return false;
        }

        return true;
    }

    /**
     * Sort numbers in ascending order (for display consistency)
     * @param {Array} numbers - Array of numbers to sort
     * @returns {Array} - Sorted array
     */
    static sortNumbers(numbers) {
        return [...numbers].sort((a, b) => a - b);
    }

    /**
     * Create a loading placeholder for cards
     * @param {string} message - Loading message
     * @returns {HTMLElement} - Loading placeholder element
     */
    static createLoadingPlaceholder(message = 'Loading...') {
        const placeholder = document.createElement('div');
        placeholder.className = 'loading-placeholder text-center py-12';
        const spinner = document.createElement('i');
        spinner.className = 'fas fa-spinner fa-spin text-gray-300 text-3xl mb-4 loading-spinner';
        placeholder.appendChild(spinner);
        
        const loadingText = document.createElement('p');
        loadingText.className = 'text-gray-300';
        loadingText.textContent = message;
        placeholder.appendChild(loadingText);
        return placeholder;
    }

    /**
     * Create an error placeholder for cards
     * @param {string} message - Error message
     * @returns {HTMLElement} - Error placeholder element
     */
    static createErrorPlaceholder(message = 'Error loading data') {
        const placeholder = document.createElement('div');
        placeholder.className = 'error-placeholder text-center py-12';
        const icon = document.createElement('i');
        icon.className = 'fas fa-exclamation-triangle text-red-400 text-3xl mb-4';
        placeholder.appendChild(icon);
        
        const errorText = document.createElement('p');
        errorText.className = 'text-red-500';
        errorText.textContent = message;
        placeholder.appendChild(errorText);
        
        const retryButton = document.createElement('button');
        retryButton.className = 'mt-4 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors';
        retryButton.textContent = 'Retry';
        retryButton.onclick = () => location.reload();
        placeholder.appendChild(retryButton);
        return placeholder;
    }

    /**
     * Animate card entrance
     * @param {HTMLElement} card - Card element to animate
     * @param {number} delay - Animation delay in milliseconds
     */
    static animateCardEntrance(card, delay = 0) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, delay);
    }

    /**
     * Get API base URL with automatic detection
     * @returns {string} - API base URL
     */
    static getApiBaseUrl() {
        const baseUrl = window.location.origin + '/api/v1';
        console.log('API Base URL detected:', baseUrl);
        return baseUrl;
    }

    /**
     * Make API request with error handling
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise} - API response promise
     */
    static async apiRequest(endpoint, options = {}) {
        const baseUrl = this.getApiBaseUrl();
        const url = `${baseUrl}${endpoint}`;
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.detail || `HTTP error! Status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error);
            throw error;
        }
    }

    /**
     * Create upgrade overlay for locked predictions
     * @param {number} rank - Prediction rank
     * @returns {HTMLElement} - Upgrade overlay element
     */
    static createUpgradeOverlay(rank) {
        const overlay = document.createElement('div');
        overlay.className = 'upgrade-overlay';
        
        // Lock icon
        const lockIcon = document.createElement('i');
        lockIcon.className = 'fas fa-lock lock-icon';
        overlay.appendChild(lockIcon);
        
        // Rank badge
        const rankBadge = document.createElement('div');
        rankBadge.className = 'rank-badge';
        rankBadge.textContent = Number.isFinite(rank) ? 
            window.AppTexts.format(window.AppTexts.modals.upgrade.overlay.rankBadge, { rank: rank }) : 
            window.AppTexts.modals.upgrade.overlay.premiumContent;
        overlay.appendChild(rankBadge);
        
        // Upgrade message with urgency and social proof
        const upgradeMessage = document.createElement('div');
        upgradeMessage.className = 'upgrade-message';
        upgradeMessage.innerHTML = window.AppTexts.modals.upgrade.overlay.socialProof;
        overlay.appendChild(upgradeMessage);
        
        // Urgency indicator
        const urgencyBadge = document.createElement('div');
        urgencyBadge.className = 'urgency-badge';
        urgencyBadge.textContent = window.AppTexts.modals.upgrade.overlay.urgency;
        overlay.appendChild(urgencyBadge);
        
        // Value proposition
        const valueProp = document.createElement('div');
        valueProp.className = 'value-proposition';
        valueProp.textContent = window.AppTexts.modals.upgrade.overlay.valueProp;
        overlay.appendChild(valueProp);
        
        // CTA button with urgency
        const ctaButton = document.createElement('button');
        ctaButton.className = 'upgrade-cta';
        ctaButton.innerHTML = window.AppTexts.modals.upgrade.overlay.ctaButton;
        ctaButton.onclick = () => {
            // Check if AuthManager is available and show upgrade modal
            if (window.authManager && typeof window.authManager.showUpgradeModal === 'function') {
                window.authManager.showUpgradeModal();
            } else {
                // Fallback: open register modal to encourage signup
                const registerBtn = document.getElementById('register-btn');
                if (registerBtn) {
                    registerBtn.click();
                }
            }
        };
        overlay.appendChild(ctaButton);
        
        return overlay;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Type of notification (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds
     */
    static showToast(message, type = 'info', duration = 5000) {
        const toast = document.getElementById('toast-notification');
        const icon = document.getElementById('toast-icon');
        const messageEl = document.getElementById('toast-message');

        if (!toast || !icon || !messageEl) {
            console.warn('Toast elements not found');
            return;
        }

        // Set icon based on type
        const icons = {
            success: 'fas fa-check',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        icon.className = icons[type] || icons.info;
        messageEl.textContent = message;
        toast.className = `fixed bottom-5 right-5 text-white py-3 px-4 rounded-lg shadow-xl opacity-100 transition-opacity duration-300 z-50 ${type}`;

        // Auto-hide after duration
        setTimeout(() => {
            toast.classList.remove('opacity-100');
            toast.classList.add('opacity-0');
        }, duration);
    }
}

// Export for use in other scripts
window.PowerballUtils = PowerballUtils;