import json
import requests
import os # For potential future use, good to have

# Assuming this file (on_chain.py) is in src/collectors/, 
# and config.py is in src/utils/. We need to adjust path to import config for API key.
import sys
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.utils import config # For ETHERSCAN_API_KEY

# Etherscan API Configuration
ETHERSCAN_API_URL = "https://api.etherscan.io/api"

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

# --- Etherscan API Integration ---
def ping_etherscan() -> bool:
    """
    Pings the Etherscan API by fetching the current ETH price to check connectivity and API key validity.

    Returns:
        bool: True if the ping is successful and API key seems valid, False otherwise.
    """
    if not config.ETHERSCAN_API_KEY or config.ETHERSCAN_API_KEY == "YOUR_ETHERSCAN_API_KEY_HERE":
        print("Etherscan API key not configured or is placeholder. Skipping ping.")
        return False
    
    params = {
        "module": "stats",
        "action": "ethprice",
        "apikey": config.ETHERSCAN_API_KEY
    }
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        # Etherscan returns "1" for error if API key is invalid, and "0" if OK (even if result is empty for some queries)
        # For ethprice, a valid response should have status "1" (meaning success) and a non-error message.
        if data.get("status") == "1" and data.get("message") == "OK":
            print(f"Etherscan API ping successful. Current ETH Price: {data.get('result', {}).get('ethusd')}")
            return True
        else:
            print(f"Etherscan API ping failed or key invalid. Response: {data}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error pinging Etherscan API: {e}")
        return False
    except json.JSONDecodeError:
        print(f"Error decoding Etherscan API response. Raw response: {response.text if response else 'No response'}")
        return False

def fetch_etherscan_token_active_addresses(contract_address: str) -> dict:
    """
    Fetches a proxy for active addresses of an ERC20 token by counting unique participants 
    in the last N transactions.

    Args:
        contract_address (str): The ERC20 token's contract address.

    Returns:
        dict: Contains {"contract_address": address, "active_addresses_proxy": count} 
              or {"error": ...} if an issue occurs.
              The active_addresses_proxy is the count of unique addresses in 'from' and 'to' fields
              of the most recent transactions (up to 1000).
    """
    if not config.ETHERSCAN_API_KEY or config.ETHERSCAN_API_KEY == "YOUR_ETHERSCAN_API_KEY_HERE":
        return {"contract_address": contract_address, "error": "Etherscan API key not configured."}
    if not contract_address:
        return {"contract_address": contract_address, "error": "Contract address not provided."}

    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": contract_address,
        "page": 1,
        "offset": 1000, # Max 10000 for pro, public API might be less or slower
        "sort": "desc",
        "apikey": config.ETHERSCAN_API_KEY
    }
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("message") == "OK":
            transactions = data.get("result", [])
            if not isinstance(transactions, list):
                 # Can happen if the contract address is wrong or has no txs, Etherscan might return a string message
                return {"contract_address": contract_address, "active_addresses_proxy": 0, "info": "No transactions found or invalid contract for tokentx."}
            
            unique_addresses = set()
            for tx in transactions:
                if tx.get("from"): unique_addresses.add(tx["from"].lower())
                if tx.get("to"): unique_addresses.add(tx["to"].lower())
            return {"contract_address": contract_address, "active_addresses_proxy": len(unique_addresses)}
        elif data.get("status") == "0" and "No transactions found" in data.get("message", ""):
             return {"contract_address": contract_address, "active_addresses_proxy": 0, "info": "No transactions found for this token."}
        else:
            return {"contract_address": contract_address, "error": f"Etherscan API error: {data.get('message', 'Unknown error')} - Result: {data.get('result', '')}"}

    except requests.exceptions.RequestException as e:
        return {"contract_address": contract_address, "error": f"RequestException: {e}"}
    except json.JSONDecodeError:
        return {"contract_address": contract_address, "error": f"JSONDecodeError with Etherscan response. Raw: {response.text if response else 'No response'}"}
    except Exception as e:
        return {"contract_address": contract_address, "error": f"An unexpected error occurred: {e}"}

def fetch_etherscan_token_transaction_count(contract_address: str, offset: int = 1000) -> dict:
    """
    Fetches the count of recent token transactions for an ERC20 token.

    Args:
        contract_address (str): The ERC20 token's contract address.
        offset (int): The number of recent transactions to check (max 10000 for pro, public might be less).
                      The actual count returned will be min(offset, actual_tx_count_in_response).

    Returns:
        dict: Contains {"contract_address": address, "transaction_count_proxy": count} 
              or {"error": ...} if an issue occurs.
              The transaction_count_proxy is the number of transactions returned by the API call (up to offset).
    """
    if not config.ETHERSCAN_API_KEY or config.ETHERSCAN_API_KEY == "YOUR_ETHERSCAN_API_KEY_HERE":
        return {"contract_address": contract_address, "error": "Etherscan API key not configured."}
    if not contract_address:
        return {"contract_address": contract_address, "error": "Contract address not provided."}

    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": contract_address,
        "page": 1,
        "offset": offset,
        "sort": "desc",
        "apikey": config.ETHERSCAN_API_KEY
    }
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("message") == "OK":
            transactions = data.get("result", [])
            if not isinstance(transactions, list):
                return {"contract_address": contract_address, "transaction_count_proxy": 0, "info": "No transactions found or invalid response for tokentx."}
            return {"contract_address": contract_address, "transaction_count_proxy": len(transactions)}
        elif data.get("status") == "0" and "No transactions found" in data.get("message", ""):
             return {"contract_address": contract_address, "transaction_count_proxy": 0, "info": "No transactions found for this token."}
        else:
            return {"contract_address": contract_address, "error": f"Etherscan API error: {data.get('message', 'Unknown error')} - Result: {data.get('result', '')}"}

    except requests.exceptions.RequestException as e:
        return {"contract_address": contract_address, "error": f"RequestException: {e}"}
    except json.JSONDecodeError:
        return {"contract_address": contract_address, "error": f"JSONDecodeError with Etherscan response. Raw: {response.text if response else 'No response'}"}
    except Exception as e:
        return {"contract_address": contract_address, "error": f"An unexpected error occurred: {e}"}

def fetch_etherscan_token_total_supply(contract_address: str, coingecko_id: str) -> dict:
    """
    Fetches the total supply of an ERC20 token and converts it to its standard unit using decimals from config.

    Args:
        contract_address (str): The ERC20 token's contract address.
        coingecko_id (str): The CoinGecko ID of the token, used to look up its decimals in config.COIN_MAPPING.

    Returns:
        dict: Contains {"contract_address": address, "total_supply": value, "total_supply_display": "value unit"}
              or {"error": ...} if an issue occurs.
    """
    if not config.ETHERSCAN_API_KEY or config.ETHERSCAN_API_KEY == "YOUR_ETHERSCAN_API_KEY_HERE":
        return {"contract_address": contract_address, "error": "Etherscan API key not configured."}
    if not contract_address:
        # For ETH itself, total supply is fetched differently (e.g., ethsupply action or from CoinGecko)
        # This function is specifically for ERC20 tokens with a contract address.
        return {"contract_address": contract_address, "error": "Contract address not provided for ERC20 token."}
    if not coingecko_id:
        return {"contract_address": contract_address, "error": "CoinGecko ID not provided for fetching decimals."}

    coin_info = config.COIN_MAPPING.get(coingecko_id)
    decimals = coin_info.get("decimals") if coin_info else None

    if decimals is None:
        return {"contract_address": contract_address, "error": f"Decimals not found in COIN_MAPPING for coingecko_id: {coingecko_id}"}

    params = {
        "module": "stats",
        "action": "tokensupply",
        "contractaddress": contract_address,
        "apikey": config.ETHERSCAN_API_KEY
    }
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("message") == "OK":
            raw_supply_str = data.get("result")
            if raw_supply_str is None:
                 return {"contract_address": contract_address, "error": "Total supply not found in Etherscan response."}
            try:
                raw_supply = int(raw_supply_str)
                actual_supply = raw_supply / (10 ** decimals)
                token_symbol = coin_info.get("symbol", "tokens")
                return {
                    "contract_address": contract_address,
                    "total_supply_raw": raw_supply_str, 
                    "total_supply_adjusted": actual_supply,
                    "total_supply_display": f"{actual_supply:,.{min(decimals, 8)}f} {token_symbol}" # Format with commas and appropriate decimal places
                }
            except ValueError:
                return {"contract_address": contract_address, "error": f"Invalid total supply value from Etherscan: {raw_supply_str}"}
        else:
            return {"contract_address": contract_address, "error": f"Etherscan API error for token supply: {data.get('message', 'Unknown error')} - Result: {data.get('result', '')}"}

    except requests.exceptions.RequestException as e:
        return {"contract_address": contract_address, "error": f"RequestException: {e}"}
    except json.JSONDecodeError:
        return {"contract_address": contract_address, "error": f"JSONDecodeError for token supply. Raw: {response.text if response else 'No response'}"}
    except Exception as e:
        return {"contract_address": contract_address, "error": f"An unexpected error occurred: {e}"}

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

    print("\n--- Testing Etherscan API Ping ---")
    if ping_etherscan():
        print("Etherscan API ping test successful!")
    else:
        print("Etherscan API ping test failed. Check API key and configuration.")

    print("\n--- Testing fetch_etherscan_token_active_addresses ---")
    # Example: Chainlink (LINK) contract address
    link_contract_address = "0x514910771AF9Ca656af840dff83E8264EcF986CA"
    link_active_addr_data = fetch_etherscan_token_active_addresses(link_contract_address)
    print(f"\nActive addresses data for LINK ({link_contract_address}): {json.dumps(link_active_addr_data, indent=4)}")

    # Example: A non-existent or invalid contract address for testing error handling
    invalid_contract_address = "0x0000000000000000000000000000000000000000"
    invalid_active_addr_data = fetch_etherscan_token_active_addresses(invalid_contract_address)
    print(f"\nActive addresses data for invalid contract ({invalid_contract_address}): {json.dumps(invalid_active_addr_data, indent=4)}")
    
    # Test with an empty contract address
    empty_contract_addr_data = fetch_etherscan_token_active_addresses("")
    print(f"\nActive addresses data for empty contract string: {json.dumps(empty_contract_addr_data, indent=4)}")

    print("\n--- Testing fetch_etherscan_token_transaction_count ---")
    # Example: Chainlink (LINK) contract address
    link_tx_count_data = fetch_etherscan_token_transaction_count(link_contract_address, offset=100) # Check last 100 txns
    print(f"\nTransaction count data for LINK ({link_contract_address}): {json.dumps(link_tx_count_data, indent=4)}")

    # Test with a contract that might have fewer than the offset transactions, or zero
    # For this test, we'll use the invalid address again, expecting 0 or error.
    invalid_tx_count_data = fetch_etherscan_token_transaction_count(invalid_contract_address)
    print(f"\nTransaction count data for invalid contract ({invalid_contract_address}): {json.dumps(invalid_tx_count_data, indent=4)}")

    print("\n--- Testing fetch_etherscan_token_total_supply ---")
    # Example: Chainlink (LINK)
    link_coingecko_id = "chainlink" # Must match a key in COIN_MAPPING with decimals
    link_supply_data = fetch_etherscan_token_total_supply(link_contract_address, link_coingecko_id)
    print(f"\nTotal supply data for LINK ({link_contract_address}): {json.dumps(link_supply_data, indent=4)}")

    # Example: Uniswap (UNI)
    uni_coingecko_id = "uniswap"
    uni_contract_address = config.COIN_MAPPING.get(uni_coingecko_id, {}).get("contract_address")
    if uni_contract_address:
        uni_supply_data = fetch_etherscan_token_total_supply(uni_contract_address, uni_coingecko_id)
        print(f"\nTotal supply data for UNI ({uni_contract_address}): {json.dumps(uni_supply_data, indent=4)}")
    else:
        print(f"\nCould not test UNI total supply: contract address not found in COIN_MAPPING for id '{uni_coingecko_id}'.")

    # Test with a coingecko_id not in mapping or missing decimals
    supply_data_no_decimals = fetch_etherscan_token_total_supply(link_contract_address, "nonexistent_cg_id_for_decimals")
    print(f"\nTotal supply data for token with no decimals in config: {json.dumps(supply_data_no_decimals, indent=4)}")

    print("\n--- Test Finished ---") 