import json

# Mock data source for on-chain metrics
MOCK_ON_CHAIN_DATA = {
    "BTC": {"active_addresses": 1200000, "transaction_volume_usd": 10000000000.00},
    "ETH": {"active_addresses": 800000, "transaction_volume_usd": 7500000000.00},
    "SOL": {"active_addresses": 300000, "transaction_volume_usd": 1500000000.00},
}

def fetch_on_chain_metrics(coin_symbol: str) -> dict:
    """
    Fetches mock on-chain metrics for a given coin symbol.

    Args:
        coin_symbol (str): The symbol of the coin (e.g., "BTC").

    Returns:
        dict: A dictionary containing the coin's symbol, active_addresses, 
              and transaction_volume_usd.
              Example: {"symbol": "BTC", "active_addresses": 1200000, "transaction_volume_usd": 10000000000.00}
              Returns an error field if data is not found.
              Example: {"symbol": "XYZ", "active_addresses": None, "transaction_volume_usd": None, "error": "On-chain data not found for symbol XYZ"}
    """
    coin_symbol_upper = coin_symbol.upper()
    if coin_symbol_upper in MOCK_ON_CHAIN_DATA:
        data = MOCK_ON_CHAIN_DATA[coin_symbol_upper]
        return {
            "symbol": coin_symbol_upper,
            "active_addresses": data["active_addresses"],
            "transaction_volume_usd": data["transaction_volume_usd"]
        }
    else:
        return {
            "symbol": coin_symbol_upper,
            "active_addresses": None,
            "transaction_volume_usd": None,
            "error": f"On-chain data not found for symbol {coin_symbol_upper}"
        }

if __name__ == "__main__":
    print("--- Testing fetch_on_chain_metrics ---")

    # Test with a known coin symbol
    btc_metrics = fetch_on_chain_metrics("BTC")
    print(f"\nOn-chain metrics for BTC: {json.dumps(btc_metrics, indent=4)}")

    eth_metrics_lower = fetch_on_chain_metrics("eth")
    print(f"\nOn-chain metrics for eth (lowercase): {json.dumps(eth_metrics_lower, indent=4)}")

    # Test with an unknown coin symbol
    xyz_metrics = fetch_on_chain_metrics("XYZ")
    print(f"\nOn-chain metrics for XYZ: {json.dumps(xyz_metrics, indent=4)}")

    sol_metrics = fetch_on_chain_metrics("SOL")
    print(f"\nOn-chain metrics for SOL: {json.dumps(sol_metrics, indent=4)}")

    print("\n--- Test Finished ---") 