import os
import logging
from dotenv import load_dotenv # Added for .env loading

# Load environment variables from .env file
load_dotenv()

# --- Project Root Configuration ---
# Assuming config.py is in src/utils/, so project_root is two levels up
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# --- Database Configuration ---
DATA_DIR_NAME = "data"
DATABASE_NAME = "database.db"
DB_DATA_DIR = os.path.join(PROJECT_ROOT, DATA_DIR_NAME) # Absolute path to data directory for DB
DATABASE_PATH = os.path.join(DB_DATA_DIR, DATABASE_NAME) # Absolute path to DB file

# --- Raw Data Storage Paths ---
RAW_DATA_DIR = os.path.join(DB_DATA_DIR, "raw") # General raw data directory
GDELT_RAW_DATA_DIR = os.path.join(RAW_DATA_DIR, "gdelt") # For GDELT raw files

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
HOURLY_PIPELINE_INTERVAL_MINUTES = 60  # Changed from 1 for hourly runs
WEEKLY_SUMMARY_INTERVAL_MINUTES = 1440 # Changed from 3 for daily runs (24 * 60)

# --- API Configuration (Example) ---
# Placeholder for API keys or endpoints if the project were to use real APIs
# Example: COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY", "your_default_api_key_here")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "YOUR_ETHERSCAN_API_KEY_HERE") 
CRYPTO_PANIC_API_KEY = os.getenv("CRYPTO_PANIC_API_KEY", "YOUR_CRYPTO_PANIC_API_KEY_HERE") # Added CryptoPanic API Key
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", None) # Added Discord Webhook URL

# --- GDELT Configuration ---
GDELT_DOC_API_TIMESPAN = "72h" # Timespan for GDELT DOC API queries (e.g., "24h", "3d", "1week")

# --- CoinGecko Configuration ---
# Mapping from CoinGecko ID to our internal symbol and full name
# This will be the primary source for which coins to track and their details.
# Ensure these symbols are consistent with what might be expected by other (mock) data sources if used.
COIN_MAPPING = {
    "bitcoin": {"symbol": "BTC", "name": "Bitcoin"}, # Not on Ethereum
    "ethereum": {"symbol": "ETH", "name": "Ethereum", "decimals": 18}, # Native coin, decimals for ETH
    "solana": {"symbol": "SOL", "name": "Solana"}, # Not an ERC20 token by default
    "bittensor": {"symbol": "TAO", "name": "Bittensor"}, # Not an ERC20 token
    "near": {"symbol": "NEAR", "name": "NEAR Protocol"}, # Primarily its own L1. Wrapped ERC20: 0x85f17cf997934a597031b2e18a9ab6ebd4b9f6a4, Decimals: 24
    "render-token": {"symbol": "RNDR", "name": "Render Token", "contract_address": "0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24", "decimals": 18},
    "fetch-ai": {"symbol": "FET", "name": "Fetch.ai", "contract_address": "0xaea46a60368a7bd060eec7df8cba43b7ef41ad85", "decimals": 18}
}

# --- Other Application Settings ---
TOP_N_COINS_REPORT = 3

# Re-derive TRACKED_COIN_IDS and SAMPLE_COINS_FOR_TESTING from COIN_MAPPING to ensure consistency
TRACKED_COIN_IDS = list(COIN_MAPPING.keys())
SAMPLE_COINS_FOR_TESTING = [(details["symbol"], details["name"]) for details in COIN_MAPPING.values()]

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
    print(f"Discord Webhook URL Loaded: {bool(DISCORD_WEBHOOK_URL)}") # Added for verification
    print(f"Sample coins for testing: {SAMPLE_COINS_FOR_TESTING}")
    print(f"Tracked CoinGecko IDs: {TRACKED_COIN_IDS}")
    print(f"Coin Mapping: {COIN_MAPPING}")
    print(f"Etherscan API Key Loaded: {bool(ETHERSCAN_API_KEY and ETHERSCAN_API_KEY != 'YOUR_ETHERSCAN_API_KEY_HERE')}") 
    print(f"CryptoPanic API Key Loaded: {bool(CRYPTO_PANIC_API_KEY and CRYPTO_PANIC_API_KEY != 'YOUR_CRYPTO_PANIC_API_KEY_HERE')}")
    print(f"GDELT Raw Data Directory: {GDELT_RAW_DATA_DIR}")
    print(f"GDELT DOC API Timespan: {GDELT_DOC_API_TIMESPAN}") # Added for verification 