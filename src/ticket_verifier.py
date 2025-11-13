"""
Powerball Ticket Verification Module
Verifies extracted ticket numbers against official draw results and calculates prizes.
"""

from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime, timedelta

import src.database as db
from src.prize_calculator import calculate_prize_amount


class TicketVerifier:
    """
    Verifies Powerball ticket numbers against official results and calculates prizes.
    """

    def __init__(self):
        """Initialize the ticket verifier."""
        pass

    def find_matching_draw(self, draw_date: str) -> Optional[Dict]:
        """
        Find the official draw result for a given date.
        
        Args:
            draw_date: Date in YYYY-MM-DD format
            
        Returns:
            Draw result dictionary or None if not found
        """
        try:
            # Get all draws from database
            all_draws = db.get_all_draws()

            if all_draws is None or all_draws.empty:
                logger.warning("No draws found in database")
                return None

            # Look for exact date match first
            for _, draw in all_draws.iterrows():
                # Handle pandas Timestamp objects properly
                if hasattr(draw['draw_date'], 'strftime'):
                    # It's a pandas Timestamp or datetime object
                    draw_date_str = draw['draw_date'].strftime('%Y-%m-%d')
                else:
                    # It's a string, convert and extract just the date part
                    draw_date_str = str(draw['draw_date'])
                    if 'T' in draw_date_str:  # If it's a datetime string, extract just the date
                        draw_date_str = draw_date_str.split('T')[0]

                if draw_date_str == draw_date:
                    logger.info(f"Found exact match for draw date: {draw_date}")
                    return draw.to_dict()

            # If no exact match, try to find the closest draw date
            # (in case the date parsing was slightly off)
            target_date = datetime.strptime(draw_date, '%Y-%m-%d')
            closest_draw = None
            min_diff = timedelta.max

            for _, draw in all_draws.iterrows():
                try:
                    # Handle both pandas Timestamp and string formats
                    if hasattr(draw['draw_date'], 'strftime'):
                        # It's a pandas Timestamp or datetime object
                        draw_datetime = draw['draw_date'].to_pydatetime() if hasattr(draw['draw_date'], 'to_pydatetime') else draw['draw_date']
                    else:
                        # It's a string, parse it
                        draw_date_str = str(draw['draw_date'])
                        if 'T' in draw_date_str:  # If it's a datetime string, extract just the date
                            draw_date_str = draw_date_str.split('T')[0]
                        draw_datetime = datetime.strptime(draw_date_str, '%Y-%m-%d')

                    diff = abs(target_date - draw_datetime)
                    if diff < min_diff and diff <= timedelta(days=3):  # Within 3 days
                        min_diff = diff
                        closest_draw = draw.to_dict()
                except (ValueError, KeyError, AttributeError) as e:
                    logger.debug(f"Error parsing date {draw['draw_date']}: {e}")
                    continue

            if closest_draw:
                logger.info(f"Found closest draw for {draw_date}: {closest_draw['draw_date']}")
                return closest_draw

            logger.warning(f"No matching draw found for date: {draw_date}")
            return None

        except Exception as e:
            logger.error(f"Error finding matching draw: {e}")
            return None

    def verify_single_play(self, play_numbers: List[int], powerball: int,
                          official_numbers: List[int], official_powerball: int) -> Dict:
        """
        Verify a single play against official results.
        
        Args:
            play_numbers: Player's main numbers (5 numbers)
            powerball: Player's powerball number
            official_numbers: Official winning main numbers
            official_powerball: Official winning powerball
            
        Returns:
            Verification result with matches and prize information
        """
        try:
            # Count main number matches
            main_matches = len(set(play_numbers) & set(official_numbers))

            # Check powerball match
            powerball_match = (powerball == official_powerball)

            # Determine prize tier and amount
            prize_amount, prize_description = calculate_prize_amount(main_matches, powerball_match)
            prize_info = {
                'amount': prize_amount,
                'tier': prize_description
            }

            result = {
                'main_matches': main_matches,
                'powerball_match': powerball_match,
                'total_matches': main_matches + (1 if powerball_match else 0),
                'prize_tier': prize_info.get('tier', 'No Prize'),
                'prize_amount': prize_info.get('amount', 0),
                'is_winner': prize_info.get('amount', 0) > 0,
                'play_numbers': play_numbers,
                'powerball': powerball,
                'winning_numbers': official_numbers,
                'winning_powerball': official_powerball
            }

            return result

        except Exception as e:
            logger.error(f"Error verifying single play: {e}")
            return {
                'main_matches': 0,
                'powerball_match': False,
                'total_matches': 0,
                'prize_tier': 'Error',
                'prize_amount': 0,
                'is_winner': False,
                'error': str(e)
            }

    def verify_ticket(self, ticket_data: Dict) -> Dict:
        """
        Verify an entire ticket with multiple plays.
        
        Args:
            ticket_data: Ticket data from ticket processor
            
        Returns:
            Complete verification result
        """
        try:
            if not ticket_data.get('success', False):
                return {
                    'success': False,
                    'error': 'Ticket processing failed',
                    'verification_results': []
                }

            plays = ticket_data.get('plays', [])
            draw_date = ticket_data.get('draw_date')

            if not plays:
                return {
                    'success': False,
                    'error': 'No valid plays found on ticket',
                    'verification_results': []
                }

            if not draw_date:
                return {
                    'success': False,
                    'error': 'Could not determine draw date from ticket',
                    'verification_results': []
                }

            # Find the matching official draw
            official_draw = self.find_matching_draw(draw_date)
            if not official_draw:
                return {
                    'success': False,
                    'error': f'No official draw results found for date: {draw_date}',
                    'verification_results': []
                }

            # Extract official winning numbers
            official_numbers = [
                official_draw.get('n1', 0),
                official_draw.get('n2', 0),
                official_draw.get('n3', 0),
                official_draw.get('n4', 0),
                official_draw.get('n5', 0)
            ]
            official_powerball = official_draw.get('pb', 0)

            # Verify each play
            verification_results = []
            total_prize_amount = 0
            total_winning_plays = 0

            for play in plays:
                result = self.verify_single_play(
                    play['main_numbers'],
                    play['powerball'],
                    official_numbers,
                    official_powerball
                )

                result['line'] = play.get('line', '?')
                verification_results.append(result)

                if result.get('is_winner', False):
                    total_winning_plays += 1
                    total_prize_amount += result.get('prize_amount', 0)

            # Prepare final result
            final_result = {
                'success': True,
                'draw_date': draw_date,
                'official_draw_id': official_draw.get('id'),
                'official_numbers': official_numbers,
                'official_powerball': official_powerball,
                'total_plays': len(plays),
                'total_winning_plays': total_winning_plays,
                'total_prize_amount': total_prize_amount,
                'is_winning_ticket': total_winning_plays > 0,
                'verification_results': verification_results,
                'processed_at': datetime.now().isoformat()
            }

            logger.info(f"Ticket verified: {total_winning_plays}/{len(plays)} winning plays, total prize: ${total_prize_amount}")

            return final_result

        except Exception as e:
            logger.error(f"Error verifying ticket: {e}")
            return {
                'success': False,
                'error': f'Ticket verification failed: {str(e)}',
                'verification_results': []
            }

    def format_verification_summary(self, verification_result: Dict) -> str:
        """
        Format verification result into a human-readable summary.
        
        Args:
            verification_result: Result from verify_ticket
            
        Returns:
            Formatted summary string
        """
        try:
            if not verification_result.get('success', False):
                return f"❌ Verification failed: {verification_result.get('error', 'Unknown error')}"

            if verification_result.get('is_winning_ticket', False):
                total_prize = verification_result.get('total_prize_amount', 0)
                winning_plays = verification_result.get('total_winning_plays', 0)
                total_plays = verification_result.get('total_plays', 0)

                summary = "✅ WINNING TICKET!\n"
                summary += f"💰 Total Prize: ${total_prize:,.2f}\n"
                summary += f"🎯 Winning Plays: {winning_plays} out of {total_plays}\n"
                summary += f"📅 Draw Date: {verification_result.get('draw_date', 'Unknown')}\n\n"

                # Add details for each winning play
                for result in verification_result.get('verification_results', []):
                    if result.get('is_winner', False):
                        line = result.get('line', '?')
                        matches = result.get('main_matches', 0)
                        pb_match = result.get('powerball_match', False)
                        prize = result.get('prize_amount', 0)
                        tier = result.get('prize_tier', 'Unknown')

                        summary += f"Line {line}: {matches} numbers"
                        if pb_match:
                            summary += " + Powerball"
                        summary += f" = ${prize:,.2f} ({tier})\n"

                return summary
            else:
                return "❌ No winning numbers found on this ticket."

        except Exception as e:
            logger.error(f"Error formatting verification summary: {e}")
            return "❌ Error formatting results."


def create_ticket_verifier() -> TicketVerifier:
    """
    Factory function to create a ticket verifier instance.
    
    Returns:
        Configured TicketVerifier instance
    """
    return TicketVerifier()
