// Suppress Chrome extension errors
try {
    if (typeof chrome !== 'undefined' && chrome.runtime) {
        // Override console.error to filter chrome extension errors
        const originalConsoleError = console.error;
        console.error = function(...args) {
            const message = args.join(' ');
            if (message.includes('Unchecked runtime.lastError') ||
                message.includes('message port closed') ||
                message.includes('Extension context invalidated')) {
                // Suppress these specific chrome extension errors
                return;
            }
            originalConsoleError.apply(console, args);
        };

        // Also handle the runtime.lastError directly
        if (chrome.runtime.lastError) {
            // Clear the error silently
            const error = chrome.runtime.lastError;
            if (error.message && error.message.includes('message port closed')) {
                // Acknowledge the error to clear it
                void chrome.runtime.lastError;
            }
        }
    }
} catch (e) {
    // If chrome object manipulation fails, just continue
}

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    // Pipeline dashboard elements
    const pipelineStatusIndicator = document.getElementById('pipeline-status-indicator');
    const pipelineStatusText = document.getElementById('pipeline-status-text');
    const pipelineStatusDescription = document.getElementById('pipeline-status-description');
    const nextExecutionTime = document.getElementById('next-execution-time');
    const nextExecutionCountdown = document.getElementById('next-execution-countdown');
    const systemHealthIndicator = document.getElementById('system-health-indicator');
    const systemHealthText = document.getElementById('system-health-text');
    const systemHealthDetails = document.getElementById('system-health-details');
    const triggerPipelineBtn = document.getElementById('trigger-pipeline-btn');
    const viewLogsBtn = document.getElementById('view-logs-btn');
    const refreshPipelineBtn = document.getElementById('refresh-pipeline-btn');
    const autoRefreshCheckbox = document.getElementById('auto-refresh-checkbox');
    const executionHistoryTbody = document.getElementById('execution-history-tbody');
    const lastGeneratedPlays = document.getElementById('last-generated-plays');
    const lastPlaysContainer = document.getElementById('last-plays-container');
    const lastPlaysTimestamp = document.getElementById('last-plays-timestamp');
    const pipelineTriggerModal = document.getElementById('pipeline-trigger-modal');
    const cancelTriggerBtn = document.getElementById('cancel-trigger-btn');
    const confirmTriggerBtn = document.getElementById('confirm-trigger-btn');
    const pipelineNotification = document.getElementById('pipeline-notification');
    const pipelineNotificationIcon = document.getElementById('pipeline-notification-icon');
    const pipelineNotificationText = document.getElementById('pipeline-notification-text');

    // --- API Configuration ---
    // Enhanced dynamic API URL configuration with automatic detection
    function getApiBaseUrl() {
        // Use current origin for API calls - automatically adapts to any server IP
        const baseUrl = window.location.origin + '/api/v1';

        // Log the detected configuration for debugging
        console.log('API Base URL detected:', baseUrl);
        console.log('Current location:', {
            protocol: window.location.protocol,
            hostname: window.location.hostname,
            port: window.location.port,
            origin: window.location.origin
        });

        return baseUrl;
    }

    // --- Timezone Conversion Functions ---
    function convertToETTimezone(dateString) {
        if (!dateString || dateString === 'N/A') return 'N/A';
        
        try {
            // The backend already provides dates in ET timezone
            // We just need to format them for display without additional conversion
            let date;
            
            if (dateString.includes('T')) {
                // ISO format - parse directly
                date = new Date(dateString);
            } else if (dateString.includes('-')) {
                // YYYY-MM-DD HH:MM:SS format
                date = new Date(dateString);
            } else {
                return dateString; // Return as-is if can't parse
            }
            
            // Check if the date parsed correctly
            if (isNaN(date.getTime())) {
                console.warn('Invalid date parsed:', dateString);
                return dateString;
            }
            
            // Format for display: MM/DD/YYYY H:MM AM/PM ET
            // Use local browser formatting but display the time as-is from backend
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const year = date.getFullYear();
            
            let hours = date.getHours();
            let minutes = String(date.getMinutes()).padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            
            // Convert to 12-hour format
            hours = hours % 12;
            hours = hours ? hours : 12; // 0 should be 12
            
            const formattedTime = `${hours}:${minutes} ${ampm}`;
            const formattedDate = `${month}/${day}/${year} ${formattedTime} ET`;
            
            return formattedDate;
            
        } catch (error) {
            console.warn('Error formatting date for ET display:', dateString, error);
            return dateString; // Return original if conversion fails
        }
    }

    const API_BASE_URL = getApiBaseUrl();

    let lastPredictions = [];
    let lastPredictionData = null;
    let currentMethod = 'traditional';
    let autoRefreshInterval = null;
    let countdownInterval = null;
    let syndicateData = null;

    // --- Event Listeners ---
    // Pipeline dashboard event listeners
    if (triggerPipelineBtn) {
        triggerPipelineBtn.addEventListener('click', showTriggerModal);
    }
    if (viewLogsBtn) {
        viewLogsBtn.addEventListener('click', viewPipelineLogs);
    }
    if (refreshPipelineBtn) {
        refreshPipelineBtn.addEventListener('click', refreshPipelineStatus);
    }
    if (autoRefreshCheckbox) {
        autoRefreshCheckbox.addEventListener('change', handleAutoRefreshToggle);
    }
    if (cancelTriggerBtn) {
        cancelTriggerBtn.addEventListener('click', hideTriggerModal);
    }
    if (confirmTriggerBtn) {
        confirmTriggerBtn.addEventListener('click', triggerPipeline);
    }

    // Close modal when clicking outside
    if (pipelineTriggerModal) {
        pipelineTriggerModal.addEventListener('click', (e) => {
            if (e.target === pipelineTriggerModal) {
                hideTriggerModal();
            }
        });
    }

    // Syndicate predictions event listeners
    const generateSyndicateBtn = document.getElementById('generate-syndicate-btn');
    const exportSyndicateBtn = document.getElementById('export-syndicate-btn');

    if (generateSyndicateBtn) {
        generateSyndicateBtn.addEventListener('click', generateSyndicatePredictions);
    }
    if (exportSyndicateBtn) {
        exportSyndicateBtn.addEventListener('click', exportSyndicateData);
    }

    // --- Pipeline Dashboard Functions ---
    async function fetchPipelineStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/pipeline/status`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });

            if (response.status === 401) {
                showPipelineError('Authentication required. Please login.');
                setTimeout(() => window.location.href = '/login', 2000);
                return null;
            }

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            updatePipelineStatus(data);
            return data;
        } catch (error) {
            console.error('Pipeline status fetch error:', error);
            showPipelineError(`Failed to fetch pipeline status: ${error.message}`);
            return null;
        }
    }

    function updatePipelineStatus(data) {
        if (!data) return;

        // Extract pipeline status data
        const pipelineStatus = data.pipeline_status || {};
        const status = pipelineStatus.current_status || 'unknown';

        // Update current status
        if (pipelineStatusIndicator && pipelineStatusText && pipelineStatusDescription) {
            pipelineStatusIndicator.className = `w-3 h-3 rounded-full status-${status}`;
            pipelineStatusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            pipelineStatusDescription.textContent = `Pipeline is currently ${status}`;
        }

        // Update next execution time
        if (nextExecutionTime && nextExecutionCountdown) {
            if (pipelineStatus.next_scheduled_execution) {
                const nextTime = new Date(pipelineStatus.next_scheduled_execution);
                nextExecutionTime.textContent = nextTime.toLocaleTimeString();
                updateCountdown(nextTime);
            } else {
                nextExecutionTime.textContent = 'Not scheduled';
                nextExecutionCountdown.textContent = 'Manual execution only';
            }
        }

        // Update system health
        if (systemHealthIndicator && systemHealthText && systemHealthDetails) {
            const health = pipelineStatus.system_health || {};
            let healthStatus = 'unknown';
            let healthDetails = 'No health information available';

            // Determine health status based on system metrics
            if (health.cpu_usage_percent !== undefined) {
                if (health.cpu_usage_percent < 80 && health.memory_usage_percent < 85 && health.disk_usage_percent < 90) {
                    healthStatus = 'healthy';
                    healthDetails = `CPU: ${health.cpu_usage_percent}%, Memory: ${health.memory_usage_percent}%, Disk: ${health.disk_usage_percent}%`;
                } else {
                    healthStatus = 'degraded';
                    healthDetails = `High resource usage - CPU: ${health.cpu_usage_percent}%, Memory: ${health.memory_usage_percent}%`;
                }
            }

            systemHealthIndicator.className = `w-3 h-3 rounded-full health-${healthStatus}`;
            systemHealthText.textContent = healthStatus.charAt(0).toUpperCase() + healthStatus.slice(1);
            systemHealthDetails.textContent = healthDetails;
        }

        // Update execution history
        if (pipelineStatus.recent_execution_history) {
            updateExecutionHistory(pipelineStatus.recent_execution_history);
        }

        // Update last generated plays
        if (data.generated_plays_last_run && data.generated_plays_last_run.length > 0) {
            updateLastGeneratedPlays({
                plays: data.generated_plays_last_run.map(play => [...play.numbers, play.powerball]),
                scores: data.generated_plays_last_run.map(play => play.score),
                timestamp: data.generated_plays_last_run[0].timestamp
            });
        }

        // Update trigger button state based on current execution status
        if (triggerPipelineBtn) {
            // FIXED: Only enable button when pipeline is not running/starting/processing
            const canTrigger = status !== 'running' && status !== 'starting' && status !== 'processing';
            triggerPipelineBtn.disabled = !canTrigger;
            
            // Update button text based on status
            if (status === 'running' || status === 'starting' || status === 'processing') {
                triggerPipelineBtn.innerHTML = '<i class="fas fa-cog fa-spin mr-2"></i>Pipeline Running...';
                triggerPipelineBtn.className = triggerPipelineBtn.className.replace(/bg-\w+-\d+/g, 'bg-blue-600');
            } else {
                triggerPipelineBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Run Pipeline Now';
                triggerPipelineBtn.className = triggerPipelineBtn.className.replace(/bg-\w+-\d+/g, 'bg-green-600 hover:bg-green-700');
            }
        }
    }

    function updateCountdown(targetTime) {
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }

        countdownInterval = setInterval(() => {
            const now = new Date();
            const diff = targetTime - now;

            if (diff <= 0) {
                nextExecutionCountdown.textContent = 'Execution due';
                clearInterval(countdownInterval);
                return;
            }

            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            if (hours > 0) {
                nextExecutionCountdown.textContent = `in ${hours}h ${minutes}m`;
            } else if (minutes > 0) {
                nextExecutionCountdown.textContent = `in ${minutes}m ${seconds}s`;
            } else {
                nextExecutionCountdown.textContent = `in ${seconds}s`;
            }
        }, 1000);
    }

    function updateExecutionHistory(executions) {
        if (!executionHistoryTbody) return;

        if (!executions || executions.length === 0) {
            executionHistoryTbody.textContent = ''; // Clear existing content safely
            const row = document.createElement('tr');
            const cell = document.createElement('td');
            cell.colSpan = 5;
            cell.className = 'px-4 py-8 text-center text-gray-500 dark:text-gray-400';
            cell.textContent = 'No execution history available';
            row.appendChild(cell);
            executionHistoryTbody.appendChild(row);
            return;
        }

        executionHistoryTbody.textContent = ''; // Clear previous content safely

        // Sort executions by start time (most recent first)
        const sortedExecutions = [...executions].sort((a, b) => {
            const timeA = new Date(a.start_time || 0);
            const timeB = new Date(b.start_time || 0);
            return timeB - timeA;
        });

        sortedExecutions.forEach((execution, index) => {
            const startTime = execution.start_time ? convertToETTimezone(execution.start_time) : 'N/A';
            const endTime = execution.end_time ? new Date(execution.end_time) : null;
            const startTimeObj = execution.start_time ? new Date(execution.start_time) : null;

            let duration = 'N/A';
            if (execution.status === 'running') {
                duration = 'In progress...';
            } else if (startTimeObj && endTime) {
                const durationMs = endTime - startTimeObj;
                const minutes = Math.floor(durationMs / 60000);
                const seconds = Math.floor((durationMs % 60000) / 1000);
                duration = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
            }

            const status = execution.status || 'unknown';
            const executionId = execution.execution_id || 'unknown';

            const row = document.createElement('tr');
            
            // Highlight the most recent execution
            if (index === 0) {
                row.className = 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500';
            }

            // Start time cell
            const startTimeCell = document.createElement('td');
            startTimeCell.className = 'px-4 py-3 text-sm text-gray-900 dark:text-gray-100';
            startTimeCell.textContent = startTime;
            row.appendChild(startTimeCell);

            // Status cell with enhanced styling
            const statusCell = document.createElement('td');
            statusCell.className = 'px-4 py-3';
            const statusSpan = document.createElement('span');
            
            // Enhanced status styling
            const statusStyles = {
                'running': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 animate-pulse',
                'completed': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
                'failed': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
                'starting': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
            };
            
            statusSpan.className = `px-2 py-1 text-xs font-medium rounded-full ${statusStyles[status] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}`;
            
            // Add icon based on status
            const statusIcons = {
                'running': 'fas fa-spinner fa-spin',
                'completed': 'fas fa-check-circle',
                'failed': 'fas fa-exclamation-circle',
                'starting': 'fas fa-play-circle'
            };
            
            const statusIcon = document.createElement('i');
            statusIcon.className = `${statusIcons[status] || 'fas fa-question-circle'} mr-1`;
            
            statusSpan.appendChild(statusIcon);
            statusSpan.appendChild(document.createTextNode(status.charAt(0).toUpperCase() + status.slice(1)));
            statusCell.appendChild(statusSpan);
            row.appendChild(statusCell);

            // Duration cell
            const durationCell = document.createElement('td');
            durationCell.className = 'px-4 py-3 text-sm text-gray-900 dark:text-gray-100';
            durationCell.textContent = duration;
            row.appendChild(durationCell);

            // Steps cell with progress bar for running executions
            const stepsCell = document.createElement('td');
            stepsCell.className = 'px-4 py-3';
            
            const stepsContainer = document.createElement('div');
            // Use actual steps data with proper defaults - FIXED: 6 steps total
            let stepsCompleted = execution.steps_completed || 0;
            let totalSteps = 6; // CORRECTED: Pipeline has 6 steps, not 7
            
            // Fix: If execution is completed but steps_completed is 0, set to total steps
            if (status === 'completed' && stepsCompleted === 0) {
                stepsCompleted = totalSteps;
            }
            
            // Fix: If execution failed, show actual progress or at least 1 step
            if (status === 'failed' && stepsCompleted === 0) {
                stepsCompleted = 1; // At least started
            }
            
            const stepsText = document.createElement('div');
            stepsText.className = 'text-sm text-gray-900 dark:text-gray-100';
            stepsText.textContent = `${stepsCompleted}/${totalSteps}`;
            
            if (status === 'running' && totalSteps > 0) {
                const progressBar = document.createElement('div');
                progressBar.className = 'w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1';
                
                const progressFill = document.createElement('div');
                const progressPercent = (stepsCompleted / totalSteps) * 100;
                progressFill.className = 'bg-blue-600 h-1.5 rounded-full transition-all duration-300';
                progressFill.style.width = `${progressPercent}%`;
                
                progressBar.appendChild(progressFill);
                stepsContainer.appendChild(stepsText);
                stepsContainer.appendChild(progressBar);
            } else if (status === 'completed') {
                // Show completed progress bar for completed executions
                const progressBar = document.createElement('div');
                progressBar.className = 'w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1';
                
                const progressFill = document.createElement('div');
                progressFill.className = 'bg-green-600 h-1.5 rounded-full';
                progressFill.style.width = '100%';
                
                progressBar.appendChild(progressFill);
                stepsContainer.appendChild(stepsText);
                stepsContainer.appendChild(progressBar);
            } else if (status === 'failed') {
                // Show partial progress bar for failed executions
                const progressBar = document.createElement('div');
                progressBar.className = 'w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1';
                
                const progressFill = document.createElement('div');
                const progressPercent = (stepsCompleted / totalSteps) * 100;
                progressFill.className = 'bg-red-600 h-1.5 rounded-full';
                progressFill.style.width = `${Math.max(progressPercent, 10)}%`; // Minimum 10% to show something
                
                progressBar.appendChild(progressFill);
                stepsContainer.appendChild(stepsText);
                stepsContainer.appendChild(progressBar);
            } else {
                stepsContainer.appendChild(stepsText);
            }
            
            stepsCell.appendChild(stepsContainer);
            row.appendChild(stepsCell);

            // Actions cell
            const actionsCell = document.createElement('td');
            actionsCell.className = 'px-4 py-3';
            const detailsButton = document.createElement('button');
            detailsButton.className = 'text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 text-sm font-medium';
            detailsButton.textContent = 'View Details';
            detailsButton.onclick = () => window.viewExecutionDetails(executionId);
            actionsCell.appendChild(detailsButton);
            row.appendChild(actionsCell);

            executionHistoryTbody.appendChild(row);
        });
    }

    function updateLastGeneratedPlays(lastRun) {
        if (!lastGeneratedPlays || !lastPlaysContainer || !lastRun.plays) return;

        const timestamp = new Date(lastRun.timestamp).toLocaleString();
        lastPlaysTimestamp.textContent = `Generated: ${timestamp}`;

        // Clear container safely
        while (lastPlaysContainer.firstChild) {
            lastPlaysContainer.removeChild(lastPlaysContainer.firstChild);
        }

        // Display all 5 plays (not just 3) using safe DOM methods
        lastRun.plays.slice(0, 5).forEach((play, index) => {
            // Create main container
            const playContainer = document.createElement('div');
            playContainer.className = 'flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg mb-2';

            // Create left side container (play label and numbers)
            const leftContainer = document.createElement('div');
            leftContainer.className = 'flex items-center space-x-2';

            // Create play label
            const playLabel = document.createElement('span');
            playLabel.className = 'text-sm font-medium text-gray-600 dark:text-gray-400';
            playLabel.textContent = `Play ${index + 1}:`;
            leftContainer.appendChild(playLabel);

            // Create white balls safely
            play.slice(0, 5).forEach(num => {
                const sanitizedNum = parseInt(num, 10);
                const ballSpan = document.createElement('span');
                ballSpan.className = 'number-ball';

                if (isNaN(sanitizedNum) || sanitizedNum < 1 || sanitizedNum > 69) {
                    ballSpan.textContent = '?';
                } else {
                    ballSpan.textContent = sanitizedNum.toString();
                }
                leftContainer.appendChild(ballSpan);
            });

            // Create powerball safely
            const powerballSpan = document.createElement('span');
            powerballSpan.className = 'powerball-number';
            const sanitizedPowerball = parseInt(play[5], 10);
            powerballSpan.textContent = isNaN(sanitizedPowerball) ? '?' : sanitizedPowerball.toString();
            leftContainer.appendChild(powerballSpan);

            // Create right side container (score)
            const rightContainer = document.createElement('div');
            rightContainer.className = 'text-xs text-gray-500 dark:text-gray-400';

            const scoreText = document.createElement('span');
            if (lastRun.scores && lastRun.scores[index]) {
                const score = Math.round(parseFloat(lastRun.scores[index]) * 100);
                scoreText.textContent = `Score: ${score}%`;
            } else {
                scoreText.textContent = 'Score: N/A';
            }
            rightContainer.appendChild(scoreText);

            // Assemble the play container
            playContainer.appendChild(leftContainer);
            playContainer.appendChild(rightContainer);

            // Add to main container
            lastPlaysContainer.appendChild(playContainer);
        });
        lastGeneratedPlays.classList.remove('hidden');
    }

    async function triggerPipeline() {
        hideTriggerModal();

        try {
            // Set initial loading state
            triggerPipelineBtn.disabled = true;
            triggerPipelineBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Starting Pipeline...';
            triggerPipelineBtn.className = triggerPipelineBtn.className.replace('bg-green-600 hover:bg-green-700', 'bg-orange-500');

            const response = await fetch(`${API_BASE_URL}/pipeline/trigger`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });

            if (response.status === 401) {
                showPipelineNotification('Authentication required. Please login.', 'error');
                setTimeout(() => window.location.href = '/login', 2000);
                return;
            }

            if (response.status === 409) {
                showPipelineNotification('Pipeline is already running', 'warning');
                return;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            showPipelineNotification(`Pipeline started successfully! ID: ${data.execution_id}`, 'success');

            // Update button to show execution in progress
            triggerPipelineBtn.innerHTML = '<i class="fas fa-cog fa-spin mr-2"></i>Pipeline Running...';
            triggerPipelineBtn.className = triggerPipelineBtn.className.replace('bg-orange-500', 'bg-blue-600');
            
            // Start monitoring pipeline status with execution ID
            startPipelineMonitoring(data.execution_id);

        } catch (error) {
            console.error('Pipeline trigger error:', error);
            showPipelineNotification(`Error starting pipeline: ${error.message}`, 'error');
            resetPipelineButton();
        }
    }

    function startPipelineMonitoring(executionId) {
        let monitoringAttempts = 0;
        const maxAttempts = 120; // 10 minutos máximo
        const checkInterval = 5000; // Check every 5 seconds
        
        // Update status immediately and continue monitoring
        const monitoringInterval = setInterval(async () => {
            monitoringAttempts++;
            
            try {
                const status = await fetchPipelineStatus();
                
                if (status && status.pipeline_status) {
                    const currentStatus = status.pipeline_status.current_status;
                    const recentHistory = status.pipeline_status.recent_execution_history || [];
                    
                    // Find our specific execution
                    const ourExecution = recentHistory.find(ex => ex.execution_id === executionId);
                    
                    if (ourExecution) {
                        updatePipelineButtonForExecution(ourExecution);
                        
                        if (ourExecution.status === 'completed') {
                            clearInterval(monitoringInterval);
                            showPipelineNotification('Pipeline completed successfully!', 'success');
                            resetPipelineButton();
                            // Force refresh of execution history
                            setTimeout(() => fetchPipelineStatus(), 1000);
                            return;
                        } else if (ourExecution.status === 'failed') {
                            clearInterval(monitoringInterval);
                            showPipelineNotification(`Pipeline failed: ${ourExecution.error || 'Unknown error'}`, 'error');
                            resetPipelineButton();
                            return;
                        }
                    }
                    
                    // Check if pipeline is no longer running (generic check)
                    if (currentStatus !== 'running' && monitoringAttempts > 3) {
                        clearInterval(monitoringInterval);
                        showPipelineNotification('Pipeline completado', 'info');
                        resetPipelineButton();
                        return;
                    }
                }
                
                // Timeout check
                if (monitoringAttempts >= maxAttempts) {
                    clearInterval(monitoringInterval);
                    showPipelineNotification('Monitoring timeout reached. Pipeline may still be running.', 'warning');
                    resetPipelineButton();
                    return;
                }
                
            } catch (error) {
                console.warn('Error during pipeline monitoring:', error);
                // Continue monitoring despite errors
            }
        }, checkInterval);
    }

    function updatePipelineButtonForExecution(execution) {
        if (!triggerPipelineBtn) return;
        
        const stepsCompleted = execution.steps_completed || 0;
        const totalSteps = 6; // CORRECTED: Pipeline has 6 steps
        const currentStep = execution.current_step || 'processing';
        
        // Update button text with progress
        triggerPipelineBtn.innerHTML = `<i class="fas fa-cog fa-spin mr-2"></i>Step ${stepsCompleted}/${totalSteps} - ${currentStep}`;
        
        // Keep blue color while running
        if (!triggerPipelineBtn.className.includes('bg-blue-600')) {
            triggerPipelineBtn.className = triggerPipelineBtn.className.replace(/bg-\w+-\d+/g, 'bg-blue-600');
        }
    }

    function resetPipelineButton() {
        if (!triggerPipelineBtn) return;
        
        triggerPipelineBtn.disabled = false;
        triggerPipelineBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Run Pipeline Now';
        triggerPipelineBtn.className = triggerPipelineBtn.className.replace(/bg-\w+-\d+/g, 'bg-green-600 hover:bg-green-700');
    }

    function showTriggerModal() {
        if (pipelineTriggerModal) {
            pipelineTriggerModal.classList.remove('hidden');
        }
    }

    function hideTriggerModal() {
        if (pipelineTriggerModal) {
            pipelineTriggerModal.classList.add('hidden');
        }
    }

    async function viewPipelineLogs() {
        try {
            const response = await fetch(`${API_BASE_URL}/pipeline/logs`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.status === 401) {
                showPipelineNotification('Authentication required. Please login.', 'error');
                setTimeout(() => window.location.href = '/login', 2000);
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();

            // Create a simple modal to display logs safely
            const logsModal = document.createElement('div');
            logsModal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';

            const modalContent = document.createElement('div');
            modalContent.className = 'bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-96 overflow-hidden';

            const headerDiv = document.createElement('div');
            headerDiv.className = 'flex justify-between items-center mb-4';

            const title = document.createElement('h3');
            title.className = 'text-lg font-semibold text-gray-800 dark:text-white';
            title.textContent = 'Pipeline Logs';

            const closeButton = document.createElement('button');
            closeButton.className = 'text-gray-500 hover:text-gray-700';
            closeButton.onclick = () => logsModal.remove();

            const closeIcon = document.createElement('i');
            closeIcon.className = 'fas fa-times';
            closeButton.appendChild(closeIcon);

            headerDiv.appendChild(title);
            headerDiv.appendChild(closeButton);

            const logsContainer = document.createElement('div');
            logsContainer.className = 'bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-y-auto max-h-80';

            // Safely display logs without innerHTML - prevent XSS
            if (data.logs) {
                const lines = data.logs.split('\n');
                lines.forEach((line, index) => {
                    if (index > 0) {
                        logsContainer.appendChild(document.createElement('br'));
                    }
                    // Use safe text content to prevent XSS - no HTML parsing
                    const textNode = document.createTextNode(line);
                    logsContainer.appendChild(textNode);
                });
            } else {
                logsContainer.textContent = 'No logs available';
            }

            modalContent.appendChild(headerDiv);
            modalContent.appendChild(logsContainer);
            logsModal.appendChild(modalContent);
            document.body.appendChild(logsModal);

        } catch (error) {
            console.error('Logs fetch error:', error);
            showPipelineNotification('Failed to fetch logs', 'error');
        }
    }

    function refreshPipelineStatus() {
        if (refreshPipelineBtn) {
            const originalHTML = refreshPipelineBtn.innerHTML;
            refreshPipelineBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Refreshing...';
            refreshPipelineBtn.disabled = true;

            fetchPipelineStatus().finally(() => {
                refreshPipelineBtn.innerHTML = originalHTML;
                refreshPipelineBtn.disabled = false;
            });
        }
    }

    function handleAutoRefreshToggle() {
        if (!autoRefreshCheckbox) return;

        if (autoRefreshCheckbox.checked) {
            // Start auto-refresh every 60 seconds
            autoRefreshInterval = setInterval(fetchPipelineStatus, 60000);
            showPipelineNotification('Auto-refresh enabled', 'info');
        } else {
            // Stop auto-refresh
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
            showPipelineNotification('Auto-refresh disabled', 'info');
        }
    }

    function showPipelineNotification(message, type = 'info') {
        if (!pipelineNotification || !pipelineNotificationIcon || !pipelineNotificationText) return;

        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        pipelineNotificationIcon.className = icons[type] || icons.info;
        pipelineNotificationText.textContent = message;
        pipelineNotification.className = `fixed bottom-5 left-5 py-3 px-4 rounded-lg shadow-xl opacity-100 transition-opacity duration-300 z-50 ${type}`;

        setTimeout(() => {
            pipelineNotification.classList.remove('opacity-100');
            pipelineNotification.classList.add('opacity-0');
        }, 5000);
    }

    function showPipelineError(message) {
        if (pipelineStatusText) {
            pipelineStatusText.textContent = 'Error';
        }
        if (pipelineStatusDescription) {
            pipelineStatusDescription.textContent = message;
        }
        if (pipelineStatusIndicator) {
            pipelineStatusIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
        }
    }

    // Global function for execution details (called from HTML)
    window.viewExecutionDetails = async function(executionId) {
        try {
            showPipelineNotification('Loading execution details...', 'info');
            
            const response = await fetch(`${API_BASE_URL}/pipeline/execution/${executionId}`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.status === 401) {
                showPipelineNotification('Authentication required. Please login.', 'error');
                return;
            }
            
            let executionDetails;
            if (response.ok) {
                const responseData = await response.json();
                executionDetails = responseData.execution || responseData;
            } else {
                // Fallback: find execution in current status data
                const statusResponse = await fetch(`${API_BASE_URL}/pipeline/status`);
                if (statusResponse.ok) {
                    const statusData = await statusResponse.json();
                    executionDetails = statusData.pipeline_status?.recent_execution_history?.find(
                        ex => ex.execution_id === executionId
                    );
                }
            }
            
            if (!executionDetails) {
                showPipelineNotification('Execution details not found', 'warning');
                return;
            }

            // Get predictions for this execution
            let predictions = [];
            try {
                const predictionsResponse = await fetch(`${API_BASE_URL}/predict/smart?limit=100`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                });
                
                if (predictionsResponse.ok) {
                    const predictionsData = await predictionsResponse.json();
                    predictions = predictionsData.smart_predictions || predictionsData.predictions || [];
                    // Limit to top 10 for the modal
                    predictions = predictions.slice(0, 10);
                }
            } catch (predError) {
                console.warn('Could not load predictions for execution:', predError);
            }
            
            // Create detailed modal
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
            
            const modalContent = document.createElement('div');
            modalContent.className = 'bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden';
            
            // Header
            const header = document.createElement('div');
            header.className = 'flex justify-between items-center mb-4 border-b border-gray-200 dark:border-gray-700 pb-4';
            
            const title = document.createElement('h3');
            title.className = 'text-lg font-semibold text-gray-800 dark:text-white';
            title.textContent = `Execution ${executionId} - Generated Predictions`;
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'text-gray-500 hover:text-gray-700';
            closeBtn.innerHTML = '<i class="fas fa-times"></i>';
            closeBtn.onclick = () => modal.remove();
            
            header.appendChild(title);
            header.appendChild(closeBtn);
            
            // Content
            const content = document.createElement('div');
            content.className = 'overflow-y-auto max-h-[70vh]';
            
            // Execution summary section
            const summarySection = document.createElement('div');
            summarySection.className = 'mb-6 bg-gray-50 dark:bg-gray-900 rounded-lg p-4';
            
            const formatDateTime = (dateStr) => {
                if (!dateStr) return 'Not available';
                try {
                    return convertToETTimezone(dateStr);
                } catch (e) {
                    return dateStr;
                }
            };

            const getStatusBadge = (status) => {
                const statusColors = {
                    'completed': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
                    'running': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
                    'failed': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
                    'starting': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                };
                const colorClass = statusColors[status] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
                const statusText = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
                return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}">${statusText}</span>`;
            };

            summarySection.innerHTML = `
                <h4 class="text-md font-semibold text-gray-900 dark:text-white mb-3">
                    <i class="fas fa-info-circle mr-2 text-blue-600"></i>Execution Summary
                </h4>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Status:</span><br>
                        ${getStatusBadge(executionDetails.status)}
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Progress:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${executionDetails.steps_completed || (executionDetails.status === 'completed' ? 6 : 0)}/6 steps</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Start Time:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${formatDateTime(executionDetails.start_time)}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">End Time:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${formatDateTime(executionDetails.end_time)}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Trigger:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${executionDetails.trigger_type || executionDetails.trigger_source || 'Manual'}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Predictions:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${executionDetails.num_predictions || 100} generated</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Success:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">${executionDetails.subprocess_success ? 'Yes' : 'No'}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700 dark:text-gray-300">Method:</span><br>
                        <span class="text-gray-900 dark:text-gray-100">Smart AI Pipeline</span>
                    </div>
                </div>
                ${executionDetails.error ? `
                    <div class="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
                        <span class="font-medium text-red-700 dark:text-red-300">Error:</span><br>
                        <span class="text-red-600 dark:text-red-400 text-sm">${executionDetails.error}</span>
                    </div>
                ` : ''}
            `;

            // Predictions table section
            const predictionsSection = document.createElement('div');
            predictionsSection.className = 'bg-white dark:bg-gray-800';
            
            if (predictions.length > 0) {
                predictionsSection.innerHTML = `
                    <h4 class="text-md font-semibold text-gray-900 dark:text-white mb-3">
                        <i class="fas fa-dice mr-2 text-green-600"></i>Top 10 Generated Predictions
                    </h4>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-900">
                                <tr>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Rank</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Numbers</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Powerball</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">AI Score</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Method</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                ${predictions.map((pred, index) => `
                                    <tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
                                        <td class="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                                            ${pred.rank || index + 1}
                                        </td>
                                        <td class="px-4 py-3">
                                            <div class="flex space-x-1">
                                                ${(pred.numbers || []).map(num => 
                                                    `<span class="inline-flex items-center justify-center w-7 h-7 bg-blue-600 text-white rounded-full text-xs font-bold">${num}</span>`
                                                ).join('')}
                                            </div>
                                        </td>
                                        <td class="px-4 py-3">
                                            <span class="inline-flex items-center justify-center w-7 h-7 bg-red-600 text-white rounded-full text-xs font-bold">
                                                ${pred.powerball || pred.pb || 1}
                                            </span>
                                        </td>
                                        <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                                            ${((pred.total_score || pred.score_total || 0) * 100).toFixed(1)}%
                                        </td>
                                        <td class="px-4 py-3">
                                            <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                                                ${pred.method || 'Smart AI'}
                                            </span>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            } else {
                predictionsSection.innerHTML = `
                    <h4 class="text-md font-semibold text-gray-900 dark:text-white mb-3">
                        <i class="fas fa-dice mr-2 text-green-600"></i>Generated Predictions
                    </h4>
                    <div class="text-center py-8 bg-gray-50 dark:bg-gray-900 rounded-lg">
                        <i class="fas fa-exclamation-triangle text-3xl text-yellow-500 mb-3"></i>
                        <p class="text-gray-600 dark:text-gray-400">No predictions available for this execution</p>
                        <p class="text-sm text-gray-500 dark:text-gray-500 mt-1">Predictions may have been generated in a separate run</p>
                    </div>
                `;
            }
            
            content.appendChild(summarySection);
            content.appendChild(predictionsSection);
            
            modalContent.appendChild(header);
            modalContent.appendChild(content);
            modal.appendChild(modalContent);
            document.body.appendChild(modal);
            
        } catch (error) {
            console.error('Error loading execution details:', error);
            showPipelineNotification('Error loading execution details: ' + error.message, 'error');
        }
    };

    // Check authentication status
    async function checkAuthStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/verify`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (response.status === 401 || response.status === 403) {
                console.log('Authentication failed, redirecting to login...');
                window.location.href = '/login.html';
                return false;
            }

            if (response.ok) {
                const data = await response.json();
                if (data.valid && data.authenticated) {
                    console.log('Dashboard authentication verified for user:', data.user.username);
                    return true;
                }
            }

            console.log('Authentication check failed, redirecting to login...');
            window.location.href = '/login.html';
            return false;

        } catch (error) {
            console.error('Auth check failed:', error);
            window.location.href = '/login.html';
            return false;
        }
    }

    // --- Helper functions for scheduler ---
    function getTimeUntilNext(targetDate) {
        const now = new Date();
        const diff = targetDate - now;

        if (diff <= 0) {
            return 'Due now';
        }

        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        if (hours > 0) {
            return `in ${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            return `in ${minutes}m ${seconds}s`;
        } else {
            return `in ${seconds}s`;
        }
    }

    // Load pipeline status
    async function loadPipelineStatus() {
        try {
            showSpinner('pipeline-status');
            const response = await fetch(`${API_BASE_URL}/pipeline/status`);
            const data = await response.json();

            updateStatusDisplay(data);
            updateSchedulerDisplay(data.scheduler);
            updateExecutionHistory(data.recent_executions || []);

            // Load detailed scheduler jobs
            await loadDetailedSchedulerJobs();

        } catch (error) {
            console.error('Error loading pipeline status:', error);
            showError('Failed to load pipeline status');
        } finally {
            hideSpinner('pipeline-status');
        }
    }

    // Load detailed scheduler jobs information
    async function loadDetailedSchedulerJobs() {
        try {
            const response = await fetch(`${API_BASE_URL}/pipeline/scheduler/jobs`);
            const data = await response.json();

            if (data.jobs && data.jobs.length > 0) {
                displayDetailedSchedulerJobs(data.jobs);
            }
        } catch (error) {
            console.error('Error loading detailed scheduler jobs:', error);
        }
    }

    // Update scheduler information
    function updateSchedulerDisplay(scheduler) {
        const statusEl = document.getElementById('scheduler-status');
        const jobsEl = document.getElementById('scheduler-jobs');

        if (scheduler && scheduler.active) {
            statusEl.innerHTML = '<i class="fas fa-check-circle mr-1"></i>Active';
            statusEl.className = 'text-lg font-bold text-green-600';

            const jobText = scheduler.job_count === 1 ? '1 job scheduled' : `${scheduler.job_count} jobs scheduled`;
            jobsEl.textContent = jobText;

            if (scheduler.next_run) {
                const nextRun = new Date(scheduler.next_run);
                const timeUntil = getTimeUntilNext(nextRun);
                jobsEl.textContent += ` • Next: ${timeUntil}`;
            }
        } else {
            statusEl.innerHTML = '<i class="fas fa-times-circle mr-1"></i>Inactive';
            statusEl.className = 'text-lg font-bold text-red-600';
            jobsEl.textContent = 'No jobs scheduled';
        }
    }

    // Display detailed scheduler jobs information
    function displayDetailedSchedulerJobs(jobs) {
        console.log('Detailed scheduler jobs:', jobs);

        // Find the scheduler section and add detailed info
        const schedulerSection = document.querySelector('.bg-white.dark\\:bg-gray-800.rounded-xl.shadow-lg.border.border-gray-200.dark\\:border-gray-700');

        if (schedulerSection) {
            // Remove existing detailed jobs section
            const existingDetails = schedulerSection.querySelector('#scheduler-jobs-details');
            if (existingDetails) {
                existingDetails.remove();
            }

            // Create new detailed jobs section
            const detailsDiv = document.createElement('div');
            detailsDiv.id = 'scheduler-jobs-details';
            detailsDiv.className = 'mt-6 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700';

            const title = document.createElement('h4');
            title.className = 'text-md font-semibold text-gray-900 dark:text-white mb-4 flex items-center';
            title.innerHTML = '<i class="fas fa-list mr-2 text-blue-600"></i>Scheduled Jobs Details';
            detailsDiv.appendChild(title);

            // Create jobs list
            const jobsList = document.createElement('div');
            jobsList.className = 'space-y-3';

            jobs.forEach((job, index) => {
                const jobDiv = document.createElement('div');
                jobDiv.className = 'bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-600';

                const nextRunDate = job.next_run_time ? new Date(job.next_run_time) : null;
                const timeUntil = nextRunDate ? getTimeUntilNext(nextRunDate) : 'Not scheduled';

                // Determine job description based on ID
                let jobDescription = '';
                let jobIcon = 'fas fa-cog';
                let jobColor = 'text-blue-600';

                if (job.id === 'post_drawing_pipeline') {
                    jobDescription = 'Full Pipeline Execution (30 min after Powerball drawing)';
                    jobIcon = 'fas fa-rocket';
                    jobColor = 'text-green-600';
                } else if (job.id === 'maintenance_data_update') {
                    jobDescription = 'Maintenance Data Update (non-drawing days)';
                    jobIcon = 'fas fa-database';
                    jobColor = 'text-orange-600';
                }

                jobDiv.innerHTML = `
                    <div class="flex items-start justify-between">
                        <div class="flex items-start space-x-3">
                            <i class="${jobIcon} ${jobColor} mt-1"></i>
                            <div>
                                <h5 class="font-semibold text-gray-900 dark:text-white">${job.name}</h5>
                                <p class="text-sm text-gray-600 dark:text-gray-400">${jobDescription}</p>
                                <div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                                    <span class="inline-block mr-4"><strong>ID:</strong> ${job.id}</span>
                                    <span class="inline-block mr-4"><strong>Function:</strong> ${job.func_name}</span>
                                </div>
                                ${job.trigger.type === 'cron' ? `
                                <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    <span class="inline-block mr-4"><strong>Schedule:</strong> ${job.trigger.day_of_week} at ${job.trigger.hour}:${job.trigger.minute}</span>
                                    <span class="inline-block"><strong>Timezone:</strong> ${job.trigger.timezone}</span>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-medium text-gray-900 dark:text-white">
                                ${job.next_run_time_display || 'Not scheduled'}
                            </div>
                            <div class="text-xs text-gray-500 dark:text-gray-400">
                                ${timeUntil}
                            </div>
                        </div>
                    </div>
                `;

                jobsList.appendChild(jobDiv);
            });

            detailsDiv.appendChild(jobsList);

            // Add to scheduler section
            const schedulerContent = schedulerSection.querySelector('.p-6:last-child');
            if (schedulerContent) {
                schedulerContent.appendChild(detailsDiv);
            }
        }
    }

    // Initialize pipeline dashboard
    function initializePipelineDashboard() {
        // Check authentication first
        checkAuthStatus().then(isAuthenticated => {
            if (isAuthenticated) {
                // Test API connectivity
                testApiConnectivity().then(isConnected => {
                    if (isConnected) {
                        console.log('✅ API connectivity confirmed');
                        // Initial status fetch
                        fetchPipelineStatus();

                        // Start auto-refresh if enabled
                        if (autoRefreshCheckbox && autoRefreshCheckbox.checked) {
                            handleAutoRefreshToggle();
                        }
                    } else {
                        console.warn('⚠️ API connectivity issues detected');
                        showPipelineError('Unable to connect to API server. Check if server is running.');
                    }
                });
            } else {
                showPipelineError('Authentication required. Redirecting to login...');
                setTimeout(() => window.location.href = '/login.html', 2000);
            }
        });
    }

    // Test API connectivity
    async function testApiConnectivity() {
        try {
            const response = await fetch(`${API_BASE_URL}/pipeline/status`, {
                method: 'GET',
                timeout: 5000
            });
            return response.ok;
        } catch (error) {
            console.error('API connectivity test failed:', error);
            return false;
        }
    }

    // --- Syndicate Predictions Functions ---
    async function generateSyndicatePredictions() {
        const playsInput = document.getElementById('syndicate-plays');
        const loadingDiv = document.getElementById('syndicate-loading');
        const resultsDiv = document.getElementById('syndicate-results');
        const btn = document.getElementById('generate-syndicate-btn');

        if (!playsInput || !loadingDiv || !resultsDiv || !btn) {
            console.error('Required syndicate elements not found');
            return;
        }

        const numPlays = parseInt(playsInput.value);

        if (numPlays < 10 || numPlays > 500) {
            showToast('Number of plays must be between 10 and 500', 'error');
            return;
        }

        try {
            // Show loading state
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Generating...';
            loadingDiv.classList.remove('hidden');
            resultsDiv.classList.add('hidden');

            // Make API request to Smart AI endpoint
            const response = await fetch(`${API_BASE_URL}/predict/smart?num_plays=${numPlays}`);

            if (!response.ok) {
                let errorMessage = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    if (errorData?.detail) {
                        errorMessage = errorData.detail;
                    } else if (errorData?.message) {
                        errorMessage = errorData.message;
                    }
                } catch (parseError) {
                    console.warn('Could not parse error response:', parseError);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            // Process and display results
            if (data.smart_predictions && data.smart_predictions.length > 0) {
                syndicateData = data; // Store data for export
                displaySmartAIResults(data);
                showToast(`AI generated ${data.total_predictions} smart predictions successfully!`, 'success');
            } else {
                throw new Error('No predictions generated');
            }

        } catch (error) {
            console.error('Syndicate generation error:', error);
            loadingDiv.classList.add('hidden');

            let errorMessage = 'Failed to generate syndicate predictions';
            if (error.message && error.message !== '[object Object]') {
                errorMessage += ': ' + error.message;
            } else if (error.detail) {
                errorMessage += ': ' + error.detail;
            } else {
                errorMessage += '. Please check server logs.';
            }

            showToast(errorMessage, 'error');
        } finally {
            // Reset button state
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-brain mr-2"></i>Generate Smart AI Predictions';
            loadingDiv.classList.add('hidden');
        }
    }

    function displaySmartAIResults(data) {
        const resultsDiv = document.getElementById('syndicate-results');
        if (!resultsDiv) return;

        const predictions = data.smart_predictions;
        const analysis = data.ai_analysis;

        // Fix XSS: Use safe DOM manipulation instead of innerHTML
        resultsDiv.textContent = ''; // Clear existing content safely

        // Create main container
        const mainContainer = document.createElement('div');
        mainContainer.className = 'space-y-6';

        // Create AI Analysis Summary section
        const analysisDiv = document.createElement('div');
        analysisDiv.className = 'bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 p-6 rounded-lg border border-blue-200 dark:border-blue-800';

        // Header with brain icon
        const headerDiv = document.createElement('div');
        headerDiv.className = 'flex items-center space-x-3 mb-4';

        const brainIcon = document.createElement('i');
        brainIcon.className = 'fas fa-brain text-2xl text-blue-600 dark:text-blue-400';

        const headerTitle = document.createElement('h3');
        headerTitle.className = 'text-lg font-bold text-blue-800 dark:text-blue-200';
        headerTitle.textContent = 'Smart AI Analysis';

        headerDiv.appendChild(brainIcon);
        headerDiv.appendChild(headerTitle);

        // Stats grid
        const statsGrid = document.createElement('div');
        statsGrid.className = 'grid grid-cols-1 md:grid-cols-3 gap-4 text-sm';

        // Candidates Evaluated stat
        const candidatesDiv = document.createElement('div');
        candidatesDiv.className = 'bg-white dark:bg-gray-800 p-3 rounded-lg';

        const candidatesLabel = document.createElement('div');
        candidatesLabel.className = 'font-semibold text-gray-700 dark:text-gray-300';
        candidatesLabel.textContent = 'Candidates Evaluated';

        const candidatesValue = document.createElement('div');
        candidatesValue.className = 'text-2xl font-bold text-blue-600 dark:text-blue-400';
        candidatesValue.textContent = analysis.candidates_evaluated.toLocaleString();

        candidatesDiv.appendChild(candidatesLabel);
        candidatesDiv.appendChild(candidatesValue);

        // AI Methods stat
        const methodsDiv = document.createElement('div');
        methodsDiv.className = 'bg-white dark:bg-gray-800 p-3 rounded-lg';

        const methodsLabel = document.createElement('div');
        methodsLabel.className = 'font-semibold text-gray-700 dark:text-gray-300';
        methodsLabel.textContent = 'AI Methods Used';

        const methodsValue = document.createElement('div');
        methodsValue.className = 'text-sm text-blue-600 dark:text-blue-400';
        methodsValue.textContent = analysis.methods_used.join(', ').toUpperCase();

        methodsDiv.appendChild(methodsLabel);
        methodsDiv.appendChild(methodsValue);

        // Average Score stat
        const scoreDiv = document.createElement('div');
        scoreDiv.className = 'bg-white dark:bg-gray-800 p-3 rounded-lg';

        const scoreLabel = document.createElement('div');
        scoreLabel.className = 'font-semibold text-gray-700 dark:text-gray-300';
        scoreLabel.textContent = 'Average AI Score';

        const scoreValue = document.createElement('div');
        scoreValue.className = 'text-2xl font-bold text-green-600 dark:text-green-400';
        scoreValue.textContent = (analysis.score_range.average * 100).toFixed(1) + '%';

        scoreDiv.appendChild(scoreLabel);
        scoreDiv.appendChild(scoreValue);

        statsGrid.appendChild(candidatesDiv);
        statsGrid.appendChild(methodsDiv);
        statsGrid.appendChild(scoreDiv);

        // Recommendation box
        const recBox = document.createElement('div');
        recBox.className = 'mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800';

        const recText = document.createElement('p');
        recText.className = 'text-sm text-green-800 dark:text-green-200';

        const lightbulbIcon = document.createElement('i');
        lightbulbIcon.className = 'fas fa-lightbulb mr-2';

        const strongText = document.createElement('strong');
        strongText.textContent = 'AI Recommendation: ';

        recText.appendChild(lightbulbIcon);
        recText.appendChild(strongText);
        recText.appendChild(document.createTextNode(data.recommendation));

        recBox.appendChild(recText);

        analysisDiv.appendChild(headerDiv);
        analysisDiv.appendChild(statsGrid);
        analysisDiv.appendChild(recBox);

        // Create predictions table section
        const tableSection = document.createElement('div');
        tableSection.className = 'bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700';

        // Table header
        const tableHeader = document.createElement('div');
        tableHeader.className = 'px-6 py-4 border-b border-gray-200 dark:border-gray-700';

        const tableTitle = document.createElement('h4');
        tableTitle.className = 'text-lg font-semibold text-gray-900 dark:text-white';
        tableTitle.textContent = 'Smart AI Predictions (Ranked by AI Score)';

        const tableSubtitle = document.createElement('p');
        tableSubtitle.className = 'text-sm text-gray-600 dark:text-gray-400 mt-1';
        tableSubtitle.textContent = `Top ${predictions.length} predictions automatically selected and ranked by AI`;

        tableHeader.appendChild(tableTitle);
        tableHeader.appendChild(tableSubtitle);

        // Create table
        const tableContainer = document.createElement('div');
        tableContainer.className = 'overflow-x-auto';

        const table = document.createElement('table');
        table.className = 'min-w-full divide-y divide-gray-200 dark:divide-gray-700';

        // Table head
        const thead = document.createElement('thead');
        thead.className = 'bg-gray-50 dark:bg-gray-900';

        const headerRow = document.createElement('tr');
        const headers = ['Rank', 'Numbers', 'PB', 'AI Score', 'Tier', 'Method'];

        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.className = 'px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider';
            th.textContent = headerText;
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);

        // Table body
        const tbody = document.createElement('tbody');
        tbody.className = 'bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700';

        predictions.forEach((pred, index) => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700';

            // Rank cell
            const rankCell = document.createElement('td');
            rankCell.className = 'px-6 py-4 whitespace-nowrap';

            const rankContainer = document.createElement('div');
            rankContainer.className = 'flex items-center';

            const rankSpan = document.createElement('span');
            rankSpan.className = `inline-flex items-center justify-center w-8 h-8 rounded-full ${index < 10 ? 'bg-yellow-100 text-yellow-800 border-2 border-yellow-300' : 'bg-gray-100 text-gray-800'} text-sm font-bold`;
            rankSpan.textContent = pred.rank;

            rankContainer.appendChild(rankSpan);
            rankCell.appendChild(rankContainer);

            // Numbers cell
            const numbersCell = document.createElement('td');
            numbersCell.className = 'px-6 py-4 whitespace-nowrap';

            const numbersContainer = document.createElement('div');
            numbersContainer.className = 'flex space-x-1';

            pred.numbers.forEach(num => {
                const numSpan = document.createElement('span');
                numSpan.className = 'powerball-number small bg-blue-600 text-white';
                numSpan.textContent = num;
                numbersContainer.appendChild(numSpan);
            });

            numbersCell.appendChild(numbersContainer);

            // Powerball cell
            const pbCell = document.createElement('td');
            pbCell.className = 'px-6 py-4 whitespace-nowrap';

            const pbSpan = document.createElement('span');
            pbSpan.className = 'powerball-number small bg-red-600 text-white';
            pbSpan.textContent = pred.powerball;

            pbCell.appendChild(pbSpan);

            // Score cell
            const scoreCell = document.createElement('td');
            scoreCell.className = 'px-6 py-4 whitespace-nowrap';

            const scoreMain = document.createElement('div');
            scoreMain.className = 'text-sm font-medium text-gray-900 dark:text-white';
            scoreMain.textContent = (pred.smart_ai_score * 100).toFixed(1) + '%';

            const scoreBase = document.createElement('div');
            scoreBase.className = 'text-xs text-gray-500 dark:text-gray-400';
            scoreBase.textContent = 'Base: ' + (pred.base_score * 100).toFixed(1) + '%';

            scoreCell.appendChild(scoreMain);
            scoreCell.appendChild(scoreBase);

            // Tier cell
            const tierCell = document.createElement('td');
            tierCell.className = 'px-6 py-4 whitespace-nowrap';

            const tierSpan = document.createElement('span');
            tierSpan.className = `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTierColor(pred.tier)}`;
            tierSpan.textContent = pred.tier;

            tierCell.appendChild(tierSpan);

            // Method cell
            const methodCell = document.createElement('td');
            methodCell.className = 'px-6 py-4 whitespace-nowrap';
            methodCell.innerHTML = getMethodBadge(pred.ai_method); // This is safe as getMethodBadge returns predefined HTML

            row.appendChild(rankCell);
            row.appendChild(numbersCell);
            row.appendChild(pbCell);
            row.appendChild(scoreCell);
            row.appendChild(tierCell);
            row.appendChild(methodCell);

            tbody.appendChild(row);
        });

        table.appendChild(thead);
        table.appendChild(tbody);
        tableContainer.appendChild(table);

        tableSection.appendChild(tableHeader);
        tableSection.appendChild(tableContainer);

        mainContainer.appendChild(analysisDiv);
        mainContainer.appendChild(tableSection);

        resultsDiv.appendChild(mainContainer);
        resultsDiv.classList.remove('hidden');
    }

    function getTierColor(tier) {
        const colors = {
            'Premium': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
            'High': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
            'Medium': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
            'Standard': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
        };
        return colors[tier] || colors['Standard'];
    }

    function getMethodBadge(method) {
        const badges = {
            'ensemble': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Ensemble</span>',
            'deterministic': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Deterministic</span>',
            'adaptive': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">Adaptive</span>'
        };
        return badges[method] || '<span class="text-xs text-gray-500">Unknown</span>';
    }

    function updateSyndicateResults(data) {
        if (!data || !data.syndicate_predictions) {
            console.error('Invalid syndicate data received');
            return;
        }

        // Update coverage analysis
        const coverage = data.coverage_analysis || {};
        updateElementText('premium-tier-count', coverage.premium_tier || 0);
        updateElementText('high-tier-count', coverage.high_tier || 0);
        updateElementText('medium-tier-count', coverage.medium_tier || 0);
        updateElementText('standard-tier-count', coverage.standard_tier || 0);

        // Update total plays
        updateElementText('syndicate-total-plays', `${data.total_plays} plays`);

        // Update plays table
        const tbody = document.getElementById('syndicate-plays-tbody');
        if (!tbody) return;

        // Fix XSS: Clear tbody safely and use DOM methods
        tbody.textContent = ''; // Clear existing content safely

        data.syndicate_predictions.forEach((prediction, index) => {
            const numbers = prediction.numbers || [];
            const powerball = prediction.powerball || 0;
            const score = prediction.score || 0;
            const tier = prediction.tier || 'Standard';
            const method = prediction.method || data.method;
            const rank = prediction.rank || (index + 1);

            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700';

            // Rank cell
            const rankCell = document.createElement('td');
            rankCell.className = 'px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100';
            rankCell.textContent = rank;

            // Numbers cell
            const numbersCell = document.createElement('td');
            numbersCell.className = 'px-4 py-3';

            const numbersContainer = document.createElement('div');
            numbersContainer.className = 'flex items-center';

            // Create white balls safely
            numbers.forEach(num => {
                const ball = document.createElement('span');
                ball.className = 'inline-flex items-center justify-center w-6 h-6 bg-gray-200 dark:bg-gray-600 rounded-full text-xs font-semibold text-gray-800 dark:text-white mr-1';
                ball.textContent = num;
                numbersContainer.appendChild(ball);
            });

            // Add separator
            const separator = document.createElement('span');
            separator.className = 'mx-2 text-red-500';
            separator.textContent = '•';
            numbersContainer.appendChild(separator);

            // Create powerball safely
            const powerBall = document.createElement('span');
            powerBall.className = 'inline-flex items-center justify-center w-6 h-6 bg-red-500 rounded-full text-xs font-semibold text-white';
            powerBall.textContent = powerball;
            numbersContainer.appendChild(powerBall);

            numbersCell.appendChild(numbersContainer);

            // Score cell
            const scoreCell = document.createElement('td');
            scoreCell.className = 'px-4 py-3 text-sm text-gray-900 dark:text-gray-100';
            scoreCell.textContent = (score * 100).toFixed(2) + '%';

            // Tier cell
            const tierCell = document.createElement('td');
            tierCell.className = 'px-4 py-3';

            const tierSpan = document.createElement('span');
            const tierColors = {
                'Premium': 'text-purple-600 bg-purple-100 dark:bg-purple-900 dark:text-purple-300',
                'High': 'text-blue-600 bg-blue-100 dark:bg-blue-900 dark:text-blue-300',
                'Medium': 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-300',
                'Standard': 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-100 dark:text-gray-300'
            };

            tierSpan.className = `px-2 py-1 text-xs font-medium rounded-full ${tierColors[tier] || tierColors['Standard']}`;
            tierSpan.textContent = tier;
            tierCell.appendChild(tierSpan);

            // Method cell
            const methodCell = document.createElement('td');
            methodCell.className = 'px-4 py-3 text-sm text-gray-500 dark:text-gray-400';
            methodCell.textContent = method;

            row.appendChild(rankCell);
            row.appendChild(numbersCell);
            row.appendChild(scoreCell);
            row.appendChild(tierCell);
            row.appendChild(methodCell);

            tbody.appendChild(row);
        });
    }

    function exportSyndicateData() {
        if (!syndicateData || !syndicateData.syndicate_predictions) {
            showToast('No syndicate data to export', 'warning');
            return;
        }

        try {
            // Create CSV content
            const headers = ['Rank', 'Number1', 'Number2', 'Number3', 'Number4', 'Number5', 'Powerball', 'Score', 'Tier', 'Method'];
            const csvRows = [headers.join(',')];

            syndicateData.syndicate_predictions.forEach((prediction, index) => {
                const numbers = prediction.numbers || [];
                const powerball = prediction.powerball || 0;
                const score = prediction.score || 0;
                const tier = prediction.tier || 'Standard';
                const method = prediction.method || syndicateData.method;
                const rank = prediction.rank || (index + 1);

                const row = [
                    rank,
                    ...numbers,
                    powerball,
                    (score * 100).toFixed(2),
                    tier,
                    method
                ];
                csvRows.push(row.join(','));
            });

            // Create and download file
            const csvContent = csvRows.join('\n');
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');

            if (link.download !== undefined) {
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', `shiol_syndicate_${syndicateData.total_plays}_plays_${new Date().toISOString().slice(0, 10)}.csv`);
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                showToast('Syndicate data exported successfully!', 'success');
            }
        } catch (error) {
            console.error('Export error:', error);
            showToast('Failed to export syndicate data', 'error');
        }
    }

    function updateElementText(elementId, text) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = text;
        }
    }

    /**
     * Sanitize text content to prevent XSS
     * @param {string} text - Text to sanitize
     * @returns {string} - Sanitized text
     */
    function sanitizeText(text) {
        if (typeof text !== 'string') {
            return String(text || '');
        }

        // Create a temporary element to use browser's built-in HTML escaping
        const tempElement = document.createElement('div');
        tempElement.textContent = text;
        return tempElement.innerHTML;
    }

    /**
     * Sanitize DOM element to prevent XSS attacks
     * @param {HTMLElement} element - Element to sanitize
     */
    function sanitizeElement(element) {
        // Remove potentially dangerous attributes
        const dangerousAttrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur', 'onchange', 'onsubmit'];
        dangerousAttrs.forEach(attr => {
            if (element.hasAttribute(attr)) {
                element.removeAttribute(attr);
            }
        });

        // Recursively sanitize child elements
        for (let child of element.children) {
            this.sanitizeElement(child);
        }

        // Sanitize text content (remove script tags and dangerous content)
        if (element.textContent) {
            element.textContent = element.textContent.replace(/<script[^>]*>.*?<\/script>/gi, '');
        }
    }

    /**
     * Show notification message
     * @param {string} message - Message to display
     * @param {string} type - Type of notification (success, error, warning, info)
     */
    function showNotification(message, type = 'info') {
        const toast = document.getElementById('toast-notification');
        if (!toast) return;

        const typeClasses = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };

        toast.className = `fixed bottom-5 right-5 text-white py-2 px-4 rounded-lg shadow-xl opacity-100 transition-opacity duration-300 z-50 ${typeClasses[type] || typeClasses.info}`;
        // Create content safely without innerHTML
        toast.textContent = ''; // Clear existing content

        const icon = document.createElement('i');
        icon.className = 'fas fa-info mr-2';

        const messageSpan = document.createElement('span');
        messageSpan.textContent = message; // Safe text content, prevents XSS

        toast.appendChild(icon);
        toast.appendChild(messageSpan);

        setTimeout(() => {
            toast.classList.remove('opacity-100');
            toast.classList.add('opacity-0');
        }, 3000);
    }


    // Initialize UI state
    initializePipelineDashboard();
    
    // Enable auto-refresh by default
    if (autoRefreshCheckbox) {
        autoRefreshCheckbox.checked = true;
        handleAutoRefreshToggle();
    }

});