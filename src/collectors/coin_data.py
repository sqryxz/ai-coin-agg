import json
import requests
import time

# --- CoinGecko API Integration ---
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

def ping_coingecko() -> bool:
    """
    Pings the CoinGecko API to check for connectivity.

    Returns:
        bool: True if the ping is successful (status code 200), False otherwise.
    """
    try:
        response = requests.get(f"{COINGECKO_API_URL}/ping")
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        time.sleep(2)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error pinging CoinGecko API: {e}")
        return False

def fetch_coingecko_market_data(coin_id: str, vs_currency: str = "usd") -> dict:
    """
    Fetches market data (price, volume, market cap) for a single coin from CoinGecko.

    Args:
        coin_id (str): The CoinGecko ID of the coin (e.g., "bitcoin", "ethereum").
        vs_currency (str): The currency to get the price in (e.g., "usd").

    Returns:
        dict: A dictionary containing the coin's ID, price, volume, and market cap.
              Example: {"id": "bitcoin", "price": 60000.00, "volume": 50000000000.00, "market_cap": 1200000000000.00}
              Returns an error field if data retrieval fails or the coin is not found.
    """
    params = {
        "vs_currency": vs_currency,
        "ids": coin_id,
        "order": "market_cap_desc",
        "per_page": 1,
        "page": 1,
        "sparkline": "false"
    }
    try:
        response = requests.get(f"{COINGECKO_API_URL}/coins/markets", params=params)
        response.raise_for_status()
        time.sleep(2)
        data = response.json()
        if data:
            coin_data = data[0]
            return {
                "id": coin_data.get("id"),
                "price": coin_data.get("current_price"),
                "volume": coin_data.get("total_volume"),
                "market_cap": coin_data.get("market_cap")
            }
        else:
            return {"error": f"No data found for coin ID {coin_id} with vs_currency {vs_currency}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Error fetching data from CoinGecko for {coin_id}: {e}"}
    except (IndexError, KeyError) as e:
        return {"error": f"Error parsing CoinGecko response for {coin_id}: {e}"}

def fetch_coingecko_historical_data(coin_id: str, vs_currency: str = "usd", days: str = "1", interval: str = "daily") -> dict:
    """
    Fetches historical market data (prices, market caps, total volumes) for a single coin from CoinGecko.

    Args:
        coin_id (str): The CoinGecko ID of the coin (e.g., "bitcoin").
        vs_currency (str): The currency to get the price in (e.g., "usd").
        days (str): Data up to number of days ago (e.g., "1", "7", "max").
        interval (str): Data interval. Can be "daily" or None for hourly/minutely based on `days`.
                       CoinGecko determines granularity: 
                       1/"max" days: hourly data (automatic)
                       2-90 days: hourly data
                       91+ days: daily data (00:00 UTC)

    Returns:
        dict: A dictionary containing lists of timestamps and corresponding prices, market caps, and total volumes.
              Example: {"prices": [[timestamp, price], ...], "market_caps": ..., "total_volumes": ...}
              Returns an error field if data retrieval fails.
    """
    params = {
        "vs_currency": vs_currency,
        "days": days,
        "interval": interval
    }
    try:
        response = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart", params=params)
        response.raise_for_status()
        time.sleep(2)
        data = response.json()
        # Ensure all expected keys are present, even if empty, for consistent structure
        return {
            "prices": data.get("prices", []),
            "market_caps": data.get("market_caps", []),
            "total_volumes": data.get("total_volumes", [])
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Error fetching historical data from CoinGecko for {coin_id}: {e}"}
    except KeyError as e:
        return {"error": f"Error parsing CoinGecko historical response for {coin_id} - missing key: {e}"}

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

    print("\n--- Testing CoinGecko API Ping ---")
    if ping_coingecko():
        print("CoinGecko API ping successful!")
    else:
        print("CoinGecko API ping failed.")

    print("\n--- Testing fetch_coingecko_market_data ---")
    bitcoin_data = fetch_coingecko_market_data("bitcoin")
    print(f"\nMarket data for Bitcoin (USD): {json.dumps(bitcoin_data, indent=4)}")

    ethereum_data_eur = fetch_coingecko_market_data("ethereum", vs_currency="eur")
    print(f"\nMarket data for Ethereum (EUR): {json.dumps(ethereum_data_eur, indent=4)}")
    
    non_existent_coin = fetch_coingecko_market_data("nonexistentcoin123")
    print(f"\nMarket data for NonExistentCoin: {json.dumps(non_existent_coin, indent=4)}")

    print("\n--- Testing fetch_coingecko_historical_data ---")
    # Fetch 1 day of daily data for bitcoin
    bitcoin_hist_daily = fetch_coingecko_historical_data("bitcoin", days="1", interval="daily")
    print(f"\nHistorical data for Bitcoin (1 day, daily):")
    # To keep output clean, just print the number of data points or first few
    if "error" not in bitcoin_hist_daily:
        print(f"  Prices points: {len(bitcoin_hist_daily.get('prices', []))}")
        print(f"  Market caps points: {len(bitcoin_hist_daily.get('market_caps', []))}")
        print(f"  Total volumes points: {len(bitcoin_hist_daily.get('total_volumes', []))}")
        if bitcoin_hist_daily.get('prices'):
            print(f"  First price point: {bitcoin_hist_daily['prices'][0]}")
    else:
        print(f"  Error: {bitcoin_hist_daily['error']}")

    # Fetch 7 days of default interval (hourly) data for ethereum in EUR
    ethereum_hist_hourly = fetch_coingecko_historical_data("ethereum", vs_currency="eur", days="7")
    print(f"\nHistorical data for Ethereum (7 days, hourly, EUR):")
    if "error" not in ethereum_hist_hourly:
        print(f"  Prices points: {len(ethereum_hist_hourly.get('prices', []))}")
        if ethereum_hist_hourly.get('prices'):
            print(f"  First price point: {ethereum_hist_hourly['prices'][0]}")
    else:
        print(f"  Error: {ethereum_hist_hourly['error']}")

    print("\n--- Test Finished ---") 