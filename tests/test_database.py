import unittest
import sys
import os

# Adjust sys.path to allow importing from the project root
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.main import process_and_save_coin_data
from src.database.db_manager import (
    initialize_database,
    execute_read_query,
    get_coin_id_by_symbol,
    execute_write_query # For local clear_scores_table helper
)
from src.database.data_loader import load_test_coins_data, clear_coins_table

# Local test helper to clear scores table for repeatable tests
# This is important because process_and_save_coin_data inserts into scores
def clear_scores_table_for_integration_test():
    execute_write_query("DELETE FROM scores;")
    # Resetting auto-increment for 'scores' table.
    execute_write_query("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'scores';")

class TestIntegrationPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize DB schema once for all tests in this class
        # This ensures the database file and tables are created.
        print("Initializing database schema for integration tests...")
        initialize_database()

    def setUp(self):
        # Runs before each test method
        # Ensure a clean state for coins and scores tables for each test.
        # print(f"Setting up for test: {self._testMethodName}") # Optional: for verbose test logs
        clear_coins_table() # Clears coins table and resets its sequence
        clear_scores_table_for_integration_test() # Clears scores table and resets its sequence

        # Load a standard set of test coins. These coins have mock data defined in collectors.
        self.sample_coins = [
            ("BTC", "Bitcoin"), 
            ("ETH", "Ethereum"), 
            ("SOL", "Solana"),
            ("DOGE", "Dogecoin") # DOGE has specific mock data characteristics
        ]
        load_test_coins_data(self.sample_coins)
        
        # Store IDs for easy verification
        self.btc_id = get_coin_id_by_symbol("BTC")
        self.eth_id = get_coin_id_by_symbol("ETH")
        self.sol_id = get_coin_id_by_symbol("SOL")
        self.doge_id = get_coin_id_by_symbol("DOGE")
        self.assertIsNotNone(self.btc_id, "BTC coin ID should not be None after setup")
        self.assertIsNotNone(self.doge_id, "DOGE coin ID should not be None after setup")

    def test_pipeline_for_fully_mocked_coin_btc(self):
        # BTC has mock data in all collectors. Expected score based on current scorer.py is 1.0.
        process_and_save_coin_data("BTC")
        
        score_info = execute_read_query("SELECT score FROM scores WHERE coin_id = ? ORDER BY timestamp DESC LIMIT 1", 
                                        params=(self.btc_id,), fetch_one=True)
        self.assertIsNotNone(score_info, "No score found in DB for BTC")
        self.assertAlmostEqual(score_info[0], 1.0, msg="BTC score did not match expected value")

    def test_pipeline_for_partially_mocked_coin_doge(self):
        # DOGE has mock social data, but not price/volume or on-chain.
        # Expected to be ineligible for full scoring, resulting in score 0.0, which should be saved.
        process_and_save_coin_data("DOGE")
        
        score_info = execute_read_query("SELECT score FROM scores WHERE coin_id = ? ORDER BY timestamp DESC LIMIT 1", 
                                        params=(self.doge_id,), fetch_one=True)
        self.assertIsNotNone(score_info, "No score found in DB for DOGE")
        self.assertEqual(score_info[0], 0.0, msg="DOGE score was not 0.0 as expected for ineligibility")

    def test_pipeline_for_unknown_coin_not_in_db(self):
        # "XYZCOIN" is not loaded into the 'coins' table.
        # process_and_save_coin_data should try to find coin_id, fail, and not save a score.
        # No new entries should be in the scores table after this specific call.
        
        # Get initial score count (should be 0 due to setUp)
        initial_scores = execute_read_query("SELECT COUNT(*) FROM scores;", fetch_one=True)
        self.assertEqual(initial_scores[0], 0, "Scores table should be empty at start of this test")

        process_and_save_coin_data("XYZCOIN")
        
        # Verify XYZCOIN itself does not have an ID and no score was saved for it.
        xyz_id = get_coin_id_by_symbol("XYZCOIN")
        self.assertIsNone(xyz_id, "XYZCOIN should not have an ID in the coins table")
        
        # Verify that no new scores were added to the table as a result of processing XYZCOIN.
        final_scores = execute_read_query("SELECT COUNT(*) FROM scores;", fetch_one=True)
        self.assertEqual(final_scores[0], 0, "No scores should have been saved for XYZCOIN")

if __name__ == '__main__':
    unittest.main() 