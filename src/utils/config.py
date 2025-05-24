import os
import logging

# --- Project Root Configuration ---
# Assuming config.py is in src/utils/, so project_root is two levels up
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# --- Database Configuration ---
DATA_DIR_NAME = "data"
DATABASE_NAME = "database.db"
DB_DATA_DIR = os.path.join(PROJECT_ROOT, DATA_DIR_NAME) # Absolute path to data directory for DB
DATABASE_PATH = os.path.join(DB_DATA_DIR, DATABASE_NAME) # Absolute path to DB file

# Schema file is relative to the database submodule
# Let db_manager.py continue to define this relative to its own location for simplicity,
# or we can make it absolute from project root here:
DB_MODULE_PATH = os.path.join(PROJECT_ROOT, 'src', 'database')
SCHEMA_FILE_NAME = "schema.sql"
SCHEMA_FILE_PATH = os.path.join(DB_MODULE_PATH, SCHEMA_FILE_NAME)

# --- Logging Configuration ---
# General log settings
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
LOG_DATA_DIR = DB_DATA_DIR # Store logs in the same top-level data directory

# Specific log file names
APP_LOG_FILE = "app.log"             # For main.py and general app functions
SCHEDULER_LOG_FILE = "scheduler.log" # For scheduler.py
PROCESSOR_LOG_FILE = "processor.log" # For data processors like aggregator.py
DB_LOG_FILE = "database.log"       # For database specific operations (if we add detailed DB logging)
COLLECTOR_LOG_FILE = "collector.log" # For data collectors (if we add detailed collector logging)

# --- Scheduler Configuration ---
# Times are in seconds for testing; use larger values for production
# schedule.every().hour, .day.at("10:30") etc. are more readable for prod.
HOURLY_PIPELINE_INTERVAL_MINUTES = 1  # For testing, changed from seconds
WEEKLY_SUMMARY_INTERVAL_MINUTES = 3 # For testing, changed from seconds

# --- API Configuration (Example) ---
# Placeholder for API keys or endpoints if the project were to use real APIs
# Example: COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY", "your_default_api_key_here")

# --- Other Application Settings ---
TOP_N_COINS_REPORT = 3

# --- Test Data Configuration ---
# Used by data_loader.py and tests
SAMPLE_COINS_FOR_TESTING = [
    ("BTC", "Bitcoin"), 
    ("ETH", "Ethereum"), 
    ("SOL", "Solana"),
    ("ADA", "Cardano"), # Used in aggregator tests
    ("DOGE", "Dogecoin") # Used in main.py tests and has partial mock data
]


if __name__ == '__main__':
    # Print out some configured paths to verify them if this file is run directly
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Database Data Directory: {DB_DATA_DIR}")
    print(f"Database Path: {DATABASE_PATH}")
    print(f"Schema File Path: {SCHEMA_FILE_PATH}")
    print(f"Log Data Directory: {LOG_DATA_DIR}")
    print(f"App Log File would be at: {os.path.join(LOG_DATA_DIR, APP_LOG_FILE)}")
    print(f"Scheduler Log File would be at: {os.path.join(LOG_DATA_DIR, SCHEDULER_LOG_FILE)}")
    print(f"Processor Log File would be at: {os.path.join(LOG_DATA_DIR, PROCESSOR_LOG_FILE)}")
    print(f"Hourly pipeline interval (minutes): {HOURLY_PIPELINE_INTERVAL_MINUTES}")
    print(f"Weekly summary interval (minutes): {WEEKLY_SUMMARY_INTERVAL_MINUTES}")
    print(f"Sample coins for testing: {SAMPLE_COINS_FOR_TESTING}") 