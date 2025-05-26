import json
import sys # For sys.exit in main block
import os # For path joining for logger if needed
import datetime # For timestamping metrics
import sqlite3
import time # Added for sleep between batches

# Import config first
from src.utils import config # Imports TRACKED_COIN_IDS, COIN_MAPPING

# Attempt to import collector functions.
from src.collectors.coin_data import (
    fetch_coingecko_market_data,
    # fetch_coin_price_volume # This was mock, replaced by coingecko
    ping_coingecko,
)
from src.collectors.on_chain import (
    fetch_on_chain_metrics, # This is currently mock, will be partly replaced/supplemented
    ping_etherscan, # For checking Etherscan API status if needed, not directly used in data collection loop yet
    fetch_etherscan_token_active_addresses,
    fetch_etherscan_token_transaction_count,
    fetch_etherscan_token_total_supply
)
from src.collectors.social_data import (
    # fetch_social_sentiment, # This will be replaced by the CryptoPanic pipeline
    ping_cryptopanic, # For checking API status
    fetch_cryptopanic_news_for_coin,
    filter_cryptopanic_posts,
    calculate_aggregate_sentiment_from_posts,
    fetch_gdelt_doc_api_news_sentiment
)

from src.processors.data_cleaner import clean_coin_data
from src.processors.scorer import calculate_coin_score

from src.database.db_manager import (
    execute_write_query, 
    execute_read_query,
    get_coin_id_by_symbol,
    initialize_database # To ensure DB is set up
)
from src.database.data_loader import (
    load_coins_from_mapping, 
    clear_all_transactional_tables 
)
from src.utils.logger import setup_logger # Import the logger setup function

# Setup logger for the main application module, using config for file name
logger = setup_logger(name='main_app', log_file_name=config.APP_LOG_FILE)

def collect_all_data_for_coin(coingecko_id: str) -> dict:
    """
    Collects all available data for a given CoinGecko ID.
    Uses CoinGecko for market data, Etherscan for ERC20 on-chain, CryptoPanic for social sentiment.
    Other metrics might still use mock data or other collectors.

    Args:
        coingecko_id (str): The CoinGecko ID of the coin (e.g., "bitcoin").

    Returns:
        dict: A combined dictionary containing all fetched data.
    """
    coin_details = config.COIN_MAPPING.get(coingecko_id)
    if not coin_details:
        logger.error(f"CoinGecko ID '{coingecko_id}' not found in COIN_MAPPING. Skipping collection.")
        return {"coingecko_id": coingecko_id, "error": "ID not found in mapping"}
    
    symbol = coin_details["symbol"]
    contract_address = coin_details.get("contract_address") # Will be None if not an ERC20 or not specified
    
    logger.debug(f"Collecting all data for CoinGecko ID: {coingecko_id} (Symbol: {symbol}, Contract: {contract_address or 'N/A'})")
    
    combined_data = {
        "coingecko_id": coingecko_id,
        "symbol": symbol, 
        "price": None,
        "volume": None, # This is USD volume from CoinGecko
        "market_cap": None,
        # Fields for on-chain data
        "active_addresses": None, # This will be populated by Etherscan for ERC20s, or mock for others
        "transaction_volume_usd": None, # This will remain from mock (or could be CoinGecko volume if we choose)
        # Etherscan specific fields (new)
        "etherscan_active_addresses_proxy": None,
        "etherscan_transaction_count_proxy": None,
        "etherscan_total_supply_adjusted": None,
        # Fields for social data
        "mentions": None, # Will be populated by CryptoPanic's articles_with_votes
        "sentiment_score": None, # Will be populated by CryptoPanic's aggregated_sentiment_score
        "gdelt_sentiment_score": None,
        "gdelt_article_count": None
    }
    errors = []

    # 1. Fetch Market Data from CoinGecko
    market_data = fetch_coingecko_market_data(coingecko_id)
    if "error" in market_data:
        errors.append(f"CoinGecko MarketData: {market_data['error']}")
        logger.warning(f"Error fetching CoinGecko market data for {coingecko_id}: {market_data['error']}")
    else:
        combined_data["price"] = market_data.get("price")
        combined_data["volume"] = market_data.get("volume") # Storing CoinGecko's USD volume
        combined_data["market_cap"] = market_data.get("market_cap")
        logger.debug(f"CoinGecko market data for {coingecko_id} fetched.")
        # We can use CoinGecko's volume as the primary transaction_volume_usd
        combined_data["transaction_volume_usd"] = market_data.get("volume")


    # 2. Fetch On-Chain Metrics
    if contract_address and coingecko_id != "ethereum": # It's an ERC20 token with a contract address
        logger.info(f"Fetching Etherscan data for ERC20 token: {symbol} ({contract_address})")
        
        active_addr_data = fetch_etherscan_token_active_addresses(contract_address)
        if "error" in active_addr_data:
            errors.append(f"Etherscan ActiveAddresses: {active_addr_data['error']}")
            logger.warning(f"Error Etherscan active_addresses for {symbol}: {active_addr_data['error']}")
        else:
            combined_data["etherscan_active_addresses_proxy"] = active_addr_data.get("active_addresses_proxy")
            combined_data["active_addresses"] = active_addr_data.get("active_addresses_proxy") # Use this for the main field
            logger.debug(f"Etherscan active_addresses_proxy for {symbol}: {combined_data['etherscan_active_addresses_proxy']}")

        tx_count_data = fetch_etherscan_token_transaction_count(contract_address)
        if "error" in tx_count_data:
            errors.append(f"Etherscan TxCount: {tx_count_data['error']}")
            logger.warning(f"Error Etherscan tx_count for {symbol}: {tx_count_data['error']}")
        else:
            combined_data["etherscan_transaction_count_proxy"] = tx_count_data.get("transaction_count_proxy")
            logger.debug(f"Etherscan transaction_count_proxy for {symbol}: {combined_data['etherscan_transaction_count_proxy']}")

        total_supply_data = fetch_etherscan_token_total_supply(contract_address, coingecko_id)
        if "error" in total_supply_data:
            errors.append(f"Etherscan TotalSupply: {total_supply_data['error']}")
            logger.warning(f"Error Etherscan total_supply for {symbol}: {total_supply_data['error']}")
        else:
            combined_data["etherscan_total_supply_adjusted"] = total_supply_data.get("total_supply_adjusted")
            logger.debug(f"Etherscan total_supply_adjusted for {symbol}: {combined_data['etherscan_total_supply_adjusted']}")
            
        # If it's an ERC20, we might not call the generic mock fetch_on_chain_metrics
        # or we ensure its mock data doesn't overwrite Etherscan data.
        # For now, if Etherscan active_addresses is fetched, it populates combined_data["active_addresses"].
        # The mock fetch_on_chain_metrics also provides "active_addresses" and "transaction_volume_usd".
        # Let's ensure Etherscan data takes precedence for active_addresses for ERC20s.
        # transaction_volume_usd is now primarily from CoinGecko.
        # The original mock fetch_on_chain_metrics for non-ERC20s (or if Etherscan fails) might still be useful.
        
        # Call mock for any remaining fields IF NOT an ERC20 token or if Etherscan calls fail for some reason
        # For now, let's assume if it's ERC20, Etherscan is the source for active_addresses.
        # If it's NOT an ERC20 (e.g. BTC), then call the mock.
        # Ethereum (ETH) itself is special: it's not an ERC20 with a contract for these Etherscan calls.
        # Its on-chain data would come from network-level stats (or mock).

    # If not an ERC20 token with contract (e.g. BTC, or ETH itself for some metrics)
    # or if we still want to supplement with mock data for fields not covered by Etherscan for ERC20s:
    if not contract_address or coingecko_id == "ethereum": # e.g. Bitcoin, or Ethereum native
        logger.debug(f"Using mock on-chain metrics for {symbol} (not a specific ERC20 contract or is ETH native)")
        mock_on_chain_data = fetch_on_chain_metrics(symbol) # Original mock data function
        if "error" in mock_on_chain_data:
            errors.append(f"MockOnChain: {mock_on_chain_data['error']}")
            logger.warning(f"Error fetching mock on-chain data for {symbol}: {mock_on_chain_data['error']}")
        else:
            # Only fill if not already populated by a more specific source (like Etherscan for ERC20s)
            if combined_data["active_addresses"] is None:
                combined_data["active_addresses"] = mock_on_chain_data.get("active_addresses")
            # transaction_volume_usd is now primarily from CoinGecko, but mock can be a fallback.
            if combined_data["transaction_volume_usd"] is None:
                 combined_data["transaction_volume_usd"] = mock_on_chain_data.get("transaction_volume_usd")
            logger.debug(f"Mock on-chain for {symbol} applied for non-ERC20 specific fields.")


    # 3. Fetch Social Sentiment Data from CryptoPanic
    logger.info(f"Fetching CryptoPanic news sentiment for {symbol}...")
    raw_news = fetch_cryptopanic_news_for_coin(symbol)
    if "error" in raw_news:
        errors.append(f"CryptoPanic FetchNews: {raw_news['error']}")
        logger.warning(f"Error fetching CryptoPanic news for {symbol}: {raw_news['error']}")
    else:
        logger.debug(f"Successfully fetched {len(raw_news.get('results',[]))} raw news items for {symbol} from CryptoPanic.")
        filtered_news = filter_cryptopanic_posts(raw_news, symbol)
        if "error" in filtered_news:
            errors.append(f"CryptoPanic FilterNews: {filtered_news['error']}")
            logger.warning(f"Error filtering CryptoPanic news for {symbol}: {filtered_news['error']}")
        else:
            logger.debug(f"Successfully filtered CryptoPanic news for {symbol}, {len(filtered_news.get('filtered_results',[]))} items remain.")
            sentiment_data = calculate_aggregate_sentiment_from_posts(filtered_news)
            if "error" in sentiment_data:
                errors.append(f"CryptoPanic SentimentCalc: {sentiment_data['error']}")
                logger.warning(f"Error calculating CryptoPanic sentiment for {symbol}: {sentiment_data['error']}")
            else:
                combined_data["sentiment_score"] = sentiment_data.get("aggregated_sentiment_score")
                combined_data["mentions"] = sentiment_data.get("articles_with_votes") # Using articles_with_votes as 'mentions'
                logger.debug(f"CryptoPanic sentiment for {symbol}: Score={combined_data['sentiment_score']}, Mentions(articles_w_votes)={combined_data['mentions']}")
    
    # 4. Fetch GDELT News Sentiment Data
    gdelt_data = None
    gdelt_sentiment_score = None
    gdelt_article_count = None
    
    # Construct GDELT query using both name and symbol for better coverage
    gdelt_query = f'"{coin_details["name"]}" OR "{symbol.upper()}"' 
    # For coins with common words in their names, we might want to be more specific, 
    # e.g., by adding context like "crypto" or "blockchain" but this is a general approach.
    # Example: (("crypto" OR "blockchain") AND ("LINK" OR "Chainlink"))

    try:
        logger.info(f"Fetching GDELT news sentiment for {symbol} with query: {gdelt_query}")
        # Use the configured timespan from config.py
        gdelt_data = fetch_gdelt_doc_api_news_sentiment(query=gdelt_query, 
                                                          timespan=config.GDELT_DOC_API_TIMESPAN, 
                                                          max_records=30) # Max records can be tuned
        if gdelt_data and not gdelt_data.get("error"):
            gdelt_sentiment_score = gdelt_data.get("gdelt_average_tone")
            gdelt_article_count = gdelt_data.get("gdelt_article_count")
            logger.info(f"  GDELT data for {symbol}: Score={gdelt_sentiment_score}, Articles={gdelt_article_count}")
        elif gdelt_data and gdelt_data.get("error"):
            logger.warning(f"  Error fetching GDELT data for {symbol}: {gdelt_data.get('error')}")
        else:
            logger.warning(f"  No GDELT data returned for {symbol}.")
    except Exception as e:
        logger.error(f"  Exception during GDELT data collection for {symbol}: {e}", exc_info=True)

    # Combine data
    combined_data["gdelt_sentiment_score"] = gdelt_sentiment_score
    combined_data["gdelt_article_count"] = gdelt_article_count

    if errors:
        combined_data["collection_errors"] = errors
        logger.info(f"Finished collecting data for {coingecko_id} (Symbol: {symbol}) with {len(errors)} error(s).")
    else:
        logger.info(f"Successfully collected all data for {coingecko_id} (Symbol: {symbol}).")
    return combined_data

def process_and_save_coin_data(coingecko_id: str):
    logger.info(f"Starting full process for CoinGecko ID: {coingecko_id}")
    
    coin_details = config.COIN_MAPPING.get(coingecko_id)
    if not coin_details:
        logger.error(f"CoinGecko ID '{coingecko_id}' not found in COIN_MAPPING. Aborting processing.")
        return
    symbol = coin_details["symbol"]

    logger.info(f"Collecting data for {coingecko_id} (Symbol: {symbol})...")
    raw_data = collect_all_data_for_coin(coingecko_id)
    logger.debug(f"Raw data for {coingecko_id}: {json.dumps(raw_data, indent=2)}")
    
    if "error" in raw_data or raw_data.get("price") is None: 
        logger.error(f"Failed to collect sufficient raw data for {coingecko_id}. Aborting further processing. Errors: {raw_data.get('collection_errors')}")
        return

    # Save collected metrics to the database
    db_coin_id = get_coin_id_by_symbol(symbol)
    if not db_coin_id:
        logger.error(f"Could not find database ID for symbol '{symbol}' (CoinGecko ID: {coingecko_id}). Metrics not saved.")
    else:
        metrics_timestamp = datetime.datetime.utcnow()
        insert_metrics_query = """
        INSERT INTO metrics (coin_id, timestamp, price, volume, market_cap, active_addresses, transaction_volume)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        # 'active_addresses' now comes from Etherscan for ERC20s, or mock for others.
        # 'transaction_volume' is CoinGecko's USD volume.
        metrics_params = (
            db_coin_id,
            metrics_timestamp,
            raw_data.get("price"),
            raw_data.get("volume"), # This is CoinGecko's total_volume in USD
            raw_data.get("market_cap"),
            raw_data.get("active_addresses"), # Populated by Etherscan proxy or mock
            raw_data.get("transaction_volume_usd") # Primarily CoinGecko volume, fallback to mock
        )
        if execute_write_query(insert_metrics_query, metrics_params):
            logger.info(f"Metrics for {symbol} saved successfully at {metrics_timestamp}.")
        else:
            logger.error(f"Failed to save metrics for {symbol}.")

    logger.info(f"Cleaning data for {symbol}...")
    cleaned_data = clean_coin_data(raw_data) 
    logger.debug(f"Cleaned data for {symbol}: {json.dumps(cleaned_data, indent=2)}")

    logger.info(f"Scoring data for {symbol}...")
    score_data = calculate_coin_score(cleaned_data) 
    # Log the detailed score data for debugging/transparency, then extract key parts for DB
    logger.debug(f"Detailed score data for {symbol}: {json.dumps(score_data, indent=2)}")

    # Extract necessary fields for database saving from the new score_data structure
    final_symbol_from_scorer = score_data.get("symbol") 
    final_score = score_data.get("score") # This is the 0-100 scaled score
    score_timestamp = score_data.get("score_calculation_timestamp_utc")
    # coingecko_id_from_scorer = score_data.get("coingecko_id") # Also available, good for verification

    if final_symbol_from_scorer and final_score is not None and score_timestamp is not None:
        # Verify that the symbol from scorer matches the symbol we are processing for this iteration
        if final_symbol_from_scorer != symbol:
            logger.error(f"Symbol mismatch! Scorer returned data for '{final_symbol_from_scorer}' but current processing is for '{symbol}'. Score not saved.")
        else:
            score_db_coin_id = get_coin_id_by_symbol(final_symbol_from_scorer) # Use symbol from scorer
            if score_db_coin_id:
                logger.info(f"Saving score for {final_symbol_from_scorer} (ID: {score_db_coin_id}, Score: {final_score}) to database...")
                insert_score_query = "INSERT INTO scores (coin_id, timestamp, score) VALUES (?, ?, ?);"
                params = (score_db_coin_id, score_timestamp, final_score)
                if execute_write_query(insert_score_query, params):
                    logger.info(f"Score for {final_symbol_from_scorer} saved successfully.")
                else:
                    logger.error(f"Failed to save score for {final_symbol_from_scorer}.")
            else:
                logger.error(f"Could not find coin ID for symbol '{final_symbol_from_scorer}' from scorer. Score not saved.")
    else:
        logger.warning(f"Skipping database save for score from {coingecko_id} due to invalid/missing symbol from scorer, score, or timestamp. Score: {final_score}")
    logger.info(f"Finished full process for CoinGecko ID: {coingecko_id}")

def run_full_data_pipeline():
    """
    Runs the full data collection, processing, and saving pipeline for all tracked coins.
    Processes coins in two batches with a delay in between.
    """
    logger.info("--- Full Data Pipeline Started ---")

    # Initial API Pings
    if any(details.get("contract_address") for details in config.COIN_MAPPING.values()):
        logger.info("ERC20 tokens found. Pinging Etherscan...")
        if ping_etherscan(): 
            logger.info("Initial Etherscan ping successful.")
    
    if not config.CRYPTO_PANIC_API_KEY or config.CRYPTO_PANIC_API_KEY == "YOUR_CRYPTO_PANIC_API_KEY_HERE":
        logger.warning("Warning: CryptoPanic API key is not configured. Social sentiment data will be limited.")
    else:
        if not ping_cryptopanic():
            logger.warning("CryptoPanic API ping failed. Check your API key and network.")
        else:
            logger.info("CryptoPanic API ping successful.")

    logger.info(f"GDELT DOC API will be queried with timespan: {config.GDELT_DOC_API_TIMESPAN}")

    logger.info("Step 0: Initializing database and loading coin data from COIN_MAPPING...")
    initialize_database() # Ensures DB schema is created if not exists
    # Consider if clearing tables should be part of a scheduled run. 
    # For continuous operation, you usually wouldn't clear all transactional tables every run.
    # clear_all_transactional_tables() # Keep this commented out for typical scheduled runs.
    
    if not load_coins_from_mapping(config.COIN_MAPPING):
        logger.critical("Failed to load coin data from COIN_MAPPING into DB. Aborting pipeline run.")
        return # Exit this pipeline run
    logger.info("Database initialized and coins (re)loaded/updated from COIN_MAPPING.")

    all_coin_ids = list(config.COIN_MAPPING.keys())
    num_coins = len(all_coin_ids)
    
    if num_coins == 0:
        logger.info("No coins in COIN_MAPPING. Pipeline finished.")
        logger.info("--- Full Data Pipeline Finished ---")
        return

    # Determine batch sizes
    batch_size_1 = (num_coins + 1) // 2 # Handles odd numbers by putting more in the first batch
    
    batch_1_ids = all_coin_ids[:batch_size_1]
    batch_2_ids = all_coin_ids[batch_size_1:]

    logger.info(f"Starting Batch 1/2 processing {len(batch_1_ids)} coins.")
    for coingecko_id_to_process in batch_1_ids:
        logger.info(f"Processing CoinGecko ID: {coingecko_id_to_process} from pipeline (Batch 1)...")
        process_and_save_coin_data(coingecko_id_to_process)
    
    if batch_2_ids: # Only pause and proceed if there's a second batch
        logger.info(f"Batch 1/2 finished. Waiting for 10 minutes before starting Batch 2/2 ({len(batch_2_ids)} coins)...")
        time.sleep(60 * 10) # 10 minutes delay
        
        logger.info(f"Starting Batch 2/2 processing {len(batch_2_ids)} coins.")
        for coingecko_id_to_process in batch_2_ids:
            logger.info(f"Processing CoinGecko ID: {coingecko_id_to_process} from pipeline (Batch 2)...")
            process_and_save_coin_data(coingecko_id_to_process)
    else:
        logger.info("Only one batch was needed as there are not enough coins for two batches.")
    
    logger.info("--- Full Data Pipeline Finished ---")

if __name__ == "__main__":
    logger.info("--- Main Orchestration Script Started (Manual Run) ---")
    
    # Run the pipeline
    run_full_data_pipeline()

    # Verification part (can be kept for manual runs or made a separate utility)
    logger.info("Verifying Saved Data for a sample coin (e.g., Chainlink if present, else Bitcoin)...")
    
    sample_cg_id_for_verify = None
    if "chainlink" in config.COIN_MAPPING: # Prefer an ERC20 for Etherscan data verification
        sample_cg_id_for_verify = "chainlink"
    elif "bitcoin" in config.COIN_MAPPING:
        sample_cg_id_for_verify = "bitcoin"
    elif config.COIN_MAPPING:
        sample_cg_id_for_verify = list(config.COIN_MAPPING.keys())[0] # Fallback to first coin

    if sample_cg_id_for_verify:
        sample_symbol_for_verify = config.COIN_MAPPING.get(sample_cg_id_for_verify, {}).get("symbol")
        if sample_symbol_for_verify:
            db_coin_id_for_verify = get_coin_id_by_symbol(sample_symbol_for_verify)
            if db_coin_id_for_verify:
                # Verify metrics
                query_metrics = "SELECT timestamp, price, volume, market_cap, active_addresses, transaction_volume FROM metrics WHERE coin_id = ? ORDER BY timestamp DESC LIMIT 1;"
                latest_metrics = execute_read_query(query_metrics, params=(db_coin_id_for_verify,), fetch_all=False) 
                if latest_metrics:
                    logger.info(f"Latest metrics for {sample_symbol_for_verify} (ID: {db_coin_id_for_verify}): Timestamp={latest_metrics[0]}, Price={latest_metrics[1]}, Volume(USD)={latest_metrics[2]}, MCAP={latest_metrics[3]}, ActiveAddresses={latest_metrics[4]}, TxVol(USD)={latest_metrics[5]}")
                else:
                    logger.warning(f"No metrics found in DB for {sample_symbol_for_verify}.")
                
                # Verify scores
                query_scores = "SELECT timestamp, score FROM scores WHERE coin_id = ? ORDER BY timestamp DESC LIMIT 1;"
                latest_score = execute_read_query(query_scores, params=(db_coin_id_for_verify,), fetch_all=False)
                if latest_score:
                    logger.info(f"Latest score for {sample_symbol_for_verify} (ID: {db_coin_id_for_verify}): Timestamp={latest_score[0]}, Score={latest_score[1]}")
                else:
                    logger.warning(f"No scores found in DB for {sample_symbol_for_verify}.")
            else:
                logger.error(f"Could not get DB ID for {sample_symbol_for_verify} for verification.")
        else:
            logger.error(f"Sample coin '{sample_cg_id_for_verify}' symbol not found in COIN_MAPPING for verification.")
    else:
        logger.warning("COIN_MAPPING is empty. Cannot verify saved data.")

    logger.info("--- Main Orchestration Script Finished (Manual Run) ---") 