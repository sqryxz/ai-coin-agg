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

def get_daily_summary_for_coin(coin_id: int, day_date: datetime.date) -> dict:
    """
    Aggregates scores for a single coin for the given day_date.
    Fetches the latest score of the day and its sub-scores.

    Args:
        coin_id (int): The ID of the coin.
        day_date (datetime.date): The date for aggregation.

    Returns:
        dict: A summary including the latest score, sub-scores, and number of scores considered.
    """
    day_date_str = day_date.isoformat()
    
    query = """
    SELECT score, sub_scores_json, timestamp
    FROM scores 
    WHERE coin_id = ? 
      AND date(timestamp) = ?
    ORDER BY timestamp DESC
    LIMIT 1; 
    """
    params = (coin_id, day_date_str)
    
    logger.debug(f"Fetching latest score for coin_id {coin_id} for date {day_date_str}")
    score_entry = execute_read_query(query, params=params, fetch_one=True) # Fetch one row
    
    latest_score = None
    sub_scores = None
    num_scores_on_day = 0 # To keep track if any score was found for the day.

    if score_entry:
        latest_score = score_entry[0]
        sub_scores_json = score_entry[1]
        # score_timestamp = score_entry[2] # Available if needed
        num_scores_on_day = 1 # Since we fetched LIMIT 1
        
        if sub_scores_json:
            try:
                sub_scores = json.loads(sub_scores_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse sub_scores_json for coin_id {coin_id} on {day_date_str}")
                sub_scores = {} # Default to empty dict on error
        else:
            sub_scores = {} # Default to empty dict if no sub_scores_json
        
    logger.info(f"Summary for Coin ID {coin_id} on {day_date_str}: Score={latest_score}, HasSubScores={bool(sub_scores)}")

    return {
        "coin_id": coin_id,
        "date": day_date_str,
        "average_score": latest_score, # Renaming this for consistency, but it's the latest score of the day
        "sub_scores": sub_scores if sub_scores else {}, # Ensure it's a dict
        "number_of_scores_considered": num_scores_on_day, # Reflects we are looking at one score
        "aggregation_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

def send_to_discord(webhook_url: str, report_title: str, all_coins_data: list):
    """
    Sends a formatted message with all coins and their subscores in a table to a Discord webhook.

    Args:
        webhook_url (str): The Discord webhook URL.
        report_title (str): The title for the Discord message.
        all_coins_data (list): A list of dictionaries, e.g.,
                                 [{"symbol": "BTC", "average_score": 75.5, "sub_scores": {...}}, ...]
    """
    if not webhook_url:
        logger.info("Discord webhook URL not configured. Skipping notification.")
        return

    if not all_coins_data:
        message_content = f"**{report_title}**\\n\\nNo scorable data available for this period."
        try:
            response = requests.post(webhook_url, json={"content": message_content})
            response.raise_for_status()
            logger.info(f"Successfully sent empty report to Discord: {report_title}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending empty report to Discord: {e}")
        return

    # Define the subscore keys we want to display and their headers
    # This needs to match the keys in `contributing_metrics` from the scorer.
    # We'll take the 'contribution' part of each sub_score.
    subscore_display_keys = {
        "volume": "Volume",
        "market_cap": "MCap",
        "active_addresses": "ActiveAddr",
        "etherscan_transaction_count_proxy": "EthTx",
        "sentiment_score": "Sentiment",
        "gdelt_sentiment_score": "GDELTsent",
    }
    
    # Build the table header
    headers = ["Coin", "Score"] + [header for header in subscore_display_keys.values()]
    table_header = "| " + " | ".join(headers) + " |"
    table_separator = "|-" + "-|-".join(["-" * len(h) for h in headers]) + "-|" # Dynamic separator based on header length

    table_rows = [table_header, table_separator]

    for coin in all_coins_data:
        symbol = coin.get('symbol', 'N/A')
        score = f"{coin.get('average_score', 0):.2f}" if coin.get('average_score') is not None else "N/A"
        
        row_values = [symbol, score]
        
        sub_scores = coin.get("sub_scores", {})
        if not isinstance(sub_scores, dict): # Ensure sub_scores is a dict
            sub_scores = {}

        for key in subscore_display_keys.keys():
            metric_detail = sub_scores.get(key, {})
            contribution = metric_detail.get("contribution", 0.0) if isinstance(metric_detail, dict) else 0.0
            row_values.append(f"{contribution:.2f}")
            
        table_rows.append("| " + " | ".join(row_values) + " |")

    # Join all parts into a single message string
    # Using code block for monospace font which helps with table alignment
    table_string = "\n".join(table_rows)
    
    # Discord message limits
    # Max 2000 chars for regular message content. Embeds have other limits.
    # If table_string becomes too long, it needs to be split or sent differently.
    
    description_content = f"```markdown\n{table_string}\n```"
    
    embed = {
        "title": f":bar_chart: {report_title}",
        "description": description_content,
        "color": 0x00ff00,  # Green color
        "footer": {
            "text": f"Report generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
    }
    
    # Check total length; Discord descriptions have a limit (e.g., 4096 for embeds)
    # A single message content limit is 2000. We are using embed description.
    if len(description_content) > 4096:
        logger.warning("Generated Discord table is too long for a single embed description. Truncating or consider splitting.")
        # Basic truncation, could be smarter
        embed["description"] = description_content[:4090] + "\n... (truncated)"
        # Fallback to sending a simpler message if the table is massive, or split. For now, just truncate.

    message_payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=message_payload)
        response.raise_for_status()
        logger.info(f"Successfully sent report to Discord: {report_title}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending report to Discord: {e}. Payload: {json.dumps(message_payload)[:200]}")

def generate_and_save_top_coins_report(day_date: datetime.date, top_n_for_db_summary: int = config.TOP_N_COINS_REPORT) -> bool:
    """
    Generates a report of ALL coins with their average daily scores and sub-scores.
    Saves a summary of TOP N coins to the summaries table.
    Sends a Discord notification with data for ALL coins.

    Args:
        day_date (datetime.date): The date for the report.
        top_n_for_db_summary (int): The number of top coins to include in the database summary.

    Returns:
        bool: True if the report was successfully generated and Discord send attempted, False otherwise.
    """
    logger.info(f"Generating Full Coin Report for Discord and Top {top_n_for_db_summary} DB Summary for day {day_date.isoformat()}")
    all_symbols = get_all_coin_symbols()
    
    if not all_symbols:
        logger.warning("No coin symbols found in the database. Cannot generate report.")
        return False

    coin_data_for_discord = []
    all_coin_summaries_for_db = [] # For sorting and picking top N for DB

    for symbol in all_symbols:
        coin_id = get_coin_id_by_symbol(symbol)
        if coin_id:
            summary = get_daily_summary_for_coin(coin_id, day_date)
            summary['symbol'] = symbol # Ensure symbol is in the summary
            if summary.get("average_score") is not None: # average_score is now latest_score
                coin_data_for_discord.append({
                    "symbol": summary["symbol"],
                    "average_score": round(summary["average_score"], 2), # Store rounded for Discord
                    "sub_scores": summary.get("sub_scores", {})
                })
                all_coin_summaries_for_db.append({ # For DB, keep more precision if needed, and no sub_scores
                    "symbol": summary["symbol"],
                    "average_score": summary["average_score"] 
                })
        else:
            logger.warning(f"Could not find ID for symbol {symbol} while generating report.")

    if not coin_data_for_discord: # If no coins had any scorable data
        logger.info("No coins had scorable data for the period. No report generated or sent.")
        # Optionally, send a "No data" message to Discord
        if config.DISCORD_WEBHOOK_URL:
            report_title = f"Daily Coin Report: For {day_date.isoformat()}"
            send_to_discord(config.DISCORD_WEBHOOK_URL, report_title, []) # Send empty list
        return False # Indicate no data processed for DB saving either

    # Sort all coins by average_score for consistent Discord output order (highest first)
    # And for picking top N for DB
    sorted_coin_data = sorted(
        coin_data_for_discord,
        key=lambda x: x["average_score"],
        reverse=True
    )
    
    sorted_db_summaries = sorted(
        all_coin_summaries_for_db,
        key=lambda x: x["average_score"],
        reverse=True
    )

    # Prepare top N for database summary
    top_n_list_for_db = []
    for summary in sorted_db_summaries[:top_n_for_db_summary]: # Use the provided top_n argument
        top_n_list_for_db.append({
            "symbol": summary["symbol"],
            "average_score": round(summary["average_score"], 4) # Keep precision for DB
        })
    
    if top_n_list_for_db: # Only save to DB if there's something to save
        day_date_str = day_date.isoformat()
        top_coins_json_for_db = json.dumps(top_n_list_for_db)
        insert_report_query = """
        INSERT INTO summaries (report_date, top_coins) 
        VALUES (?, ?);
        """
        params = (day_date_str, top_coins_json_for_db)
        logger.info(f"Saving Top {top_n_for_db_summary} report to database: Date={day_date_str}, Report={top_coins_json_for_db}")
        if execute_write_query(insert_report_query, params):
            logger.info(f"Daily Top {top_n_for_db_summary} coins summary saved successfully.")
        else:
            logger.error(f"Failed to save daily Top {top_n_for_db_summary} coins summary.")
            # Continue to send Discord report even if DB save fails for summary
    else:
        logger.info("No coins made it to the top list for DB summary (e.g., all had null scores or list was empty). DB Summary not saved.")
        

    # Send ALL coins data to Discord
    if config.DISCORD_WEBHOOK_URL:
        discord_report_title = f"Daily Coin Scores Report: {day_date.isoformat()}"
        # Send the 'sorted_coin_data' which contains all coins with their scores and sub_scores
        send_to_discord(config.DISCORD_WEBHOOK_URL, discord_report_title, sorted_coin_data)
    
    return True # Report generation process attempted for Discord

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
        c.id AS coin_id,
        c.symbol,
        c.name,
        s.score,
        s.timestamp AS score_timestamp,
        (SELECT m.price FROM metrics m WHERE m.coin_id = c.id ORDER BY m.timestamp DESC LIMIT 1) AS latest_price,
        (SELECT m.market_cap FROM metrics m WHERE m.coin_id = c.id ORDER BY m.timestamp DESC LIMIT 1) AS latest_market_cap,
        (SELECT m.timestamp FROM metrics m WHERE m.coin_id = c.id ORDER BY m.timestamp DESC LIMIT 1) AS latest_metrics_timestamp
    FROM coins c
    JOIN (
        SELECT 
            coin_id, 
            score, 
            timestamp,
            ROW_NUMBER() OVER(PARTITION BY coin_id ORDER BY timestamp DESC) as rn
        FROM scores
    ) s ON c.id = s.coin_id AND s.rn = 1
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
    logger.info("--- Testing Daily Aggregator & Report Generation ---") # Changed

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
    # Define a sample sub_scores structure, focusing on the 'contribution' part
    # as that's what send_to_discord currently uses.
    sample_sub_scores_structure = {
        "volume": {"contribution": 1.5, "original_value": 1000000, "transformed_value": 13.8, "weight": 0.20},
        "market_cap": {"contribution": 2.0, "original_value": 50000000, "transformed_value": 17.7, "weight": 0.20},
        "active_addresses": {"contribution": 1.0, "original_value": 5000, "transformed_value": 8.5, "weight": 0.20},
        "etherscan_transaction_count_proxy": {"contribution": 0.5, "original_value": 100, "transformed_value": 4.6, "weight": 0.10},
        "sentiment_score": {"contribution": 1.2, "original_value": 0.5, "transformed_value": 0.75, "base_weight": 0.20, "mention_multiplier_applied": 1.0, "effective_weight": 0.20},
        "gdelt_sentiment_score": {"contribution": 0.3, "original_value": 1.0, "transformed_value": 0.55, "base_weight": 0.10, "mention_multiplier_applied": 1.0, "effective_weight": 0.10},
        "mention_analysis": {"cp_mentions": 100, "gdelt_article_count": 10, "total_mentions": 110, "mention_multiplier_for_sentiment": 0.8},
        "volume_momentum": {"status": "Placeholder", "current_contribution": 0.0, "weight_to_be_assigned": 0.0}
    }
    sample_sub_scores_json = json.dumps(sample_sub_scores_structure)
    
    # Slightly different sub_scores for another coin for variety
    sample_sub_scores_alt_structure = {
        "volume": {"contribution": 1.8}, "market_cap": {"contribution": 2.5}, "active_addresses": {"contribution": 1.2},
        "etherscan_transaction_count_proxy": {"contribution": 0.0}, # e.g. non-ERC20
        "sentiment_score": {"contribution": 1.0}, "gdelt_sentiment_score": {"contribution": 0.5},
        "mention_analysis": {"total_mentions": 50, "mention_multiplier_for_sentiment": 0.8},
        "volume_momentum": {"current_contribution": 0.0}
    }
    sample_sub_scores_alt_json = json.dumps(sample_sub_scores_alt_structure)

    mock_scores_map = {}
    if btc_id: mock_scores_map[btc_id] = {"scores": [0.8, 0.85, 0.75, None, 0.82, 0.9, 0.88], "sub_scores_json": sample_sub_scores_alt_json}
    if eth_id: mock_scores_map[eth_id] = {"scores": [0.7, 0.65, 0.72, 0.68, 0.71, 0.7, 0.66], "sub_scores_json": sample_sub_scores_json}
    if sol_id: mock_scores_map[sol_id] = {"scores": [0.9, 0.92, 0.95, 0.91, 0.88, 0.93, 0.94], "sub_scores_json": sample_sub_scores_json}
    if ada_id: mock_scores_map[ada_id] = {"scores": [0.5, None, 0.55, 0.48, None, 0.52, 0.45], "sub_scores_json": sample_sub_scores_alt_json}

    insert_query = "INSERT INTO scores (coin_id, timestamp, score, sub_scores_json) VALUES (?, ?, ?, ?);"
    total_mock_scores_inserted = 0
    for coin_id_key, data in mock_scores_map.items():
        scores_list = data["scores"]
        sub_scores_to_insert = data["sub_scores_json"]
        for i, score_value in enumerate(scores_list): # Mock scores still for multiple days
            score_timestamp_obj = datetime.now(timezone.utc) - timedelta(days=i)
            # For the purpose of testing daily summary, we want one score for 'today'
            # Let's ensure the first score (index 0) corresponds to 'today' for simplicity in test logic
            if i == 0:
                 current_day_timestamp = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()
                 params = (coin_id_key, current_day_timestamp, score_value, sub_scores_to_insert if score_value is not None else None)
            else:
                # Other scores can be for previous days
                older_timestamp_iso = (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
                params = (coin_id_key, older_timestamp_iso, score_value, sub_scores_to_insert if score_value is not None and i % 2 == 0 else None) # Add subscores to some older ones too

            if execute_write_query(insert_query, params=params):
                total_mock_scores_inserted += 1
    logger.info(f"Inserted {total_mock_scores_inserted} total mock scores for available coins, some with sub_scores.")

    # Step 3 (from previous task, run for context if needed, but report generator will call it)
    # btc_summary = get_daily_summary_for_coin(coin_id=btc_id, day_date=today) # Changed
    # print(json.dumps(btc_summary, indent=4))

    logger.info("Step 4: Generating and saving the top coins report for today...") # Changed
    report_saved = generate_and_save_top_coins_report(day_date=today) # Changed
    if report_saved:
        logger.info("Attempted to save report. Verifying...")
        # Assuming summaries table now has 'report_date' instead of 'week_start', 'week_end'
        verify_query = "SELECT report_date, top_coins FROM summaries ORDER BY id DESC LIMIT 1;" 
        saved_report_data = execute_read_query(verify_query, fetch_one=True)
        if saved_report_data:
            logger.info("--- Latest Saved Report from DB ---")
            logger.info(f"Date: {saved_report_data[0]}") # Changed
            logger.info(f"Top Coins JSON: {saved_report_data[1]}")
            try:
                top_coins_parsed = json.loads(saved_report_data[1]) # Index changed
                logger.info("Top Coins Parsed:")
                for i, coin_info in enumerate(top_coins_parsed):
                    logger.info(f"  {i+1}. Symbol: {coin_info.get('symbol')}, Avg Score: {coin_info.get('average_score')}")
            except json.JSONDecodeError:
                logger.error("Could not parse top_coins JSON from DB.")
        else:
            logger.error("ERROR: Could not retrieve any report from summaries table for verification.")
    else:
        logger.warning("Report not saved as per generate_and_save_top_coins_report function logic.")
    
    logger.info("--- Daily Aggregator & Report Test Finished ---") # Changed

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