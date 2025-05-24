import sqlite3
import os
from src.utils import config # Import the config module
from src.utils.logger import setup_logger # Import for __main__ block

# DATA_DIR = "data" # Replaced by config
# DATABASE_NAME = "database.db"  # Replaced by config
# DATABASE_PATH = os.path.join(DATA_DIR, DATABASE_NAME) # Replaced by config.DATABASE_PATH
# SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql") # Replaced by config.SCHEMA_FILE_PATH

def get_db_connection():
    """Establishes a connection to the SQLite database.
    The database file will be created if it doesn't exist based on config.DATABASE_PATH.
    """
    # Ensure the directory for the database exists (taken from config.DATABASE_PATH)
    db_dir = os.path.dirname(config.DATABASE_PATH)
    os.makedirs(db_dir, exist_ok=True)
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        return conn
    except sqlite3.Error as e:
        # Consider using a logger here if db_manager gets its own logger
        print(f"Error connecting to database at {config.DATABASE_PATH}: {e}")
        return None

def execute_write_query(query, params=()):
    """Executes a given SQL query that writes to the database (INSERT, UPDATE, DELETE, CREATE).
    Changes are committed. Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error executing write query: {e}")
        return False
    finally:
        if conn:
            conn.close()

def execute_read_query(query, params=(), fetch_one=False, fetch_all=False):
    """Executes a given SQL SELECT query and fetches results.
    Returns fetched data (single row, all rows, or None on error or if no data).
    """
    conn = None
    if not (fetch_one or fetch_all):
        print("Error: For read queries, either fetch_one or fetch_all must be True.")
        return None
    if fetch_one and fetch_all:
        print("Error: For read queries, only one of fetch_one or fetch_all can be True.")
        return None

    try:
        conn = get_db_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        result = None
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        return result
    except sqlite3.Error as e:
        print(f"Error executing read query: {e}")
        return None
    finally:
        if conn:
            conn.close()

def initialize_database():
    """Initializes the database by executing the schema.sql script from config.SCHEMA_FILE_PATH."""
    conn = None
    try:
        with open(config.SCHEMA_FILE_PATH, 'r') as f:
            sql_script = f.read()
        
        conn = get_db_connection()
        if conn is None:
            # print("Failed to get database connection for initialization.") # Consider logger
            return False
        
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()
        # print(f"Database initialized successfully using {config.SCHEMA_FILE_PATH}.") # Consider logger
        # If db_manager gets a logger, use it here.
        # For now, let's assume the caller (e.g., main.py or scheduler.py) logs initialization status.
        return True
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}") # Consider logger
        return False
    except FileNotFoundError:
        print(f"Error: Schema file not found at {config.SCHEMA_FILE_PATH}") # Consider logger
        return False
    finally:
        if conn:
            conn.close()

def get_coin_id_by_symbol(symbol: str) -> int | None:
    """Retrieves the ID of a coin by its symbol."""
    query = "SELECT id FROM coins WHERE symbol = ?;"
    result = execute_read_query(query, params=(symbol,), fetch_one=True)
    if result:
        return result[0]
    return None

def get_all_coin_symbols() -> list[str]:
    """Retrieves a list of all coin symbols from the coins table."""
    query = "SELECT symbol FROM coins ORDER BY symbol;"
    results = execute_read_query(query, fetch_all=True)
    if results:
        return [row[0] for row in results]
    return []

if __name__ == "__main__":
    main_logger = setup_logger(name='db_manager_test', log_file_name=config.DB_LOG_FILE if hasattr(config, 'DB_LOG_FILE') else 'db_test.log')
    main_logger.info(f"Database operations will use: {os.path.abspath(config.DATABASE_PATH)}")

    main_logger.info("--- Testing Database File Creation ---")
    db_dir_path = os.path.dirname(config.DATABASE_PATH)
    if not os.path.exists(db_dir_path):
        main_logger.info(f"Directory for DB '{db_dir_path}' does not exist. Expecting it to be created.")
    
    conn_test = get_db_connection()
    if conn_test:
        main_logger.info("Successfully connected to database.")
        conn_test.close()
        if os.path.exists(config.DATABASE_PATH):
            main_logger.info(f"Database file verified at: '{config.DATABASE_PATH}'")
        else:
            main_logger.critical(f"CRITICAL ERROR: Database file '{config.DATABASE_PATH}' was NOT found after connection attempt.")
    else:
        main_logger.error(f"Failed to connect to/create database at '{config.DATABASE_PATH}'.")

    main_logger.info("--- Testing Database Initialization ---")
    if initialize_database(): 
        main_logger.info("initialize_database() reported success.")
        expected_tables = ["coins", "metrics", "scores", "summaries"]
        main_logger.info("--- Verifying Table Creation After Initialization ---")
        for table_name in expected_tables:
            check_table_query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
            result = execute_read_query(check_table_query, fetch_one=True)
            if result and result[0] == table_name:
                main_logger.info(f"Table '{table_name}' verified.")
            else:
                main_logger.error(f"ERROR: Table '{table_name}' NOT found after initialization.")
    else:
        main_logger.error("initialize_database() reported failure.")
    
    main_logger.info("--- Testing get_coin_id_by_symbol (example) ---")
    btc_id_example = get_coin_id_by_symbol("BTC")
    if btc_id_example:
        main_logger.info(f"Retrieved ID for BTC (example): {btc_id_example}. (This relies on BTC being in DB)")
    else:
        main_logger.info("Could not retrieve ID for BTC (example). (BTC might not be in DB or an error occurred)")

    main_logger.info("--- Testing get_all_coin_symbols (example) ---")
    all_symbols = get_all_coin_symbols()
    if all_symbols:
        main_logger.info(f"Retrieved symbols: {all_symbols} (Relies on data_loader having run or coins existing)")
    elif not all_symbols and all_symbols == []:
        main_logger.info("No symbols retrieved. (This is expected if DB is empty or has no coins)")
    else: 
        main_logger.error("Failed to retrieve symbols or an error occurred.")

    main_logger.info("--- Testing Read Query (SQLite Version) ---")
    version = execute_read_query("SELECT sqlite_version();", fetch_one=True)
    if version:
        main_logger.info(f"SQLite version: {version[0]}")
    else:
        main_logger.error("Failed to execute SELECT sqlite_version() or database connection failed earlier.")

    main_logger.info("--- Testing Write Query (CREATE TABLE & INSERT) ---")
    create_table_query = """
    CREATE TABLE IF NOT EXISTS temp_test_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL
    );
    """
    if execute_write_query(create_table_query):
        main_logger.info("Successfully executed: CREATE TABLE IF NOT EXISTS temp_test_table.")
        
        insert_query = "INSERT INTO temp_test_table (description) VALUES (?);"
        test_description = "Basic DB Manager Test Entry"
        if execute_write_query(insert_query, params=(test_description,)):
            main_logger.info(f"Successfully inserted data: '{test_description}'.")
            main_logger.info("--- Verifying Insert with Read Query ---")
            fetched_data = execute_read_query(
                "SELECT id, description FROM temp_test_table WHERE description = ?;",
                params=(test_description,),
                fetch_one=True
            )
            if fetched_data:
                main_logger.info(f"Fetched data: ID={fetched_data[0]}, Description='{fetched_data[1]}'")
            else:
                main_logger.error("Failed to fetch inserted data or data not found.")
        else:
            main_logger.error("Failed to insert data into temp_test_table.")
    else:
        main_logger.error("Failed to create temp_test_table.")

    main_logger.info("--- Cleaning Up Temporary Test Table ---")
    if execute_write_query("DROP TABLE IF EXISTS temp_test_table;"):
        main_logger.info("Successfully dropped temp_test_table.")
    else:
        main_logger.error("Failed to drop temp_test_table.")
    
    main_logger.info("--- db_manager.py tests finished ---") 