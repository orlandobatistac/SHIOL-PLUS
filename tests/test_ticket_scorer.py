"""
Tests for TicketScorer class
=============================
Tests for scoring user tickets based on diversity, balance, and potential
"""

import pytest
from src.ticket_scorer import TicketScorer


class TestTicketScorerValidation:
    """Test ticket validation"""
    
    def test_valid_ticket(self):
        """Test scoring a valid ticket"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {
                'white_balls': {i: 10 for i in range(1, 70)},
                'powerball': {i: 10 for i in range(1, 27)}
            },
            'momentum_scores': {
                'white_balls': {i: 0.0 for i in range(1, 70)},
                'powerball': {i: 0.0 for i in range(1, 27)}
            }
        }
        
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        assert 'total_score' in result
        assert 0 <= result['total_score'] <= 100
        assert 'details' in result
        assert 'recommendation' in result
    
    def test_invalid_ticket_wrong_count(self):
        """Test ticket with wrong number of white balls"""
        scorer = TicketScorer()
        context = {}
        
        result = scorer.score_ticket([5, 15, 25], 10, context)
        
        assert result['total_score'] == 0
        assert 'Must have exactly 5' in result['recommendation']
    
    def test_invalid_ticket_out_of_range(self):
        """Test ticket with numbers out of range"""
        scorer = TicketScorer()
        context = {}
        
        result = scorer.score_ticket([1, 2, 3, 4, 70], 10, context)
        
        assert result['total_score'] == 0
        assert 'between 1 and 69' in result['recommendation']
    
    def test_invalid_ticket_duplicates(self):
        """Test ticket with duplicate numbers"""
        scorer = TicketScorer()
        context = {}
        
        result = scorer.score_ticket([5, 5, 15, 25, 35], 10, context)
        
        assert result['total_score'] == 0
        assert 'must be unique' in result['recommendation']
    
    def test_invalid_powerball(self):
        """Test ticket with invalid powerball"""
        scorer = TicketScorer()
        context = {}
        
        result = scorer.score_ticket([5, 15, 25, 35, 45], 27, context)
        
        assert result['total_score'] == 0
        assert 'Powerball must be between 1 and 26' in result['recommendation']


class TestDiversityScore:
    """Test diversity scoring component"""
    
    def test_perfect_diversity(self):
        """Test ticket with maximum diversity (5 different decades)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # Numbers from 5 different decades: 5 (1-9), 15 (10-19), 25 (20-29), 35 (30-39), 45 (40-49)
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        assert result['details']['diversity']['unique_decades'] == 5
        assert result['details']['diversity']['score'] == 1.0
        assert result['details']['diversity']['quality'] == 'Excellent'
    
    def test_poor_diversity(self):
        """Test ticket with poor diversity (all from same decade)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # All numbers from 11-19 decade (decade 1)
        result = scorer.score_ticket([11, 12, 14, 16, 18], 10, context)
        
        assert result['details']['diversity']['unique_decades'] == 1
        assert result['details']['diversity']['score'] == 0.2
        assert result['details']['diversity']['quality'] == 'Poor'
    
    def test_good_diversity(self):
        """Test ticket with good diversity (4 decades)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # 4 decades: 5, 15, 25, 35, 36
        result = scorer.score_ticket([5, 15, 25, 35, 36], 10, context)
        
        assert result['details']['diversity']['unique_decades'] == 4
        assert result['details']['diversity']['score'] == 0.8


class TestBalanceScore:
    """Test balance scoring component"""
    
    def test_optimal_balance(self):
        """Test ticket with optimal sum and odd/even ratio"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # Sum = 175 (optimal range), 3 odd + 2 even (balanced)
        # 25 + 35 + 45 + 30 + 40 = 175
        result = scorer.score_ticket([25, 30, 35, 40, 45], 10, context)
        
        balance_details = result['details']['balance']
        assert balance_details['sum_quality'] == 'Optimal'
        assert balance_details['ratio_quality'] == 'Balanced'
        assert balance_details['score'] == 1.0
    
    def test_poor_sum(self):
        """Test ticket with very low sum"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # Sum = 25 (very low)
        result = scorer.score_ticket([1, 2, 3, 4, 15], 10, context)
        
        balance_details = result['details']['balance']
        assert balance_details['sum'] == 25
        assert balance_details['sum_quality'] == 'Poor'
    
    def test_unbalanced_odd_even(self):
        """Test ticket with all odd or all even numbers"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # All odd numbers
        result = scorer.score_ticket([1, 3, 5, 7, 9], 10, context)
        
        balance_details = result['details']['balance']
        assert balance_details['odd_count'] == 5
        assert balance_details['even_count'] == 0
        assert balance_details['ratio_quality'] == 'Unbalanced'


class TestPotentialScore:
    """Test potential scoring component"""
    
    def test_high_potential_hot_numbers(self):
        """Test ticket with many hot numbers (recently appeared)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {
                'white_balls': {
                    5: 10, 15: 15, 25: 20, 35: 25, 45: 5  # All recent (< 30 days)
                },
                'powerball': {10: 10}
            },
            'momentum_scores': {
                'white_balls': {
                    5: 0.5, 15: 0.4, 25: 0.3, 35: 0.25, 45: 0.6  # All rising (> 0.2)
                },
                'powerball': {10: 0.5}
            }
        }
        
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        potential_details = result['details']['potential']
        assert potential_details['hot_count'] == 5  # All numbers are hot
        assert potential_details['rising_count'] == 5  # All have positive momentum > 0.2
        assert potential_details['powerball_hot'] is True
        assert potential_details['powerball_rising'] is True
        assert potential_details['quality'] in ['Excellent', 'Good']
    
    def test_low_potential_cold_numbers(self):
        """Test ticket with cold numbers (overdue)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {
                'white_balls': {
                    5: 100, 15: 150, 25: 200, 35: 250, 45: 300  # All overdue
                },
                'powerball': {10: 100}
            },
            'momentum_scores': {
                'white_balls': {
                    5: -0.5, 15: -0.4, 25: -0.3, 35: -0.2, 45: -0.6  # All falling
                },
                'powerball': {10: -0.5}
            }
        }
        
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        potential_details = result['details']['potential']
        assert potential_details['hot_count'] == 0  # No hot numbers
        assert potential_details['rising_count'] == 0  # No rising momentum
        assert potential_details['quality'] in ['Poor', 'Fair']
    
    def test_potential_with_missing_context(self):
        """Test potential scoring handles missing context gracefully"""
        scorer = TicketScorer()
        context = {}  # No analytics data
        
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        potential_details = result['details']['potential']
        assert potential_details['score'] == 0.5  # Neutral score
        assert 'Insufficient data' in potential_details['explanation']


class TestRecommendations:
    """Test recommendation generation"""
    
    def test_excellent_ticket_recommendation(self):
        """Test recommendation for high-scoring ticket"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {
                'white_balls': {i: 10 for i in range(1, 70)},
                'powerball': {i: 10 for i in range(1, 27)}
            },
            'momentum_scores': {
                'white_balls': {i: 0.5 for i in range(1, 70)},
                'powerball': {i: 0.5 for i in range(1, 27)}
            }
        }
        
        # Ticket with good diversity, balance, and potential
        result = scorer.score_ticket([5, 15, 25, 35, 45], 10, context)
        
        if result['total_score'] >= 80:
            assert 'Excellent' in result['recommendation']
    
    def test_poor_ticket_recommendation(self):
        """Test recommendation for low-scoring ticket"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # Poor ticket: all from same decade, unbalanced odd/even
        result = scorer.score_ticket([1, 3, 5, 7, 9], 10, context)
        
        assert result['total_score'] < 60
        assert 'DIVERSITY' in result['recommendation'] or 'BALANCE' in result['recommendation']
    
    def test_recommendation_includes_specific_advice(self):
        """Test that recommendations include actionable advice"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        # Ticket with specific issues
        result = scorer.score_ticket([1, 2, 3, 4, 5], 10, context)
        
        # Should mention diversity (all in 1-9 range)
        # Should mention sum (very low)
        recommendation = result['recommendation']
        assert len(recommendation) > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_boundary_numbers(self):
        """Test ticket with boundary numbers (1, 69)"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {
                'white_balls': {i: 10 for i in range(1, 70)},
                'powerball': {i: 10 for i in range(1, 27)}
            },
            'momentum_scores': {
                'white_balls': {i: 0.0 for i in range(1, 70)},
                'powerball': {i: 0.0 for i in range(1, 27)}
            }
        }
        
        result = scorer.score_ticket([1, 20, 35, 50, 69], 1, context)
        
        assert result['total_score'] > 0
        assert 'total_score' in result
    
    def test_consecutive_numbers(self):
        """Test ticket with consecutive numbers"""
        scorer = TicketScorer()
        context = {
            'gap_analysis': {'white_balls': {}, 'powerball': {}},
            'momentum_scores': {'white_balls': {}, 'powerball': {}}
        }
        
        result = scorer.score_ticket([10, 11, 12, 13, 14], 10, context)
        
        # Should have poor diversity (all in same decade)
        assert result['details']['diversity']['unique_decades'] <= 2
