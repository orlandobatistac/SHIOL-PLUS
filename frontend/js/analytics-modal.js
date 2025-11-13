// ============================================================================
// ANALYTICS MODAL - COMPLETE DASHBOARD IMPLEMENTATION
// ============================================================================

// Helper: Format numbers as currency
function formatCurrency(cents) {
    // If the value is already in dollars, don't divide
    if (cents >= 1000) {
        return `$${Number(cents).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    }
    // If the value is less than 1000, assume it's in dollars
    return `$${Number(cents).toFixed(2)}`;
}

// Helper: Generate Strategy Breakdown HTML (Ranking View)
function generateStrategyRankingHTML(strategyData) {
    if (!strategyData || Object.keys(strategyData).length === 0) {
        return '<div class="text-center py-8 text-white/60">No strategy data available</div>';
    }

    // Calculate scores and sort
    const strategies = Object.entries(strategyData).map(([name, info]) => ({
        name,
        count: info.count || 0,
        wins: info.wins || 0,
        total_prize: info.total_prize || 0,
        best_match: info.best_match || 'None',
        avg_prize_per_win: info.wins > 0 ? (info.total_prize / info.wins) : 0,
        win_rate: info.count > 0 ? ((info.wins / info.count) * 100) : 0,
        score: (info.wins * 1000) + (info.total_prize)
    })).sort((a, b) => b.score - a.score);

    let html = `
        <div class="overflow-x-auto">
            <table class="min-w-full">
                <thead class="bg-canvas-card/30">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-medium text-white/60 uppercase">Rank</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-white/60 uppercase">Strategy</th>
                        <th class="px-4 py-3 text-center text-xs font-medium text-white/60 uppercase">Tickets</th>
                        <th class="px-4 py-3 text-center text-xs font-medium text-white/60 uppercase">Wins</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-white/60 uppercase">Win Rate</th>
                        <th class="px-4 py-3 text-right text-xs font-medium text-white/60 uppercase">Total Prize</th>
                        <th class="px-4 py-3 text-right text-xs font-medium text-white/60 uppercase">Avg/W</th>
                        <th class="px-4 py-3 text-center text-xs font-medium text-white/60 uppercase">Best</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-canvas-line/30">`;

    strategies.forEach((s, idx) => {
        let rankBadge = '';
        if (idx === 0) rankBadge = '<span class="text-yellow-400">🥇</span>';
        else if (idx === 1) rankBadge = '<span class="text-gray-300">🥈</span>';
        else if (idx === 2) rankBadge = '<span class="text-orange-400">🥉</span>';
        else rankBadge = `<span class="text-white/40">#${idx + 1}</span>`;

        const winRateWidth = Math.min(100, s.win_rate);
        const hasPB = s.best_match && s.best_match.includes('PB');
        const bestMatchClass = hasPB ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white' : 'bg-white/10 text-white/70';

        html += `
            <tr class="hover:bg-canvas-line/20 transition-colors">
                <td class="px-4 py-3">${rankBadge}</td>
                <td class="px-4 py-3">
                    <span class="inline-block px-3 py-1 rounded-full bg-canvas-accent/20 text-canvas-accent text-sm font-medium">
                        ${s.name}
                    </span>
                </td>
                <td class="px-4 py-3 text-center text-white/80">${s.count}</td>
                <td class="px-4 py-3 text-center font-semibold ${s.wins > 0 ? 'text-green-400' : 'text-white/40'}">${s.wins}</td>
                <td class="px-4 py-3">
                    <div class="text-xs text-white/70 mb-1">${s.win_rate.toFixed(1)}%</div>
                    <div class="w-full bg-white/5 rounded-full h-1.5">
                        <div class="bg-gradient-to-r from-green-400 to-emerald-500 h-1.5 rounded-full transition-all duration-500"
                             style="width: ${winRateWidth}%"></div>
                    </div>
                </td>
                <td class="px-4 py-3 text-right font-semibold text-canvas-accent">${formatCurrency(s.total_prize)}</td>
                <td class="px-4 py-3 text-right text-white/70 text-sm">${s.wins > 0 ? formatCurrency(s.avg_prize_per_win) : '—'}</td>
                <td class="px-4 py-3 text-center">
                    <span class="inline-block px-2 py-1 rounded text-xs font-bold ${bestMatchClass}">
                        ${s.best_match}
                    </span>
                </td>
            </tr>`;
    });

    html += `
                </tbody>
            </table>
        </div>`;

    return html;
}

// Helper: Generate Strategy Breakdown HTML (Bars View)
function generateStrategyBarsHTML(strategyData) {
    if (!strategyData || Object.keys(strategyData).length === 0) {
        return '<div class="text-center py-8 text-white/60">No strategy data available</div>';
    }

    const strategies = Object.entries(strategyData)
        .map(([name, info]) => ({
            name,
            count: info.count || 0,
            wins: info.wins || 0,
            total_prize: info.total_prize || 0
        }))
        .sort((a, b) => b.total_prize - a.total_prize);

    const maxPrize = Math.max(...strategies.map(s => s.total_prize), 1);

    let html = '<div class="space-y-4">';
    strategies.forEach(s => {
        const width = (s.total_prize / maxPrize) * 100;
        html += `
            <div>
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-white">${s.name}</span>
                    <div class="text-xs text-white/60">
                        <span class="mr-3">${s.count} tickets</span>
                        <span class="${s.wins > 0 ? 'text-green-400' : 'text-white/40'}">${s.wins} wins</span>
                    </div>
                </div>
                <div class="relative">
                    <div class="w-full bg-white/5 rounded-full h-8 overflow-hidden">
                        <div class="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-end px-3 transition-all duration-700"
                             style="width: ${width}%">
                            <span class="text-white text-xs font-bold">${formatCurrency(s.total_prize)}</span>
                        </div>
                    </div>
                </div>
            </div>`;
    });
    html += '</div>';

    return html;
}

// Helper: Generate Match Distribution HTML
function generateMatchDistributionHTML(distribution, totalPredictions) {
    if (!distribution || Object.keys(distribution).length === 0) {
        return '<div class="text-center py-4 text-white/60">No distribution data available</div>';
    }

    const matches = ['0', '1', '2', '3', '4', '5'];
    let html = '<div class="space-y-3">';

    matches.forEach(m => {
           // Support both formats: "wb_0" or "0"
           const data = distribution[`wb_${m}`] || distribution[m] || { without_pb: 0, with_pb: 0 };
        const total = (data.without_pb || 0) + (data.with_pb || 0);
        const withPB = data.with_pb || 0;
        const percent = totalPredictions > 0 ? ((total / totalPredictions) * 100) : 0;

        html += `
            <div>
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm text-white/80">${m} White Ball${m !== '1' ? 's' : ''}</span>
                    <div class="text-xs text-white/60">
                        <span class="mr-2">${total} total</span>
                        ${withPB > 0 ? `<span class="text-pink-400">${withPB} +PB</span>` : ''}
                    </div>
                </div>
                <div class="w-full bg-white/5 rounded-full h-6 overflow-hidden">
                    <div class="h-full bg-gradient-to-r from-cyan-400 to-purple-500 rounded-full flex items-center justify-end px-2 transition-all duration-500"
                         style="width: ${percent}%">
                        <span class="text-white text-xs font-bold">${percent.toFixed(1)}%</span>
                    </div>
                </div>
            </div>`;
    });

    html += '</div>';
    return html;
}

// Helper: Generate Prize Tiers HTML
function generatePrizeTiersHTML(prizeTiers) {
    if (!prizeTiers || Object.keys(prizeTiers).length === 0) {
        return '<div class="text-center py-4 text-white/60">No prize tier data available</div>';
    }

    const tiers = Object.entries(prizeTiers)
        .filter(([tier, info]) => (info.count || 0) > 0 && tier !== 'No Prize')
        .sort((a, b) => (b[1].total_prize || 0) - (a[1].total_prize || 0));

    if (tiers.length === 0) {
        return '<div class="text-center py-4 text-white/60">No prizes won</div>';
    }

    let html = '<div class="space-y-2">';
    tiers.forEach(([tier, info]) => {
        const hasPB = tier.toLowerCase().includes('pb') || tier.toLowerCase().includes('powerball');
        const bgClass = hasPB ? 'bg-gradient-to-r from-purple-500/20 to-pink-500/20 border-purple-500/30' : 'bg-white/5 border-white/10';
        
        html += `
            <div class="flex items-center justify-between p-3 rounded-lg border ${bgClass}">
                <div class="flex items-center gap-3">
                    <span class="text-yellow-400">🏆</span>
                    <div>
                        <div class="text-sm font-semibold text-white">${tier}</div>
                        <div class="text-xs text-white/60">${info.count} ${info.count === 1 ? 'insight' : 'insights'}</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-sm font-bold text-canvas-accent">${formatCurrency(info.total_prize)}</div>
                </div>
            </div>`;
    });
    html += '</div>';

    return html;
}

// Global function to switch strategy view
window.switchStrategyView = function(mode) {
    if (!window.currentStrategyData) return;

    const container = document.getElementById('strategy-content-container');
    if (!container) return;

    const btnRanking = document.getElementById('btn-strategy-ranking');
    const btnBars = document.getElementById('btn-strategy-bars');

    if (mode === 'ranking') {
        container.innerHTML = generateStrategyRankingHTML(window.currentStrategyData);
        if (btnRanking) {
            btnRanking.className = 'px-3 py-1 text-sm rounded bg-canvas-accent text-white font-medium';
        }
        if (btnBars) {
            btnBars.className = 'px-3 py-1 text-sm rounded bg-canvas-surface text-white/70 hover:bg-canvas-accent/30';
        }
    } else if (mode === 'bars') {
        container.innerHTML = generateStrategyBarsHTML(window.currentStrategyData);
        if (btnBars) {
            btnBars.className = 'px-3 py-1 text-sm rounded bg-canvas-accent text-white font-medium';
        }
        if (btnRanking) {
            btnRanking.className = 'px-3 py-1 text-sm rounded bg-canvas-surface text-white/70 hover:bg-canvas-accent/30';
        }
    }
};

// Main function to fetch and display complete analytics dashboard
async function fetchDrawAnalyticsComplete(drawDate) {
    const modal = document.getElementById('drawMatchesModal');
    const loadingEl = document.getElementById('modal-loading');
    const emptyEl = document.getElementById('modal-empty');
    const contentEl = document.getElementById('modal-content');

    if (!modal) {
        console.error('Analytics modal not found');
        return;
    }

    // Show modal and loading
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

        // Update header date
        const modalDrawDate = document.getElementById('modal-draw-date');
        if (modalDrawDate) {
            modalDrawDate.textContent = formatDrawDateLabel(data.draw_date || drawDate);
        }

        // Row 1: Winning Numbers
        const winNumsEl = document.getElementById('modal-winning-numbers');
        const winPBEl = document.getElementById('modal-winning-powerball');
        if (winNumsEl && data.winning_numbers?.main_numbers) {
            winNumsEl.innerHTML = data.winning_numbers.main_numbers
                .map(n => `<span class="num-chip">${n}</span>`)
                .join('');
        }
        if (winPBEl && data.winning_numbers?.powerball) {
            winPBEl.innerHTML = `<span class="num-chip powerball-chip">${data.winning_numbers.powerball}</span>`;
        }

        // Row 2: KPIs
        const totalPredEl = document.getElementById('modal-total-predictions');
        const matchesFoundEl = document.getElementById('modal-matches-found');
        const winRateEl = document.getElementById('modal-win-rate');
        const bestMatchEl = document.getElementById('modal-best-match');
        const totalPrizesEl = document.getElementById('modal-total-prizes');

        if (totalPredEl) totalPredEl.textContent = String(data.total_predictions || 0);
        
        const withMatches = data.predictions_with_prizes || 0;
        if (matchesFoundEl) matchesFoundEl.textContent = String(withMatches);
        if (winRateEl) {
            const rate = data.total_predictions > 0 ? ((withMatches / data.total_predictions) * 100) : 0;
            winRateEl.textContent = `(${rate.toFixed(1)}%)`;
        }

        // Best Match from prize tiers (display VALUE and add (TIER) in a separate lighter element)
        let bestMatchTier = 'None';
        let bestMatchValue = null; // highest individual prize amount
        if (data.prize_tiers && Object.keys(data.prize_tiers).length > 0) {
            const tiersWithWins = Object.entries(data.prize_tiers)
                .filter(([tier, info]) => (info.count || 0) > 0 && tier !== 'No Prize')
                .sort((a, b) => {
                    // Sort by the unit prize amount (prize per win), not total prize
                    const aUnitPrize = (a[1].count || 0) > 0 ? (a[1].total_prize || 0) / a[1].count : 0;
                    const bUnitPrize = (b[1].count || 0) > 0 ? (b[1].total_prize || 0) / b[1].count : 0;
                    return bUnitPrize - aUnitPrize;
                });
            if (tiersWithWins.length > 0) {
                const [rawTier, info] = tiersWithWins[0];
                bestMatchTier = abbreviatePrizeTierLabel(rawTier);
                const cnt = Number(info.count || 0);
                const total = Number(info.total_prize || 0);
                bestMatchValue = cnt > 0 ? (total / cnt) : null; // unit prize for that tier (what each win pays)
            }
        }
        if (bestMatchEl) {
            // Main: only the value (e.g., $4.00) or 'None'
            bestMatchEl.textContent = bestMatchValue != null ? formatCurrency(bestMatchValue) : 'None';
            // Small inline element: parentheses tier (e.g., (PB))
            const tierEl = document.getElementById('modal-best-match-tier');
            if (tierEl) {
                const showTier = (bestMatchValue != null) && bestMatchTier && bestMatchTier.toLowerCase() !== 'none';
                tierEl.textContent = showTier ? `(${bestMatchTier})` : '';
            }
        }
        if (totalPrizesEl) totalPrizesEl.textContent = formatCurrency(data.total_prize || 0);

        // Row 3: Smart Insights with Matches (Winners Only)
        const tbody = document.getElementById('modal-predictions-tbody');
        const list = document.getElementById('modal-predictions-list');
        const noWinnersEl = document.getElementById('modal-no-winners');
        const winnersSection = document.getElementById('modal-winners-section');
        const isMobile = window.innerWidth < 640;

        if (tbody) {
            // Use winning_predictions if available (all with prizes), otherwise filter top_predictions
            const winners = data.winning_predictions || 
                (Array.isArray(data.top_predictions) ? data.top_predictions : (data.predictions || []))
                    .filter(p => (p.prize_won || 0) > 0)
                    .sort((a, b) => (b.prize_won || 0) - (a.prize_won || 0));

            const winningNums = data.winning_numbers?.main_numbers || [];
            const winningPB = data.winning_numbers?.powerball;

            tbody.innerHTML = '';
            if (list) list.innerHTML = '';
            
            if (winners.length === 0) {
                if (winnersSection) winnersSection.querySelector('table')?.classList.add('hidden');
                if (noWinnersEl) noWinnersEl.classList.remove('hidden');
                
                const emptyMsg = `
                    <div class="px-4 py-8 text-center text-white/60">
                        <i class="fas fa-trophy text-2xl mb-2"></i>
                        <br>
                        No winning AI insights found for this draw.
                        <br>
                        <span class="text-sm">Try again with the next drawing!</span>
                    </div>
                `;
                if (isMobile && list) {
                    list.innerHTML = emptyMsg;
                }
            } else {
                if (winnersSection) winnersSection.querySelector('table')?.classList.remove('hidden');
                if (noWinnersEl) noWinnersEl.classList.add('hidden');

                winners.forEach((p, idx) => {
                    const nums = [p.n1, p.n2, p.n3, p.n4, p.n5];
                    const pbMatch = (p.powerball || p.pb) === winningPB;
                    
                    // Calculate matches for display
                    const whiteMatches = nums.filter(n => winningNums.includes(n)).length;
                    const matchDisplay = `${whiteMatches}${pbMatch ? '+PB' : ''}`;
                    const displayRank = (p.generation_rank && Number.isFinite(p.generation_rank)) ? p.generation_rank : (idx + 1);
                    const prizeAmount = p.prize_won || 0;
                    const prizeText = formatCurrency(prizeAmount);
                    
                    // Mobile: card layout
                    if (isMobile && list) {
                        const numsHTML = nums.map(n => {
                            const isWin = winningNums.includes(n);
                            const chipClass = isWin 
                                ? 'num-chip text-xs w-7 h-7' 
                                : 'num-chip text-xs w-7 h-7';
                            const style = isWin ? 'style="background: #00e0ff; color: #0a0c14;"' : '';
                            return `<span class="${chipClass}" ${style}>${n}</span>`;
                        }).join('');
                        
                        const pbClass = pbMatch ? 'num-chip powerball-chip text-xs w-7 h-7' : 'num-chip powerball-chip text-xs w-7 h-7';
                        const pbStyle = pbMatch ? 'style="background: #00e0ff; color: #0a0c14;"' : '';
                        
                        const cardDiv = document.createElement('div');
                        cardDiv.className = 'bg-canvas-card rounded-lg border border-white/5 p-4 space-y-3';
                        cardDiv.innerHTML = `
                            <div class="flex items-center justify-between border-b border-white/5 pb-2">
                                <div class="flex items-center gap-2">
                                    <span class="inline-flex items-center justify-center w-8 h-6 rounded-md bg-gradient-to-r from-canvas-accent to-canvas-accent2 text-white text-sm font-bold shadow-md">
                                        #${displayRank}
                                    </span>
                                    <span class="text-xs text-white/60">${p.strategy_used || 'AI'}</span>
                                </div>
                                <div class="text-right">
                                    <div class="text-xs text-white/50">Matches</div>
                                    <div class="text-sm font-bold text-white">${matchDisplay}</div>
                                </div>
                            </div>
                            <div class="flex items-center justify-center gap-1.5 flex-wrap">
                                ${numsHTML}
                                <div class="w-0.5"></div>
                                <span class="${pbClass}" ${pbStyle}>${p.powerball || p.pb}</span>
                            </div>
                            <div class="flex items-center justify-between pt-1 border-t border-white/5">
                                <span class="text-[10px] text-white/50 uppercase tracking-wide">Prize</span>
                                <span class="text-sm font-bold text-emerald-400">${prizeText}</span>
                            </div>
                        `;
                        list.appendChild(cardDiv);
                    } else {
                        // Desktop: table row
                        const numsHTML = nums.map(n => {
                            const isWin = winningNums.includes(n);
                            const chipClass = isWin 
                                ? 'num-chip bg-green-500/30 text-green-300 ring-2 ring-green-400/50 shadow-[0_0_10px_rgba(74,222,128,0.5)]' 
                                : 'num-chip';
                            return `<span class="${chipClass}">${n}</span>`;
                        }).join('');
                        
                        const pbClass = pbMatch
                            ? 'num-chip num-chip-match-pb'
                            : 'num-chip powerball-chip';
                        
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-canvas-line/10 transition-colors';
                        tr.innerHTML = `
                            <td class="px-4 py-3 text-white/60 font-medium">#${displayRank}</td>
                            <td class="px-4 py-3">
                                <div class="flex items-center gap-1 flex-wrap">${numsHTML}</div>
                            </td>
                            <td class="px-4 py-3"><span class="${pbClass}">${p.powerball || p.pb}</span></td>
                            <td class="px-4 py-3">
                                <span class="px-2 py-1 rounded text-xs font-medium bg-canvas-accent/20 text-canvas-accent">
                                    ${p.strategy_used || 'N/A'}
                                </span>
                            </td>
                            <td class="px-4 py-3">
                                <span class="px-2 py-1 rounded text-xs font-bold ${pbMatch ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white' : 'bg-white/10 text-white/70'}">
                                    ${matchDisplay}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right font-bold text-canvas-accent">${prizeText}</td>
                        `;
                        tbody.appendChild(tr);
                    }
                });
            }
        }

        // Row 4: Strategy Breakdown
        const strategySection = document.getElementById('modal-strategy-section');
        if (strategySection && data.strategy_counts && Object.keys(data.strategy_counts).length > 0) {
            strategySection.classList.remove('hidden');
            window.currentStrategyData = data.strategy_counts;
            window.switchStrategyView('ranking'); // Default to ranking view
        }

        // Row 5: Match Distribution & Prize Tiers
        const distributionSection = document.getElementById('modal-distribution-section');
        const prizeTiersSection = document.getElementById('modal-prize-tiers-section');

        if (distributionSection && data.match_distribution) {
            distributionSection.classList.remove('hidden');
            const distributionContent = document.getElementById('distribution-content');
            if (distributionContent) {
                distributionContent.innerHTML = generateMatchDistributionHTML(
                    data.match_distribution,
                    data.total_predictions || 0
                );
            }
        }

        if (prizeTiersSection && data.prize_tiers) {
            prizeTiersSection.classList.remove('hidden');
            const prizeTiersContent = document.getElementById('prize-tiers-content');
            if (prizeTiersContent) {
                prizeTiersContent.innerHTML = generatePrizeTiersHTML(data.prize_tiers);
            }
        }

        // Show content
        if (loadingEl) loadingEl.classList.add('hidden');
        if (contentEl) contentEl.classList.remove('hidden');

    } catch (e) {
        console.error('Error fetching analytics:', e);
        if (loadingEl) loadingEl.classList.add('hidden');
        if (emptyEl) emptyEl.classList.remove('hidden');
        const emptyText = emptyEl?.querySelector('p');
        if (emptyText) emptyText.textContent = 'Failed to load analytics. Please try again.';
    }
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        fetchDrawAnalyticsComplete,
        formatCurrency,
        generateStrategyRankingHTML,
        generateStrategyBarsHTML,
        generateMatchDistributionHTML,
        generatePrizeTiersHTML
    };
}
