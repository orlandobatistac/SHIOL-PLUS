"""
SHIOL+ Strategy Generators
===========================
Six different strategies for intelligent ticket generation.
"""

import numpy as np
import random
from typing import List, Dict, Tuple, Any
from loguru import logger
from src.database import get_db_connection, get_all_draws


class BaseStrategy:
    """Base class for all ticket generation strategies"""

    def __init__(self, name: str, max_date: str = None):
        self.name = name
        self.max_date = max_date
        self.draws_df = get_all_draws(max_date=max_date)

        if self.draws_df.empty:
            logger.warning(f"Strategy {name}: No historical data available")
        elif max_date:
            logger.debug(f"Strategy {name}: Loaded {len(self.draws_df)} draws before {max_date}")

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

    def __init__(self, max_date: str = None):
        super().__init__("frequency_weighted", max_date=max_date)
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

    def __init__(self, max_date: str = None):
        super().__init__("coverage_optimizer", max_date=max_date)

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

    def __init__(self, max_date: str = None):
        super().__init__("cooccurrence", max_date=max_date)
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

    def __init__(self, max_date: str = None):
        super().__init__("range_balanced", max_date=max_date)

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
    """Use ML model (XGBoost) predictions for intelligent ticket generation"""

    def __init__(self, max_date: str = None):
        super().__init__("ai_guided", max_date=max_date)
        self._predictor = None
        self._ml_available = self._initialize_ml_predictor()

    def _initialize_ml_predictor(self) -> bool:
        """Initialize the ML predictor. Returns True if successful."""
        try:
            from src.predictor import Predictor
            self._predictor = Predictor()
            
            # Verify model is loaded
            if self._predictor.model is not None:
                logger.info(f"{self.name}: XGBoost ML model loaded successfully")
                return True
            else:
                logger.warning(f"{self.name}: ML model not available, will use fallback")
                return False
        except Exception as e:
            logger.warning(f"{self.name}: Could not initialize ML predictor: {e}")
            return False

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using XGBoost ML model probabilities"""
        tickets = []

        # Try ML-guided generation first
        if self._ml_available and self._predictor is not None:
            try:
                # Get probability predictions from ML model
                wb_probs, pb_probs = self._predictor.predict_probabilities(use_ensemble=False)
                
                logger.info(f"{self.name}: Successfully obtained ML probabilities")
                
                # Generate tickets using ML probabilities
                for _ in range(count):
                    try:
                        # Sample white balls using ML probabilities
                        white_balls = sorted(np.random.choice(
                            range(1, 70),
                            size=5,
                            replace=False,
                            p=wb_probs
                        ).tolist())
                        
                        # Sample powerball using ML probabilities
                        powerball = int(np.random.choice(range(1, 27), p=pb_probs))
                        
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.85  # Higher confidence since using ML
                        })
                        
                    except Exception as e:
                        logger.error(f"{self.name}: Error generating ticket with ML probs: {e}")
                        # Fallback to random for this ticket
                        white_balls = sorted(random.sample(range(1, 70), 5))
                        powerball = random.randint(1, 26)
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.50
                        })
                
                logger.info(f"{self.name}: Generated {len(tickets)} tickets using ML model")
                return tickets
                
            except Exception as e:
                logger.error(f"{self.name}: ML prediction pipeline failed: {e}, using fallback")
                # Continue to fallback below

        # Fallback: Use IntelligentGenerator (frequency-based)
        try:
            from src.intelligent_generator import IntelligentGenerator
            
            try:
                gen = IntelligentGenerator()
            except TypeError:
                # Try passing historical data if required
                historical = self.draws_df if hasattr(self, 'draws_df') else None
                gen = IntelligentGenerator(historical)

            for _ in range(count):
                try:
                    prediction = gen.generate_smart_play()

                    tickets.append({
                        'white_balls': sorted(prediction['numbers']),
                        'powerball': prediction['powerball'],
                        'strategy': self.name,
                        'confidence': prediction.get('score', 0.70)
                    })
                except Exception as e:
                    logger.error(f"{self.name}: IntelligentGenerator failed: {e}")
                    white_balls = sorted(random.sample(range(1, 70), 5))
                    powerball = random.randint(1, 26)
                    tickets.append({
                        'white_balls': white_balls,
                        'powerball': powerball,
                        'strategy': self.name,
                        'confidence': 0.50
                    })
                    
        except ImportError as e:
            logger.error(f"{self.name}: Cannot import IntelligentGenerator: {e}")
            # Final fallback to pure random
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

    def __init__(self, max_date: str = None):
        super().__init__("random_baseline", max_date=max_date)

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


class XGBoostMLStrategy(BaseStrategy):
    """Generate tickets using XGBoost ML model from predictor.py"""

    def __init__(self, max_date: str = None):
        super().__init__("xgboost_ml", max_date=max_date)
        self._predictor = None
        self._ml_available = self._initialize_ml_predictor()

    def _initialize_ml_predictor(self) -> bool:
        """Initialize the XGBoost predictor. Returns True if successful."""
        try:
            from src.predictor import Predictor
            self._predictor = Predictor()
            
            # Verify model is loaded
            if self._predictor.model is not None:
                logger.info(f"{self.name}: XGBoost ML model loaded successfully")
                return True
            else:
                logger.warning(f"{self.name}: ML model not available, will use fallback")
                return False
        except Exception as e:
            logger.warning(f"{self.name}: Could not initialize ML predictor: {e}")
            return False

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using XGBoost ML model probabilities"""
        tickets = []

        # Try ML-guided generation first
        if self._ml_available and self._predictor is not None:
            try:
                # Get probability predictions from XGBoost model (use_ensemble=False for pure XGBoost)
                wb_probs, pb_probs = self._predictor.predict_probabilities(use_ensemble=False)
                
                logger.debug(f"{self.name}: Successfully obtained XGBoost ML probabilities")
                
                # Generate tickets using ML probabilities
                for _ in range(count):
                    try:
                        # Sample white balls using ML probabilities
                        white_balls = sorted(np.random.choice(
                            range(1, 70),
                            size=5,
                            replace=False,
                            p=wb_probs
                        ).tolist())
                        
                        # Sample powerball using ML probabilities
                        powerball = int(np.random.choice(range(1, 27), p=pb_probs))
                        
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.85  # Higher confidence since using ML
                        })
                        
                    except Exception as e:
                        logger.error(f"{self.name}: Error generating ticket with ML probs: {e}")
                        # Fallback to random for this ticket
                        white_balls = sorted(random.sample(range(1, 70), 5))
                        powerball = random.randint(1, 26)
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.50
                        })
                
                logger.debug(f"{self.name}: Generated {len(tickets)} tickets using XGBoost ML model")
                return tickets
                
            except Exception as e:
                logger.error(f"{self.name}: ML prediction pipeline failed: {e}, using fallback")
                # Continue to fallback below

        # Fallback to random if ML not available
        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.50
            })

        logger.debug(f"{self.name}: Generated {count} tickets (fallback mode)")
        return tickets


class RandomForestMLStrategy(BaseStrategy):
    """Generate tickets using Random Forest ML model"""

    def __init__(self, max_date: str = None):
        super().__init__("random_forest_ml", max_date=max_date)
        self._rf_model = None
        self._ml_available = self._initialize_rf_model()

    def _initialize_rf_model(self) -> bool:
        """Initialize the Random Forest model. Returns True if successful."""
        try:
            from src.ml_models.random_forest_model import RandomForestModel
            self._rf_model = RandomForestModel(use_pretrained=True)
            
            # Verify models are loaded
            if self._rf_model.wb_models and self._rf_model.pb_model:
                logger.info(f"{self.name}: Random Forest models loaded successfully")
                return True
            else:
                logger.warning(f"{self.name}: RF models not available, will use fallback")
                return False
        except Exception as e:
            logger.warning(f"{self.name}: Could not initialize RF model: {e}")
            return False

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using Random Forest model probabilities"""
        tickets = []

        # Try RF-guided generation first
        if self._ml_available and self._rf_model is not None:
            try:
                # Get probability predictions from Random Forest model
                wb_probs, pb_probs = self._rf_model.predict_probabilities(self.draws_df)
                
                logger.debug(f"{self.name}: Successfully obtained Random Forest probabilities")
                
                # Generate tickets using RF probabilities
                for _ in range(count):
                    try:
                        # Sample white balls using RF probabilities
                        white_balls = sorted(np.random.choice(
                            range(1, 70),
                            size=5,
                            replace=False,
                            p=wb_probs
                        ).tolist())
                        
                        # Sample powerball using RF probabilities
                        powerball = int(np.random.choice(range(1, 27), p=pb_probs))
                        
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.80  # High confidence for RF
                        })
                        
                    except Exception as e:
                        logger.error(f"{self.name}: Error generating ticket with RF probs: {e}")
                        # Fallback to random for this ticket
                        white_balls = sorted(random.sample(range(1, 70), 5))
                        powerball = random.randint(1, 26)
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.50
                        })
                
                logger.debug(f"{self.name}: Generated {len(tickets)} tickets using Random Forest")
                return tickets
                
            except Exception as e:
                logger.error(f"{self.name}: RF prediction pipeline failed: {e}, using fallback")
                # Continue to fallback below

        # Fallback to random if RF not available
        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.50
            })

        logger.debug(f"{self.name}: Generated {count} tickets (fallback mode)")
        return tickets


class LSTMNeuralStrategy(BaseStrategy):
    """Generate tickets using LSTM neural network model"""

    def __init__(self, max_date: str = None):
        super().__init__("lstm_neural", max_date=max_date)
        self._lstm_model = None
        self._ml_available = self._initialize_lstm_model()

    def _initialize_lstm_model(self) -> bool:
        """Initialize the LSTM model. Returns True if successful."""
        try:
            from src.ml_models.lstm_model import LSTMModel
            self._lstm_model = LSTMModel(use_pretrained=True)
            
            # Verify models are loaded
            if self._lstm_model.wb_model and self._lstm_model.pb_model:
                logger.info(f"{self.name}: LSTM models loaded successfully")
                return True
            else:
                logger.warning(f"{self.name}: LSTM models not available, will use fallback")
                return False
        except Exception as e:
            logger.warning(f"{self.name}: Could not initialize LSTM model: {e}")
            return False

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using LSTM model probabilities"""
        tickets = []

        # Try LSTM-guided generation first
        if self._ml_available and self._lstm_model is not None:
            try:
                # Get probability predictions from LSTM model
                wb_probs, pb_probs = self._lstm_model.predict_probabilities(self.draws_df)
                
                logger.debug(f"{self.name}: Successfully obtained LSTM probabilities")
                
                # Generate tickets using LSTM probabilities
                for _ in range(count):
                    try:
                        # Sample white balls using LSTM probabilities
                        white_balls = sorted(np.random.choice(
                            range(1, 70),
                            size=5,
                            replace=False,
                            p=wb_probs
                        ).tolist())
                        
                        # Sample powerball using LSTM probabilities
                        powerball = int(np.random.choice(range(1, 27), p=pb_probs))
                        
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.78  # High confidence for LSTM
                        })
                        
                    except Exception as e:
                        logger.error(f"{self.name}: Error generating ticket with LSTM probs: {e}")
                        # Fallback to random for this ticket
                        white_balls = sorted(random.sample(range(1, 70), 5))
                        powerball = random.randint(1, 26)
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.50
                        })
                
                logger.debug(f"{self.name}: Generated {len(tickets)} tickets using LSTM")
                return tickets
                
            except Exception as e:
                logger.error(f"{self.name}: LSTM prediction pipeline failed: {e}, using fallback")
                # Continue to fallback below

        # Fallback to random if LSTM not available
        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.50
            })

        logger.debug(f"{self.name}: Generated {count} tickets (fallback mode)")
        return tickets


class HybridEnsembleStrategy(BaseStrategy):
    """Hybrid strategy combining 70% XGBoost + 30% Cooccurrence"""

    def __init__(self, max_date: str = None):
        super().__init__("hybrid_ensemble", max_date=max_date)
        self._xgboost_strategy = XGBoostMLStrategy()
        self._cooccurrence_strategy = CooccurrenceStrategy()

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets by blending XGBoost (70%) and Cooccurrence (30%)"""
        tickets = []
        
        # Calculate split: 70% XGBoost, 30% Cooccurrence
        xgboost_count = int(count * 0.7)
        cooccurrence_count = count - xgboost_count
        
        # Generate from XGBoost
        if xgboost_count > 0:
            xgboost_tickets = self._xgboost_strategy.generate(xgboost_count)
            # Update strategy name to hybrid_ensemble
            for ticket in xgboost_tickets:
                ticket['strategy'] = self.name
                ticket['confidence'] = 0.82  # Slightly higher for hybrid
            tickets.extend(xgboost_tickets)
        
        # Generate from Cooccurrence
        if cooccurrence_count > 0:
            cooccurrence_tickets = self._cooccurrence_strategy.generate(cooccurrence_count)
            # Update strategy name to hybrid_ensemble
            for ticket in cooccurrence_tickets:
                ticket['strategy'] = self.name
                ticket['confidence'] = 0.82  # Slightly higher for hybrid
            tickets.extend(cooccurrence_tickets)
        
        logger.debug(f"{self.name}: Generated {len(tickets)} tickets (70% XGBoost + 30% Cooccurrence)")
        return tickets


class IntelligentScoringStrategy(BaseStrategy):
    """Generate tickets using multi-criteria intelligent scoring system"""

    def __init__(self, max_date: str = None):
        super().__init__("intelligent_scoring", max_date=max_date)
        self._generator = None
        self._generator_available = self._initialize_generator()

    def _initialize_generator(self) -> bool:
        """Initialize the IntelligentGenerator. Returns True if successful."""
        try:
            from src.intelligent_generator import IntelligentGenerator
            
            # Try initializing without parameters first
            try:
                self._generator = IntelligentGenerator()
            except TypeError:
                # If it requires historical data, pass it
                self._generator = IntelligentGenerator(self.draws_df)
            
            logger.info(f"{self.name}: IntelligentGenerator initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"{self.name}: Could not initialize IntelligentGenerator: {e}")
            return False

    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using intelligent multi-criteria scoring"""
        tickets = []

        # Try intelligent generation first
        if self._generator_available and self._generator is not None:
            try:
                for _ in range(count):
                    try:
                        prediction = self._generator.generate_smart_play()
                        
                        tickets.append({
                            'white_balls': sorted(prediction['numbers']),
                            'powerball': prediction['powerball'],
                            'strategy': self.name,
                            'confidence': prediction.get('score', 0.75)
                        })
                    except Exception as e:
                        logger.error(f"{self.name}: IntelligentGenerator failed: {e}")
                        # Fallback to random for this ticket
                        white_balls = sorted(random.sample(range(1, 70), 5))
                        powerball = random.randint(1, 26)
                        tickets.append({
                            'white_balls': white_balls,
                            'powerball': powerball,
                            'strategy': self.name,
                            'confidence': 0.50
                        })
                
                logger.debug(f"{self.name}: Generated {len(tickets)} tickets using IntelligentGenerator")
                return tickets
                
            except Exception as e:
                logger.error(f"{self.name}: Intelligent scoring failed: {e}, using fallback")
                # Continue to fallback below

        # Fallback to random if generator not available
        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.50
            })

        logger.debug(f"{self.name}: Generated {count} tickets (fallback mode)")
        return tickets


class CustomInteractiveGenerator(BaseStrategy):
    """
    Generate tickets based on user-defined parameters (risk, temperature, exclusions).
    
    This strategy allows interactive customization:
    - Risk level: How much to deviate from statistical norms
    - Temperature: Favor hot (recent) or cold (overdue) numbers
    - Exclusions: Numbers to avoid
    """
    
    def __init__(self, max_date: str = None):
        super().__init__("custom_interactive", max_date=max_date)
        self._analytics_cache = None
        
    def _get_analytics(self) -> Dict[str, Any]:
        """Get or cache analytics data for efficient generation."""
        if self._analytics_cache is None:
            try:
                from src.analytics_engine import compute_gap_analysis, compute_temporal_frequencies
                
                # Use instance's draws_df which respects max_date
                self._analytics_cache = {
                    'gap_analysis': compute_gap_analysis(self.draws_df),
                    'temporal_frequencies': compute_temporal_frequencies(self.draws_df, decay_rate=0.05)
                }
            except Exception as e:
                logger.error(f"Failed to compute analytics for custom generator: {e}")
                # Return default analytics
                self._analytics_cache = {
                    'gap_analysis': {
                        'white_balls': {i: 0 for i in range(1, 70)},
                        'powerball': {i: 0 for i in range(1, 27)}
                    },
                    'temporal_frequencies': {
                        'white_balls': np.ones(69) / 69,
                        'powerball': np.ones(26) / 26
                    }
                }
        
        return self._analytics_cache
    
    def generate_custom(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> List[Dict]:
        """
        Generate tickets based on custom parameters.
        
        Args:
            params: Dict with:
                - count: Number of tickets to generate (default 5)
                - risk: 'low', 'med', 'high' (default 'med')
                - temperature: 'hot', 'cold', 'neutral' (default 'neutral')
                - exclude: List of numbers to exclude (default [])
            context: Optional analytics context (if not provided, will compute)
            
        Returns:
            List of ticket dictionaries
        """
        # Parse parameters with defaults
        count = params.get('count', 5)
        risk = params.get('risk', 'med').lower()
        temperature = params.get('temperature', 'neutral').lower()
        exclude = set(params.get('exclude', []))
        
        logger.info(f"Generating {count} custom tickets: risk={risk}, temperature={temperature}, exclude={len(exclude)} numbers")
        
        # Validate risk level
        if risk not in ['low', 'med', 'high']:
            logger.warning(f"Invalid risk level '{risk}', defaulting to 'med'")
            risk = 'med'
        
        # Validate temperature
        if temperature not in ['hot', 'cold', 'neutral']:
            logger.warning(f"Invalid temperature '{temperature}', defaulting to 'neutral'")
            temperature = 'neutral'
        
        # Get analytics (use provided context or compute)
        if context:
            analytics = context
        else:
            analytics = self._get_analytics()
        
        tickets = []
        
        for _ in range(count):
            try:
                # Generate white balls based on parameters
                white_balls = self._generate_white_balls(risk, temperature, exclude, analytics)
                
                # Generate powerball based on parameters
                powerball = self._generate_powerball(risk, temperature, analytics)
                
                # Calculate confidence based on parameters
                confidence = self._calculate_confidence(risk, temperature)
                
                tickets.append({
                    'white_balls': sorted(white_balls),
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': confidence
                })
                
            except Exception as e:
                logger.error(f"Error generating custom ticket: {e}, using fallback")
                # Fallback to random
                available = [n for n in range(1, 70) if n not in exclude]
                if len(available) < 5:
                    available = list(range(1, 70))  # Ignore exclusions if not enough numbers
                
                white_balls = sorted(random.sample(available, 5))
                powerball = random.randint(1, 26)
                
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.50
                })
        
        logger.debug(f"{self.name}: Generated {len(tickets)} custom tickets")
        return tickets
    
    def _generate_white_balls(
        self,
        risk: str,
        temperature: str,
        exclude: set,
        analytics: Dict[str, Any]
    ) -> List[int]:
        """
        Generate 5 white balls based on parameters.
        
        Args:
            risk: Risk level ('low', 'med', 'high')
            temperature: Temperature preference ('hot', 'cold', 'neutral')
            exclude: Set of numbers to exclude
            analytics: Analytics data with gap_analysis and temporal_frequencies
            
        Returns:
            List of 5 white ball numbers (not sorted)
        """
        # Filter available numbers (exclude user-specified numbers)
        available = [n for n in range(1, 70) if n not in exclude]
        
        if len(available) < 5:
            logger.warning(f"Exclusions too restrictive ({len(exclude)} excluded), ignoring exclusions")
            available = list(range(1, 70))
        
        # Get weighting based on temperature
        if temperature == 'hot':
            # Use temporal frequencies (favor recent numbers)
            temporal_freq = analytics.get('temporal_frequencies', {}).get('white_balls', np.ones(69) / 69)
            weights = np.array([temporal_freq[n - 1] for n in available])
            
        elif temperature == 'cold':
            # Use gap analysis (favor overdue numbers)
            gap_data = analytics.get('gap_analysis', {}).get('white_balls', {})
            # Higher gap = more overdue = higher weight
            gaps = np.array([gap_data.get(n, 0) for n in available])
            # Normalize gaps to weights (higher gap = higher weight)
            if gaps.sum() > 0:
                weights = gaps / gaps.sum()
            else:
                weights = np.ones(len(available)) / len(available)
                
        else:  # neutral
            # Uniform distribution
            weights = np.ones(len(available)) / len(available)
        
        # Adjust weights based on risk level
        if risk == 'low':
            # Low risk: Flatten the distribution (less extreme)
            weights = np.power(weights, 0.5)  # Reduce contrast
        elif risk == 'high':
            # High risk: Sharpen the distribution (more extreme)
            weights = np.power(weights, 2.0)  # Increase contrast
        # 'med' keeps weights as-is
        
        # Normalize weights
        weights = weights / weights.sum()
        
        # Sample without replacement
        try:
            selected = np.random.choice(
                available,
                size=5,
                replace=False,
                p=weights
            ).tolist()
            return selected
        except Exception as e:
            logger.error(f"Error in weighted sampling: {e}, using uniform random")
            return random.sample(available, 5)
    
    def _generate_powerball(
        self,
        risk: str,
        temperature: str,
        analytics: Dict[str, Any]
    ) -> int:
        """
        Generate powerball based on parameters.
        
        Args:
            risk: Risk level ('low', 'med', 'high')
            temperature: Temperature preference ('hot', 'cold', 'neutral')
            analytics: Analytics data
            
        Returns:
            Powerball number (1-26)
        """
        # Get weighting based on temperature
        if temperature == 'hot':
            temporal_freq = analytics.get('temporal_frequencies', {}).get('powerball', np.ones(26) / 26)
            weights = temporal_freq
            
        elif temperature == 'cold':
            gap_data = analytics.get('gap_analysis', {}).get('powerball', {})
            gaps = np.array([gap_data.get(n, 0) for n in range(1, 27)])
            if gaps.sum() > 0:
                weights = gaps / gaps.sum()
            else:
                weights = np.ones(26) / 26
                
        else:  # neutral
            weights = np.ones(26) / 26
        
        # Adjust weights based on risk level
        if risk == 'low':
            weights = np.power(weights, 0.5)
        elif risk == 'high':
            weights = np.power(weights, 2.0)
        
        # Normalize
        weights = weights / weights.sum()
        
        # Sample
        try:
            return int(np.random.choice(range(1, 27), p=weights))
        except Exception as e:
            logger.error(f"Error in powerball sampling: {e}, using random")
            return random.randint(1, 26)
    
    def _calculate_confidence(self, risk: str, temperature: str) -> float:
        """
        Calculate confidence score based on parameters.
        
        Args:
            risk: Risk level
            temperature: Temperature preference
            
        Returns:
            Confidence score (0.0-1.0)
        """
        # Base confidence
        base = 0.70
        
        # Temperature affects confidence
        if temperature in ['hot', 'cold']:
            base += 0.05  # Slight boost for strategic choice
        
        # Risk affects confidence
        if risk == 'low':
            base += 0.05  # Conservative approach
        elif risk == 'high':
            base -= 0.10  # Risky approach
        
        return min(0.95, max(0.50, base))
    
    def generate(self, count: int = 5) -> List[Dict]:
        """
        Standard generate method (uses neutral parameters).
        
        Args:
            count: Number of tickets to generate
            
        Returns:
            List of ticket dictionaries
        """
        # Use neutral parameters for standard generation
        params = {
            'count': count,
            'risk': 'med',
            'temperature': 'neutral',
            'exclude': []
        }
        return self.generate_custom(params)


class StrategyManager:
    """
    Manages all 11 strategies and selects which to use based on adaptive weights.
    
    Uses Bayesian weight updating based on historical performance.
    """

    def __init__(self, max_date: str = None):
        """
        Initialize StrategyManager.
        
        Args:
            max_date: Optional date limit (YYYY-MM-DD). Only uses historical data before this date.
                      Critical for preventing data leakage when generating historical predictions.
        """
        self.max_date = max_date
        self.strategies = {
            # Original 6 strategies
            'frequency_weighted': FrequencyWeightedStrategy(max_date=max_date),
            'coverage_optimizer': CoverageOptimizerStrategy(max_date=max_date),
            'cooccurrence': CooccurrenceStrategy(max_date=max_date),
            'range_balanced': RangeBalancedStrategy(max_date=max_date),
            'ai_guided': AIGuidedStrategy(max_date=max_date),
            'random_baseline': RandomBaselineStrategy(max_date=max_date),
            # New 5 ML strategies (PHASE 2)
            'xgboost_ml': XGBoostMLStrategy(max_date=max_date),
            'random_forest_ml': RandomForestMLStrategy(max_date=max_date),
            'lstm_neural': LSTMNeuralStrategy(max_date=max_date),
            'hybrid_ensemble': HybridEnsembleStrategy(max_date=max_date),
            'intelligent_scoring': IntelligentScoringStrategy(max_date=max_date)
        }

        self._initialize_strategy_weights()
        if max_date:
            logger.info(f"StrategyManager initialized with {len(self.strategies)} strategies (data filtered to before {max_date})")
        else:
            logger.info(f"StrategyManager initialized with {len(self.strategies)} strategies")

    def _initialize_strategy_weights(self):
        """Initialize strategy_performance table with equal weights (1/11 each = ~0.091)"""
        conn = get_db_connection()
        cursor = conn.cursor()

        for name in self.strategies.keys():
            cursor.execute("""
                INSERT OR IGNORE INTO strategy_performance 
                (strategy_name, current_weight, confidence)
                VALUES (?, 0.091, 0.5)
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
        logger.info(f"StrategyManager.generate_balanced_tickets called with total={total}")
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

        logger.info(f"StrategyManager generated {len(all_tickets)} tickets (requested: {total})")
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
