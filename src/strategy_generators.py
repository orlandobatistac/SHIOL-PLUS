"""
SHIOL+ Strategy Generators
===========================
Six different strategies for intelligent ticket generation.
"""

import numpy as np
import random
from typing import List, Dict, Tuple
from loguru import logger
from src.database import get_db_connection, get_all_draws


class BaseStrategy:
    """Base class for all ticket generation strategies"""

    def __init__(self, name: str):
        self.name = name
        self.draws_df = get_all_draws()

        if self.draws_df.empty:
            logger.warning(f"Strategy {name}: No historical data available")

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets. Must be implemented by subclasses"""
        raise NotImplementedError(f"Strategy {self.name} must implement generate()")

    def validate_ticket(self, white_balls: List[int], powerball: int) -> bool:
        """Validate ticket constraints"""
        if len(white_balls) != 5:
            return False
        if len(set(white_balls)) != 5:  # No duplicates
            return False
        if not all(1 <= n <= 69 for n in white_balls):
            return False
        if not 1 <= powerball <= 26:
            return False
        return True


class FrequencyWeightedStrategy(BaseStrategy):
    """Generate tickets using most frequent numbers with weighted probability"""

    def __init__(self):
        super().__init__("frequency_weighted")
        self.frequencies = self._calculate_frequencies()

    def _calculate_frequencies(self) -> np.ndarray:
        """Calculate normalized frequency of each number 1-69"""
        freq = np.zeros(69)

        if self.draws_df.empty:
            # Uniform distribution if no data
            return np.ones(69) / 69

        for _, draw in self.draws_df.iterrows():
            for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
                freq[num - 1] += 1

        # Normalize to probabilities
        total = freq.sum()
        if total > 0:
            freq = freq / total
        else:
            freq = np.ones(69) / 69

        return freq

    def _calculate_pb_frequencies(self) -> np.ndarray:
        """Calculate Powerball frequencies using only current-era draws (PB 1-26)"""
        freq = np.zeros(26)

        if self.draws_df.empty:
            return np.ones(26) / 26

        # Filter to current era (pb between 1-26)
        current_era_draws = self.draws_df[
            (self.draws_df['pb'] >= 1) & (self.draws_df['pb'] <= 26)
        ]

        skipped_historical = len(self.draws_df) - len(current_era_draws)

        if current_era_draws.empty:
            logger.warning("No current-era draws found, using uniform distribution")
            return np.ones(26) / 26

        # Log once instead of per-row
        if skipped_historical > 0:
            logger.info(f"Using {len(current_era_draws)} current-era draws for PB frequencies "
                       f"(skipped {skipped_historical} historical draws from 2009-2015)")

        # Count frequencies
        for _, draw in current_era_draws.iterrows():
            pb = draw['pb']
            if 1 <= pb <= 26:
                freq[pb - 1] += 1

        # Normalize
        total = freq.sum()
        if total > 0:
            return freq / total
        else:
            return np.ones(26) / 26

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets favoring frequent numbers"""
        tickets = []
        # Precompute PB frequencies once to avoid repeated logging
        pb_freq = self._calculate_pb_frequencies()

        for _ in range(count):
            try:
                # Sample white balls without replacement using frequencies as weights
                white_balls = sorted(np.random.choice(
                    range(1, 70),
                    size=5,
                    replace=False,
                    p=self.frequencies
                ).tolist())

                # Powerball with frequencies (FIXED VERSION)
                # Validate and normalize
                if pb_freq.sum() == 0 or len(pb_freq) != 26:
                    # Fallback to uniform if invalid
                    powerball = random.randint(1, 26)
                else:
                    # Normalize to ensure sum = 1.0
                    pb_freq_normalized = pb_freq / pb_freq.sum()
                    powerball = int(np.random.choice(range(1, 27), p=pb_freq_normalized))

                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.75
                })

            except Exception as e:
                logger.error(f"{self.name} generation failed: {e}, using fallback")
                # Complete fallback
                white_balls = sorted(random.sample(range(1, 70), 5))
                powerball = random.randint(1, 26)
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.50
                })

        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets


class CoverageOptimizerStrategy(BaseStrategy):
    """Maximize unique numbers across all tickets"""

    def __init__(self):
        super().__init__("coverage_optimizer")

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets maximizing number coverage"""
        tickets = []
        used_numbers = set()

        for _ in range(count):
            # Avoid previously used numbers
            available = [n for n in range(1, 70) if n not in used_numbers]

            if len(available) < 5:
                # Reset if not enough numbers remain
                used_numbers = set()
                available = list(range(1, 70))

            white_balls = sorted(random.sample(available, 5))
            used_numbers.update(white_balls)

            powerball = random.randint(1, 26)

            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.70
            })

        logger.debug(f"{self.name}: Generated {count} tickets with {len(used_numbers)} unique numbers")
        return tickets


class CooccurrenceStrategy(BaseStrategy):
    """Use number pairs that frequently appear together"""

    def __init__(self):
        super().__init__("cooccurrence")
        self.strong_pairs = self._get_strong_pairs()

    def _get_strong_pairs(self) -> List[Tuple[int, int]]:
        """Get pairs with significant positive deviation (>20%)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT number_a, number_b
                FROM cooccurrences
                WHERE is_significant = TRUE AND deviation_pct > 20
                ORDER BY deviation_pct DESC
                LIMIT 50
            """)

            pairs = [(row[0], row[1]) for row in cursor.fetchall()]
            conn.close()

            if not pairs:
                logger.warning("No significant co-occurrence pairs found, using fallback")
                return [(i, i+10) for i in range(1, 60, 10)]  # Fallback pairs

            return pairs
        except Exception as e:
            logger.error(f"Error fetching co-occurrence pairs: {e}")
            return [(1, 11), (5, 15), (10, 20), (20, 30), (30, 40)]  # Fallback

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate using strong co-occurrence pairs"""
        tickets = []

        for _ in range(count):
            # Start with a strong pair
            if self.strong_pairs:
                pair = random.choice(self.strong_pairs)
                white_balls = list(pair)
            else:
                white_balls = random.sample(range(1, 70), 2)

            # Fill remaining 3 numbers
            available = [n for n in range(1, 70) if n not in white_balls]
            white_balls.extend(random.sample(available, 3))
            white_balls.sort()

            powerball = random.randint(1, 26)

            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.65
            })

        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets


class RangeBalancedStrategy(BaseStrategy):
    """Generate with balanced distribution: 2 low, 2 mid, 1 high"""

    def __init__(self):
        super().__init__("range_balanced")

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate with typical low/mid/high distribution"""
        tickets = []

        for _ in range(count):
            try:
                low = random.sample(range(1, 24), 2)     # 1-23
                mid = random.sample(range(24, 47), 2)    # 24-46
                high = random.sample(range(47, 70), 1)   # 47-69

                white_balls = sorted(low + mid + high)
                powerball = random.randint(1, 26)

                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.68
                })
            except ValueError as e:
                logger.error(f"Error in range sampling: {e}")
                # Fallback to pure random
                white_balls = sorted(random.sample(range(1, 70), 5))
                powerball = random.randint(1, 26)
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.50
                })

        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets


class AIGuidedStrategy(BaseStrategy):
    """Use existing ML model predictions (backward compatibility)"""

    def __init__(self):
        super().__init__("ai_guided")

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate using existing IntelligentGenerator"""
        tickets = []

        try:
            from src.intelligent_generator import IntelligentGenerator
            # Try to instantiate IntelligentGenerator with zero args first; if it requires historical_data, handle gracefully
            try:
                gen = IntelligentGenerator()
            except TypeError:
                try:
                    # Try passing draws from DB if available
                    historical = self.draws_df if hasattr(self, 'draws_df') else None
                    gen = IntelligentGenerator(historical)
                except Exception as inner_e:
                    logger.error(f"IntelligentGenerator instantiation failed: {inner_e}")
                    raise

            for _ in range(count):
                try:
                    prediction = gen.generate_smart_play()

                    tickets.append({
                        'white_balls': sorted(prediction['numbers']),
                        'powerball': prediction['powerball'],
                        'strategy': self.name,
                        'confidence': prediction.get('score', 0.80)
                    })
                except Exception as e:
                    logger.error(f"ML prediction failed: {e}, using fallback")
                    # Fallback to random
                    white_balls = sorted(random.sample(range(1, 70), 5))
                    powerball = random.randint(1, 26)
                    tickets.append({
                        'white_balls': white_balls,
                        'powerball': powerball,
                        'strategy': self.name,
                        'confidence': 0.50
                    })
        except ImportError as e:
            logger.error(f"Cannot import IntelligentGenerator: {e}")
            # Pure fallback
            for _ in range(count):
                white_balls = sorted(random.sample(range(1, 70), 5))
                powerball = random.randint(1, 26)
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.50
                })

        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets


class RandomBaselineStrategy(BaseStrategy):
    """Pure random generation (scientific control baseline)"""

    def __init__(self):
        super().__init__("random_baseline")

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate completely random tickets"""
        tickets = []

        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)

            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.50
            })

        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets


class StrategyManager:
    """
    Manages all 6 strategies and selects which to use based on adaptive weights.
    
    Uses Bayesian weight updating based on historical performance.
    """

    def __init__(self):
        self.strategies = {
            'frequency_weighted': FrequencyWeightedStrategy(),
            'coverage_optimizer': CoverageOptimizerStrategy(),
            'cooccurrence': CooccurrenceStrategy(),
            'range_balanced': RangeBalancedStrategy(),
            'ai_guided': AIGuidedStrategy(),
            'random_baseline': RandomBaselineStrategy()
        }

        self._initialize_strategy_weights()
        logger.info(f"StrategyManager initialized with {len(self.strategies)} strategies")

    def _initialize_strategy_weights(self):
        """Initialize strategy_performance table with equal weights (1/6 each)"""
        conn = get_db_connection()
        cursor = conn.cursor()

        for name in self.strategies.keys():
            cursor.execute("""
                INSERT OR IGNORE INTO strategy_performance 
                (strategy_name, current_weight, confidence)
                VALUES (?, 0.1667, 0.5)
            """, (name,))

        conn.commit()
        conn.close()
        logger.debug("Strategy weights initialized")

    def get_strategy_weights(self) -> Dict[str, float]:
        """Get current adaptive weights from database"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT strategy_name, current_weight FROM strategy_performance")
        weights = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        # Ensure all strategies have weights
        for name in self.strategies.keys():
            if name not in weights:
                weights[name] = 0.1667

        return weights

    def generate_balanced_tickets(self, total: int = 5) -> List[Dict]:
        """
        Generate tickets using weighted strategy selection.
        
        Each strategy is chosen proportionally to its adaptive weight.
        Ensures 5 different Powerballs across all tickets.
        
        Args:
            total: Number of tickets to generate (default 5)
            
        Returns:
            List of ticket dictionaries
        """
        weights = self.get_strategy_weights()

        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            normalized = {k: v/total_weight for k, v in weights.items()}
        else:
            # Fallback to equal weights
            normalized = {k: 1/len(weights) for k in weights.keys()}

        # Select strategies proportionally
        try:
            selected = np.random.choice(
                list(normalized.keys()),
                size=total,
                p=list(normalized.values()),
                replace=True
            )
        except ValueError as e:
            logger.error(f"Error in strategy selection: {e}, using uniform")
            selected = np.random.choice(list(self.strategies.keys()), size=total)

        # Generate one ticket per selected strategy
        all_tickets = []
        for strategy_name in selected:
            try:
                tickets = self.strategies[strategy_name].generate(1)
                all_tickets.extend(tickets)
            except Exception as e:
                logger.error(f"Strategy {strategy_name} failed: {e}")
                # Fallback to random
                fallback = RandomBaselineStrategy().generate(1)
                all_tickets.extend(fallback)

        # Ensure 5 different Powerballs
        all_tickets = self._ensure_different_powerballs(all_tickets[:total])

        logger.info(f"Generated {len(all_tickets)} tickets with balanced strategies")
        return all_tickets

    def _ensure_different_powerballs(self, tickets: List[Dict]) -> List[Dict]:
        """Modify Powerballs to ensure all are unique"""
        used_pbs = set()

        for ticket in tickets:
            attempts = 0
            while ticket['powerball'] in used_pbs and attempts < 26:
                ticket['powerball'] = random.randint(1, 26)
                attempts += 1

            used_pbs.add(ticket['powerball'])

        return tickets

    def get_strategy_summary(self) -> Dict[str, Dict]:
        """Get performance summary of all strategies"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT strategy_name, total_plays, total_wins, win_rate, 
                   roi, current_weight, confidence
            FROM strategy_performance
            ORDER BY roi DESC
        """)

        summary = {}
        for row in cursor.fetchall():
            summary[row[0]] = {
                'total_plays': row[1],
                'total_wins': row[2],
                'win_rate': row[3],
                'roi': row[4],
                'current_weight': row[5],
                'confidence': row[6]
            }

        conn.close()
        return summary
