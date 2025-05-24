# Placeholder for scheduler.py 
import schedule
import time
import sys
import os
from datetime import datetime, date, UTC # Added date, UTC

# Adjust sys.path to allow importing from the project root (src)
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

# Import config first
from src.utils import config

from src.main import process_and_save_coin_data
from src.database.db_manager import get_all_coin_symbols, initialize_database
from src.database.data_loader import load_test_coins_data, clear_coins_table
from src.processors.aggregator import generate_and_save_top_coins_report
from src.utils.logger import setup_logger # Import the logger

# Setup logger for the scheduler, using defaults from config for log file name
logger = setup_logger(name='scheduler_app', log_file_name=config.SCHEDULER_LOG_FILE)

def run_hourly_data_pipeline():
    logger.info("--- Hourly Data Pipeline Started ---")
    coin_symbols = get_all_coin_symbols() # This directly returns list[str], e.g., ['BTC', 'ETH']
    if not coin_symbols:
        logger.warning("No coin symbols found in the database. Hourly pipeline will not process any coins.")
        logger.info("--- Hourly Data Pipeline Finished (No Coins) ---")
        return

    logger.info(f"Found {len(coin_symbols)} coin(s) to process: {coin_symbols}")
    for symbol in coin_symbols:
        logger.info(f"Processing symbol: {symbol} as part of hourly pipeline...")
        try:
            process_and_save_coin_data(symbol)
            logger.info(f"Successfully processed symbol: {symbol}")
        except Exception as e:
            logger.error(f"Error processing symbol {symbol} in hourly pipeline: {e}", exc_info=True)
    logger.info("--- Hourly Data Pipeline Finished ---")

def weekly_summary_task():
    logger.info("--- Weekly Summary Task Started ---")
    try:
        # For the report, we need a week_end_date. Let's use the current date.
        week_end_date_obj = datetime.now(UTC).date() # Use datetime.now(UTC).date() for a date object
        logger.info(f"Generating weekly summary report for week ending: {week_end_date_obj.strftime('%Y-%m-%d')}")
        generate_and_save_top_coins_report(week_end_date=week_end_date_obj, top_n=3)
        logger.info("Successfully generated and saved weekly summary report.")
    except Exception as e:
        logger.error(f"Error during weekly summary task: {e}", exc_info=True)
    logger.info("--- Weekly Summary Task Finished ---")

def run_scheduler():
    logger.info("Scheduler started. Setting up jobs...")

    # Schedule the hourly data pipeline using interval from config
    schedule.every(config.HOURLY_PIPELINE_INTERVAL_MINUTES).minutes.do(run_hourly_data_pipeline)
    logger.info(f"Scheduled 'run_hourly_data_pipeline' to run every {config.HOURLY_PIPELINE_INTERVAL_MINUTES} minute(s).")

    # Schedule the weekly summary task using interval from config
    schedule.every(config.WEEKLY_SUMMARY_INTERVAL_MINUTES).minutes.do(weekly_summary_task)
    logger.info(f"Scheduled 'weekly_summary_task' to run every {config.WEEKLY_SUMMARY_INTERVAL_MINUTES} minute(s).")

    logger.info("Scheduler is now running. Press Ctrl+C to exit.")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    logger.info("Scheduler script started directly.")
    logger.info("Initializing database for scheduler test run...")
    initialize_database()
    clear_coins_table()
    # Use SAMPLE_COINS_FOR_TESTING from config
    if load_test_coins_data(config.SAMPLE_COINS_FOR_TESTING):
        logger.info(f"Loaded {len(config.SAMPLE_COINS_FOR_TESTING)} test coins for scheduler test run from config.")
    else:
        logger.error("Failed to load test coins for scheduler from config.")

    logger.info("Starting the scheduler...")
    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Scheduler terminated due to an unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Scheduler script finished.") 