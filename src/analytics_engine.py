"""
SHIOL+ Analytics Engine
=======================
Advanced statistical analysis for Powerball historical data.
"""

import numpy as np
import pandas as pd
from loguru import logger
from typing import Dict, Any
from src.database import get_db_connection, get_all_draws


class AnalyticsEngine:
    """Advanced analytics for Powerball historical data"""

    def __init__(self):
        self.draws_df = get_all_draws()

        if self.draws_df.empty:
            logger.warning("No historical data available for analytics")
        else:
            # Era-aware counts
            current_era = self.draws_df[
                (self.draws_df['pb'] >= 1) & (self.draws_df['pb'] <= 26)
            ]
            historical_count = len(self.draws_df) - len(current_era)
            logger.info(f"Analytics Engine initialized with {len(self.draws_df)} draws "
                        f"({len(current_era)} current-era, {historical_count} historical)")

    def _safe_get_numbers(self, draw_row) -> list:
        """
        Safely extract five white ball numbers from a draw row.
        Returns a sorted list of five integers in range 1-69, or empty list if invalid.
        """
        try:
            # draw_row may be a pandas Series or dict-like
            nums = [int(draw_row.get('n1')) if hasattr(draw_row, 'get') else int(draw_row['n1']),
                    int(draw_row.get('n2')) if hasattr(draw_row, 'get') else int(draw_row['n2']),
                    int(draw_row.get('n3')) if hasattr(draw_row, 'get') else int(draw_row['n3']),
                    int(draw_row.get('n4')) if hasattr(draw_row, 'get') else int(draw_row['n4']),
                    int(draw_row.get('n5')) if hasattr(draw_row, 'get') else int(draw_row['n5'])]
        except Exception:
            return []

        # Validate range and uniqueness
        if any(n < 1 or n > 69 for n in nums):
            return []
        if len(set(nums)) != 5:
            return []

        return sorted(nums)

    def calculate_cooccurrence_matrix(self) -> np.ndarray:
        """
        Calculate 69x69 matrix of how often number pairs appear together.
        
        Returns:
            np.ndarray: Symmetric matrix where [i][j] = count of times i and j appeared together
        """
        matrix = np.zeros((69, 69), dtype=int)

        # Use safe accessor to avoid invalid historical entries
        total = len(self.draws_df)
        for idx, (_, draw) in enumerate(self.draws_df.iterrows(), start=1):
            numbers = self._safe_get_numbers(draw)
            if not numbers:
                continue

            # For each pair in this draw
            for i in range(len(numbers)):
                for j in range(i + 1, len(numbers)):
                    num_a = min(numbers[i], numbers[j]) - 1  # 0-indexed
                    num_b = max(numbers[i], numbers[j]) - 1
                    matrix[num_a][num_b] += 1
                    matrix[num_b][num_a] += 1  # Symmetric

            # Progress logging for long runs
            if idx % 100 == 0 or idx == total:
                logger.info(f"Co-occurrence progress: processed {idx}/{total} draws")

        logger.info("Co-occurrence matrix calculated")
        return matrix

    def save_cooccurrence_to_db(self):
        """Save co-occurrence data to database with statistical analysis"""
        matrix = self.calculate_cooccurrence_matrix()
        total_draws = len(self.draws_df)

        if total_draws == 0:
            logger.warning("Cannot calculate co-occurrence: no draws available")
            return

        # Expected frequency for each pair (without replacement probability)
        # P(both A and B in same draw) = (5/69) * (4/68)
        expected_per_pair = (5/69) * (4/68) * total_draws

        conn = get_db_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM cooccurrences")

        records = []
        for i in range(69):
            for j in range(i + 1, 69):  # Only upper triangle (avoid duplicates)
                count = int(matrix[i][j])
                expected = expected_per_pair
                deviation_pct = ((count - expected) / expected * 100) if expected > 0 else 0
                is_significant = abs(deviation_pct) > 20  # >20% deviation is significant

                records.append((
                    i + 1, j + 1, count, expected, deviation_pct, is_significant
                ))

        cursor.executemany("""
            INSERT INTO cooccurrences (number_a, number_b, count, expected, deviation_pct, is_significant)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)

        conn.commit()
        conn.close()
        logger.info(f"Saved {len(records)} co-occurrence pairs to database")

    def calculate_pattern_statistics(self) -> Dict[str, Dict]:
        """
        Analyze patterns in draws: sum, range, gaps, distribution.
        
        Returns:
            Dict with statistics for each pattern type
        """
        if self.draws_df.empty:
            logger.warning("Cannot calculate patterns: no draws available")
            return {}

        patterns = {}

        # 1. Sum distribution (sum of 5 white balls)
        sums = []
        for _, draw in self.draws_df.iterrows():
            total = draw['n1'] + draw['n2'] + draw['n3'] + draw['n4'] + draw['n5']
            sums.append(total)

        patterns['sum'] = {
            'mean': float(np.mean(sums)),
            'std': float(np.std(sums)),
            'min': int(np.min(sums)),
            'max': int(np.max(sums)),
            'typical_range': (float(np.percentile(sums, 16)), float(np.percentile(sums, 84)))  # ±1σ
        }

        # 2. Range distribution (max - min)
        ranges = []
        for _, draw in self.draws_df.iterrows():
            r = draw['n5'] - draw['n1']
            ranges.append(r)

        patterns['range'] = {
            'mean': float(np.mean(ranges)),
            'std': float(np.std(ranges)),
            'typical_range': (float(np.percentile(ranges, 16)), float(np.percentile(ranges, 84)))
        }

        # 3. Gap analysis (average spacing between consecutive numbers)
        gaps = []
        for _, draw in self.draws_df.iterrows():
            numbers = [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]
            draw_gaps = [numbers[i+1] - numbers[i] for i in range(4)]
            gaps.append(np.mean(draw_gaps))

        patterns['gaps'] = {
            'mean': float(np.mean(gaps)),
            'std': float(np.std(gaps)),
            'typical_range': (float(np.percentile(gaps, 16)), float(np.percentile(gaps, 84)))
        }

        # 4. Low/Mid/High distribution (1-23 low, 24-46 mid, 47-69 high)
        distributions = {'low': [], 'mid': [], 'high': []}
        for _, draw in self.draws_df.iterrows():
            numbers = [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]
            low = sum(1 for n in numbers if n <= 23)
            mid = sum(1 for n in numbers if 24 <= n <= 46)
            high = sum(1 for n in numbers if n >= 47)
            distributions['low'].append(low)
            distributions['mid'].append(mid)
            distributions['high'].append(high)

        patterns['distribution'] = {
            'low_mean': float(np.mean(distributions['low'])),
            'mid_mean': float(np.mean(distributions['mid'])),
            'high_mean': float(np.mean(distributions['high']))
        }

        logger.info("Pattern statistics calculated")
        return patterns

    def save_patterns_to_db(self):
        """Save pattern statistics to database"""
        patterns = self.calculate_pattern_statistics()

        if not patterns:
            logger.warning("No patterns to save")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Log era distribution for pattern analysis
        current_era_count = len(self.draws_df[
            (self.draws_df['pb'] >= 1) & (self.draws_df['pb'] <= 26)
        ])
        logger.info(f"Pattern analysis using {len(self.draws_df)} draws ({current_era_count} current-era for PB-specific patterns)")

        cursor.execute("DELETE FROM pattern_stats")

        records = []

        # Sum patterns
        for percentile in [10, 25, 50, 75, 90]:
            sums = [d['n1']+d['n2']+d['n3']+d['n4']+d['n5'] for _, d in self.draws_df.iterrows()]
            _ = np.percentile(sums, percentile)
            records.append(('sum', f'p{percentile}', 0, percentile/100, True,
                          patterns['sum']['mean'], patterns['sum']['std']))

        # Range patterns
        records.append(('range', 'mean', 0, 0, True,
                       patterns['range']['mean'], patterns['range']['std']))

        # Gap patterns
        records.append(('gaps', 'mean', 0, 0, True,
                       patterns['gaps']['mean'], patterns['gaps']['std']))

        # Distribution patterns
        records.append(('distribution', 'low_mean', 0, 0, True,
                       patterns['distribution']['low_mean'], 0))
        records.append(('distribution', 'mid_mean', 0, 0, True,
                       patterns['distribution']['mid_mean'], 0))
        records.append(('distribution', 'high_mean', 0, 0, True,
                       patterns['distribution']['high_mean'], 0))

        cursor.executemany("""
            INSERT INTO pattern_stats (pattern_type, pattern_value, frequency, percentage, 
                                      is_typical, mean_value, std_dev)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, records)

        conn.commit()
        conn.close()
        logger.info(f"Saved {len(records)} pattern statistics to database")


def compute_gap_analysis(df: pd.DataFrame) -> Dict[str, Dict[int, int]]:
    """
    Calculate days since last appearance for each number.
    
    Args:
        df: DataFrame with draw_date, n1-n5 (white balls), and pb (powerball) columns
        
    Returns:
        Dict with 'white_balls' and 'powerball' keys, each mapping number to gap in days
        Example: {'white_balls': {1: 14, 2: 7, ...}, 'powerball': {1: 21, 2: 3, ...}}
    """
    if df.empty:
        logger.warning("Empty dataframe provided to compute_gap_analysis")
        # Return default gaps (all numbers equally overdue)
        return {
            'white_balls': {i: 0 for i in range(1, 70)},
            'powerball': {i: 0 for i in range(1, 27)}
        }
    
    # Ensure draw_date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['draw_date']):
        df = df.copy()
        df['draw_date'] = pd.to_datetime(df['draw_date'])
    
    # Get the most recent draw date
    most_recent_date = df['draw_date'].max()
    
    # Initialize gap tracking (last seen date for each number)
    white_ball_last_seen = {}
    powerball_last_seen = {}
    
    # Process draws in chronological order
    for _, draw in df.iterrows():
        draw_date = draw['draw_date']
        
        # Track white balls
        for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
            white_ball_last_seen[int(num)] = draw_date
        
        # Track powerball (only current era: 1-26)
        pb = int(draw['pb'])
        if 1 <= pb <= 26:
            powerball_last_seen[pb] = draw_date
    
    # Calculate gaps in days
    white_ball_gaps = {}
    for num in range(1, 70):
        if num in white_ball_last_seen:
            gap = (most_recent_date - white_ball_last_seen[num]).days
            white_ball_gaps[num] = gap
        else:
            # Never appeared in dataset
            white_ball_gaps[num] = 999  # Large number to indicate very overdue
    
    powerball_gaps = {}
    for num in range(1, 27):
        if num in powerball_last_seen:
            gap = (most_recent_date - powerball_last_seen[num]).days
            powerball_gaps[num] = gap
        else:
            powerball_gaps[num] = 999
    
    logger.debug(f"Gap analysis complete: {len(white_ball_gaps)} white balls, {len(powerball_gaps)} powerballs")
    return {
        'white_balls': white_ball_gaps,
        'powerball': powerball_gaps
    }


def compute_temporal_frequencies(df: pd.DataFrame, decay_rate: float = 0.05) -> Dict[str, np.ndarray]:
    """
    Calculate weighted frequency where recent draws matter more.
    
    Uses exponential decay: weight = exp(-decay_rate * days_ago)
    
    Args:
        df: DataFrame with draw_date, n1-n5, and pb columns
        decay_rate: Decay rate for exponential weighting (default 0.05)
        
    Returns:
        Dict with 'white_balls' (69-element array) and 'powerball' (26-element array)
        containing normalized probability distributions
    """
    if df.empty:
        logger.warning("Empty dataframe provided to compute_temporal_frequencies")
        return {
            'white_balls': np.ones(69) / 69,  # Uniform distribution
            'powerball': np.ones(26) / 26
        }
    
    # Ensure draw_date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['draw_date']):
        df = df.copy()
        df['draw_date'] = pd.to_datetime(df['draw_date'])
    
    # Get the most recent draw date
    most_recent_date = df['draw_date'].max()
    
    # Initialize weighted frequency counters
    white_ball_freq = np.zeros(69)
    powerball_freq = np.zeros(26)
    
    # Process each draw with exponential decay weight
    for _, draw in df.iterrows():
        days_ago = (most_recent_date - draw['draw_date']).days
        weight = np.exp(-decay_rate * days_ago)
        
        # Weight white balls
        for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
            if 1 <= num <= 69:
                white_ball_freq[int(num) - 1] += weight
        
        # Weight powerball (current era only)
        pb = int(draw['pb'])
        if 1 <= pb <= 26:
            powerball_freq[pb - 1] += weight
    
    # Normalize to probabilities
    wb_total = white_ball_freq.sum()
    if wb_total > 0:
        white_ball_freq = white_ball_freq / wb_total
    else:
        white_ball_freq = np.ones(69) / 69
    
    pb_total = powerball_freq.sum()
    if pb_total > 0:
        powerball_freq = powerball_freq / pb_total
    else:
        powerball_freq = np.ones(26) / 26
    
    logger.debug(f"Temporal frequencies computed with decay_rate={decay_rate}")
    return {
        'white_balls': white_ball_freq,
        'powerball': powerball_freq
    }


def compute_momentum_scores(df: pd.DataFrame, window: int = 20) -> Dict[str, Dict[int, float]]:
    """
    Compare frequency in recent draws vs previous draws to identify rising/falling numbers.
    
    Momentum score ranges from -1.0 (falling) to +1.0 (rising).
    
    Args:
        df: DataFrame with draw_date, n1-n5, and pb columns
        window: Total window size (default 20). Compares last window/2 vs previous window/2 draws
        
    Returns:
        Dict with 'white_balls' and 'powerball' keys, each mapping number to momentum score
        Example: {'white_balls': {1: 0.5, 2: -0.3, ...}, 'powerball': {1: 0.8, ...}}
    """
    if df.empty or len(df) < window:
        logger.warning(f"Insufficient data for momentum analysis (need {window} draws, have {len(df)})")
        # Return neutral momentum (0.0) for all numbers
        return {
            'white_balls': {i: 0.0 for i in range(1, 70)},
            'powerball': {i: 0.0 for i in range(1, 27)}
        }
    
    # Ensure chronological order
    df = df.sort_values('draw_date').reset_index(drop=True)
    
    half_window = window // 2
    
    # Get recent and previous windows
    recent_draws = df.tail(half_window)
    previous_draws = df.tail(window).head(half_window)
    
    # Count frequencies in each window
    def count_frequencies(draws_subset):
        wb_counts = np.zeros(69)
        pb_counts = np.zeros(26)
        
        for _, draw in draws_subset.iterrows():
            for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
                if 1 <= num <= 69:
                    wb_counts[int(num) - 1] += 1
            
            pb = int(draw['pb'])
            if 1 <= pb <= 26:
                pb_counts[pb - 1] += 1
        
        return wb_counts, pb_counts
    
    recent_wb, recent_pb = count_frequencies(recent_draws)
    previous_wb, previous_pb = count_frequencies(previous_draws)
    
    # Calculate momentum scores
    # Momentum = (recent_freq - previous_freq) / (recent_freq + previous_freq + epsilon)
    # This gives a score between -1 and +1
    epsilon = 0.1  # Small constant to avoid division by zero
    
    white_ball_momentum = {}
    for num in range(1, 70):
        idx = num - 1
        momentum = (recent_wb[idx] - previous_wb[idx]) / (recent_wb[idx] + previous_wb[idx] + epsilon)
        white_ball_momentum[num] = float(momentum)
    
    powerball_momentum = {}
    for num in range(1, 27):
        idx = num - 1
        momentum = (recent_pb[idx] - previous_pb[idx]) / (recent_pb[idx] + previous_pb[idx] + epsilon)
        powerball_momentum[num] = float(momentum)
    
    logger.debug(f"Momentum scores computed with window={window}")
    return {
        'white_balls': white_ball_momentum,
        'powerball': powerball_momentum
    }


def get_analytics_overview() -> Dict[str, Any]:
    """
    Facade function that consolidates all analytics for dashboard display.
    
    Returns:
        Dict containing gap_analysis, temporal_frequencies, momentum_scores,
        and traditional pattern statistics
    """
    logger.info("Computing analytics overview...")
    
    try:
        # Fetch historical data
        df = get_all_draws()
        
        if df.empty:
            logger.warning("No historical data available for analytics overview")
            return {
                'gap_analysis': {'white_balls': {}, 'powerball': {}},
                'temporal_frequencies': {'white_balls': [], 'powerball': []},
                'momentum_scores': {'white_balls': {}, 'powerball': {}},
                'pattern_statistics': {},
                'data_summary': {
                    'total_draws': 0,
                    'most_recent_date': None,
                    'current_era_draws': 0
                }
            }
        
        # Compute new analytics
        gap_analysis = compute_gap_analysis(df)
        temporal_frequencies = compute_temporal_frequencies(df, decay_rate=0.05)
        momentum_scores = compute_momentum_scores(df, window=20)
        
        # Get traditional pattern statistics
        engine = AnalyticsEngine()
        pattern_statistics = engine.calculate_pattern_statistics()
        
        # Data summary
        current_era_count = len(df[(df['pb'] >= 1) & (df['pb'] <= 26)])
        most_recent_date = df['draw_date'].max() if not df.empty else None
        
        overview = {
            'gap_analysis': gap_analysis,
            'temporal_frequencies': {
                'white_balls': temporal_frequencies['white_balls'].tolist(),
                'powerball': temporal_frequencies['powerball'].tolist()
            },
            'momentum_scores': momentum_scores,
            'pattern_statistics': pattern_statistics,
            'data_summary': {
                'total_draws': len(df),
                'most_recent_date': str(most_recent_date) if most_recent_date else None,
                'current_era_draws': current_era_count
            }
        }
        
        logger.info("Analytics overview computed successfully")
        return overview
        
    except Exception as e:
        logger.error(f"Error computing analytics overview: {e}")
        return {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'temporal_frequencies': {'white_balls': [], 'powerball': []},
            'momentum_scores': {'white_balls': {}, 'powerball': {}},
            'pattern_statistics': {},
            'data_summary': {
                'total_draws': 0,
                'most_recent_date': None,
                'current_era_draws': 0
            },
            'error': str(e)
        }


def update_analytics():
    """Main function to update all analytics tables"""
    logger.info("Starting analytics update...")

    try:
        engine = AnalyticsEngine()
        engine.save_cooccurrence_to_db()
        engine.save_patterns_to_db()
        logger.info("All analytics updated successfully")
        return True
    except Exception as e:
        logger.error(f"Analytics update failed: {e}")
        return False
