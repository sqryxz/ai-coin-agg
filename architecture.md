# Program Architecture for AI Altcoin Data Collection, Scoring, and Weekly Summary

This document outlines the architecture of a program designed to collect data for AI altcoins, score them based on various metrics, and generate weekly investment summaries. The program uses SQLite for database management.

---

## **File and Folder Structure**

```
project_root/
│
├── data/
│   ├── raw/                 # Stores raw data collected from APIs
│   ├── processed/           # Stores processed and cleaned data
│   └── database.db          # SQLite database file
│
├── src/
│   ├── collectors/          # Modules for data collection
│   │   ├── coin_data.py     # Fetches coin-specific data (e.g., price, volume)
│   │   ├── on_chain.py      # Fetches on-chain metrics (e.g., active addresses)
│   │   └── social_data.py   # Fetches social sentiment data
│   │
│   ├── processors/          # Modules for data processing and scoring
│   │   ├── data_cleaner.py  # Cleans and formats raw data
│   │   ├── scorer.py        # Scores coins based on metrics
│   │   └── aggregator.py    # Aggregates hourly data into weekly summaries
│   │
│   ├── database/            # Modules for database interaction
│   │   ├── schema.sql       # Contains SQL schema for database tables
│   │   ├── db_manager.py    # Handles database queries and updates
│   │   └── data_loader.py   # Loads data into the database
│   │
│   ├── utils/               # Utility scripts
│   │   ├── config.py        # Configuration settings (API keys, constants)
│   │   ├── logger.py        # Handles logging
│   │   └── scheduler.py     # Schedules hourly/weekly tasks
│   │
│   └── main.py              # Entry point for the program
│
├── tests/                   # Unit and integration tests
│   ├── test_collectors.py   # Tests for data collection modules
│   ├── test_processors.py   # Tests for data processing modules
│   └── test_database.py     # Tests for database interactions
│
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation
└── .env                     # Environment variables (e.g., API keys)
```

---

## **Component Breakdown**

### **1. Data Collection**
- **Folder:** `src/collectors/`
- **Purpose:** Collects data from various sources (e.g., APIs, on-chain metrics, social sentiment).
- **Modules:**
  - **`coin_data.py`**: Fetches price, volume, and market cap data for each coin.
  - **`on_chain.py`**: Collects on-chain metrics like active wallets, transaction volume, etc.
  - **`social_data.py`**: Scrapes or queries social sentiment data (e.g., mentions, sentiment scores).

### **2. Data Processing**
- **Folder:** `src/processors/`
- **Purpose:** Cleans, processes, and scores data.
- **Modules:**
  - **`data_cleaner.py`**: Cleans raw data (e.g., removes null values, formats timestamps).
  - **`scorer.py`**: Calculates scores for each coin based on predefined metrics (e.g., price performance, social sentiment).
  - **`aggregator.py`**: Aggregates hourly data into weekly summaries for reporting.

### **3. Database Management**
- **Folder:** `src/database/`
- **Purpose:** Handles all interactions with the SQLite database.
- **Modules:**
  - **`schema.sql`**: Contains SQL schema for creating database tables (e.g., `coins`, `metrics`, `scores`).
  - **`db_manager.py`**: Handles CRUD operations in the database.
  - **`data_loader.py`**: Inserts processed data into the database.

### **4. Utilities**
- **Folder:** `src/utils/`
- **Purpose:** Contains reusable utility functions and configurations.
- **Modules:**
  - **`config.py`**: Stores API keys, constants (e.g., coin list, scoring weights).
  - **`logger.py`**: Logs program activity (e.g., errors, data collection status).
  - **`scheduler.py`**: Schedules hourly data collection and weekly summary generation.

### **5. Main Program**
- **File:** `src/main.py`
- **Purpose:** Entry point for the program. Orchestrates data collection, processing, and scoring.

### **6. Tests**
- **Folder:** `tests/`
- **Purpose:** Contains unit and integration tests to ensure program reliability.

---

## **State Management**

### **State Storage**
- **Database:** SQLite database (`data/database.db`) stores all persistent state, including:
  - **Coins Table:** Stores metadata about each coin (e.g., name, symbol).
  - **Metrics Table:** Stores hourly metrics for each coin.
  - **Scores Table:** Stores calculated scores for each coin.
  - **Summaries Table:** Stores weekly summaries.

### **In-Memory State**
- Temporary data (e.g., raw API responses) is held in memory during processing. Once processed, data is saved to the database.

---

## **Service Interconnections**

1. **Data Collection → Processing**
   - Collectors fetch raw data and save it to `data/raw/` or pass it directly to processors.
   - Processors clean and format the data, then calculate scores.

2. **Processing → Database**
   - Processed data and calculated scores are stored in the SQLite database via `db_manager.py`.

3. **Database → Weekly Summary**
   - Aggregated data is retrieved from the database to generate weekly summaries.

4. **Scheduler**
   - The `scheduler.py` utility triggers hourly data collection and weekly summary generation.

---

## **Example Workflow**

1. **Hourly Workflow:**
   - Scheduler triggers `main.py` to run.
   - `main.py` calls collectors to fetch raw data.
   - Raw data is cleaned and scored by processors.
   - Processed data is saved to the database.

2. **Weekly Workflow:**
   - Scheduler triggers weekly summary generation.
   - Aggregator retrieves data from the database and generates a summary.
   - Summary is saved to the database and optionally exported (e.g., as a report).

---

## **Database Schema**

### **Schema Overview**
```sql
CREATE TABLE coins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    price REAL,
    volume REAL,
    market_cap REAL,
    active_addresses INTEGER,
    transaction_volume REAL,
    FOREIGN KEY (coin_id) REFERENCES coins (id)
);

CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    score REAL,
    FOREIGN KEY (coin_id) REFERENCES coins (id)
);

CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    top_coins TEXT NOT NULL
);
```

---

## **Key Features**

1. **Hourly Data Collection:** Automatically fetches and processes data for all coins.
2. **Scoring System:** Assigns scores to coins based on metrics like price, volume, and sentiment.
3. **Weekly Summaries:** Generates investment suggestions based on aggregated scores.
4. **SQLite Database:** Stores all data and ensures persistence.
5. **Modular Design:** Each component is self-contained and reusable.

--- 

## **Dependencies**
- **Python Libraries:**
  - `sqlite3`: Database management.
  - `requests`: API calls.
  - `pandas`: Data manipulation.
  - `schedule`: Task scheduling.
  - `dotenv`: Environment variable management.
  - `logging`: Logging system.

Add these to `requirements.txt`.

```plaintext
requests
pandas
schedule
python-dotenv
```

--- 

## **Next Steps**
1. Implement the folder structure and write the modules.
2. Define the scoring logic in `scorer.py`.
3. Set up the SQLite database using `schema.sql`.
4. Write test cases to ensure reliability.
5. Deploy and schedule the program to run hourly and weekly.
