from datetime import datetime, timedelta, timezone
import json
import sys
import os
from src.utils.logger import setup_logger
import logging
import requests

# Adjust sys.path to allow importing from the project root
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

# Import config first
from src.utils import config 

from src.database.db_manager import (
    execute_read_query, 
    execute_write_query, # For inserting test scores
    get_coin_id_by_symbol, 
    initialize_database,
    get_all_coin_symbols, # Added for fetching all symbols
)
from src.database.data_loader import (
    load_test_coins_data, 
    clear_coins_table
)

# Setup logger for the aggregator module, using config for file name
logger = setup_logger(name='aggregator_proc', log_file_name=config.PROCESSOR_LOG_FILE)

# Let's add a specific function to clear scores for testing purposes.
def clear_scores_table_for_test():
    """Clears all data from the scores table for testing."""
    logger.info("Clearing data from 'scores' table for testing...")
    if execute_write_query("DELETE FROM scores;"):
        execute_write_query("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'scores';")
        logger.info("'scores' table cleared.")
        return True
    logger.info("Failed to clear 'scores' table.")
    return False

def clear_summaries_table_for_test():
    """Clears all data from the summaries table for testing."""
    logger.info("Clearing data from 'summaries' table for testing...")
    if execute_write_query("DELETE FROM summaries;"):
        execute_write_query("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'summaries';")
        logger.info("'summaries' table cleared.")
        return True
    logger.info("Failed to clear 'summaries' table.")
    return False

def get_weekly_summary_for_coin(coin_id: int, week_end_date: datetime.date) -> dict:
    """
    Aggregates scores for a single coin over the week ending on week_end_date.

    Args:
        coin_id (int): The ID of the coin.
        week_end_date (datetime.date): The end date of the week for aggregation.

    Returns:
        dict: A summary including average score and number of scores considered.
    """
    week_start_date = week_end_date - timedelta(days=6)
    # Timestamps in DB are ISO format strings. For SQLite, date range queries are usually on strings.
    # Ensure timestamps are comparable: YYYY-MM-DDTHH:MM:SS.ssssss+00:00
    # We need to compare the date part. SQLite's date functions can be used if timestamps were stored as DATE/DATETIME types.
    # With TEXT timestamps, string comparison works if format is consistent.
    # For a robust solution, use date(timestamp_column) in SQL.
    
    query = """
    SELECT score 
    FROM scores 
    WHERE coin_id = ? 
      AND date(timestamp) >= ? 
      AND date(timestamp) <= ?;
    """
    # Convert dates to string for the query
    params = (coin_id, week_start_date.isoformat(), week_end_date.isoformat())
    
    logger.debug(f"Fetching scores for coin_id {coin_id} from {week_start_date.isoformat()} to {week_end_date.isoformat()}")
    scores_data = execute_read_query(query, params=params, fetch_all=True)
    
    average_score = None
    num_scores = 0

    if scores_data:
        total_score = sum(s[0] for s in scores_data if s[0] is not None)
        num_valid_scores = sum(1 for s in scores_data if s[0] is not None)
        if num_valid_scores > 0:
            average_score = total_score / num_valid_scores
        num_scores = len(scores_data)
        
    avg_score = average_score
    logger.info(f"TEMP DEBUG: Coin ID {coin_id} (Symbol: {get_coin_id_by_symbol(coin_id)}), Calculated Avg Score for week {week_start_date.isoformat()}-{week_end_date.isoformat()}: {avg_score}")

    return {
        "coin_id": coin_id,
        "week_start_date": week_start_date.isoformat(),
        "week_end_date": week_end_date.isoformat(),
        "average_score": average_score,
        "number_of_scores_considered": num_scores,
        "aggregation_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

def send_to_discord(webhook_url: str, report_title: str, top_coins_data: list):
    """
    Sends a formatted message with the top coins report to a Discord webhook.

    Args:
        webhook_url (str): The Discord webhook URL.
        report_title (str): The title for the Discord message.
        top_coins_data (list): A list of dictionaries, e.g., 
                                 [{"symbol": "BTC", "average_score": 75.5}, ...]
    """
    if not webhook_url:
        logger.info("Discord webhook URL not configured. Skipping notification.")
        return

    if not top_coins_data:
        message_content = f"**{report_title}**\n\nNo data available for this period."
    else:
        fields = []
        for coin in top_coins_data:
            fields.append({
                "name": f":coin: {coin.get('symbol', 'N/A')}", 
                "value": f"**Score: {coin.get('average_score', 'N/A'):.2f}**", 
                "inline": True
            })
        
        # Ensure an even number of inline fields for better formatting, or add a blank if odd
        if len(fields) % 2 != 0 and len(fields) > 1: # Avoid adding blank for single coin
             fields.append({"name": "\u200b", "value": "\u200b", "inline": True}) # Zero-width space for blank field

        embed = {
            "title": f":bar_chart: {report_title}",
            "description": "Top coins based on weekly average scores.",
            "color": 0x00ff00,  # Green color
            "fields": fields,
            "footer": {
                "text": f"Report generated on {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            }
        }
        message_content = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=message_content)
        response.raise_for_status()  # Raise an exception for HTTP errors
        logger.info(f"Successfully sent report to Discord: {report_title}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending report to Discord: {e}")

def generate_and_save_top_coins_report(week_end_date: datetime.date, top_n: int = config.TOP_N_COINS_REPORT) -> bool:
    """
    Generates a report of top N coins based on their average weekly scores
    and saves it to the summaries table.

    Args:
        week_end_date (datetime.date): The end date of the week for the report.
        top_n (int): The number of top coins to include in the report.

    Returns:
        bool: True if the report was successfully generated and saved, False otherwise.
    """
    # Use TOP_N_COINS_REPORT from config if top_n is not provided
    resolved_top_n = top_n if top_n is not None else config.TOP_N_COINS_REPORT

    logger.info(f"Generating Top Coins Report for week ending {week_end_date.isoformat()} (Top {resolved_top_n})")
    all_symbols = get_all_coin_symbols() # Fetches list of symbols like ['BTC', 'ETH']
    
    if not all_symbols:
        logger.warning("No coin symbols found in the database. Cannot generate report.")
        return False

    coin_summaries = []
    for symbol in all_symbols:
        coin_id = get_coin_id_by_symbol(symbol)
        if coin_id:
            summary = get_weekly_summary_for_coin(coin_id, week_end_date)
            # We need the symbol in the summary for the report if coin_id isn't enough
            summary['symbol'] = symbol 
            if summary.get("average_score") is not None:
                coin_summaries.append(summary)
        else:
            logger.warning(f"Could not find ID for symbol {symbol} while generating report.")

    if not coin_summaries:
        logger.info("No coins had scorable data for the period. No report generated.")
        # Optionally, still save an empty report or a note
        # For now, we'll just return False if no actual summaries to rank
        return False

    # Sort coins by average_score in descending order
    # Handle cases where average_score might be None if a coin was processed but had no valid scores (though filtered above)
    sorted_summaries = sorted(
        [s for s in coin_summaries if s.get("average_score") is not None],
        key=lambda x: x["average_score"],
        reverse=True
    )

    top_coins_list = []
    for summary in sorted_summaries[:resolved_top_n]:
        top_coins_list.append({
            "symbol": summary["symbol"],
            "average_score": round(summary["average_score"], 4) # Round for cleaner report
        })
    
    if not top_coins_list:
        logger.info("No coins made it to the top list (e.g., all had null scores). Report not saved.")
        return False
        
    week_start_date_str = (week_end_date - timedelta(days=6)).isoformat()
    week_end_date_str = week_end_date.isoformat()
    top_coins_json = json.dumps(top_coins_list)

    insert_report_query = """
    INSERT INTO summaries (week_start, week_end, top_coins)
    VALUES (?, ?, ?);
    """
    params = (week_start_date_str, week_end_date_str, top_coins_json)
    
    logger.info(f"Saving report to database: Start={week_start_date_str}, End={week_end_date_str}, Report={top_coins_json}")
    if execute_write_query(insert_report_query, params):
        logger.info("Weekly top coins report saved successfully.")

        # Send to Discord if URL is configured
        if config.DISCORD_WEBHOOK_URL:
            report_title = f"Top {resolved_top_n} Coins Report: Week Ending {week_end_date_str}"
            send_to_discord(config.DISCORD_WEBHOOK_URL, report_title, top_coins_list)

        return True
    else:
        logger.error("Failed to save weekly top coins report.")
        return False

def generate_top_n_coins_report(top_n: int = config.TOP_N_COINS_REPORT) -> list[dict]:
    """
    Generates a report of the top N coins based on their latest scores.
    Also includes some recent metrics for context.

    Args:
        top_n (int): The number of top coins to include in the report. 
                     Defaults to config.TOP_N_COINS_REPORT.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a top coin
                    and contains its details, latest score, and some metrics.
                    Returns an empty list if no coins or scores are found, or on error.
    """
    logger.info(f"Generating top {top_n} coins report...")
    
    # Ensure DB is initialized if it hasn't been already (idempotent)
    # initialize_database() # Usually main.py or scheduler would handle this.
    # For standalone testing, it might be needed. Let's assume DB is up.

    query_coins_and_latest_scores = """
    SELECT 
        c.coin_id,
        c.symbol,
        c.name,
        s.score,
        s.timestamp AS score_timestamp,
        (SELECT m.price FROM metrics m WHERE m.coin_id = c.coin_id ORDER BY m.timestamp DESC LIMIT 1) AS latest_price,
        (SELECT m.market_cap FROM metrics m WHERE m.coin_id = c.coin_id ORDER BY m.timestamp DESC LIMIT 1) AS latest_market_cap,
        (SELECT m.timestamp FROM metrics m WHERE m.coin_id = c.coin_id ORDER BY m.timestamp DESC LIMIT 1) AS latest_metrics_timestamp
    FROM coins c
    JOIN (
        SELECT 
            coin_id, 
            score, 
            timestamp,
            ROW_NUMBER() OVER(PARTITION BY coin_id ORDER BY timestamp DESC) as rn
        FROM scores
    ) s ON c.coin_id = s.coin_id AND s.rn = 1
    ORDER BY s.score DESC
    LIMIT ?;
    """
    
    try:
        top_coins_data = execute_read_query(query_coins_and_latest_scores, params=(top_n,), fetch_all=True)
        
        if not top_coins_data:
            logger.warning("No coin data or scores found to generate a top N report.")
            return []

        report = []
        for row in top_coins_data:
            coin_id, symbol, name, score, score_ts, price, mcap, metrics_ts = row
            report.append({
                "rank": len(report) + 1,
                "coin_id": coin_id,
                "symbol": symbol,
                "name": name,
                "latest_score": score,
                "score_timestamp": score_ts,
                "latest_price_usd": price,
                "latest_market_cap_usd": mcap,
                "latest_metrics_timestamp": metrics_ts
            })
        
        logger.info(f"Successfully generated report for top {len(report)} coins.")
        return report
        
    except Exception as e:
        logger.error(f"Error generating top N coins report: {e}", exc_info=True)
        return []

if __name__ == "__main__":
    logger.info("--- Testing Weekly Aggregator & Report Generation ---")

    logger.info("Step 1: Initializing database and test data...")
    initialize_database()
    clear_coins_table()
    clear_scores_table_for_test()
    clear_summaries_table_for_test() # Clear summaries table for fresh test
    
    # Use SAMPLE_COINS_FOR_TESTING from config
    if not load_test_coins_data(config.SAMPLE_COINS_FOR_TESTING):
        logger.critical("Failed to load test coin data from config. Aborting aggregator test.")
        sys.exit(1)
    logger.info("Database setup complete with coins from config.")

    # Get IDs for test score insertion
    btc_id = get_coin_id_by_symbol("BTC") # Assuming BTC is in config.SAMPLE_COINS_FOR_TESTING
    eth_id = get_coin_id_by_symbol("ETH") # Assuming ETH is in config.SAMPLE_COINS_FOR_TESTING
    sol_id = get_coin_id_by_symbol("SOL") # Assuming SOL is in config.SAMPLE_COINS_FOR_TESTING
    ada_id = get_coin_id_by_symbol("ADA") # Assuming ADA is in config.SAMPLE_COINS_FOR_TESTING

    if not all([btc_id, eth_id, sol_id, ada_id]): # This check might fail if any are not in sample_coins
        logger.warning("Could not get IDs for all expected test coins (BTC, ETH, SOL, ADA). Mock scores might be incomplete.")
        # Proceeding, but be aware that some mock scores might not be inserted.

    logger.info("Step 2: Inserting mock scores for coins over the past week...")
    today = datetime.now(timezone.utc).date()
    
    # Create mock scores only for coin IDs that were found
    mock_scores_map = {}
    if btc_id: mock_scores_map[btc_id] = [0.8, 0.85, 0.75, None, 0.82, 0.9, 0.88]
    if eth_id: mock_scores_map[eth_id] = [0.7, 0.65, 0.72, 0.68, 0.71, 0.7, 0.66]
    if sol_id: mock_scores_map[sol_id] = [0.9, 0.92, 0.95, 0.91, 0.88, 0.93, 0.94]
    if ada_id: mock_scores_map[ada_id] = [0.5, None, 0.55, 0.48, None, 0.52, 0.45]

    insert_query = "INSERT INTO scores (coin_id, timestamp, score) VALUES (?, ?, ?);"
    total_mock_scores_inserted = 0
    for coin_id_key, scores_list in mock_scores_map.items():
        for i, score_value in enumerate(scores_list):
            score_timestamp_obj = datetime.now(timezone.utc) - timedelta(days=i)
            score_timestamp_iso = score_timestamp_obj.isoformat()
            if execute_write_query(insert_query, params=(coin_id_key, score_timestamp_iso, score_value)):
                total_mock_scores_inserted += 1
    logger.info(f"Inserted {total_mock_scores_inserted} total mock scores for available coins.")

    # Step 3 (from previous task, run for context if needed, but report generator will call it)
    # btc_summary = get_weekly_summary_for_coin(coin_id=btc_id, week_end_date=today)
    # print(json.dumps(btc_summary, indent=4))

    logger.info("Step 4: Generating and saving the top coins report for the week ending today...")
    report_saved = generate_and_save_top_coins_report(week_end_date=today)
    if report_saved:
        logger.info("Attempted to save report. Verifying...")
        verify_query = "SELECT week_start, week_end, top_coins FROM summaries ORDER BY id DESC LIMIT 1;"
        saved_report_data = execute_read_query(verify_query, fetch_one=True)
        if saved_report_data:
            logger.info("--- Latest Saved Report from DB ---")
            logger.info(f"Week Start: {saved_report_data[0]}")
            logger.info(f"Week End: {saved_report_data[1]}")
            logger.info(f"Top Coins JSON: {saved_report_data[2]}")
            try:
                top_coins_parsed = json.loads(saved_report_data[2])
                logger.info("Top Coins Parsed:")
                for i, coin_info in enumerate(top_coins_parsed):
                    logger.info(f"  {i+1}. Symbol: {coin_info.get('symbol')}, Avg Score: {coin_info.get('average_score')}")
            except json.JSONDecodeError:
                logger.error("Could not parse top_coins JSON from DB.")
        else:
            logger.error("ERROR: Could not retrieve any report from summaries table for verification.")
    else:
        logger.warning("Report not saved as per generate_and_save_top_coins_report function logic.")
    
    logger.info("--- Aggregator & Report Test Finished ---")

    logger.info("--- Aggregator Script Test Run ---")
    
    # For standalone testing, ensure the database exists and has some data.
    # You might need to run main.py first to populate it.
    # initialize_database() # Call if you're sure it's needed for a standalone test setup
    
    print(f"Attempting to generate top {config.TOP_N_COINS_REPORT} coins report...")
    top_n_report = generate_top_n_coins_report(config.TOP_N_COINS_REPORT)
    
    if top_n_report:
        print("\n--- Top Coins Report ---")
        for coin_entry in top_n_report:
            print(json.dumps(coin_entry, indent=2))
        print(f"\nReport generated for {len(top_n_report)} coins.")
    else:
        print("\nNo data to generate report, or an error occurred. Check logs.")
        
    # Example: Generate report for a different N
    custom_top_n = 1
    print(f"\nAttempting to generate top {custom_top_n} coin report...")
    top_one_report = generate_top_n_coins_report(custom_top_n)
    if top_one_report:
        print("\n--- Top Coin Report (N=1) ---")
        for coin_entry in top_one_report:
            print(json.dumps(coin_entry, indent=2))
    else:
        print("\nNo data to generate report for N=1, or an error occurred.")

    logger.info("--- Aggregator Script Test Finished ---") 