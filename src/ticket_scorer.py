"""
SHIOL+ Ticket Scorer
====================
Score user tickets (0-100 scale) based on statistical quality.

Analyzes tickets based on:
- Diversity: Spread across number ranges
- Balance: Sum range and odd/even ratio
- Potential: Alignment with hot numbers and rising momentum
"""

from typing import List, Dict, Any
from loguru import logger


class TicketScorer:
    """
    Score lottery tickets based on multiple statistical criteria.
    
    Provides a comprehensive 0-100 score along with detailed breakdown
    and recommendations for improvement.
    """
    
    def __init__(self):
        """Initialize the ticket scorer."""
        self.optimal_sum_range = (130, 220)  # Statistical sweet spot for sum of 5 numbers
        self.optimal_odd_even = (2, 3)  # 2-3 odd or 2-3 even is balanced
        
    def score_ticket(
        self,
        ticket_numbers: List[int],
        powerball: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Score a ticket on a 0-100 scale with detailed breakdown.
        
        Args:
            ticket_numbers: List of 5 white ball numbers (1-69)
            powerball: Powerball number (1-26)
            context: Analytics context containing:
                - gap_analysis: Dict with 'white_balls' and 'powerball' gaps
                - temporal_frequencies: Dict with frequency distributions
                - momentum_scores: Dict with momentum scores
                
        Returns:
            Dict with:
                - total_score: int (0-100)
                - details: Dict with individual scores and explanations
                - recommendation: str with improvement suggestions
        """
        # Validate inputs
        if len(ticket_numbers) != 5:
            return self._invalid_ticket_response("Must have exactly 5 white ball numbers")
        
        if not all(1 <= n <= 69 for n in ticket_numbers):
            return self._invalid_ticket_response("White ball numbers must be between 1 and 69")
        
        if len(set(ticket_numbers)) != 5:
            return self._invalid_ticket_response("White ball numbers must be unique")
        
        if not 1 <= powerball <= 26:
            return self._invalid_ticket_response("Powerball must be between 1 and 26")
        
        # Calculate individual scores
        diversity_score = self._calculate_diversity_score(ticket_numbers)
        balance_score = self._calculate_balance_score(ticket_numbers)
        potential_score = self._calculate_potential_score(ticket_numbers, powerball, context)
        
        # Weighted average (all components equally weighted)
        total_score = int(
            (diversity_score['score'] + balance_score['score'] + potential_score['score']) / 3.0 * 100
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            total_score, diversity_score, balance_score, potential_score
        )
        
        return {
            'total_score': total_score,
            'details': {
                'diversity': diversity_score,
                'balance': balance_score,
                'potential': potential_score
            },
            'recommendation': recommendation
        }
    
    def _calculate_diversity_score(self, numbers: List[int]) -> Dict[str, Any]:
        """
        Calculate diversity score based on number spread across decades.
        
        High diversity = numbers spread across different ranges (1-9, 10-19, etc.)
        
        Returns:
            Dict with score (0.0-1.0) and explanation
        """
        # Define decades: 1-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69
        decades = set()
        for num in numbers:
            decade = (num - 1) // 10  # 0-6 for 7 decades
            decades.add(decade)
        
        unique_decades = len(decades)
        
        # Score based on unique decades (5 is perfect, 1 is worst)
        # 5 decades = 1.0, 4 = 0.8, 3 = 0.6, 2 = 0.4, 1 = 0.2
        score = unique_decades / 5.0
        
        explanation = f"Numbers spread across {unique_decades} of 7 possible ranges"
        
        if unique_decades >= 4:
            quality = "Excellent"
        elif unique_decades == 3:
            quality = "Good"
        else:
            quality = "Poor"
        
        return {
            'score': score,
            'unique_decades': unique_decades,
            'quality': quality,
            'explanation': explanation
        }
    
    def _calculate_balance_score(self, numbers: List[int]) -> Dict[str, Any]:
        """
        Calculate balance score based on sum range and odd/even ratio.
        
        Returns:
            Dict with score (0.0-1.0) and explanation
        """
        total_sum = sum(numbers)
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        even_count = 5 - odd_count
        
        # Score for sum (optimal range is 130-220)
        if self.optimal_sum_range[0] <= total_sum <= self.optimal_sum_range[1]:
            sum_score = 1.0
            sum_quality = "Optimal"
        elif total_sum < 100 or total_sum > 250:
            sum_score = 0.3
            sum_quality = "Poor"
        else:
            sum_score = 0.6
            sum_quality = "Fair"
        
        # Score for odd/even ratio (2-3 or 3-2 is optimal)
        if odd_count in [2, 3]:
            ratio_score = 1.0
            ratio_quality = "Balanced"
        elif odd_count in [1, 4]:
            ratio_score = 0.6
            ratio_quality = "Acceptable"
        else:
            ratio_score = 0.3
            ratio_quality = "Unbalanced"
        
        # Combined balance score
        score = (sum_score + ratio_score) / 2.0
        
        return {
            'score': score,
            'sum': total_sum,
            'sum_quality': sum_quality,
            'odd_count': odd_count,
            'even_count': even_count,
            'ratio_quality': ratio_quality,
            'explanation': f"Sum={total_sum} ({sum_quality}), Odd/Even={odd_count}/{even_count} ({ratio_quality})"
        }
    
    def _calculate_potential_score(
        self,
        numbers: List[int],
        powerball: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate potential score based on hot numbers and momentum.
        
        High potential = numbers align with hot frequencies and positive momentum
        
        Returns:
            Dict with score (0.0-1.0) and explanation
        """
        # Extract context data
        gap_analysis = context.get('gap_analysis', {})
        temporal_frequencies = context.get('temporal_frequencies', {})
        momentum_scores = context.get('momentum_scores', {})
        
        # If no context available, return neutral score
        if not gap_analysis or not momentum_scores:
            return {
                'score': 0.5,
                'hot_count': 0,
                'rising_count': 0,
                'quality': 'Unknown',
                'explanation': 'Insufficient data for potential analysis'
            }
        
        wb_gaps = gap_analysis.get('white_balls', {})
        pb_gaps = gap_analysis.get('powerball', {})
        wb_momentum = momentum_scores.get('white_balls', {})
        pb_momentum = momentum_scores.get('powerball', {})
        
        # Count hot numbers (gap < 30 days = recently appeared)
        hot_count = sum(1 for n in numbers if wb_gaps.get(n, 999) < 30)
        
        # Count rising momentum numbers (momentum > 0.2)
        rising_count = sum(1 for n in numbers if wb_momentum.get(n, 0.0) > 0.2)
        
        # Check powerball
        pb_is_hot = pb_gaps.get(powerball, 999) < 30
        pb_is_rising = pb_momentum.get(powerball, 0.0) > 0.2
        
        # Calculate score
        # Base score from white balls: hot_count and rising_count
        white_ball_score = (hot_count / 5.0 * 0.5) + (rising_count / 5.0 * 0.5)
        
        # Powerball bonus
        pb_score = 0.0
        if pb_is_hot:
            pb_score += 0.5
        if pb_is_rising:
            pb_score += 0.5
        
        # Combined score (70% white balls, 30% powerball)
        score = white_ball_score * 0.7 + pb_score * 0.3
        
        if score >= 0.7:
            quality = "Excellent"
        elif score >= 0.5:
            quality = "Good"
        elif score >= 0.3:
            quality = "Fair"
        else:
            quality = "Poor"
        
        return {
            'score': score,
            'hot_count': hot_count,
            'rising_count': rising_count,
            'powerball_hot': pb_is_hot,
            'powerball_rising': pb_is_rising,
            'quality': quality,
            'explanation': f"{hot_count} hot numbers, {rising_count} with rising momentum ({quality})"
        }
    
    def _generate_recommendation(
        self,
        total_score: int,
        diversity: Dict,
        balance: Dict,
        potential: Dict
    ) -> str:
        """
        Generate actionable recommendation based on scores.
        
        Returns:
            String with improvement suggestions
        """
        recommendations = []
        
        # Overall assessment
        if total_score >= 80:
            recommendations.append("Excellent ticket! This combination shows strong statistical characteristics.")
        elif total_score >= 60:
            recommendations.append("Good ticket with solid fundamentals.")
        elif total_score >= 40:
            recommendations.append("Acceptable ticket, but there's room for improvement.")
        else:
            recommendations.append("This ticket has several weaknesses to address.")
        
        # Specific improvements
        if diversity['score'] < 0.6:
            recommendations.append(
                f"DIVERSITY: Spread numbers across more ranges (currently {diversity['unique_decades']} ranges)."
            )
        
        if balance['score'] < 0.6:
            if balance['sum_quality'] != 'Optimal':
                recommendations.append(
                    f"BALANCE: Target sum between 130-220 (current: {balance['sum']})."
                )
            if balance['ratio_quality'] != 'Balanced':
                recommendations.append(
                    f"BALANCE: Aim for 2-3 odd and 2-3 even numbers (current: {balance['odd_count']} odd, {balance['even_count']} even)."
                )
        
        if potential['score'] < 0.6:
            recommendations.append(
                f"POTENTIAL: Consider including more hot numbers or numbers with rising momentum (currently {potential['hot_count']} hot, {potential['rising_count']} rising)."
            )
        
        return " ".join(recommendations)
    
    def _invalid_ticket_response(self, error_message: str) -> Dict[str, Any]:
        """
        Return error response for invalid tickets.
        
        Returns:
            Dict with zero score and error explanation
        """
        return {
            'total_score': 0,
            'details': {
                'diversity': {'score': 0.0, 'explanation': 'Invalid ticket'},
                'balance': {'score': 0.0, 'explanation': 'Invalid ticket'},
                'potential': {'score': 0.0, 'explanation': 'Invalid ticket'}
            },
            'recommendation': f"Error: {error_message}"
        }
