import sys
import os
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.database.db_manager import execute_read_query, get_all_coin_symbols
from src.utils import config # Import the config module to ensure db_manager uses correct paths

def get_latest_metrics(coin_id: int) -> dict | None:
    """Fetches the latest metrics for a given coin_id."""
    query = """
    SELECT price, volume, market_cap, active_addresses, transaction_volume, timestamp
    FROM metrics
    WHERE coin_id = ?
    ORDER BY timestamp DESC
    LIMIT 1;
    """
    result = execute_read_query(query, params=(coin_id,), fetch_one=True)
    if result:
        return {
            "price": result[0],
            "volume": result[1],
            "market_cap": result[2],
            "active_addresses": result[3],
            "transaction_volume": result[4],
            "timestamp": result[5]
        }
    return None

def get_latest_score(coin_id: int) -> dict | None:
    """Fetches the latest score for a given coin_id."""
    query = """
    SELECT score, timestamp
    FROM scores
    WHERE coin_id = ?
    ORDER BY timestamp DESC
    LIMIT 1;
    """
    result = execute_read_query(query, params=(coin_id,), fetch_one=True)
    if result:
        return {"score": result[0], "timestamp": result[1]}
    return None

def get_coin_id_and_name(symbol: str) -> tuple[int | None, str | None]:
    """Retrieves the ID and name of a coin by its symbol."""
    query = "SELECT id, name FROM coins WHERE symbol = ?;"
    result = execute_read_query(query, params=(symbol,), fetch_one=True)
    if result:
        return result[0], result[1] # id, name
    return None, None


def main():
    """Fetches and prints statistics for all coins in the database."""
    print(f"Accessing database at: {os.path.abspath(config.DATABASE_PATH)}")
    
    coin_symbols = get_all_coin_symbols()

    if not coin_symbols:
        print("No coins found in the database.")
        return

    header = [
        "Symbol", "Name", "Price", "Volume (24h)", "Market Cap", 
        "Active Addresses", "Transaction Volume", "Metrics Timestamp", 
        "Score", "Score Timestamp"
    ]
    
    # Determine column widths dynamically based on header and potential data
    # Initialize with header lengths
    col_widths = {h: len(h) for h in header} 

    all_coin_data = []

    for symbol in coin_symbols:
        coin_id, coin_name = get_coin_id_and_name(symbol)
        if coin_id is None:
            print(f"Could not find ID for symbol: {symbol}")
            continue

        latest_metrics = get_latest_metrics(coin_id)
        latest_score = get_latest_score(coin_id)

        data_row = {
            "Symbol": symbol,
            "Name": coin_name or "N/A",
            "Price": "N/A",
            "Volume (24h)": "N/A",
            "Market Cap": "N/A",
            "Active Addresses": "N/A",
            "Transaction Volume": "N/A",
            "Metrics Timestamp": "N/A",
            "Score": "N/A",
            "Score Timestamp": "N/A"
        }

        if latest_metrics:
            data_row["Price"] = f"{latest_metrics['price']:.2f}" if latest_metrics['price'] is not None else "N/A"
            data_row["Volume (24h)"] = f"{latest_metrics['volume']:.2f}" if latest_metrics['volume'] is not None else "N/A"
            data_row["Market Cap"] = f"{latest_metrics['market_cap']:.2f}" if latest_metrics['market_cap'] is not None else "N/A"
            data_row["Active Addresses"] = str(latest_metrics['active_addresses']) if latest_metrics['active_addresses'] is not None else "N/A"
            data_row["Transaction Volume"] = f"{latest_metrics['transaction_volume']:.2f}" if latest_metrics['transaction_volume'] is not None else "N/A"
            try:
                mts = datetime.fromisoformat(latest_metrics['timestamp']).strftime('%Y-%m-%d %H:%M') if latest_metrics['timestamp'] else "N/A"
                data_row["Metrics Timestamp"] = mts
            except (ValueError, TypeError):
                 data_row["Metrics Timestamp"] = latest_metrics['timestamp'] # Or some other fallback

        if latest_score:
            data_row["Score"] = f"{latest_score['score']:.2f}" if latest_score['score'] is not None else "N/A"
            try:
                sts = datetime.fromisoformat(latest_score['timestamp']).strftime('%Y-%m-%d %H:%M') if latest_score['timestamp'] else "N/A"
                data_row["Score Timestamp"] = sts
            except (ValueError, TypeError):
                data_row["Score Timestamp"] = latest_score['timestamp'] # Or some other fallback


        all_coin_data.append(data_row)

        # Update column widths based on current row data
        for key, value in data_row.items():
            col_widths[key] = max(col_widths[key], len(str(value)))

    # Print header
    header_line = " | ".join(h.ljust(col_widths[h]) for h in header)
    print(header_line)
    print("-" * len(header_line))

    # Print data rows
    for row_data in all_coin_data:
        data_line = " | ".join(str(row_data[h]).ljust(col_widths[h]) for h in header)
        print(data_line)

if __name__ == "__main__":
    # This ensures that the config module is loaded, which sets up DATABASE_PATH
    # The config module itself might print the path it's using if its logger is active
    # print(f"Current DB path from config: {config.DATABASE_PATH}") # For debugging
    main() 