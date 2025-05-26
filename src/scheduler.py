import schedule
import time
import sys
import os
from datetime import datetime, timezone

# Adjust path to import from other modules in the project
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.utils import config
from src.utils.logger import setup_logger

# Import the pipeline function from main.py
# Ensure main.py has a callable function for its primary operations
from src.main import run_full_data_pipeline 

# Import the summary generation function from aggregator.py
# Using generate_and_save_top_coins_report as it persists the data
from src.processors.aggregator import generate_and_save_top_coins_report # Corrected import

# Setup logger for the scheduler module
logger = setup_logger(name='scheduler_app', log_file_name=config.SCHEDULER_LOG_FILE)

def main_data_pipeline_job():
    """Job wrapper for the main data collection and processing pipeline."""
    logger.info("Scheduler starting: Main Data Pipeline Job")
    try:
        run_full_data_pipeline()
        logger.info("Scheduler finished: Main Data Pipeline Job completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler error: Main Data Pipeline Job failed: {e}", exc_info=True)

def weekly_summary_job():
    """Job wrapper for generating and saving the weekly top coins report."""
    logger.info("Scheduler starting: Weekly Summary Report Job")
    try:
        # The generate_and_save_top_coins_report function needs a week_end_date
        # For a truly weekly report, this would be the current date or end of the last full week.
        today = datetime.now(timezone.utc).date() # Use timezone.utc
        
        # If aggregator.py is designed for a weekly report, it should handle the date logic.
        # Here, we just call it. The current aggregator.py test uses today.
        generate_and_save_top_coins_report(week_end_date=today, top_n=config.TOP_N_COINS_REPORT)
        logger.info("Scheduler finished: Weekly Summary Report Job completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler error: Weekly Summary Report Job failed: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("--- Scheduler Service Started ---")
    logger.info(f"Main data pipeline will run every {config.HOURLY_PIPELINE_INTERVAL_MINUTES} minute(s).")
    logger.info(f"Daily summary report will run daily at 01:00 UTC (9 AM GMT+8).")

    # Schedule jobs
    # For testing, using minutes. For production, these would be .hours, .days.at("HH:MM"), etc.
    schedule.every(config.HOURLY_PIPELINE_INTERVAL_MINUTES).minutes.do(main_data_pipeline_job)
    schedule.every().day.at("01:00", "UTC").do(weekly_summary_job) # Schedule daily at 1 AM UTC
    
    # Initial run immediately for testing, then rely on schedule
    # logger.info("Performing initial run of main_data_pipeline_job...")
    # main_data_pipeline_job()
    # logger.info("Performing initial run of weekly_summary_job...")
    # weekly_summary_job()

    logger.info("Scheduler is now running. Press Ctrl+C to exit.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1) # Sleep for a second to avoid busy-waiting
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"Scheduler encountered a critical error: {e}", exc_info=True)
    finally:
        logger.info("--- Scheduler Service Shutting Down ---") 