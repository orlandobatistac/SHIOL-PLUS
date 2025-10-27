"""
SHIOL+ Analytics Engine
=======================
Advanced statistical analysis for Powerball historical data.
"""

import numpy as np
from loguru import logger
from typing import Dict
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
