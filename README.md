# AI Altcoin Aggregator

This project collects, processes, scores, and summarizes data for various altcoins.

## Project Structure

- `data/`: Stores raw, processed data, logs, and the database.
  - `raw/`: Placeholder for raw data dumps (if any).
  - `processed/`: Placeholder for processed data files (if any).
  - `app.log`, `scheduler.log`, etc.: Log files.
  - `database.db`: SQLite database.
- `src/`: Contains all source code.
  - `collectors/`: Modules for fetching data from various (mock) sources.
  - `database/`: Database management (`db_manager.py`, `schema.sql`, `data_loader.py`).
  - `processors/`: Modules for cleaning, scoring, and aggregating data.
  - `utils/`: Utility modules like configuration (`config.py`), logging (`logger.py`), and scheduling (`scheduler.py`).
  - `main.py`: Main script to process a single coin or a list of coins.
- `tests/`: Unit and integration tests.
- `.env`: Environment variables (e.g., API keys - though not used with current mock data).
- `requirements.txt`: Python dependencies.
- `architecture.md`: System architecture overview.
- `tasks.md`: Project development tasks.
- `coding_protocol.md`: Coding standards and conventions.

## Setup

1.  **Clone the repository.**
2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up the `.env` file:**
    Copy `.env.example` (if provided, otherwise create `.env`) and fill in any necessary API keys.
    Refer to `src/utils/config.py` for API keys used (e.g., `ETHERSCAN_API_KEY`, `CRYPTO_PANIC_API_KEY`).
    If API keys are not provided, the respective data collectors will either fail gracefully or return limited/mock data.

## How It Works

The AI Altcoin Aggregator is designed to run as an automated system, orchestrated by a scheduler. It continuously collects, processes, scores, and summarizes data for a predefined list of cryptocurrencies.

**1. Scheduled Data Pipeline (`main_data_pipeline_job` run by `scheduler.py`):**

This is the core data processing engine of the application. It runs at a configurable interval (e.g., hourly, as defined by `HOURLY_PIPELINE_INTERVAL_MINUTES` in `src/utils/config.py`).

When this job runs, it executes `run_full_data_pipeline()` from `src/main.py`, which performs the following steps:

*   **Initialization:** 
    *   Ensures the SQLite database (`data/database.db`) is initialized and the schema (from `src/database/schema.sql`) exists.
    *   Loads or updates the list of tracked cryptocurrencies from `COIN_MAPPING` in `src/utils/config.py` into the `coins` table in the database. This mapping defines which coins to process and their specific details (like contract addresses for ERC20 tokens).
*   **Data Collection & Processing Loop (for each tracked coin):**
    1.  **CoinGecko Data:** Fetches current market data (price, volume, market cap) and historical market data using the CoinGecko API.
    2.  **Etherscan Data:** For ERC20 tokens (identified by a `contract_address` in `COIN_MAPPING`), it fetches on-chain data such as active address proxies, transaction count proxies, and total token supply from the Etherscan API.
    3.  **CryptoPanic Data:** Fetches news articles related to the coin from the CryptoPanic API, filters them, and calculates an aggregate sentiment score based on vote counts.
    4.  **GDELT Data:** Queries the GDELT DOC 2.0 API for news articles mentioning the coin and extracts an average sentiment tone from these articles.
    5.  **Data Cleaning (`src/processors/data_cleaner.py`):** The raw data collected from all sources is passed to `clean_coin_data`. This function handles missing values by imputing sensible defaults (e.g., 0.0 for numerical fields, 0 for counts), ensures correct data types, and logs any cleaning actions.
    6.  **Scoring (`src/processors/scorer.py`):** The cleaned data is then fed into `calculate_coin_score`. This function calculates a composite score (0-100) for the coin based on a weighted sum of several transformed metrics. Key aspects of the scoring include:
        *   Logarithmic scaling for metrics with wide ranges (e.g., volume, market cap).
        *   Rescaling of sentiment scores to a common range (0-1).
        *   A **mention multiplier**: The total number of mentions (from CryptoPanic + GDELT article count) influences the weight of the sentiment scores. Higher mentions can amplify the impact of positive or negative sentiment.
        *   A placeholder for future **volume momentum** calculation.
    7.  **Database Persistence:**
        *   The collected and cleaned metrics (price, volume, market cap, active addresses, etc.) are saved to the `metrics` table.
        *   The calculated composite score and its timestamp are saved to the `scores` table.
*   **Logging:** All significant actions, errors, and results from this pipeline are logged to `data/app.log` (and to the console if run directly).

**2. Scheduled Summary Report (`weekly_summary_job` run by `scheduler.py`):**

This job is responsible for generating periodic summary reports. It also runs at a configurable interval (e.g., daily or weekly, as defined by `WEEKLY_SUMMARY_INTERVAL_MINUTES` in `src/utils/config.py` - note that the variable name implies weekly, but the default config value is for frequent testing).

When this job runs, it executes `generate_and_save_top_coins_report()` from `src/processors/aggregator.py`:

*   **Data Aggregation:**
    *   Determines the reporting period (e.g., the week ending on the current day).
    *   For every coin listed in the `coins` table, it fetches all scores recorded within the defined reporting period from the `scores` table.
    *   Calculates an average score for each coin over that period.
*   **Report Generation & Saving:**
    *   Ranks the coins based on their average weekly scores.
    *   Generates a "Top N Coins" report (where N is configurable via `TOP_N_COINS_REPORT` in `config.py`), listing the top coins and their average scores.
    *   Saves this report (typically as a JSON string) into the `summaries` table in the database, along with the start and end dates of the report period.
*   **Logging:** Activities related to summary generation are logged to `data/processor.log`.

**Overall Automated Flow:**

The `scheduler.py` script acts as the heart of the automation. It ensures that the data pipeline runs regularly to keep coin data fresh and scores updated. Concurrently, the summary job runs to periodically analyze these scores and save insightful reports.

This setup allows for continuous, unattended operation of the AI Altcoin Aggregator, providing up-to-date metrics, scores, and summary views over time.

**(End of "How It Works" Section)**

## Running the Application

### Initialize Database & Load Test Coins
The database schema needs to be initialized, and sample coins loaded if you want to test the full pipeline. Several scripts do this in their `if __name__ == "__main__":` blocks.

For example, to run the main processing pipeline for test coins:
```bash
python3 -m src.main
```
This will:
1. Initialize the database (`data/database.db`) if it doesn't exist, using `src/database/schema.sql`.
2. Clear and load sample coins defined in `src/utils/config.py` (via `src/database/data_loader.py`).
3. Process a predefined list of test symbols (e.g., BTC, ETH, DOGE, XYZ) by:
    a. Collecting mock data.
    b. Cleaning the data.
    c. Scoring the data.
    d. Saving the score to the database.
4. Log activities to `data/app.log` and console.

### Running the Scheduler
The scheduler runs tasks at defined intervals (e.g., hourly data collection, weekly report generation).
```bash
python3 src/utils/scheduler.py
```
This will:
1. Initialize the database and load sample coins if its main block is run.
2. Start scheduling defined jobs.
3. Log activities to `data/scheduler.log`, `data/app.log` (for tasks called from `main.py` functions), `data/processor.log` (for aggregator tasks) and console.

### Running Individual Components or Tests

-   **Collectors, Processors, Utils:** Most modules in `src/` can be run directly to see their standalone behavior (often using mock data or simple tests in their `if __name__ == "__main__":` blocks).
    Example: `python3 src/collectors/coin_data.py`
-   **Tests:** Run unit and integration tests using:
    ```bash
    python3 -m unittest discover tests
    ```
    Or run individual test files:
    ```bash
    python3 tests/test_collectors.py
    ```

## Logging
Log files are stored in the `data/` directory as specified in `src/utils/config.py`.
- `app.log`: General application logs from `main.py`.
- `scheduler.log`: Logs from the `scheduler.py` script.
- `processor.log`: Logs from processing tasks like `aggregator.py`.
- `db.log`: Logs from `db_manager.py`'s test block.
- `collector.log`: (Not currently used by default, but configured in `config.py`).

Additional log files might be created by specific test runs within `if __name__ == "__main__":` blocks (e.g., `custom_test_logger.log` from `logger.py`'s test). 