"""
Test SQL NULL handling for prize_won calculations.

This test validates that the SUM(COALESCE(prize_won, 0)) pattern correctly
handles NULL values in the prize_won column, ensuring that draws with
unevaluated predictions still return 0.0 instead of NULL for total_prize.
"""
import sqlite3
import tempfile
import os


def test_sum_null_handling():
    """Test that SUM with COALESCE handles NULL values correctly."""
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create test tables
        cursor.execute("""
            CREATE TABLE powerball_draws (
                draw_date DATE PRIMARY KEY,
                n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, pb INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE generated_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draw_date DATE,
                n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
                powerball INTEGER,
                prize_won REAL,
                evaluated INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE draw_evaluation_results (
                draw_date DATE PRIMARY KEY,
                total_tickets INTEGER DEFAULT 0,
                total_prize REAL DEFAULT 0,
                has_predictions BOOLEAN DEFAULT 1
            )
        """)
        
        # Insert test data
        # Draw 1: Has evaluated predictions with prizes
        cursor.execute("INSERT INTO powerball_draws VALUES ('2025-11-10', 1, 2, 3, 4, 5, 6)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-10', 1, 2, 3, 4, 5, 6, 100.0, 1)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-10', 2, 3, 4, 5, 6, 7, 7.0, 1)")
        
        # Draw 2: Has unevaluated predictions (prize_won is NULL)
        cursor.execute("INSERT INTO powerball_draws VALUES ('2025-11-08', 10, 20, 30, 40, 50, 16)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-08', 11, 22, 33, 44, 55, 17, NULL, 0)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-08', 12, 23, 34, 45, 56, 18, NULL, 0)")
        
        # Draw 3: Has no predictions
        cursor.execute("INSERT INTO powerball_draws VALUES ('2025-11-06', 15, 25, 35, 45, 55, 20)")
        
        # Draw 4: Has predictions in generated_tickets AND draw_evaluation_results with has_predictions=0 (BUG SCENARIO)
        cursor.execute("INSERT INTO powerball_draws VALUES ('2025-11-05', 5, 15, 25, 35, 45, 10)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-05', 6, 16, 26, 36, 46, 11, 4.0, 1)")
        cursor.execute("INSERT INTO generated_tickets (draw_date, n1, n2, n3, n4, n5, powerball, prize_won, evaluated) VALUES ('2025-11-05', 7, 17, 27, 37, 47, 12, 4.0, 1)")
        # WRONG: has_predictions=0 despite having predictions
        cursor.execute("INSERT INTO draw_evaluation_results (draw_date, total_tickets, total_prize, has_predictions) VALUES ('2025-11-05', 2, 8.0, 0)")
        
        conn.commit()
        
        # Test OLD query (BROKEN - uses draw_evaluation_results without fallback)
        print("\n=== Testing OLD query with draw_evaluation_results (BROKEN) ===")
        cursor.execute("""
            SELECT 
                p.draw_date,
                COALESCE(e.has_predictions, 
                    CASE WHEN EXISTS (SELECT 1 FROM generated_tickets g WHERE g.draw_date = p.draw_date) 
                    THEN 1 ELSE 0 END
                ) as has_predictions,
                COALESCE(e.total_prize,
                    (SELECT COALESCE(SUM(prize_won), 0.0) FROM generated_tickets g WHERE g.draw_date = p.draw_date)
                ) as total_prize
            FROM powerball_draws p
            LEFT JOIN draw_evaluation_results e ON p.draw_date = e.draw_date
            ORDER BY p.draw_date DESC
        """)
        
        old_results = cursor.fetchall()
        for row in old_results:
            print(f"  {row[0]}: has_predictions={row[1]}, total_prize={row[2]}")
            
        # Verify old query problem - Nov 5 has wrong has_predictions from draw_evaluation_results
        draw_2025_11_05 = [r for r in old_results if r[0] == '2025-11-05'][0]
        if draw_2025_11_05[1] == 0:
            print(f"\n  ❌ OLD QUERY BUG: Nov 5 has_predictions={draw_2025_11_05[1]} (WRONG! Should be 1, has 2 tickets in DB)")
        
        # Test NEW query (FIXED - always checks generated_tickets as source of truth)
        print("\n=== Testing NEW query (FIXED) ===")
        cursor.execute("""
            SELECT 
                p.draw_date,
                CASE WHEN EXISTS (SELECT 1 FROM generated_tickets g WHERE g.draw_date = p.draw_date) 
                THEN 1 ELSE 0 END as has_predictions,
                (SELECT COALESCE(SUM(COALESCE(prize_won, 0.0)), 0.0) FROM generated_tickets g WHERE g.draw_date = p.draw_date) as total_prize
            FROM powerball_draws p
            ORDER BY p.draw_date DESC
        """)
        
        new_results = cursor.fetchall()
        for row in new_results:
            print(f"  {row[0]}: has_predictions={row[1]}, total_prize={row[2]}")
        
        # Verify new query fix
        draw_2025_11_10 = [r for r in new_results if r[0] == '2025-11-10'][0]
        draw_2025_11_08 = [r for r in new_results if r[0] == '2025-11-08'][0]
        draw_2025_11_06 = [r for r in new_results if r[0] == '2025-11-06'][0]
        draw_2025_11_05 = [r for r in new_results if r[0] == '2025-11-05'][0]
        
        assert draw_2025_11_10[1] == 1, "Nov 10 should have predictions"
        assert draw_2025_11_10[2] == 107.0, f"Nov 10 total_prize should be 107.0, got {draw_2025_11_10[2]}"
        
        assert draw_2025_11_08[1] == 1, "Nov 8 should have predictions"
        assert draw_2025_11_08[2] == 0.0, f"Nov 8 total_prize should be 0.0, got {draw_2025_11_08[2]}"
        
        assert draw_2025_11_06[1] == 0, "Nov 6 should NOT have predictions"
        assert draw_2025_11_06[2] == 0.0, f"Nov 6 total_prize should be 0.0, got {draw_2025_11_06[2]}"
        
        assert draw_2025_11_05[1] == 1, "Nov 5 should have predictions (ignoring wrong draw_evaluation_results)"
        assert draw_2025_11_05[2] == 8.0, f"Nov 5 total_prize should be 8.0, got {draw_2025_11_05[2]}"
        
        print(f"\n  ✅ NEW QUERY WORKS: Nov 10 has predictions and total_prize=107.0 (correct!)")
        print(f"\n  ✅ NEW QUERY WORKS: Nov 8 has predictions and total_prize=0.0 (correct!)")
        print(f"\n  ✅ NEW QUERY WORKS: Nov 6 has no predictions and total_prize=0.0 (correct!)")
        print(f"\n  ✅ NEW QUERY WORKS: Nov 5 has predictions and total_prize=8.0 (IGNORING wrong draw_evaluation_results!)")
        
        conn.close()
        
        print("\n✅ All tests passed!")
        return True
        
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    test_sum_null_handling()
