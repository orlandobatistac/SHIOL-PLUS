// Utility function to close the modal
function closeDrawMatchesModal() {
    const modal = document.getElementById('drawMatchesModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Simple client-side table sorter for strategy table
function enableStrategyTableSorting() {
    const table = document.getElementById('strategyTable');
    if (!table) return;
    const ths = table.querySelectorAll('th');
    ths.forEach(th => {
        th.addEventListener('click', () => {
            const key = th.getAttribute('data-key');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const idxMap = { strategy: 0, count: 1, wins: 2, total_prize: 3 };
            const idx = idxMap[key] || 0;
            const asc = th.classList.contains('asc') ? false : true;
            rows.sort((a,b) => {
                const aText = a.children[idx].textContent.replace(/[$,]/g,'');
                const bText = b.children[idx].textContent.replace(/[$,]/g,'');
                const aVal = isNaN(aText) ? aText.toLowerCase() : parseFloat(aText);
                const bVal = isNaN(bText) ? bText.toLowerCase() : parseFloat(bText);
                if (aVal < bVal) return asc ? -1 : 1;
                if (aVal > bVal) return asc ? 1 : -1;
                return 0;
            });
            // Clear asc/desc on headers
            ths.forEach(h => h.classList.remove('asc','desc'));
            th.classList.add(asc ? 'asc' : 'desc');
            // Re-append rows
            rows.forEach(r => tbody.appendChild(r));
        });
    });
}

// Helper: format draw date like "Draw Date: Wednesday, September 17, 2025"
function formatDrawDateLabel(dateStr) {
    if (!dateStr) return 'Draw Date: —';
    try {
        const [y, m, d] = String(dateStr).split('-').map(Number);
        const dt = new Date(Date.UTC(y, (m || 1) - 1, d || 1));
        const formatted = dt.toLocaleDateString('en-US', {
            weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'
        });
        return `Draw Date: ${formatted}`;
    } catch {
        return `Draw Date: ${dateStr}`;
    }
}

// Helper: normalize prize tier label to abbreviated form like "3+PB", "3", "PB", or "None"
function abbreviatePrizeTierLabel(raw) {
    if (!raw) return 'None';
    const s = String(raw).trim();
    if (/no\s*prize/i.test(s) || /^none$/i.test(s)) return 'None';
    if (/^(pb\s*only|powerball\s*only)$/i.test(s)) return 'PB';
    let m = s.match(/(\d+)\s*\+\s*(?:pb|powerball)/i);
    if (m) return `${m[1]}+PB`;
    m = s.match(/(?:match\s*)?(\d+)\s*(?:white|numbers?)?/i);
    if (m) return `${m[1]}`;
    if (/\b(pb|powerball)\b/i.test(s)) return 'PB';
    return s;
}

// Fetch and display draw analytics in modal with dashboard-like content
async function fetchDrawAnalytics(drawDate) {
    // Delegate to the complete analytics modal implementation
    if (typeof fetchDrawAnalyticsComplete === 'function') {
        return await fetchDrawAnalyticsComplete(drawDate);
    }
    
    // Fallback to basic implementation if complete version not loaded
    console.warn('Complete analytics modal not loaded, using fallback');
    const modal = document.getElementById('drawMatchesModal');
    const loadingEl = document.getElementById('modal-loading');
    const emptyEl = document.getElementById('modal-empty');
    const contentEl = document.getElementById('modal-content');
    
    if (!modal) {
        console.error('Analytics modal not found');
        return;
    }
    
    modal.classList.remove('hidden');
    if (loadingEl) loadingEl.classList.remove('hidden');
    if (emptyEl) emptyEl.classList.add('hidden');
    if (contentEl) contentEl.classList.add('hidden');
    
    try {
        const url = `/api/v1/public/analytics/draw/${encodeURIComponent(drawDate)}`;
        const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        
        if (!data || (data.total_predictions || 0) === 0) {
            if (loadingEl) loadingEl.classList.add('hidden');
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }
        
        // Basic rendering (will be enhanced by complete version)
        const modalDrawDate = document.getElementById('modal-draw-date');
        if (modalDrawDate) modalDrawDate.textContent = formatDrawDateLabel(data.draw_date || drawDate);
        
        if (loadingEl) loadingEl.classList.add('hidden');
        if (contentEl) contentEl.classList.remove('hidden');
        
    } catch (e) {
        console.error('Error fetching analytics:', e);
        if (loadingEl) loadingEl.classList.add('hidden');
        if (emptyEl) emptyEl.classList.remove('hidden');
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
                </div>

                <!-- Analytics summary block (prize tiers, strategy, matches, confidence) -->
                ${data.prize_tiers || data.strategy_counts || data.match_distribution ? `
                <div class="mb-4 p-3 bg-white border rounded-lg text-sm text-gray-700">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <div class="font-medium text-gray-800">Prize Tiers</div>
                            <div class="mt-2">
                                ${Object.keys(data.prize_tiers || {}).length === 0 ? '<div class="text-gray-400">No prizes</div>' : Object.entries(data.prize_tiers || {}).map(([tier, info]) => {
                                    // Choose badge by total_prize
                                    const total = info.total_prize || 0;
                                    const cls = total >= 1000 ? 'badge-high' : (total >= 100 ? 'badge-medium' : 'badge-low');
                                    return `<div class="flex justify-between items-center"><span>${tier}</span><span class="${cls}">💰 ${info.count}</span></div>`
                                }).join('')}
                            </div>
                        </div>
                        <div>
                            <div class="font-medium text-gray-800">By Strategy</div>
                            <div class="mt-2">
                                ${Object.keys(data.strategy_counts || {}).length === 0 ? '<div class="text-gray-400">No data</div>' : `
                                    <table class="strategy-table" id="strategyTable">
                                        <thead>
                                            <tr>
                                                <th data-key="strategy">Strategy</th>
                                                <th data-key="count">Count</th>
                                                <th data-key="wins">Wins</th>
                                                <th data-key="total_prize">Total Prize</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${Object.entries(data.strategy_counts || {}).map(([s, info]) =>
                                                `<tr data-strategy="${s}"><td>${s}</td><td>${info.count}</td><td>${info.wins || 0}</td><td>$${(info.total_prize||0).toLocaleString()}</td></tr>`
                                            ).join('')}
                                        </tbody>
                                    </table>
                                `}
                            </div>
                        </div>
                        <div>
                            <div class="font-medium text-gray-800">Match Distribution 🎯</div>
                            <div class="mt-2 text-xs text-gray-600">
                                ${Object.entries(data.match_distribution || {}).map(([matches, md]) =>
                                    `
                                    <div class="mb-2">
                                        <div class="flex justify-between text-sm"><span>${matches} WB</span><span>${(md.without_pb + md.with_pb)}</span></div>
                                        <div class="progress-bar mt-1">
                                            <div class="progress progress-medium" style="width: ${Math.min(100, ((md.without_pb + md.with_pb) / Math.max(1, data.total_predictions)) * 100)}%"></div>
                                        </div>
                                        <div class="text-xs text-gray-400 mt-1">PB: ${md.with_pb} • Without PB: ${md.without_pb}</div>
                                    </div>
                                `
                                ).join('')}
                            </div>
                        </div>
                        <div>
                            <div class="font-medium text-gray-800">Confidence</div>
                            <div class="mt-2 text-xs text-gray-600">
                                ${Object.entries(data.confidence_summary || {}).map(([k, v]) =>
                                    `<div class="flex justify-between"><span>${k}</span><span>${v.count} (${(v.avg_confidence*100).toFixed(1)}%)</span></div>`
                                ).join('')}
                                <div class="mt-2">
                                    ${Object.entries(data.confidence_summary || {}).map(([k, v]) =>
                                        `<div class="flex items-center gap-2 mt-1"><span class="badge-${k==='high'?'high':k==='medium'?'medium':'low'}">${k === 'high' ? '🔥' : (k==='medium' ? '⚡' : '🔹')} ${k}</span><div class="progress-bar flex-1"><div class="progress ${k==='high'?'progress-high':k==='medium'?'progress-medium':'progress-low'}" style="width:${(v.count / Math.max(1, data.total_predictions) * 100).toFixed(1)}%"></div></div></div>`
                                    ).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                ` : ''}

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
        // Enable strategy table sorting if present
        try {
            enableStrategyTableSorting();
        } catch (e) {
            console.warn('Could not enable strategy table sorting:', e);
        }
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

// (Removed legacy showDetailedPredictionModal; analytics modal is the single source of truth)


// Function to handle showing the draw matches modal (now delegates to analytics)
async function showDrawMatchesModal(drawDateInput) {
    return fetchDrawAnalytics(drawDateInput);
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    // Draw loading is now handled by index.html inline code


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

    // Legacy draw-card click handler removed; cards call showDrawMatchesModal via inline onclick
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