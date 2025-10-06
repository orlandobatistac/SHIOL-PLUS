/**
 * Ticket Verification JavaScript Module
 * Handles camera capture, file upload, and ticket verification functionality
 */

class TicketVerification {
    constructor() {
        this.currentImageFile = null;
        this.verificationSessionId = 0; // Session ID to prevent stale renders
        this.initializeEventListeners();
    }

    // Función para detectar si es dispositivo móvil
    isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               window.innerWidth <= 768 ||
               ('ontouchstart' in window);
    }

    initializeEventListeners() {
        // Camera and upload button handlers
        document.getElementById('camera-btn').addEventListener('click', () => this.openCamera());
        document.getElementById('upload-btn').addEventListener('click', () => this.openFileDialog());
        
        // File input handler
        document.getElementById('ticket-file-input').addEventListener('change', (e) => this.handleFileSelect(e));
        
        // Remove image handler
        document.getElementById('remove-image-btn').addEventListener('click', () => this.removeImage());
        
        // Preview numbers handler
        document.getElementById('preview-numbers-btn').addEventListener('click', () => this.previewNumbers());
        
        // Verify ticket handler
        document.getElementById('verify-ticket-btn').addEventListener('click', () => this.verifyTicket());
        
        // Manual date handlers
        document.getElementById('verify-with-manual-date-btn').addEventListener('click', () => this.verifyWithManualDate());
        document.getElementById('cancel-manual-date-btn').addEventListener('click', () => this.hideManualDateSection());
    }

    openCamera() {
        const fileInput = document.getElementById('ticket-file-input');
        // Set capture to environment (back camera) for better photo quality
        fileInput.setAttribute('capture', 'environment');
        fileInput.click();
    }

    openFileDialog() {
        const fileInput = document.getElementById('ticket-file-input');
        // Remove capture attribute for file selection
        fileInput.removeAttribute('capture');
        fileInput.click();
    }

    async handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showError(window.AppTexts.errors.invalidFileType);
            return;
        }

        console.log(`📱 Device type: ${this.isMobileDevice() ? 'Mobile' : 'Desktop'}`);
        console.log(`📄 Original file: ${file.name}, Size: ${(file.size / 1024 / 1024).toFixed(2)}MB`);

        const isMobile = this.isMobileDevice();
        const compressionThreshold = 2 * 1024 * 1024; // 2MB threshold

        // Aplicar compresión inteligente basada en dispositivo
        if (isMobile && file.size > compressionThreshold) {
            this.showLoading(window.AppTexts.loading.optimizingImage);
            try {
                const compressedFile = await this.compressImageOptimal(file);
                this.currentImageFile = compressedFile;
                this.hideLoading();
                this.displayImagePreview(compressedFile);
            } catch (error) {
                this.hideLoading();
                this.showError(window.AppTexts.errors.imageOptimizationFailed);
                return;
            }
        } else if (!isMobile) {
            // En escritorio, usar imagen original sin modificar
            console.log('🖥️ Desktop detected: Using original image without compression');
            this.currentImageFile = file;
            this.displayImagePreview(file);
        } else {
            // Mobile con archivo pequeño, usar original
            console.log('📱 Mobile with small file: Using original image');
            this.currentImageFile = file;
            this.displayImagePreview(file);
        }
        
        this.hideError();
    }

    displayImagePreview(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const previewImg = document.getElementById('image-preview');
            previewImg.src = e.target.result;
            
            // Show preview container and preview numbers button
            document.getElementById('image-preview-container').classList.remove('hidden');
            document.getElementById('preview-btn-container').classList.remove('hidden');
            
            // Hide verify button initially (show after preview)
            document.getElementById('verify-btn-container').classList.add('hidden');
            
            // Hide any previous results and numbers preview
            this.hideResults();
            this.hideNumbersPreview();
        };
        reader.readAsDataURL(file);
    }

    async compressImageOptimal(file) {
        return new Promise((resolve, reject) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = () => {
                const originalWidth = img.width;
                const originalHeight = img.height;
                
                console.log(`🖼️ Original resolution: ${originalWidth}x${originalHeight}`);
                
                // Calcular nuevas dimensiones manteniendo mínimo de 1280px de ancho
                let newWidth = originalWidth;
                let newHeight = originalHeight;
                const minWidth = 1280;
                
                // Si el ancho es menor a 1280px, mantener original para no perder calidad
                if (originalWidth > minWidth) {
                    // Solo redimensionar si es necesario para mantener calidad
                    const aspectRatio = originalHeight / originalWidth;
                    
                    // Si es mucho más grande, reducir manteniendo proporción pero no menos de 1280px
                    if (originalWidth > 2560) { // Solo comprimir si es muy grande
                        newWidth = Math.max(minWidth, Math.floor(originalWidth * 0.7));
                        newHeight = Math.floor(newWidth * aspectRatio);
                    }
                } else {
                    console.log(`📏 Image width ${originalWidth}px is below ${minWidth}px minimum, keeping original size`);
                }
                
                console.log(`🔄 Target resolution: ${newWidth}x${newHeight}`);
                
                // Configurar canvas con nuevas dimensiones
                canvas.width = newWidth;
                canvas.height = newHeight;
                
                // Configurar contexto para mejor calidad
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                
                // Dibujar imagen redimensionada
                ctx.drawImage(img, 0, 0, newWidth, newHeight);
                
                // Determinar calidad JPEG basada en el tamaño original
                let quality;
                if (file.size > 8 * 1024 * 1024) { // > 8MB
                    quality = 0.8; // 80%
                } else if (file.size > 4 * 1024 * 1024) { // > 4MB
                    quality = 0.85; // 85%
                } else {
                    quality = 0.9; // 90%
                }
                
                console.log(`🎨 Using JPEG quality: ${(quality * 100)}%`);
                
                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            console.log(`📦 Compressed file size: ${(blob.size / 1024 / 1024).toFixed(2)}MB`);
                            console.log(`📉 Compression ratio: ${((file.size - blob.size) / file.size * 100).toFixed(1)}% reduction`);
                            
                            // Crear nuevo archivo del blob
                            const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, '.jpg'), {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            resolve(compressedFile);
                        } else {
                            reject(new Error('Image compression failed'));
                        }
                    },
                    'image/jpeg',
                    quality
                );
            };
            
            img.onerror = () => reject(new Error('Failed to load image for compression'));
            img.src = URL.createObjectURL(file);
        });
    }

    // Mantener función original para compatibilidad
    async compressImage(file, maxWidth = 1200, maxHeight = 1200, quality = 0.8) {
        return new Promise((resolve, reject) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = () => {
                // Calculate new dimensions
                let { width, height } = img;
                
                if (width > height) {
                    if (width > maxWidth) {
                        height = (height * maxWidth) / width;
                        width = maxWidth;
                    }
                } else {
                    if (height > maxHeight) {
                        width = (width * maxHeight) / height;
                        height = maxHeight;
                    }
                }
                
                // Set canvas dimensions
                canvas.width = width;
                canvas.height = height;
                
                // Draw and compress
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            // Create new file from blob
                            const compressedFile = new File([blob], file.name, {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            resolve(compressedFile);
                        } else {
                            reject(new Error('Compression failed'));
                        }
                    },
                    'image/jpeg',
                    quality
                );
            };
            
            img.onerror = () => reject(new Error('Failed to load image'));
            img.src = URL.createObjectURL(file);
        });
    }

    removeImage() {
        this.currentImageFile = null;
        document.getElementById('image-preview-container').classList.add('hidden');
        document.getElementById('preview-btn-container').classList.add('hidden');
        document.getElementById('verify-btn-container').classList.add('hidden');
        document.getElementById('ticket-file-input').value = '';
        this.hideResults();
        this.hideNumbersPreview();
        this.hideError();
    }

    async previewNumbers() {
        if (!this.currentImageFile) {
            this.showError(window.AppTexts.errors.imageRequired);
            return;
        }

        // Start verification attempt logging
        const attemptId = `preview_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        console.group(`🎫 Ticket Preview Attempt: ${attemptId}`);
        console.log('📅 Started at:', new Date().toISOString());
        console.log('📁 File:', this.currentImageFile.name, `(${(this.currentImageFile.size / 1024 / 1024).toFixed(2)}MB)`);
        console.log('🔍 Phase: PREVIEW (number detection only)');

        // CHECK VERIFICATION LIMITS FIRST (before Google AI processing)
        console.log('🚦 Checking verification limits...');
        const limitsResult = await this.checkVerificationLimits();
        if (!limitsResult.allowed) {
            console.log('🚫 Limits check failed:', limitsResult);
            this.showLimitsError(limitsResult);
            console.groupEnd();
            return;
        }
        console.log('✅ Limits check passed:', limitsResult);

        this.showLoading();
        this.hideError();

        try {
            // Prepare form data
            const formData = new FormData();
            formData.append('file', this.currentImageFile);
            
            // Add device fingerprint header for guest users
            const headers = {};
            if (window.deviceFingerprinter && window.deviceFingerprinter.isReady()) {
                headers['x-device-fingerprint'] = window.deviceFingerprinter.getFingerprintForHeader();
                console.log('🔐 Device fingerprint included for limits checking');
            } else {
                console.log('⚠️ No device fingerprint available');
            }

            // Send request to preview API
            console.log('📡 Sending preview request to /api/v1/ticket/preview...');
            const response = await fetch('/api/v1/ticket/preview', {
                method: 'POST',
                body: formData,
                headers: headers
            });
            
            console.log('📡 Preview response status:', response.status, response.statusText);

            // Check if response is JSON before parsing
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                // If not JSON, get text response
                const textResponse = await response.text();
                throw new Error(`Server error: ${response.status} - ${textResponse.substring(0, 100)}`);
            }

            if (!response.ok) {
                console.error('❌ Preview failed:', response.status, result);
                // Handle limits-related errors specially
                if (response.status === 402) {
                    console.log('🚫 Verification limits reached - showing upgrade modal');
                    this.handleLimitsReachedError(result);
                    console.groupEnd();
                    return;
                } else if (response.status === 429) {
                    console.log('⏰ Rate limit exceeded');
                    this.showError('Too many requests. Please try again later.');
                    console.groupEnd();
                    return;
                }
                throw new Error(result.details || result.error || 'Preview failed');
            }

            console.log('✅ Preview successful - detected', result.detected_plays?.length || 0, 'plays');
            console.log('📊 Detection confidence:', result.confidence || 'unknown');
            if (result.detected_plays) {
                result.detected_plays.forEach((play, index) => {
                    console.log(`  Play ${index + 1}:`, play.white_balls, 'powerball:', play.powerball);
                });
            }
            this.hideLoading();
            this.displayNumbersPreview(result);
            console.groupEnd();

        } catch (error) {
            console.error('❌ Preview error:', error);
            console.groupEnd();
            this.hideLoading();
            this.showError(`Could not preview numbers: ${error.message}`);
        }
    }

    async verifyTicket() {
        if (!this.currentImageFile) {
            this.showError(window.AppTexts.errors.imageRequired);
            return;
        }

        // Start verification attempt logging
        const attemptId = `verify_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        console.group(`🏆 Ticket Verification Attempt: ${attemptId}`);
        console.log('📅 Started at:', new Date().toISOString());
        console.log('📁 File:', this.currentImageFile.name, `(${(this.currentImageFile.size / 1024 / 1024).toFixed(2)}MB)`);
        console.log('🎯 Phase: VERIFY (full verification with prize calculation)');

        this.showLoading();
        this.hideError();
        this.hideResults();

        try {
            // Prepare form data
            const formData = new FormData();
            formData.append('file', this.currentImageFile);

            // Add device fingerprint header for limit checking
            const headers = {};
            if (window.deviceFingerprinter && window.deviceFingerprinter.isReady()) {
                headers['x-device-fingerprint'] = window.deviceFingerprinter.getFingerprintForHeader();
                console.log('🔐 Device fingerprint included for verification limits');
            } else {
                console.log('⚠️ No device fingerprint available for verification');
            }

            // Send request to verification API
            console.log('📡 Sending verification request to /api/v1/ticket/verify...');
            const response = await fetch('/api/v1/ticket/verify', {
                method: 'POST',
                body: formData,
                headers: headers
            });
            
            console.log('📡 Verification response status:', response.status, response.statusText);

            // Check if response is JSON before parsing
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                // If not JSON, get text response
                const textResponse = await response.text();
                throw new Error(`Server error: ${response.status} - ${textResponse.substring(0, 100)}`);
            }

            if (!response.ok) {
                console.error('❌ Verification failed:', response.status, result);
                // Handle limits-related errors specially
                if (response.status === 402) {
                    console.log('🚫 Verification limits reached - showing upgrade modal');
                    this.hideLoading();
                    this.handleLimitsReachedError(result);
                    console.groupEnd();
                    return;
                } else if (response.status === 429) {
                    console.log('⏰ Rate limit exceeded');
                    this.hideLoading();
                    this.showError('Too many requests. Please try again later.');
                    console.groupEnd();
                    return;
                }
                throw new Error(result.details || result.error || 'Verification failed');
            }

            const verification = result.ticket_verification;
            if (verification && verification.is_winner) {
                console.log('🎉 WINNER! Prize amount:', verification.total_prize_amount);
                console.log('🏆 Winning plays:', verification.play_results.filter(p => p.is_winner).length, 'of', verification.play_results.length);
            } else {
                console.log('❌ No winning numbers found');
            }
            
            console.log('✅ Verification completed successfully');
            this.hideLoading();
            this.displayResults(result);
            console.groupEnd();

        } catch (error) {
            console.error('❌ Verification error:', error);
            this.hideLoading();
            
            // Check if this is a date detection error
            if (error.message && error.message.includes('No official draw results found for date')) {
                console.log('📅 Date detection error - showing manual date input');
                this.showManualDateSection();
                console.groupEnd();
            } 
            // Check if this is a validation error with no valid numbers
            else if (error.message && (
                error.message.includes('No valid lottery numbers found') || 
                error.message.includes('No lottery numbers detected') ||
                error.message.includes('All detected numbers were invalid')
            )) {
                console.log('🔍 Number validation error - showing validation modal');
                this.handleValidationError(error);
                console.groupEnd();
            } else {
                this.showError(error.message || 'Failed to verify ticket. Please try again.');
                console.groupEnd();
            }
            console.error('Verification error:', error);
        }
    }

    displayResults(result) {
        const resultsContainer = document.getElementById('verification-results');
        const winnerResult = document.getElementById('winner-result');
        const noWinResult = document.getElementById('no-win-result');
        
        // Increment session ID and clear previous results
        this.verificationSessionId++;
        const currentSessionId = this.verificationSessionId;
        this.clearTicketInfo();
        
        resultsContainer.classList.remove('hidden');

        const verification = result.ticket_verification;
        
        if (verification.is_winner) {
            // Show winner result
            winnerResult.classList.remove('hidden');
            noWinResult.classList.add('hidden');
            
            // Update prize amount
            document.getElementById('total-prize-amount').textContent = 
                `$${verification.total_prize_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            
            // Display winning plays details
            this.displayWinningPlays(verification.play_results.filter(play => play.is_winner));
            
        } else {
            // Show no win result - clearTicketInfo already called above
            winnerResult.classList.add('hidden');
            noWinResult.classList.remove('hidden');
        }

        // Update ticket details (check session ID to prevent stale renders)
        if (currentSessionId === this.verificationSessionId) {
            this.updateTicketDetails(verification, currentSessionId);
        }
    }

    displayWinningPlays(winningPlays) {
        const container = document.getElementById('winning-plays-details');
        
        if (winningPlays.length === 0) {
            container.innerHTML = '';
            return;
        }

        let html = '<div class="space-y-3">';
        html += '<h4 class="font-semibold text-white mb-2">Winning Plays:</h4>';
        
        winningPlays.forEach(play => {
            html += `
                <div class="bg-canvas-card rounded-lg p-3 border border-[#00e0ff]/20">
                    <div class="flex justify-between items-start mb-2">
                        <span class="font-medium text-white">Line ${play.line}</span>
                        <span class="font-bold bg-gradient-to-r from-[#00e0ff] via-[#a855f7] to-[#ff6b9d] bg-clip-text text-transparent">$${play.prize_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div class="flex flex-wrap items-center gap-2 mb-2">
                        ${this.renderNumbers(play.numbers, 'main')}
                        <span class="text-sm text-white/70">PB:</span>
                        ${this.renderNumbers([play.powerball], 'powerball')}
                    </div>
                    <div class="text-sm text-white/70">
                        ${play.main_matches} main number${play.main_matches !== 1 ? 's' : ''}${play.powerball_match ? ' + Powerball' : ''} 
                        (${play.prize_tier})
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }

    updateTicketDetails(verification, sessionId = null) {
        // Check session ID to prevent stale renders
        if (sessionId !== null && sessionId !== this.verificationSessionId) {
            console.log('⚠️ Ignoring stale ticket details render (session mismatch)');
            return;
        }
        
        // Update basic ticket info
        document.getElementById('ticket-draw-date').textContent = verification.draw_date || 'Unknown';
        document.getElementById('ticket-total-plays').textContent = verification.total_plays || 0;
        
        // Display official winning numbers
        document.getElementById('official-numbers').innerHTML = 
            this.renderNumbers(verification.official_numbers || [], 'main');
        document.getElementById('official-powerball').innerHTML = 
            this.renderNumbers([verification.official_powerball] || [0], 'powerball');
        
        // Display player's numbers with session protection
        this.displayPlayerNumbers(verification.play_results || [], sessionId);
    }

    displayPlayerNumbers(playResults, sessionId = null) {
        // Check session ID to prevent stale renders
        if (sessionId !== null && sessionId !== this.verificationSessionId) {
            console.log('⚠️ Ignoring stale player numbers render (session mismatch)');
            return;
        }
        
        const container = document.getElementById('your-numbers-list');
        if (!container) {
            console.error('❌ your-numbers-list container not found');
            return;
        }
        
        // Clear existing content using replaceChildren (modern approach)
        if (container.replaceChildren) {
            container.replaceChildren(); // Clear all children
        } else {
            // Fallback for older browsers
            container.innerHTML = '';
        }
        
        if (playResults.length === 0) {
            return; // No numbers to display
        }
        
        // Create document fragment for efficient DOM manipulation
        const fragment = document.createDocumentFragment();
        
        playResults.forEach(play => {
            const isWinner = play.is_winner;
            const borderClass = isWinner ? 'border-[#00e0ff]/30 bg-[#00e0ff]/5' : 'border-canvas-line';
            
            // Create the play row element
            const playRow = document.createElement('div');
            playRow.className = `flex flex-wrap items-center justify-between p-3 rounded-lg border ${borderClass} mb-2 gap-2`;
            playRow.innerHTML = `
                <div class="flex flex-wrap items-center gap-2">
                    <span class="text-sm font-medium text-white">Line ${play.line}:</span>
                    ${this.renderNumbers(play.numbers, 'main')}
                    <span class="text-sm text-white/70">PB:</span>
                    ${this.renderNumbers([play.powerball], 'powerball')}
                </div>
                <div class="text-right">
                    ${isWinner ? 
                        `<span class="font-bold text-sm bg-gradient-to-r from-[#00e0ff] via-[#a855f7] to-[#ff6b9d] bg-clip-text text-transparent">$${play.prize_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>` :
                        `<span class="text-white/40 text-sm">No Prize</span>`
                    }
                </div>
            `;
            
            fragment.appendChild(playRow);
        });
        
        // Replace content with new fragment (render replacement pattern)
        container.appendChild(fragment);
    }

    /**
     * Clear all ticket information from the results panel
     */
    clearTicketInfo() {
        console.log('🧹 Clearing ticket information panel');
        
        // Clear your numbers list
        const yourNumbersList = document.getElementById('your-numbers-list');
        if (yourNumbersList) {
            if (yourNumbersList.replaceChildren) {
                yourNumbersList.replaceChildren();
            } else {
                yourNumbersList.innerHTML = '';
            }
        }
        
        // Clear winning plays details
        const winningPlaysDetails = document.getElementById('winning-plays-details');
        if (winningPlaysDetails) {
            winningPlaysDetails.innerHTML = '';
        }
        
        // Clear official numbers
        const officialNumbers = document.getElementById('official-numbers');
        const officialPowerball = document.getElementById('official-powerball');
        if (officialNumbers) officialNumbers.innerHTML = '';
        if (officialPowerball) officialPowerball.innerHTML = '';
        
        // Reset ticket details to default values
        const ticketDrawDate = document.getElementById('ticket-draw-date');
        const ticketTotalPlays = document.getElementById('ticket-total-plays');
        if (ticketDrawDate) ticketDrawDate.textContent = '-';
        if (ticketTotalPlays) ticketTotalPlays.textContent = '-';
    }

    renderNumbers(numbers, type) {
        if (!numbers || numbers.length === 0) return '';
        
        const chipClass = type === 'powerball' ? 
            'num-chip num-chip-power' : 
            'num-chip num-chip-main';
        
        return numbers.map(num => 
            `<span class="${chipClass}">${num}</span>`
        ).join('');
    }

    showLoading(message = 'Processing...') {
        const loadingElement = document.getElementById('verification-loading');
        
        // Try to update loading message if there's a text element
        const messageElement = loadingElement.querySelector('.loading-message') || 
                              loadingElement.querySelector('p') ||
                              loadingElement.querySelector('span');
        
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        loadingElement.classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('verification-loading').classList.add('hidden');
    }

    showError(message) {
        const errorDiv = document.getElementById('verification-error');
        const errorMsg = document.getElementById('error-message');
        errorMsg.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    hideError() {
        document.getElementById('verification-error').classList.add('hidden');
    }

    hideResults() {
        document.getElementById('verification-results').classList.add('hidden');
        document.getElementById('winner-result').classList.add('hidden');
        document.getElementById('no-win-result').classList.add('hidden');
    }

    async verifyWithManualDate() {
        const manualDate = document.getElementById('manual-date-input').value;
        
        if (!manualDate) {
            this.showError('Please select a draw date to continue.');
            return;
        }

        if (!this.currentImageFile) {
            this.showError(window.AppTexts.errors.imageRequired);
            return;
        }

        this.hideManualDateSection();
        this.showLoading();
        this.hideError();
        this.hideResults();

        try {
            // Prepare form data with manual date
            const formData = new FormData();
            formData.append('file', this.currentImageFile);
            formData.append('manual_date', manualDate);

            // Add device fingerprint header for limit checking
            const headers = {};
            if (window.deviceFingerprinter && window.deviceFingerprinter.isReady()) {
                headers['x-device-fingerprint'] = window.deviceFingerprinter.getFingerprintForHeader();
                console.log('🔐 Device fingerprint included for manual date verification limits');
            } else {
                console.log('⚠️ No device fingerprint available for manual date verification');
            }

            // Send request to verification API
            const response = await fetch('/api/v1/ticket/verify', {
                method: 'POST',
                body: formData,
                headers: headers
            });

            // Check if response is JSON before parsing
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                // If not JSON, get text response
                const textResponse = await response.text();
                throw new Error(`Server error: ${response.status} - ${textResponse.substring(0, 100)}`);
            }

            if (!response.ok) {
                // Handle limits-related errors specially
                if (response.status === 402) {
                    this.hideLoading();
                    this.handleLimitsReachedError(result);
                    return;
                } else if (response.status === 429) {
                    this.hideLoading();
                    this.showError('Too many requests. Please try again later.');
                    return;
                }
                throw new Error(result.details || result.error || 'Verification failed');
            }

            this.hideLoading();
            this.displayResults(result);

        } catch (error) {
            this.hideLoading();
            
            // Check if this is a validation error with no valid numbers
            if (error.message && (
                error.message.includes('No valid lottery numbers found') || 
                error.message.includes('No lottery numbers detected') ||
                error.message.includes('All detected numbers were invalid')
            )) {
                this.handleValidationError(error);
            } else {
                this.showError(error.message || 'Failed to verify ticket with manual date. Please try again.');
            }
            console.error('Manual verification error:', error);
        }
    }

    showManualDateSection() {
        document.getElementById('manual-date-section').classList.remove('hidden');
        // Set default date to August 2, 2025 (known to exist in database)
        document.getElementById('manual-date-input').value = '2025-08-02';
    }

    hideManualDateSection() {
        document.getElementById('manual-date-section').classList.add('hidden');
        document.getElementById('manual-date-input').value = '';
    }

    async handleValidationError(error, responseData = null) {
        // If we have response data from the API, use it to show detailed validation errors
        let errorDetails = null;
        
        try {
            // Try to get the response data if not provided
            if (!responseData && error.response) {
                responseData = await error.response.json();
            }
        } catch (e) {
            // Ignore if we can't parse response
        }

        if (responseData && responseData.validation_summary) {
            this.showValidationErrorWithEdit(responseData);
        } else {
            // Fallback to simple validation error
            this.showValidationError(error.message);
        }
    }

    showValidationError(message) {
        const errorHtml = `
            <div class="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg border border-red-200 dark:border-red-800">
                <div class="flex items-start">
                    <i class="fas fa-exclamation-triangle text-red-600 mr-3 mt-1"></i>
                    <div class="flex-1">
                        <h4 class="font-semibold text-red-800 dark:text-red-200 mb-2">Unable to Read Lottery Numbers</h4>
                        <p class="text-red-700 dark:text-red-300 text-sm mb-3">${message}</p>
                        <div class="text-sm text-red-600 dark:text-red-400 mb-4">
                            <p class="mb-2"><strong>Possible causes:</strong></p>
                            <ul class="list-disc list-inside space-y-1 ml-2">
                                <li>The image may be blurry or poorly lit</li>
                                <li>The ticket numbers are not clearly visible</li>
                                <li>The photo doesn't include the full ticket</li>
                                <li>The ticket may be damaged or distorted</li>
                            </ul>
                        </div>
                        <div class="flex flex-col sm:flex-row gap-2">
                            <button onclick="ticketVerification.showManualPlayEntry()" 
                                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                                <i class="fas fa-edit mr-1"></i>
                                Enter Numbers Manually
                            </button>
                            <button onclick="ticketVerification.retryImageCapture()" 
                                class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2">
                                <i class="fas fa-camera mr-1"></i>
                                Try Another Photo
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.showCustomError(errorHtml);
    }

    showValidationErrorWithEdit(responseData) {
        const validationSummary = responseData.validation_summary;
        const rawTextLines = responseData.raw_text_lines || [];
        
        let detectedInfo = '';
        if (validationSummary.total_detected > 0) {
            detectedInfo = `
                <div class="mb-3 p-3 bg-yellow-50 dark:bg-yellow-900/30 rounded border border-yellow-200 dark:border-yellow-800">
                    <p class="text-yellow-800 dark:text-yellow-200 text-sm">
                        <strong>Detection Summary:</strong> Found ${validationSummary.total_detected} number combinations, 
                        but ${validationSummary.invalid_plays} were rejected due to invalid numbers.
                    </p>
                    ${validationSummary.validation_errors.length > 0 ? `
                        <div class="mt-2">
                            <p class="text-yellow-700 dark:text-yellow-300 text-sm font-medium">Issues found:</p>
                            <ul class="text-yellow-700 dark:text-yellow-300 text-sm list-disc list-inside mt-1 ml-2">
                                ${validationSummary.validation_errors.slice(0, 3).map(err => `<li>${err}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            `;
        }

        const errorHtml = `
            <div class="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg border border-red-200 dark:border-red-800">
                <div class="flex items-start">
                    <i class="fas fa-exclamation-triangle text-red-600 mr-3 mt-1"></i>
                    <div class="flex-1">
                        <h4 class="font-semibold text-red-800 dark:text-red-200 mb-2">Invalid Lottery Numbers Detected</h4>
                        <p class="text-red-700 dark:text-red-300 text-sm mb-3">
                            The system detected some numbers on your ticket, but they were outside the valid Powerball ranges 
                            (main numbers 1-69, Powerball 1-26).
                        </p>
                        ${detectedInfo}
                        <div class="flex flex-col sm:flex-row gap-2">
                            <button onclick="ticketVerification.showManualPlayEntry()" 
                                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                                <i class="fas fa-edit mr-1"></i>
                                Enter Correct Numbers
                            </button>
                            <button onclick="ticketVerification.retryImageCapture()" 
                                class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2">
                                <i class="fas fa-camera mr-1"></i>
                                Try Better Photo
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.showCustomError(errorHtml);
    }

    showCustomError(htmlContent) {
        const errorDiv = document.getElementById('verification-error');
        errorDiv.innerHTML = htmlContent;
        errorDiv.classList.remove('hidden');
    }

    showManualPlayEntry() {
        this.hideError();
        document.getElementById('manual-play-entry').classList.remove('hidden');
        // Focus on first number input
        document.getElementById('play-1-num-1').focus();
    }

    hideManualPlayEntry() {
        document.getElementById('manual-play-entry').classList.add('hidden');
        this.clearManualPlayInputs();
    }

    retryImageCapture() {
        this.hideError();
        this.removeImage();
        // Focus on upload buttons
        document.getElementById('camera-btn').focus();
    }

    clearManualPlayInputs() {
        // Clear all manual play inputs
        for (let play = 1; play <= 5; play++) {
            for (let num = 1; num <= 5; num++) {
                document.getElementById(`play-${play}-num-${num}`).value = '';
            }
            document.getElementById(`play-${play}-pb`).value = '';
        }
        document.getElementById('manual-draw-date').value = '2025-08-02'; // Default to known date
    }

    async verifyManualPlays() {
        const manualPlays = this.getManualPlaysData();
        const drawDate = document.getElementById('manual-draw-date').value;
        
        if (manualPlays.length === 0) {
            this.showError('Please enter at least one complete play (5 main numbers + Powerball).');
            return;
        }

        if (!drawDate) {
            this.showError('Please select a draw date.');
            return;
        }

        this.hideManualPlayEntry();
        this.showLoading();
        this.hideError();

        try {
            // Send manual play data to verification API
            const response = await fetch('/api/v1/ticket/verify-manual', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    plays: manualPlays,
                    draw_date: drawDate
                })
            });

            // Check if response is JSON before parsing
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                // If not JSON, get text response
                const textResponse = await response.text();
                throw new Error(`Server error: ${response.status} - ${textResponse.substring(0, 100)}`);
            }

            if (!response.ok) {
                throw new Error(result.details || result.error || 'Manual verification failed');
            }

            this.hideLoading();
            this.displayResults(result);

        } catch (error) {
            this.hideLoading();
            this.showError(error.message || 'Failed to verify manual plays. Please check your numbers and try again.');
            console.error('Manual play verification error:', error);
        }
    }

    getManualPlaysData() {
        const plays = [];
        
        for (let playNum = 1; playNum <= 5; playNum++) {
            const mainNumbers = [];
            let hasAnyNumber = false;
            
            // Collect main numbers
            for (let numIndex = 1; numIndex <= 5; numIndex++) {
                const input = document.getElementById(`play-${playNum}-num-${numIndex}`);
                const value = parseInt(input.value.trim());
                
                if (!isNaN(value)) {
                    hasAnyNumber = true;
                    mainNumbers.push(value);
                }
            }
            
            // Get powerball
            const pbInput = document.getElementById(`play-${playNum}-pb`);
            const powerball = parseInt(pbInput.value.trim());
            
            if (!isNaN(powerball)) {
                hasAnyNumber = true;
            }
            
            // Only add play if it has complete data (5 main numbers + powerball)
            if (mainNumbers.length === 5 && !isNaN(powerball)) {
                plays.push({
                    line: playNum,
                    main_numbers: mainNumbers.sort((a, b) => a - b), // Sort numbers
                    powerball: powerball
                });
            } else if (hasAnyNumber) {
                // Partial data - show validation error
                this.showError(`Play ${playNum} is incomplete. Please enter all 5 main numbers and the Powerball number.`);
                return [];
            }
        }
        
        return plays;
    }

    displayNumbersPreview(result) {
        const detectedPlays = result.detected_plays || [];
        const playsList = document.getElementById('detected-plays-list');
        const confidence = document.getElementById('detection-confidence');
        const drawDatePreview = document.getElementById('draw-date-preview');

        // Clear previous content
        playsList.innerHTML = '';

        // Set confidence info
        confidence.textContent = `Confidence: ${Math.round(result.confidence * 100)}%`;

        // Check if we have very few plays detected (likely OCR failure)
        if (detectedPlays.length < 3) {
            // Show warning about incomplete detection
            const warningDiv = document.createElement('div');
            warningDiv.className = 'mb-3 p-3 bg-canvas-card rounded border border-gray-600/30';
            warningDiv.innerHTML = `
                <div class="flex items-start">
                    <i class="fas fa-exclamation-triangle text-gray-300 mr-2 mt-1"></i>
                    <div class="flex-1">
                        <h4 class="font-semibold text-white text-sm">Incomplete Detection</h4>
                        <p class="text-white/70 text-sm mt-1">
                            Only ${detectedPlays.length} plays detected. North Carolina tickets typically have 5 plays (A, B, C, D, E).
                            The camera may not have captured all the numbers clearly.
                        </p>
                        <button onclick="ticketVerification.showManualPlayEntry()" 
                            class="mt-2 px-3 py-1 bg-canvas-accent hover:opacity-90 text-white text-sm rounded font-medium transition-opacity duration-200">
                            <i class="fas fa-edit mr-1"></i>
                            Enter All Numbers Manually
                        </button>
                    </div>
                </div>
            `;
            playsList.appendChild(warningDiv);
        }

        // Display each detected play
        detectedPlays.forEach(play => {
            const playDiv = document.createElement('div');
            playDiv.className = `flex flex-wrap items-center justify-between p-2 bg-canvas-card rounded border ${play.is_valid ? 'border-[#00e0ff]/30' : 'border-[#ef4444]/30'} gap-2`;
            
            playDiv.innerHTML = `
                <div class="flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-sm ${play.is_valid ? 'text-[#00e0ff]' : 'text-[#ef4444]'}">
                        Play ${play.play_letter}:
                    </span>
                    <div class="flex flex-wrap items-center gap-1">
                        ${play.main_numbers.map(num => `
                            <span class="num-chip num-chip-main">
                                ${num}
                            </span>
                        `).join('')}
                        <span class="mx-1 text-white/70 text-sm">PB:</span>
                        <span class="num-chip num-chip-power">
                            ${play.powerball}
                        </span>
                    </div>
                </div>
                <div>
                    ${play.is_valid ? 
                        '<i class="fas fa-check-circle text-[#00e0ff]"></i>' : 
                        '<i class="fas fa-exclamation-triangle text-[#ef4444]" title="Invalid numbers"></i>'
                    }
                </div>
            `;
            
            playsList.appendChild(playDiv);
        });

        // Set draw date info
        if (result.draw_date_detected) {
            drawDatePreview.innerHTML = `<i class="fas fa-calendar mr-1"></i>Draw date detected: ${result.draw_date_detected}`;
        } else {
            drawDatePreview.innerHTML = `<i class="fas fa-calendar-times mr-1"></i>No draw date detected - you may need to enter it manually`;
        }

        // Show the preview and verify button
        document.getElementById('numbers-preview-container').classList.remove('hidden');
        document.getElementById('verify-btn-container').classList.remove('hidden');
        
        console.log('Numbers preview displayed:', result);
    }

    hideNumbersPreview() {
        document.getElementById('numbers-preview-container').classList.add('hidden');
    }

    /**
     * Check verification limits before attempting verification
     */
    async checkVerificationLimits() {
        try {
            const requestData = {};
            
            // Add device fingerprint data for guest users
            if (window.deviceFingerprinter && window.deviceFingerprinter.isReady()) {
                requestData.device_info = window.deviceFingerprinter.getFingerprintData();
            }
            
            const response = await fetch('/api/v1/ticket/limits-check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                credentials: 'include'
            });
            
            const result = await response.json();
            
            if (result.success && result.limits) {
                return {
                    allowed: result.limits.allowed,
                    ...result.limits
                };
            } else {
                // If limits check fails, allow but with warning
                console.warn('Limits check failed, proceeding with verification');
                return { allowed: true };
            }
        } catch (error) {
            console.warn('Error checking limits:', error);
            // If limits check fails, allow but with warning
            return { allowed: true };
        }
    }

    /**
     * Show limits error message to user
     */
    showLimitsError(limitsInfo) {
        const userType = limitsInfo.user_type || 'unknown';
        const remaining = limitsInfo.remaining || 0;
        const weeklyLimit = limitsInfo.weekly_limit || 1;
        const isRegistered = limitsInfo.is_registered || false;
        
        let message = '';
        let actionMessage = '';
        
        if (userType === 'guest') {
            message = `You've reached your weekly verification limit (${weeklyLimit} verification${weeklyLimit > 1 ? 's' : ''} per week).`;
            actionMessage = '🎯 Register for FREE to get 3 verifications per week!';
        } else if (userType === 'free_user') {
            message = `You've reached your weekly verification limit (${weeklyLimit} verifications per week).`;
            actionMessage = '⭐ Upgrade to Premium for unlimited verifications!';
        } else {
            message = 'Verification limit reached.';
            actionMessage = 'Please try again later.';
        }
        
        // Add reset time if available
        if (limitsInfo.reset_time_formatted) {
            message += ` Limits reset on ${limitsInfo.reset_time_formatted}.`;
        }
        
        this.showLimitsModal(message, actionMessage, userType, isRegistered);
    }

    /**
     * Handle limits reached error from server
     */
    handleLimitsReachedError(result) {
        if (result.limit_info) {
            this.showLimitsError(result.limit_info);
        } else {
            this.showError(result.error || 'Verification limit reached.');
        }
    }

    /**
     * Show limits modal with upgrade options
     */
    showLimitsModal(message, actionMessage, userType, isRegistered) {
        // Create modal HTML
        const modalHtml = `
            <div id="limits-modal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                <div class="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6 relative">
                    <button onclick="this.closest('#limits-modal').remove()" class="absolute top-4 right-4 text-gray-300 hover:text-gray-600">
                        <i class="fas fa-times"></i>
                    </button>
                    
                    <div class="text-center">
                        <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full ${userType === 'guest' ? 'bg-blue-100' : 'bg-orange-100'} mb-4">
                            <i class="fas ${userType === 'guest' ? 'fa-user-plus text-blue-600' : 'fa-crown text-orange-600'} text-xl"></i>
                        </div>
                        
                        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                            Verification Limit Reached
                        </h3>
                        
                        <p class="text-gray-400 dark:text-gray-300 mb-4">
                            ${message}
                        </p>
                        
                        <div class="bg-${userType === 'guest' ? 'blue' : 'orange'}-50 dark:bg-gray-700 rounded-lg p-4 mb-4">
                            <p class="text-${userType === 'guest' ? 'blue' : 'orange'}-700 dark:text-${userType === 'guest' ? 'blue' : 'orange'}-300 font-medium">
                                ${actionMessage}
                            </p>
                        </div>
                        
                        <div class="flex space-x-3">
                            <button onclick="this.closest('#limits-modal').remove()" 
                                    class="flex-1 px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-700 rounded-lg transition-colors">
                                Close
                            </button>
                            ${!isRegistered ? `
                                <button onclick="window.authManager?.showUpgradeModal(); this.closest('#limits-modal').remove();" 
                                        class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                                    Register FREE
                                </button>
                            ` : `
                                <button onclick="window.authManager?.showUpgradeModal(); this.closest('#limits-modal').remove();" 
                                        class="flex-1 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors">
                                    Upgrade to Premium
                                </button>
                            `}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove any existing limits modal
        const existingModal = document.getElementById('limits-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
}

// Initialize ticket verification when DOM is loaded
let ticketVerification;
document.addEventListener('DOMContentLoaded', () => {
    ticketVerification = new TicketVerification();
});