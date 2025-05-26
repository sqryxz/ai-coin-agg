import sys
import os

# Adjust sys.path to find db_manager and config
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.database.db_manager import execute_write_query, execute_read_query, initialize_database, get_coin_id_by_symbol
from src.utils import config # Import config
from src.utils.logger import setup_logger # For standalone test logging

# Setup a logger for data_loader if it's run standalone or for its own operations
# This could also use a DB_LOG_FILE or a generic PROCESSOR_LOG_FILE from config.
# For now, let's use a generic approach or rely on the caller's logger mostly.
# If run as __main__, it will set up its own.
_module_logger = None

def get_data_loader_logger():
    global _module_logger
    if _module_logger is None:
        # Defaulting to APP_LOG_FILE for data_loader specific messages if not covered by other loggers.
        # Or could define a LOADER_LOG_FILE in config.
        _module_logger = setup_logger(name='data_loader', log_file_name=config.APP_LOG_FILE) 
    return _module_logger

def clear_coins_table():
    """Clears all data from the coins table."""
    logger = get_data_loader_logger()
    logger.info("Clearing data from 'coins' table...")
    if execute_write_query("DELETE FROM coins;"):
        # Also reset sequence for auto-incrementing ID if SQLite (for other DBs, syntax might differ)
        execute_write_query("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'coins';")
        logger.info("'coins' table cleared and sequence reset (if applicable).")
        return True
    logger.error("Failed to clear 'coins' table.")
    return False

def clear_all_transactional_tables():
    """Clears all data from transactional tables: coins, metrics, scores, summaries."""
    logger = get_data_loader_logger()
    logger.info("Clearing all transactional data (coins, metrics, scores, summaries)...")
    tables_to_clear = ["coins", "metrics", "scores", "summaries"]
    all_cleared = True

    for table_name in tables_to_clear:
        logger.debug(f"Clearing data from '{table_name}' table...")
        if execute_write_query(f"DELETE FROM {table_name};"):
            # Reset sequence for auto-incrementing ID for SQLite
            # For other DBs, this might differ or not be needed if TRUNCATE is used and resets sequences.
            # Using `sqlite_sequence` which is specific to SQLite auto-increment behavior.
            # The `summaries` table does not have AUTOINCREMENT in the original schema but good to be consistent.
            execute_write_query(f"UPDATE sqlite_sequence SET seq = 0 WHERE name = '{table_name}';")
            logger.info(f"'{table_name}' table cleared and sequence reset (if applicable).")
        else:
            logger.error(f"Failed to clear '{table_name}' table.")
            all_cleared = False
            
    if all_cleared:
        logger.info("All transactional tables cleared successfully.")
    else:
        logger.warning("One or more transactional tables failed to clear.")
    return all_cleared

def load_test_coins_data(coins_to_load=None) -> bool:
    logger = get_data_loader_logger()
    if coins_to_load is None:
        coins_to_load = config.SAMPLE_COINS_FOR_TESTING
        logger.info(f"No specific coins provided, loading default sample coins from config: {len(coins_to_load)} coins")
    else:
        logger.info(f"Attempting to load {len(coins_to_load)} provided coins.")

    if not coins_to_load:
        logger.warning("No coins to load.")
        return False
    
    insert_query = "INSERT INTO coins (symbol, name) VALUES (?, ?);"
    loaded_count = 0
    failed_count = 0
    for coin_symbol, coin_name in coins_to_load:
        if execute_write_query(insert_query, params=(coin_symbol, coin_name)):
            loaded_count += 1
        else:
            failed_count += 1
            logger.error(f"Failed to load coin: {coin_symbol} - {coin_name}")
            
    if loaded_count > 0:
        logger.info(f"Successfully loaded {loaded_count} out of {len(coins_to_load)} coins.")
    if failed_count > 0:
        logger.warning(f"Failed to load {failed_count} out of {len(coins_to_load)} coins.")
        return False # Indicate partial or full failure
    return loaded_count > 0 # Return True if at least one coin was loaded

def load_coins_from_mapping(coin_mapping: dict) -> bool:
    """
    Loads coins into the database from the provided coin_mapping dictionary.
    Checks if a coin already exists by symbol before inserting to prevent duplicates.
    The mapping should be { "coingecko_id": {"symbol": "SYMBOL", "name": "FullName"}, ... }
    
    Args:
        coin_mapping (dict): A dictionary mapping coingecko_ids to coin details.

    Returns:
        bool: True if all new coins were loaded successfully or already existed, False if any errors occurred during new insertions.
    """
    logger = get_data_loader_logger()
    if not coin_mapping:
        logger.warning("No coin mapping provided. Nothing to load.")
        return False # Or True, as no action needed? For consistency, let's say False if no mapping.

    logger.info(f"Attempting to load/verify {len(coin_mapping)} coins from mapping into 'coins' table.")
    
    loaded_count = 0
    skipped_existing_count = 0
    failed_count = 0

    for coingecko_id, details in coin_mapping.items():
        symbol = details.get("symbol")
        name = details.get("name")
        if not symbol or not name:
            logger.error(f"Skipping coin with coingecko_id '{coingecko_id}' due to missing symbol or name in mapping.")
            failed_count += 1 # Treat as a failure in mapping data
            continue

        # Check if coin already exists
        existing_coin_id = get_coin_id_by_symbol(symbol)
        if existing_coin_id is not None:
            logger.debug(f"Coin {symbol} (ID: {existing_coin_id}) already exists in the database. Skipping insertion.")
            skipped_existing_count += 1
            continue # Skip to the next coin

        # If not existing, then insert
        insert_query = "INSERT INTO coins (symbol, name) VALUES (?, ?);"
        if execute_write_query(insert_query, params=(symbol, name)):
            loaded_count += 1
            logger.debug(f"Loaded new coin: {symbol} - {name} (from coingecko_id: {coingecko_id})")
        else:
            failed_count += 1
            logger.error(f"Failed to load new coin: {symbol} - {name} (from coingecko_id: {coingecko_id})")
            
    if loaded_count > 0:
        logger.info(f"Successfully loaded {loaded_count} new coins.")
    if skipped_existing_count > 0:
        logger.info(f"Skipped inserting {skipped_existing_count} coins that already existed.")
    
    if failed_count > 0:
        logger.warning(f"Failed to load {failed_count} coins (due to mapping issues or DB errors for new coins).")
        return False # Indicate one or more failures for new coins or critical mapping issues.
        
    # Return True if there were no failures for new coins. 
    # It's okay if all coins already existed (loaded_count = 0, failed_count = 0, skipped > 0).
    return failed_count == 0

def get_all_coins():
    """Retrieves all coins from the coins table."""
    query = "SELECT id, symbol, name FROM coins ORDER BY id;"
    logger = get_data_loader_logger()
    logger.info("Fetching all coins from database...")
    coins = execute_read_query(query, fetch_all=True)
    if coins is not None:
        logger.info(f"Found {len(coins)} coins.")
    else:
        logger.error("Failed to fetch coins or table is empty.")
    return coins

if __name__ == "__main__":
    main_logger = get_data_loader_logger() # Use the module logger for __main__ block
    main_logger.info("--- Data Loader Script Test --- ")

    main_logger.info("Step 1: Initializing database...")
    initialize_database() # This function logs its own status or prints.

    main_logger.info("\nStep 2: Clearing all transactional tables...")
    if clear_all_transactional_tables():
        main_logger.info("All transactional tables (coins, metrics, scores, summaries) cleared.")
    else:
        main_logger.error("Failed to clear all transactional tables. Check logs.")
        sys.exit(1) # Critical if clearing fails

    main_logger.info("\nStep 3: Loading coins from config.COIN_MAPPING...")
    # Ensure config is accessible for the test, it should be due to sys.path append
    if load_coins_from_mapping(config.COIN_MAPPING):
        main_logger.info("Coins loaded from mapping.")
    else:
        main_logger.error("Failed to load coins from mapping. Check logs.")
        # sys.exit(1) # Allow to continue to verification to see what was loaded

    main_logger.info("\nStep 4: Verifying loaded coins...")
    all_loaded_coins = get_all_coins()
    if all_loaded_coins:
        main_logger.info(f"Found {len(all_loaded_coins)} coins in the database:")
        for coin in all_loaded_coins:
            main_logger.info(f"  ID: {coin[0]}, Symbol: {coin[1]}, Name: {coin[2]}")
    elif all_loaded_coins == []:
        main_logger.warning("No coins found in the database after loading attempt.")
    else:
        main_logger.error("Error retrieving coins from database for verification.")
        
    main_logger.info("\n--- Data Loader Script Test Finished ---") 