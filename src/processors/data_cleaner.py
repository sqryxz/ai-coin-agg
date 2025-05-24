from datetime import datetime, timezone
import json

def clean_coin_data(raw_data: dict) -> dict:
    """
    Cleans the raw collected data for a single coin.
    - Ensures numeric types for relevant fields.
    - Adds a processing timestamp.

    Args:
        raw_data (dict): The raw data dictionary, typically from collect_all_data_for_coin.

    Returns:
        dict: The cleaned data dictionary.
    """
    cleaned_data = {
        "symbol": raw_data.get("symbol", "UNKNOWN"), # Default symbol if missing
        "price": None,
        "volume": None,
        "active_addresses": None,
        "transaction_volume_usd": None,
        "mentions": None,
        "sentiment_score": None,
        "cleaned_at_utc": datetime.now(timezone.utc).isoformat()
    }
    
    processing_notes = []

    # Fields to be treated as float
    float_fields = ["price", "volume", "transaction_volume_usd", "sentiment_score"]
    # Fields to be treated as int
    int_fields = ["active_addresses", "mentions"]

    for field in float_fields:
        value = raw_data.get(field)
        if value is not None:
            try:
                cleaned_data[field] = float(value)
            except (ValueError, TypeError):
                note = f"Could not convert '{field}' value '{value}' to float. Kept as None."
                processing_notes.append(note)
                cleaned_data[field] = None # Ensure it's None if conversion fails
        else:
            cleaned_data[field] = None # Explicitly set to None if not present in raw_data

    for field in int_fields:
        value = raw_data.get(field)
        if value is not None:
            try:
                cleaned_data[field] = int(value)
            except (ValueError, TypeError):
                note = f"Could not convert '{field}' value '{value}' to int. Kept as None."
                processing_notes.append(note)
                cleaned_data[field] = None
        else:
            cleaned_data[field] = None

    # Carry over collection errors if they exist
    if "collection_errors" in raw_data:
        cleaned_data["collection_errors"] = raw_data["collection_errors"]
    
    if processing_notes:
        cleaned_data["processing_notes"] = processing_notes
            
    return cleaned_data

if __name__ == "__main__":
    print("--- Testing clean_coin_data ---")

    # 1. Sample good raw data
    good_raw_data = {
        "symbol": "BTC",
        "price": 60000.75,
        "volume": "50000000000.00", # String, but convertible
        "active_addresses": 1200000,
        "transaction_volume_usd": 10000000000.00,
        "mentions": "15000", # String, but convertible
        "sentiment_score": 0.75
    }
    print("\n--- Cleaning good_raw_data ---")
    cleaned_good_data = clean_coin_data(good_raw_data)
    print(json.dumps(cleaned_good_data, indent=4))

    # 2. Sample mixed raw data (some missing, some non-numeric)
    mixed_raw_data = {
        "symbol": "ETH",
        "price": "not_a_number",
        "volume": 25000000000.00,
        # active_addresses is missing
        "transaction_volume_usd": None, # Explicitly None
        "mentions": "around 12k", # Not directly convertible to int
        "sentiment_score": 0.68
    }
    print("\n--- Cleaning mixed_raw_data ---")
    cleaned_mixed_data = clean_coin_data(mixed_raw_data)
    print(json.dumps(cleaned_mixed_data, indent=4))

    # 3. Sample data with collection errors (simulating output from main.py)
    error_raw_data = {
        "symbol": "XYZ",
        "price": None,
        "volume": None,
        "active_addresses": None,
        "transaction_volume_usd": None,
        "mentions": None,
        "sentiment_score": None,
        "collection_errors": [
            "CoinData: Data not found for symbol XYZ",
            "OnChain: On-chain data not found for symbol XYZ"
        ]
    }
    print("\n--- Cleaning error_raw_data ---")
    cleaned_error_data = clean_coin_data(error_raw_data)
    print(json.dumps(cleaned_error_data, indent=4))
    
    # 4. Sample data with a completely missing symbol (edge case)
    no_symbol_raw_data = {
        "price": 100.0
    }
    print("\n--- Cleaning no_symbol_raw_data ---")
    cleaned_no_symbol_data = clean_coin_data(no_symbol_raw_data)
    print(json.dumps(cleaned_no_symbol_data, indent=4))

    print("\n--- Data Cleaning Test Finished ---") 