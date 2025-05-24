import unittest
import sys
import os
from datetime import datetime, timezone

# Adjust sys.path to allow importing from the project root (src directory)
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # From tests/test_processors.py to project_root/
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.processors.data_cleaner import clean_coin_data
from src.processors.scorer import calculate_coin_score, REQUIRED_METRICS_FOR_SCORING

class TestDataCleaner(unittest.TestCase):

    def test_clean_good_data(self):
        raw_data = {
            "symbol": "BTC", "price": 60000.75, "volume": 5e10,
            "active_addresses": 1200000, "transaction_volume_usd": 1e10,
            "mentions": 15000, "sentiment_score": 0.75
        }
        cleaned = clean_coin_data(raw_data)
        self.assertEqual(cleaned["symbol"], "BTC")
        self.assertEqual(cleaned["price"], 60000.75)
        self.assertIsInstance(cleaned["price"], float)
        self.assertEqual(cleaned["mentions"], 15000)
        self.assertIsInstance(cleaned["mentions"], int)
        self.assertIn("cleaned_at_utc", cleaned)
        self.assertNotIn("processing_notes", cleaned)
        self.assertNotIn("collection_errors", cleaned)

    def test_clean_convertible_strings(self):
        raw_data = {"symbol": "ETH", "price": "4000.50", "mentions": "12000"}
        cleaned = clean_coin_data(raw_data)
        self.assertEqual(cleaned["price"], 4000.50)
        self.assertEqual(cleaned["mentions"], 12000)
        self.assertNotIn("processing_notes", cleaned)

    def test_clean_non_convertible_strings(self):
        raw_data = {"symbol": "ADA", "price": "not-a-price", "active_addresses": "many"}
        cleaned = clean_coin_data(raw_data)
        self.assertIsNone(cleaned["price"])
        self.assertIsNone(cleaned["active_addresses"])
        self.assertIn("processing_notes", cleaned)
        self.assertIn("Could not convert 'price' value 'not-a-price' to float", cleaned["processing_notes"][0])
        self.assertIn("Could not convert 'active_addresses' value 'many' to int", cleaned["processing_notes"][1])

    def test_clean_missing_fields(self):
        raw_data = {"symbol": "SOL"} # All data fields missing
        cleaned = clean_coin_data(raw_data)
        self.assertEqual(cleaned["symbol"], "SOL")
        self.assertIsNone(cleaned["price"])
        self.assertIsNone(cleaned["volume"])
        # ... and so on for other fields
        self.assertNotIn("processing_notes", cleaned) # No bad data to note, just missing

    def test_clean_with_collection_errors(self):
        raw_data = {"symbol": "XYZ", "collection_errors": ["Failed here", "Failed there"]}
        cleaned = clean_coin_data(raw_data)
        self.assertEqual(cleaned["symbol"], "XYZ")
        self.assertIn("collection_errors", cleaned)
        self.assertEqual(len(cleaned["collection_errors"]), 2)

    def test_clean_empty_raw_data(self):
        raw_data = {}
        cleaned = clean_coin_data(raw_data)
        self.assertEqual(cleaned["symbol"], "UNKNOWN") # Default symbol
        self.assertIsNone(cleaned["price"])
        self.assertIn("cleaned_at_utc", cleaned)


class TestScorer(unittest.TestCase):

    def _get_base_eligible_data(self, symbol="TEST", sentiment=0.5):
        """Helper to create a base dict with all required fields for eligibility."""
        return {
            "symbol": symbol,
            "price": 1.0, "volume": 1000.0, "active_addresses": 100, 
            "mentions": 100, "sentiment_score": sentiment,
            "transaction_volume_usd": 10000.0, # Included for completeness, though not in REQUIRED_METRICS
            "cleaned_at_utc": datetime.now(timezone.utc).isoformat()
        }

    def test_score_eligible_base_sentiment(self):
        data = self._get_base_eligible_data(sentiment=0.6)
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["symbol"], "TEST")
        self.assertEqual(score_info["score"], 0.6)
        self.assertEqual(score_info["base_sentiment_on_scoring"], 0.6)
        self.assertEqual(score_info["bonuses_applied"], ["none"])

    def test_score_ineligible_missing_metric(self):
        data = self._get_base_eligible_data()
        del data["price"] # Remove a required metric
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["score"], 0.0)
        self.assertIsNone(score_info["base_sentiment_on_scoring"])
        self.assertEqual(score_info["bonuses_applied"], ["ineligible_missing_required_metrics"])

    def test_score_clamping_above_one(self):
        data = self._get_base_eligible_data(sentiment=0.8)
        data["mentions"] = 60000         # +0.1 bonus
        data["active_addresses"] = 250000 # +0.1 bonus
        data["transaction_volume_usd"] = 6e8 # +0.1 bonus
        # Total potential: 0.8 + 0.1 + 0.1 + 0.1 = 1.1
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["score"], 1.0)
        self.assertEqual(score_info["base_sentiment_on_scoring"], 0.8)
        self.assertIn("mentions_high (>50000)", score_info["bonuses_applied"])

    def test_score_clamping_below_zero(self):
        data = self._get_base_eligible_data(sentiment=-0.5) # Negative sentiment
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["score"], 0.0)
        self.assertEqual(score_info["base_sentiment_on_scoring"], -0.5)

    def test_score_medium_bonuses(self):
        data = self._get_base_eligible_data(sentiment=0.5)
        data["mentions"] = 15000        # +0.05
        data["active_addresses"] = 60000 # +0.05
        data["transaction_volume_usd"] = 1.5e8 # +0.05
        # Total potential: 0.5 + 0.05 + 0.05 + 0.05 = 0.65
        score_info = calculate_coin_score(data)
        self.assertAlmostEqual(score_info["score"], 0.65)
        self.assertEqual(score_info["base_sentiment_on_scoring"], 0.5)
        self.assertIn("mentions_medium (>10000)", score_info["bonuses_applied"])
        self.assertIn("active_addresses_medium (>50000)", score_info["bonuses_applied"])
        self.assertIn("tx_volume_medium (>100000000)", score_info["bonuses_applied"])
    
    def test_score_all_required_metrics_present_but_some_are_zero(self):
        data = {
            "symbol": "ZEROS", "price": 0.0, "volume": 0.0, "active_addresses": 0, 
            "mentions": 0, "sentiment_score": 0.0,
            "transaction_volume_usd": 0.0,
            "cleaned_at_utc": datetime.now(timezone.utc).isoformat()
        }
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["score"], 0.0)
        self.assertEqual(score_info["base_sentiment_on_scoring"], 0.0)
        self.assertEqual(score_info["bonuses_applied"], ["none"])

    def test_score_required_metrics_not_in_cleaned_data_dict(self):
        # Test case where a key from REQUIRED_METRICS_FOR_SCORING is entirely missing from cleaned_data
        data = self._get_base_eligible_data()
        # 'price' is in REQUIRED_METRICS_FOR_SCORING
        # We remove it from the dictionary passed to calculate_coin_score
        if 'price' in data:
            del data['price'] 
        score_info = calculate_coin_score(data)
        self.assertEqual(score_info["score"], 0.0, "Score should be 0.0 if a required metric key is missing.")
        self.assertIsNone(score_info["base_sentiment_on_scoring"], "Base sentiment should be None for ineligible.")
        self.assertIn("ineligible_missing_required_metrics", score_info["bonuses_applied"], "Ineligibility reason not noted.")


if __name__ == "__main__":
    unittest.main() 