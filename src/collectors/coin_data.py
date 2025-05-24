import json

# Mock data source for coin prices and volumes
MOCK_COIN_DATA = {
    "BTC": {"price": 60000.75, "volume": 50000000000.00},
    "ETH": {"price": 4000.50, "volume": 25000000000.00},
    "SOL": {"price": 150.25, "volume": 2000000000.00},
}

def fetch_coin_price_volume(coin_symbol: str) -> dict:
    """
    Fetches the price and volume for a given coin symbol using mock data.

    Args:
        coin_symbol (str): The symbol of the coin (e.g., "BTC").

    Returns:
        dict: A dictionary containing the coin's symbol, price, and volume.
              Example: {"symbol": "BTC", "price": 60000.00, "volume": 50000000000.00}
              Returns an error field if data is not found.
              Example: {"symbol": "XYZ", "price": None, "volume": None, "error": "Data not found for symbol XYZ"}
    """
    coin_symbol_upper = coin_symbol.upper()
    if coin_symbol_upper in MOCK_COIN_DATA:
        data = MOCK_COIN_DATA[coin_symbol_upper]
        return {
            "symbol": coin_symbol_upper,
            "price": data["price"],
            "volume": data["volume"]
        }
    else:
        return {
            "symbol": coin_symbol_upper,
            "price": None,
            "volume": None,
            "error": f"Data not found for symbol {coin_symbol_upper}"
        }

if __name__ == "__main__":
    print("--- Testing fetch_coin_price_volume ---")

    # Test with a known coin symbol
    btc_data = fetch_coin_price_volume("BTC")
    print(f"\nData for BTC: {json.dumps(btc_data, indent=4)}")

    eth_data_lower = fetch_coin_price_volume("eth")
    print(f"\nData for eth (lowercase): {json.dumps(eth_data_lower, indent=4)}")

    # Test with an unknown coin symbol
    xyz_data = fetch_coin_price_volume("XYZ")
    print(f"\nData for XYZ: {json.dumps(xyz_data, indent=4)}")
    
    sol_data = fetch_coin_price_volume("SOL")
    print(f"\nData for SOL: {json.dumps(sol_data, indent=4)}")

    print("\n--- Test Finished ---") 