import unittest
import sys
import os

# Adjust sys.path to allow importing from the project root (src directory)
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # From tests/test_collectors.py to project_root/
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.collectors.on_chain import fetch_on_chain_metrics

class TestCollectors(unittest.TestCase):

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

if __name__ == "__main__":
    # This allows running the tests directly from the command line
    # Add the project root to sys.path to ensure imports work when run directly
    # The path adjustment at the top of the file should handle this if test file is in /tests
    print(f"Running tests from: {os.getcwd()}")
    print(f"Sys.path includes: {PROJECT_ROOT_PATH}")
    unittest.main() 