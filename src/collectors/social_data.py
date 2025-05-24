import json

# Mock data source for social sentiment data
MOCK_SOCIAL_DATA = {
    "BTC": {"mentions": 15000, "sentiment_score": 0.75},
    "ETH": {"mentions": 12000, "sentiment_score": 0.68},
    "SOL": {"mentions": 5000, "sentiment_score": 0.82},
    "DOGE": {"mentions": 25000, "sentiment_score": 0.55} # Added a different coin for variety
}

def fetch_social_sentiment(coin_symbol: str) -> dict:
    """
    Fetches mock social sentiment data for a given coin symbol.

    Args:
        coin_symbol (str): The symbol of the coin (e.g., "BTC").

    Returns:
        dict: A dictionary containing the coin's symbol, mentions, and sentiment_score.
              Example: {"symbol": "BTC", "mentions": 15000, "sentiment_score": 0.75}
              Returns an error field if data is not found.
              Example: {"symbol": "XYZ", "mentions": None, "sentiment_score": None, "error": "Social data not found for symbol XYZ"}
    """
    coin_symbol_upper = coin_symbol.upper()
    if coin_symbol_upper in MOCK_SOCIAL_DATA:
        data = MOCK_SOCIAL_DATA[coin_symbol_upper]
        return {
            "symbol": coin_symbol_upper,
            "mentions": data["mentions"],
            "sentiment_score": data["sentiment_score"]
        }
    else:
        return {
            "symbol": coin_symbol_upper,
            "mentions": None,
            "sentiment_score": None,
            "error": f"Social data not found for symbol {coin_symbol_upper}"
        }

if __name__ == "__main__":
    print("--- Testing fetch_social_sentiment ---")

    # Test with a known coin symbol
    btc_social = fetch_social_sentiment("BTC")
    print(f"\nSocial sentiment for BTC: {json.dumps(btc_social, indent=4)}")

    eth_social_lower = fetch_social_sentiment("eth")
    print(f"\nSocial sentiment for eth (lowercase): {json.dumps(eth_social_lower, indent=4)}")

    # Test with another known coin
    doge_social = fetch_social_sentiment("DOGE")
    print(f"\nSocial sentiment for DOGE: {json.dumps(doge_social, indent=4)}")

    # Test with an unknown coin symbol
    xyz_social = fetch_social_sentiment("XYZ")
    print(f"\nSocial sentiment for XYZ: {json.dumps(xyz_social, indent=4)}")

    print("\n--- Test Finished ---") 