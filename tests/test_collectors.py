import unittest
import sys
import os

# Adjust sys.path to allow importing from the project root (src directory)
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # From tests/test_collectors.py to project_root/
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.collectors.coin_data import fetch_coin_price_volume
from src.collectors.on_chain import fetch_on_chain_metrics
from src.collectors.social_data import fetch_social_sentiment

class TestCollectors(unittest.TestCase):

    def test_fetch_coin_price_volume_known_symbol(self):
        data = fetch_coin_price_volume("BTC")
        self.assertEqual(data["symbol"], "BTC")
        self.assertIsNotNone(data["price"])
        self.assertIsInstance(data["price"], float)
        self.assertIsNotNone(data["volume"])
        self.assertIsInstance(data["volume"], float)
        self.assertNotIn("error", data)

    def test_fetch_coin_price_volume_known_symbol_lowercase(self):
        data = fetch_coin_price_volume("eth")
        self.assertEqual(data["symbol"], "ETH") # Expect uppercase symbol in response
        self.assertIsNotNone(data["price"])
        self.assertIsInstance(data["price"], float)
        self.assertIsNotNone(data["volume"])
        self.assertIsInstance(data["volume"], float)
        self.assertNotIn("error", data)

    def test_fetch_coin_price_volume_unknown_symbol(self):
        data = fetch_coin_price_volume("XYZ")
        self.assertEqual(data["symbol"], "XYZ")
        self.assertIsNone(data["price"])
        self.assertIsNone(data["volume"])
        self.assertIn("error", data)
        self.assertIn("Data not found for symbol XYZ", data["error"])

    def test_fetch_on_chain_metrics_known_symbol(self):
        data = fetch_on_chain_metrics("BTC")
        self.assertEqual(data["symbol"], "BTC")
        self.assertIsNotNone(data["active_addresses"])
        self.assertIsInstance(data["active_addresses"], int)
        self.assertIsNotNone(data["transaction_volume_usd"])
        self.assertIsInstance(data["transaction_volume_usd"], float)
        self.assertNotIn("error", data)

    def test_fetch_on_chain_metrics_known_symbol_lowercase(self):
        data = fetch_on_chain_metrics("eth")
        self.assertEqual(data["symbol"], "ETH")
        self.assertIsNotNone(data["active_addresses"])
        self.assertIsInstance(data["active_addresses"], int)
        self.assertIsNotNone(data["transaction_volume_usd"])
        self.assertIsInstance(data["transaction_volume_usd"], float)
        self.assertNotIn("error", data)

    def test_fetch_on_chain_metrics_unknown_symbol(self):
        data = fetch_on_chain_metrics("XYZ")
        self.assertEqual(data["symbol"], "XYZ")
        self.assertIsNone(data["active_addresses"])
        self.assertIsNone(data["transaction_volume_usd"])
        self.assertIn("error", data)
        self.assertIn("On-chain data not found for symbol XYZ", data["error"])

    def test_fetch_social_sentiment_known_symbol(self):
        data = fetch_social_sentiment("BTC")
        self.assertEqual(data["symbol"], "BTC")
        self.assertIsNotNone(data["mentions"])
        self.assertIsInstance(data["mentions"], int)
        self.assertIsNotNone(data["sentiment_score"])
        self.assertIsInstance(data["sentiment_score"], float)
        self.assertNotIn("error", data)

    def test_fetch_social_sentiment_known_symbol_lowercase(self):
        data = fetch_social_sentiment("eth")
        self.assertEqual(data["symbol"], "ETH")
        self.assertIsNotNone(data["mentions"])
        self.assertIsInstance(data["mentions"], int)
        self.assertIsNotNone(data["sentiment_score"])
        self.assertIsInstance(data["sentiment_score"], float)
        self.assertNotIn("error", data)

    def test_fetch_social_sentiment_unknown_symbol(self):
        data = fetch_social_sentiment("XYZ")
        self.assertEqual(data["symbol"], "XYZ")
        self.assertIsNone(data["mentions"])
        self.assertIsNone(data["sentiment_score"])
        self.assertIn("error", data)
        self.assertIn("Social data not found for symbol XYZ", data["error"])

if __name__ == "__main__":
    # This allows running the tests directly from the command line
    # Add the project root to sys.path to ensure imports work when run directly
    # The path adjustment at the top of the file should handle this if test file is in /tests
    print(f"Running tests from: {os.getcwd()}")
    print(f"Sys.path includes: {PROJECT_ROOT_PATH}")
    unittest.main() 