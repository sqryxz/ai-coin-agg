import sys
import os

# Adjust sys.path to find db_manager and config
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.database.db_manager import execute_write_query, execute_read_query, initialize_database
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

    main_logger.info("\nStep 2: Clearing any existing coins...")
    if clear_coins_table():
        main_logger.info("Coins table cleared.")
    else:
        main_logger.error("Failed to clear coins table.")
        sys.exit(1)

    main_logger.info("\nStep 3: Loading test coins (using config.SAMPLE_COINS_FOR_TESTING by default)...")
    if load_test_coins_data(): # Uses default from config
        main_logger.info("Test coins loaded.")
    else:
        main_logger.error("Failed to load test coins.")
        # sys.exit(1) # Don't exit if some loaded, continue to verification

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