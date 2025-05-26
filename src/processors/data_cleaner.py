from datetime import datetime, timezone
import json

def clean_coin_data(raw_data: dict) -> dict:
    """
    Cleans the raw collected data for a single coin.
    - Ensures numeric types for relevant fields.
    - Imputes default values (0.0 for float, 0 for int) if data is missing or unconvertible.
    - Adds a processing timestamp.

    Args:
        raw_data (dict): The raw data dictionary, typically from collect_all_data_for_coin.

    Returns:
        dict: The cleaned data dictionary.
    """
    # Initialize all expected fields, including new ones
    cleaned_data = {
        "coingecko_id": raw_data.get("coingecko_id"), # Carry over Coingecko ID
        "symbol": raw_data.get("symbol", "UNKNOWN"),
        "price": 0.0,
        "volume": 0.0,
        "market_cap": 0.0,
        "active_addresses": 0,
        "transaction_volume_usd": 0.0,
        "etherscan_active_addresses_proxy": 0,
        "etherscan_transaction_count_proxy": 0,
        "etherscan_total_supply_adjusted": 0.0,
        "mentions": 0, # From CryptoPanic (articles_with_votes)
        "sentiment_score": 0.0, # CryptoPanic aggregate
        "gdelt_sentiment_score": 0.0,
        "gdelt_article_count": 0,
        "cleaned_at_utc": datetime.now(timezone.utc).isoformat()
    }
    
    processing_notes = []

    # Define fields and their target types and default values
    # (name, type_constructor, default_value)
    field_definitions = [
        ("price", float, 0.0),
        ("volume", float, 0.0),
        ("market_cap", float, 0.0),
        ("active_addresses", int, 0), # Main active addresses (could be from Etherscan or mock)
        ("transaction_volume_usd", float, 0.0),
        ("etherscan_active_addresses_proxy", int, 0),
        ("etherscan_transaction_count_proxy", int, 0),
        ("etherscan_total_supply_adjusted", float, 0.0),
        ("mentions", int, 0), # CryptoPanic mentions
        ("sentiment_score", float, 0.0), # CryptoPanic score
        ("gdelt_sentiment_score", float, 0.0),
        ("gdelt_article_count", int, 0)
    ]

    for field_name, type_constructor, default_value in field_definitions:
        raw_value = raw_data.get(field_name)
        if raw_value is not None:
            try:
                cleaned_data[field_name] = type_constructor(raw_value)
            except (ValueError, TypeError):
                note = f"Could not convert '{field_name}' value '{raw_value}' to {type_constructor.__name__}. Used default: {default_value}."
                processing_notes.append(note)
                cleaned_data[field_name] = default_value
        else:
            # If raw_value is None, it's already set to default in initialization or will be handled here
            cleaned_data[field_name] = default_value
            processing_notes.append(f"Field '{field_name}' was missing or None. Used default: {default_value}.")


    # Carry over collection errors if they exist
    if "collection_errors" in raw_data:
        cleaned_data["collection_errors"] = raw_data["collection_errors"]
    
    if processing_notes:
        cleaned_data["processing_notes"] = processing_notes
            
    return cleaned_data

if __name__ == "__main__":
    print("--- Testing clean_coin_data ---")

    # 1. Sample good raw data with all new fields
    good_raw_data = {
        "coingecko_id": "bitcoin",
        "symbol": "BTC",
        "price": 60000.75,
        "volume": "50000000000.00",
        "market_cap": "1200000000000.00",
        "active_addresses": 1200000,
        "transaction_volume_usd": 10000000000.00,
        "etherscan_active_addresses_proxy": None, # Example for BTC (non-ERC20)
        "etherscan_transaction_count_proxy": None,
        "etherscan_total_supply_adjusted": None,
        "mentions": "15000",
        "sentiment_score": 0.75,
        "gdelt_sentiment_score": -1.5,
        "gdelt_article_count": 25
    }
    print("\n--- Cleaning good_raw_data (BTC) ---")
    cleaned_good_data = clean_coin_data(good_raw_data)
    print(json.dumps(cleaned_good_data, indent=4))

    # 2. Sample mixed raw data for an ERC20 (e.g., LINK)
    mixed_raw_data_erc20 = {
        "coingecko_id": "chainlink",
        "symbol": "LINK",
        "price": "not_a_number", # Invalid
        "volume": 250000000.00,
        "market_cap": 7000000000.0,
        "active_addresses": 5000, # Populated by etherscan_active_addresses_proxy
        "transaction_volume_usd": None, # Explicitly None, should default
        "etherscan_active_addresses_proxy": 5000,
        "etherscan_transaction_count_proxy": "1200", # String int
        "etherscan_total_supply_adjusted": "25000000.0", # String float
        "mentions": "around 1.2k", # Not directly convertible to int
        "sentiment_score": 0.68,
        "gdelt_sentiment_score": "N/A", # Invalid
        "gdelt_article_count": "10" # String int
    }
    print("\n--- Cleaning mixed_raw_data (ERC20 - LINK) ---")
    cleaned_mixed_data_erc20 = clean_coin_data(mixed_raw_data_erc20)
    print(json.dumps(cleaned_mixed_data_erc20, indent=4))

    # 3. Sample data with collection errors and many missing fields
    error_raw_data = {
        "coingecko_id": "failingcoin",
        "symbol": "XYZ",
        # All numeric fields missing
        "collection_errors": [
            "CoinGecko: API timeout",
            "Etherscan: Rate limit exceeded"
        ]
    }
    print("\n--- Cleaning error_raw_data (XYZ) ---")
    cleaned_error_data = clean_coin_data(error_raw_data)
    print(json.dumps(cleaned_error_data, indent=4))
    
    # 4. Sample data with a completely missing symbol (edge case)
    no_symbol_raw_data = {
        "coingecko_id": "unknown_coin",
        "price": 100.0,
        "gdelt_article_count": 5
    }
    print("\n--- Cleaning no_symbol_raw_data ---")
    cleaned_no_symbol_data = clean_coin_data(no_symbol_raw_data)
    print(json.dumps(cleaned_no_symbol_data, indent=4))

    # 5. Test with all fields explicitly None
    all_none_data = {
        "coingecko_id": "nonecoin",
        "symbol": "NUL",
        "price": None, "volume": None, "market_cap": None,
        "active_addresses": None, "transaction_volume_usd": None,
        "etherscan_active_addresses_proxy": None, "etherscan_transaction_count_proxy": None,
        "etherscan_total_supply_adjusted": None, "mentions": None,
        "sentiment_score": None, "gdelt_sentiment_score": None, "gdelt_article_count": None
    }
    print("\n--- Cleaning all_none_data ---")
    cleaned_all_none_data = clean_coin_data(all_none_data)
    print(json.dumps(cleaned_all_none_data, indent=4))

    print("\n--- Data Cleaning Test Finished ---") 