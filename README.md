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
    Copy `.env.example` (if provided, otherwise create `.env`) and fill in any necessary variables. For the current version, it primarily defines `PYTHON_ENV`.

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