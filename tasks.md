# Granular Step-by-Step Plan to Build the MVP

This plan breaks the MVP development into small, testable tasks. Each task focuses on a single concern and has a clear start and end. Tasks are grouped by functional areas of the architecture.

---

## **1. Project Setup**

### **Task 1.1:** Initialize Project Structure
- **Start:** Create the folder structure as outlined in the architecture.
- **End:** Ensure all folders (`data/`, `src/`, `tests/`, etc.) are created, and empty placeholder files (e.g., `.gitkeep` or empty `.py` files) exist where necessary.

### **Task 1.2:** Configure `requirements.txt`
- **Start:** Write a `requirements.txt` file with initial dependencies (`sqlite3`, `requests`, `pandas`, `schedule`, `python-dotenv`).
- **End:** Verify dependencies are installed with `pip install -r requirements.txt`.

### **Task 1.3:** Set Up `.env` File
- **Start:** Create a `.env` file to store API keys and other sensitive configurations.
- **End:** Verify the `.env` file can be read using the `dotenv` library in a test script.

---

## **2. Database Setup**

### **Task 2.1:** Write SQL Schema
- **Start:** Create `schema.sql` to define the database structure (tables: `coins`, `metrics`, `scores`, `summaries`).
- **End:** Verify the schema is valid by running it in SQLite and confirming the tables are created.

### **Task 2.2:** Implement `db_manager.py` (Basic Setup)
- **Start:** Write a `db_manager.py` module with functions to:
  - Connect to the SQLite database.
  - Execute queries.
- **End:** Test basic database connection and query execution with a sample query.

### **Task 2.3:** Create Database Initialization Script
- **Start:** Write a script in `db_manager.py` to initialize the database using `schema.sql`.
- **End:** Run the script and confirm the database is created with the correct schema.

### **Task 2.4:** Add Test Data Loader
- **Start:** Implement a function in `data_loader.py` to insert test data into the `coins` table.
- **End:** Verify the test data is inserted and retrievable.

---

## **3. Data Collection**

### **Task 3.1:** Create `coin_data.py` (Price and Volume)
- **Start:** Write a function to fetch price and volume data for a single coin using a mock API or static data.
- **End:** Verify the function returns the expected data structure (e.g., JSON or dictionary).

### **Task 3.2:** Create `on_chain.py` (On-Chain Metrics)
- **Start:** Write a function to fetch on-chain metrics (e.g., active addresses) using mock data.
- **End:** Verify the function returns the expected data structure.

### **Task 3.3:** Create `social_data.py` (Social Sentiment)
- **Start:** Write a function to fetch social sentiment data (e.g., mentions, sentiment score) using mock data.
- **End:** Verify the function returns the expected data structure.

### **Task 3.4:** Integrate Collectors
- **Start:** Write a function in `main.py` to call all collectors (`coin_data.py`, `on_chain.py`, `social_data.py`) for a single coin.
- **End:** Verify the function returns a combined data structure for a single coin.

---

## **4. Data Processing**

### **Task 4.1:** Implement `data_cleaner.py`
- **Start:** Write a function to clean raw data (e.g., handle missing values, format timestamps).
- **End:** Verify the function outputs cleaned data for a single coin.

### **Task 4.2:** Implement `scorer.py`
- **Start:** Write a function to calculate a score for a single coin based on predefined metrics.
- **End:** Verify the function outputs a valid score for a single coin.

### **Task 4.3:** Process and Save Data
- **Start:** Write a function in `main.py` to process data for a single coin (clean, score, and save to the database).
- **End:** Verify the processed data is saved correctly in the database.

---

## **5. Scheduling**

### **Task 5.1:** Implement `scheduler.py`
- **Start:** Write a function to schedule hourly and daily tasks using the `schedule` library.
- **End:** Verify the scheduler triggers a test function at the correct intervals.

### **Task 5.2:** Integrate Scheduling with Data Collection
- **Start:** Modify the scheduler to trigger the data collection pipeline hourly.
- **End:** Verify the pipeline runs automatically and saves data to the database.

---

## **6. Daily Summary**

### **Task 6.1:** Implement `aggregator.py`
- **Start:** Write a function to aggregate hourly data into daily summaries.
- **End:** Verify the function outputs a valid daily summary for a single coin.

### **Task 6.2:** Generate Daily Report
- **Start:** Write a function to generate a report of top coins based on daily scores.
- **End:** Verify the report is generated and saved to the database.

---

## **7. Testing**

### **Task 7.1:** Write Unit Tests for Collectors
- **Start:** Write tests for `coin_data.py`, `on_chain.py`, and `social_data.py`.
- **End:** Verify all tests pass with mock data.

### **Task 7.2:** Write Unit Tests for Processors
- **Start:** Write tests for `data_cleaner.py` and `scorer.py`.
- **End:** Verify all tests pass with mock data.

### **Task 7.3:** Write Integration Tests
- **Start:** Write tests to validate the full pipeline (collection → processing → database).
- **End:** Verify the pipeline works end-to-end with mock data.

---

## **8. Deployment**

### **Task 8.1:** Set Up Logging
- **Start:** Implement logging in `logger.py` to track program activity.
- **End:** Verify logs are written to a file and include key events.

### **Task 8.2:** Deploy MVP
- **Start:** Deploy the program on a local machine or server with the scheduler running.
- **End:** Verify the program collects, processes, and saves data hourly and generates daily summaries.

---

## **Notes**
- Each task is designed to be small and testable.
- Mock data should be used for testing until real APIs are integrated.
- Tasks can be adjusted or expanded based on feedback during development.

