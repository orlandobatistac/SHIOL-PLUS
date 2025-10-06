
def calculate_prize_amount(main_matches: int, powerball_match: bool) -> tuple[float, str]:
    """
    Calculate Powerball prize amount based on matches.
    
    Args:
        main_matches: Number of main number matches (0-5)
        powerball_match: Whether the Powerball number matched
        
    Returns:
        Tuple of (prize_amount, prize_description)
    """
    
    # Official Powerball prize structure (fixed amounts)
    if main_matches == 5 and powerball_match:
        return (100000000.0, "Jackpot")  # Variable jackpot
    elif main_matches == 5 and not powerball_match:
        return (1000000.0, "Match 5")
    elif main_matches == 4 and powerball_match:
        return (50000.0, "Match 4 + Powerball")
    elif main_matches == 4 and not powerball_match:
        return (100.0, "Match 4")
    elif main_matches == 3 and powerball_match:
        return (100.0, "Match 3 + Powerball")
    elif main_matches == 3 and not powerball_match:
        return (7.0, "Match 3")
    elif main_matches == 2 and powerball_match:
        return (7.0, "Match 2 + Powerball")
    elif main_matches == 1 and powerball_match:
        return (4.0, "Match 1 + Powerball")
    elif main_matches == 0 and powerball_match:
        return (4.0, "Powerball Only")
    else:
        return (0.0, "No Prize")
