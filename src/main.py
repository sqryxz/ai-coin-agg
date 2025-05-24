import json
import sys # For sys.exit in main block
import os # For path joining for logger if needed

# Import config first
from src.utils import config

# Attempt to import collector functions. 
# This assumes main.py is run in a way that Python can find the 'collectors' package (e.g. from project root: python3 src/main.py)
from src.collectors.coin_data import fetch_coin_price_volume
from src.collectors.on_chain import fetch_on_chain_metrics
from src.collectors.social_data import fetch_social_sentiment

from src.processors.data_cleaner import clean_coin_data
from src.processors.scorer import calculate_coin_score

from src.database.db_manager import (
    execute_write_query, 
    execute_read_query,
    get_coin_id_by_symbol,
    initialize_database # To ensure DB is set up
)
from src.database.data_loader import (
    load_test_coins_data, 
    clear_coins_table # To ensure fresh state for testing saves
)
from src.utils.logger import setup_logger # Import the logger setup function

# Setup logger for the main application module, using config for file name
logger = setup_logger(name='main_app', log_file_name=config.APP_LOG_FILE)

def collect_all_data_for_coin(coin_symbol: str) -> dict:
    """
    Collects all available data (price/volume, on-chain, social) for a given coin symbol.

    Args:
        coin_symbol (str): The symbol of the coin (e.g., "BTC").

    Returns:
        dict: A combined dictionary containing all fetched data and any collection errors.
              Example for full success:
              {
                  "symbol": "BTC", "price": 60000.0, "volume": 5e10, 
                  "active_addresses": 1.2e6, "transaction_volume_usd": 1e10,
                  "mentions": 15000, "sentiment_score": 0.75
              }
              Example with partial failure:
              {
                  "symbol": "XYZ", "price": null, "volume": null, 
                  "active_addresses": null, "transaction_volume_usd": null,
                  "mentions": null, "sentiment_score": null,
                  "collection_errors": [
                      "CoinData: Data not found for symbol XYZ",
                      "OnChain: On-chain data not found for symbol XYZ",
                      "SocialData: Social data not found for symbol XYZ"
                  ]
              }
    """
    coin_symbol_upper = coin_symbol.upper()
    logger.debug(f"Collecting all data for symbol: {coin_symbol_upper}")
    
    # Initialize with all potential data keys to None for a consistent structure
    combined_data = {
        "symbol": coin_symbol_upper,
        "price": None,
        "volume": None,
        "active_addresses": None,
        "transaction_volume_usd": None,
        "mentions": None,
        "sentiment_score": None
    }
    errors = []

    # 1. Fetch Price and Volume Data
    price_volume_data = fetch_coin_price_volume(coin_symbol_upper)
    if "error" in price_volume_data:
        errors.append(f"CoinData: {price_volume_data['error']}")
        logger.warning(f"Error fetching price/volume for {coin_symbol_upper}: {price_volume_data['error']}")
    else:
        combined_data["price"] = price_volume_data.get("price")
        combined_data["volume"] = price_volume_data.get("volume")
        logger.debug(f"Price/volume for {coin_symbol_upper} fetched: Price={combined_data['price']}, Volume={combined_data['volume']}")

    # 2. Fetch On-Chain Metrics
    on_chain_data = fetch_on_chain_metrics(coin_symbol_upper)
    if "error" in on_chain_data:
        errors.append(f"OnChain: {on_chain_data['error']}")
        logger.warning(f"Error fetching on-chain data for {coin_symbol_upper}: {on_chain_data['error']}")
    else:
        combined_data["active_addresses"] = on_chain_data.get("active_addresses")
        combined_data["transaction_volume_usd"] = on_chain_data.get("transaction_volume_usd")
        logger.debug(f"On-chain for {coin_symbol_upper} fetched: ActiveAddresses={combined_data['active_addresses']}")

    # 3. Fetch Social Sentiment Data
    social_data_res = fetch_social_sentiment(coin_symbol_upper)
    if "error" in social_data_res:
        errors.append(f"SocialData: {social_data_res['error']}")
        logger.warning(f"Error fetching social data for {coin_symbol_upper}: {social_data_res['error']}")
    else:
        combined_data["mentions"] = social_data_res.get("mentions")
        combined_data["sentiment_score"] = social_data_res.get("sentiment_score")
        logger.debug(f"Social data for {coin_symbol_upper} fetched: Mentions={combined_data['mentions']}")
    
    if errors:
        combined_data["collection_errors"] = errors
        logger.info(f"Finished collecting data for {coin_symbol_upper} with {len(errors)} error(s).")
    else:
        logger.info(f"Successfully collected all data for {coin_symbol_upper}.")
    return combined_data

def process_and_save_coin_data(coin_symbol: str):
    logger.info(f"Starting full process for {coin_symbol}")
    
    logger.info(f"Collecting data for {coin_symbol}...")
    raw_data = collect_all_data_for_coin(coin_symbol)
    logger.debug(f"Raw data for {coin_symbol}: {json.dumps(raw_data, indent=2)}")
    if not raw_data or raw_data.get("symbol") == "UNKNOWN" or raw_data.get("price") is None: # Adding price check as example
        logger.error(f"Failed to collect sufficient raw data for {coin_symbol}. Aborting further processing.")
        return

    logger.info(f"Cleaning data for {coin_symbol}...")
    cleaned_data = clean_coin_data(raw_data)
    logger.debug(f"Cleaned data for {coin_symbol}: {json.dumps(cleaned_data, indent=2)}")

    logger.info(f"Scoring data for {coin_symbol}...")
    score_data = calculate_coin_score(cleaned_data)
    logger.debug(f"Score data for {coin_symbol}: {json.dumps(score_data, indent=2)}")

    # 4. Save Score to Database
    final_symbol = score_data.get("symbol")
    final_score = score_data.get("score")
    score_timestamp = score_data.get("score_calculation_timestamp_utc")

    if final_symbol != "UNKNOWN" and final_score is not None and score_timestamp is not None:
        coin_id = get_coin_id_by_symbol(final_symbol)
        if coin_id:
            logger.info(f"Saving score for {final_symbol} (ID: {coin_id}) to database...")
            insert_score_query = "INSERT INTO scores (coin_id, timestamp, score) VALUES (?, ?, ?);"
            params = (coin_id, score_timestamp, final_score)
            if execute_write_query(insert_score_query, params):
                logger.info(f"Score for {final_symbol} saved successfully.")
            else:
                logger.error(f"Failed to save score for {final_symbol}.")
        else:
            logger.error(f"Could not find coin ID for symbol '{final_symbol}'. Score not saved.")
    else:
        logger.warning(f"Skipping database save for {coin_symbol} due to invalid symbol, missing score, or timestamp. Score: {final_score}")
    logger.info(f"Finished full process for {coin_symbol}")

if __name__ == "__main__":
    logger.info("--- Main Orchestration Script Started ---")

    logger.info("Step 0: Initializing database and loading test coin symbols from config...")
    initialize_database()
    clear_coins_table()
    # Use SAMPLE_COINS_FOR_TESTING from config
    if not load_test_coins_data(config.SAMPLE_COINS_FOR_TESTING):
        logger.critical("Failed to load test coin data from config. Aborting main test.")
        sys.exit(1)
    logger.info("Database ready with test coins from config.")

    # Test symbols can be a subset of what's in config.SAMPLE_COINS_FOR_TESTING or include others
    test_symbols_for_processing = ["BTC", "DOGE", "XYZ", "ETH"]
    # Ensure these symbols are covered by mock data or DB for meaningful tests

    for symbol in test_symbols_for_processing:
        logger.info(f"Processing symbol: {symbol} from main test block...")
        process_and_save_coin_data(symbol)
    
    logger.info("Verifying Saved Scores for BTC...")
    btc_coin_id = get_coin_id_by_symbol("BTC") # Assuming BTC is usually in SAMPLE_COINS_FOR_TESTING
    if btc_coin_id:
        query_btc_scores = "SELECT timestamp, score FROM scores WHERE coin_id = ? ORDER BY timestamp DESC;"
        btc_scores_from_db = execute_read_query(query_btc_scores, params=(btc_coin_id,), fetch_all=True)
        if btc_scores_from_db:
            logger.info(f"Found {len(btc_scores_from_db)} score(s) for BTC (ID: {btc_coin_id}):")
            for record in btc_scores_from_db:
                logger.info(f"  Timestamp: {record[0]}, Score: {record[1]}")
        elif not btc_scores_from_db: 
            logger.warning(f"No scores found in DB for BTC (ID: {btc_coin_id}). This might be an error if BTC was processed.")
        else: 
            logger.error(f"Error trying to read scores for BTC (ID: {btc_coin_id}) from database.")
    else:
        logger.error("Could not get BTC coin ID for verification. Cannot check scores (BTC might not be in loaded test data).")

    logger.info("--- Main Orchestration Script Finished ---") 