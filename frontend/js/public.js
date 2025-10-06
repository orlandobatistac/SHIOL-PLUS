// Utility function to close the modal
function closeDrawMatchesModal() {
    const modal = document.getElementById('drawMatchesModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Utility function to display matches in the modal
function updateDrawMatchesModal(data) {
    const modalContent = document.getElementById('modalContent');
    if (!modalContent) {
        console.error('Modal content element not found');
        return;
    }

    const drawDate = data.draw_date || data.requested_date || 'Unknown';
    const actualDrawDate = data.draw_info?.actual_draw_date || drawDate;
    
    // Handle both API response formats
    let winningNumbers = [];
    let winningPowerball = null;
    
    if (data.winning_numbers?.main_numbers) {
        // Format from prediction endpoints
        winningNumbers = data.winning_numbers.main_numbers;
        winningPowerball = data.winning_numbers.powerball;
    } else if (data.draw_numbers) {
        // Format from public endpoints
        winningNumbers = [data.draw_numbers.n1, data.draw_numbers.n2, data.draw_numbers.n3, data.draw_numbers.n4, data.draw_numbers.n5];
        winningPowerball = data.draw_numbers.pb;
    }

    if (data.predictions && data.predictions.length > 0) {
        let contentHtml = `
            <div class="p-6">
                <h3 class="text-lg font-semibold text-blue-700 mb-4 border-b pb-2">
                    Draw Matches & Predictions
                </h3>
                <div class="mb-4 p-3 bg-blue-50 rounded-lg">
                    <div class="text-sm text-gray-400 mb-2">Draw Date: <strong>${actualDrawDate}</strong></div>
                    ${winningNumbers.length > 0 ? `
                        <div class="flex items-center space-x-2">
                            <span class="text-sm font-medium">Winning Numbers:</span>
                            ${winningNumbers.map(num => 
                                `<span class="inline-flex items-center justify-center w-7 h-7 bg-blue-600 text-white rounded-full text-xs font-bold">${num}</span>`
                            ).join('')}
                            ${winningPowerball ? `
                                <span class="text-sm mx-2">PB:</span>
                                <span class="inline-flex items-center justify-center w-7 h-7 bg-red-600 text-white rounded-full text-xs font-bold">${winningPowerball}</span>
                            ` : ''}
                        </div>
                    ` : '<div class="text-sm text-gray-400">Winning numbers not available</div>'}
                </div>
                <div class="space-y-4">
        `;

        data.predictions.forEach((prediction, index) => {
            const numbers = prediction.numbers || [prediction.n1, prediction.n2, prediction.n3, prediction.n4, prediction.n5].filter(n => n);
            const powerball = prediction.powerball || prediction.pb;
            const matches = prediction.matches_main || 0;
            const pbMatch = prediction.matches_powerball || false;
            // Handle different score formats
            let score = prediction.score_total || prediction.confidence_score || 0;
            if (score > 100) {
                // Score is already a points value (0-110), convert to percentage
                score = ((score / 110) * 100).toFixed(1);
            } else {
                // Score is already a percentage or decimal
                score = (score * 100).toFixed(1);
            }

            contentHtml += `
                <div class="bg-gray-50 p-4 rounded-lg shadow-sm border border-gray-200">
                    <div class="flex justify-between items-center mb-2">
                        <span class="font-medium text-gray-800">Prediction #${index + 1}</span>
                        <span class="text-sm text-gray-400">
                            ${matches} matches${pbMatch ? ' + PB' : ''} | Score: ${score}%
                        </span>
                    </div>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-1">
                            ${numbers.map(num => 
                                `<span class="inline-flex items-center justify-center w-7 h-7 bg-blue-600 text-white rounded-full text-xs font-bold">${num}</span>`
                            ).join('')}
                            <span class="mx-2 text-gray-300">•</span>
                            <span class="inline-flex items-center justify-center w-7 h-7 bg-red-600 text-white rounded-full text-xs font-bold">${powerball}</span>
                        </div>
                        <div class="text-sm text-gray-400">
                            ${prediction.method || 'Standard'}
                        </div>
                    </div>
                </div>
            `;
        });

        contentHtml += `
                </div>
                <div class="mt-6 flex justify-center">
                    <button onclick="closeDrawMatchesModal()" class="px-6 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition duration-200">
                        Close
                    </button>
                </div>
            </div>
        `;
        modalContent.innerHTML = contentHtml;
    } else {
        modalContent.innerHTML = `
            <div class="p-6 text-center">
                <i class="fas fa-info-circle text-3xl text-blue-500 mb-4"></i>
                <h3 class="text-lg font-semibold text-gray-700 mb-2">No Predictions Available</h3>
                <p class="text-gray-400 mb-2">No prediction data found for draw date: <strong>${actualDrawDate}</strong></p>
                <p class="text-sm text-gray-400 mb-4">${data.message || 'No matches found with the specified criteria'}</p>
                <button onclick="closeDrawMatchesModal()" class="mt-4 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
                    Close
                </button>
            </div>
        `;
    }
}

// Function to handle showing the detailed prediction modal
function showDetailedPredictionModal(drawDateInput) {
    console.log(`Loading detailed predictions for draw: ${drawDateInput}`);

    const modal = document.getElementById('drawMatchesModal');
    const modalContent = document.getElementById('modalContent');

    if (!modal || !modalContent) {
        console.error('Modal elements not found');
        return;
    }

    modal.classList.remove('hidden');
    modalContent.innerHTML = `
        <div class="flex items-center justify-center p-8">
            <i class="fas fa-spinner fa-spin text-2xl text-blue-500 mr-3"></i>
            <span class="text-lg">Loading predictions...</span>
        </div>
    `;

    // Fetch predictions for the specific draw
    const apiUrl = `/api/v1/predictions/public/by-draw/${encodeURIComponent(drawDateInput)}?min_matches=1`;
    console.log('Fetching detailed predictions from:', apiUrl);

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => { throw new Error(`HTTP ${response.status}: ${text}`) });
            }
            return response.json();
        })
        .then(data => {
            console.log('Detailed prediction data received:', data);
            updateDrawMatchesModal(data); // Reuse the existing modal update function
        })
        .catch(error => {
            console.error('Error loading detailed predictions:', error);
            const errorMessage = error.message || 'Unknown error occurred';
            // Show error message to user in the modal
            modalContent.innerHTML = `
                <div class="p-6 text-center">
                    <i class="fas fa-exclamation-triangle text-3xl text-red-500 mb-4"></i>
                    <h3 class="text-lg font-semibold text-red-600 mb-2">Error Loading Data</h3>
                    <p class="text-gray-400 mb-2">Unable to load prediction details for this draw.</p>
                    <p class="text-sm text-gray-400 mb-4">Draw date: ${drawDateInput}</p>
                    <p class="text-xs text-gray-300 mb-4">Error: ${errorMessage}</p>
                    <button onclick="closeDrawMatchesModal()" class="mt-4 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
                        Close
                    </button>
                </div>
            `;
        });
}


// Function to handle showing the draw matches modal
async function showDrawMatchesModal(drawDateInput) {
    try {
        // Keep the original date format if it's already YYYY-MM-DD
        let drawDate = drawDateInput;

        console.log(`Modal requested for: ${drawDateInput}`);

        // Only parse if it's not already in YYYY-MM-DD format
        if (typeof drawDate === 'string' && !drawDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
            try {
                // Parse the date - try different formats
                let parsedDate = new Date(drawDate);
                
                // If that fails, try adding T12:00:00Z
                if (isNaN(parsedDate.getTime())) {
                    parsedDate = new Date(drawDate + 'T12:00:00Z');
                }
                
                // If still fails, try manual parsing for format like "Mon, Sep 1, 2025"
                if (isNaN(parsedDate.getTime()) && drawDate.includes(',')) {
                    const parts = drawDate.replace(/[^a-zA-Z0-9,\s]/g, '').split(/\s+/);
                    if (parts.length >= 4) {
                        const monthMap = {'Jan':0, 'Feb':1, 'Mar':2, 'Apr':3, 'May':4, 'Jun':5, 'Jul':6, 'Aug':7, 'Sep':8, 'Oct':9, 'Nov':10, 'Dec':11};
                        const month = monthMap[parts[1]];
                        const day = parseInt(parts[2].replace(',', ''));
                        const year = parseInt(parts[3]);
                        if (month !== undefined && !isNaN(day) && !isNaN(year)) {
                            parsedDate = new Date(year, month, day);
                        }
                    }
                }
                
                if (!isNaN(parsedDate.getTime())) {
                    drawDate = parsedDate.getFullYear() + '-' + 
                              String(parsedDate.getMonth() + 1).padStart(2, '0') + '-' + 
                              String(parsedDate.getDate()).padStart(2, '0');
                }
            } catch (e) {
                console.warn('Could not parse date format, using as-is:', drawDate);
            }
        }

        console.log(`Final draw date for API: ${drawDate} (from input: ${drawDateInput})`);

        // Show modal immediately with loading state
        const modal = document.getElementById('drawMatchesModal');
        const modalContent = document.getElementById('modalContent');

        if (!modal || !modalContent) {
            console.error('Modal elements not found');
            return;
        }

        modal.classList.remove('hidden');
        modalContent.innerHTML = `
            <div class="flex items-center justify-center p-8">
                <i class="fas fa-spinner fa-spin text-2xl text-blue-500 mr-3"></i>
                <span class="text-lg">Loading predictions...</span>
            </div>
        `;

        // Try multiple API endpoints for better compatibility
        const apiEndpoints = [
            `/api/v1/public/predictions/by-draw/${encodeURIComponent(drawDate)}?min_matches=0&limit=100`,
            `/api/v1/predictions/by-draw/${encodeURIComponent(drawDate)}?min_matches=0&limit=100`,
            `/api/v1/predictions/public/by-draw/${encodeURIComponent(drawDate)}?min_matches=0&limit=100`
        ];

        let response = null;
        let lastError = null;

        for (const apiUrl of apiEndpoints) {
            try {
                console.log('Trying API URL:', apiUrl);
                response = await fetch(apiUrl, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    console.log('✅ Success with endpoint:', apiUrl);
                    break;
                } else {
                    console.warn(`❌ Failed with status ${response.status} for: ${apiUrl}`);
                    const errorText = await response.text();
                    lastError = new Error(`HTTP ${response.status}: ${errorText}`);
                    response = null;
                }
            } catch (fetchError) {
                console.warn('❌ Network error for', apiUrl, ':', fetchError.message);
                lastError = fetchError;
                response = null;
            }
        }

        if (!response || !response.ok) {
            throw lastError || new Error('All API endpoints failed');
        }

        const data = await response.json();
        console.log('Draw matches data:', data);

        // Update modal with results
        updateDrawMatchesModal(data);

    } catch (error) {
        console.error('Error loading draw matches:', error);
        const modalContent = document.getElementById('modalContent');
        if (modalContent) {
            const errorMessage = error.message || error.toString() || 'Unknown error occurred';
            console.error('Full error details:', error);
            modalContent.innerHTML = `
                <div class="p-6 text-center">
                    <i class="fas fa-exclamation-triangle text-3xl text-red-500 mb-4"></i>
                    <h3 class="text-lg font-semibold text-red-600 mb-2">Error Loading Data</h3>
                    <p class="text-gray-400 mb-2">Unable to load prediction matches for this draw.</p>
                    <p class="text-sm text-gray-400 mb-4">Draw date: ${drawDateInput}</p>
                    <p class="text-xs text-gray-300 mb-4">Error: ${errorMessage}</p>
                    <div class="space-x-3">
                        <button onclick="showDrawMatchesModal('${drawDateInput}')" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                            <i class="fas fa-redo mr-2"></i>Retry
                        </button>
                        <button onclick="closeDrawMatchesModal()" class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
                            Close
                        </button>
                    </div>
                </div>
            `;
        }
    }
}


// Load recent draws
async function loadRecentDraws() {
    try {
        console.log('Loading recent draws...');

        // Try multiple endpoint variations to ensure compatibility
        const endpointVariations = [
            `/api/v1/public/recent-draws?limit=10`,
            `/api/v1/public/draws/recent?limit=10`,
            `/api/v1/public/recent-draws?limit=10`,
            `/api/v1/public/draws/recent?limit=10`
        ];

        let response;
        let lastError;

        for (let i = 0; i < endpointVariations.length; i++) {
            const endpoint = endpointVariations[i];
            console.log(`Trying endpoint ${i + 1}/${endpointVariations.length}: ${endpoint}`);

            try {
                response = await fetch(endpoint, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                console.log(`Response status for ${endpoint}:`, response.status);

                if (response.ok) {
                    console.log(`✅ Success with endpoint: ${endpoint}`);
                    break;
                } else {
                    console.warn(`❌ Failed with status ${response.status} for: ${endpoint}`);
                    lastError = new Error(`HTTP error! status: ${response.status}`);
                }
            } catch (fetchError) {
                console.warn(`❌ Network error for ${endpoint}:`, fetchError.message);
                lastError = fetchError;
            }
        }

        if (!response || !response.ok) {
            throw lastError || new Error('All endpoint variations failed');
        }

        const data = await response.json();
        console.log('Recent draws response:', data);

        if (data.draws && data.draws.length > 0) {
            displayRecentDraws(data.draws);
        } else {
            console.warn('No recent draws data available');
            const recentDrawsContainer = document.getElementById('recentDrawsContainer');
            if (recentDrawsContainer) {
                recentDrawsContainer.innerHTML = `
                    <div class="text-center p-6 text-gray-400">
                        <i class="fas fa-info-circle text-2xl mb-2"></i>
                        <p>No recent draws available</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading recent draws:', error);
        const container = document.getElementById('recentDrawsContainer');
        if (container) {
            const errorMessage = error.message || error.toString() || 'Error loading recent draws';
            container.innerHTML = `
                <div class="text-center p-6 text-red-500">
                    <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                    <p>Error: ${errorMessage}</p>
                    <p class="text-sm text-gray-400 mt-2">Check console for details</p>
                    <button onclick="loadRecentDraws()" class="mt-4 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                        Retry
                    </button>
                </div>
            `;
        }
    }
}

// Function to display recent draws
function displayRecentDraws(draws) {
    const recentDrawsContainer = document.getElementById('recentDrawsContainer');
    if (!recentDrawsContainer) {
        console.error('Recent draws container not found');
        return;
    }

    let html = '';
    draws.forEach(draw => {
        // Use the exact draw date from the API without conversion
        const drawDate = draw.draw_date || draw.date;
        
        // Format date safely for display with weekday
        let formattedDate;
        try {
            const dateObj = new Date(drawDate + 'T00:00:00'); // Force to start of day
            formattedDate = dateObj.toLocaleDateString('en-US', {
                weekday: 'short',
                year: 'numeric', 
                month: 'short', 
                day: 'numeric',
                timeZone: 'UTC' // Force UTC to avoid timezone shifts
            });
        } catch (e) {
            console.warn('Date parsing error for:', drawDate, e);
            formattedDate = drawDate; // Fallback to raw date
        }

        console.log(`Draw date mapping: ${drawDate} -> ${formattedDate}`);

        html += `
            <div class="draw-item p-4 mb-4 bg-white rounded-lg shadow hover:shadow-md transition-shadow duration-200 flex justify-between items-center border border-gray-200 cursor-pointer"
                 data-draw-date="${drawDate}"
                 onclick="showDrawMatchesModal('${drawDate}')">
                <div class="flex items-center">
                    <i class="fas fa-calendar-alt text-blue-500 mr-3 text-lg"></i>
                    <div>
                        <p class="font-semibold text-gray-800">${formattedDate}</p>
                        <p class="text-sm text-gray-400">Draw ID: ${draw.id}</p>
                        <div class="bg-gray-50 p-2 rounded mt-2">
                            <div class="flex space-x-1 mb-1">
                                ${[draw.n1, draw.n2, draw.n3, draw.n4, draw.n5].map(num => 
                                    `<span class="inline-flex items-center justify-center w-6 h-6 bg-blue-600 text-white rounded-full text-xs font-bold">${num}</span>`
                                ).join('')}
                            </div>
                            <div class="flex items-center">
                                <span class="text-xs text-gray-400 mr-2">PB:</span>
                                <span class="inline-flex items-center justify-center w-6 h-6 bg-red-600 text-white rounded-full text-xs font-bold">${draw.pb}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <span class="text-gray-400 hover:text-blue-500 transition-colors duration-200">
                    View Matches <i class="fas fa-arrow-right ml-1"></i>
                </span>
            </div>
        `;
    });

    recentDrawsContainer.innerHTML = html;
}


// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    loadRecentDraws();

    // Add event listener for the modal overlay to close it when clicked
    const modalOverlay = document.getElementById('drawMatchesModal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (event) => {
            // Close modal only if the click is on the overlay itself, not its content
            if (event.target === modalOverlay) {
                // Assign the close function to window if it's not already there
                // to ensure it's globally accessible for the onclick attribute
                if (!window.closeDrawMatchesModal) {
                    window.closeDrawMatchesModal = closeDrawMatchesModal;
                }
                window.closeDrawMatchesModal();
            }
        });
    }

    // Handle draw card clicks for detailed view
    document.addEventListener('click', function(e) {
        const drawCard = e.target.closest('.draw-card');
        if (drawCard && !e.target.closest('button')) {
            const drawDate = drawCard.dataset.drawDate;
            if (drawDate) {
                showDetailedPredictionModal(drawDate);
            }
        }
    });
});

// Mock PowerballUtils and createErrorPlaceholder for demonstration if they are not defined
// In a real scenario, these would be imported or defined elsewhere.
if (typeof PowerballUtils === 'undefined') {
    var PowerballUtils = {
        createErrorPlaceholder: function(message) {
            return `
                <div class="text-center p-6 text-red-500">
                    <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                    <p>${message || 'An error occurred'}</p>
                </div>
            `;
        }
    };
}

// API_BASE_URL is defined in the main index.html file
// This file uses absolute paths to avoid dependency issues