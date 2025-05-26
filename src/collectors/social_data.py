import json
import requests
import os
import sys
import zipfile
import io
import pandas as pd
import time
import random # Added for jitter in backoff

# Adjust path to import config for API key
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.append(PROJECT_ROOT_PATH)

from src.utils import config

# CryptoPanic API Configuration
CRYPTO_PANIC_API_URL = "https://cryptopanic.com/api/v1"

# GDELT Configuration (Old file-based config commented out)
# GDELT_MASTER_FILE_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
# GDELT_GKG_FILE_TYPE_IDENTIFIER = ".gkg.csv.zip"
GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc" # New API endpoint

# Mock data source for social sentiment data
MOCK_SOCIAL_DATA = {
    "BTC": {"mentions": 15000, "sentiment_score": 0.75},
    "ETH": {"mentions": 12000, "sentiment_score": 0.68},
    "SOL": {"mentions": 5000, "sentiment_score": 0.82},
    "DOGE": {"mentions": 25000, "sentiment_score": 0.55} # Added a different coin for variety
}

def fetch_social_sentiment(coin_symbol: str) -> dict:
    """
    Fetches mock social sentiment data for a given coin symbol.

    Args:
        coin_symbol (str): The symbol of the coin (e.g., "BTC").

    Returns:
        dict: A dictionary containing the coin's symbol, mentions, and sentiment_score.
              Example: {"symbol": "BTC", "mentions": 15000, "sentiment_score": 0.75}
              Returns an error field if data is not found.
              Example: {"symbol": "XYZ", "mentions": None, "sentiment_score": None, "error": "Social data not found for symbol XYZ"}
    """
    coin_symbol_upper = coin_symbol.upper()
    if coin_symbol_upper in MOCK_SOCIAL_DATA:
        data = MOCK_SOCIAL_DATA[coin_symbol_upper]
        return {
            "symbol": coin_symbol_upper,
            "mentions": data["mentions"],
            "sentiment_score": data["sentiment_score"]
        }
    else:
        return {
            "symbol": coin_symbol_upper,
            "mentions": None,
            "sentiment_score": None,
            "error": f"Social data not found for symbol {coin_symbol_upper}"
        }

# --- CryptoPanic API Integration ---
def ping_cryptopanic() -> bool:
    """
    Pings the CryptoPanic API by fetching recent posts to check connectivity and API key validity.

    Returns:
        bool: True if the ping is successful, False otherwise.
    """
    if not config.CRYPTO_PANIC_API_KEY or config.CRYPTO_PANIC_API_KEY == "YOUR_CRYPTO_PANIC_API_KEY_HERE":
        print("CryptoPanic API key not configured or is placeholder. Skipping ping.")
        return False
    
    params = {
        "auth_token": config.CRYPTO_PANIC_API_KEY,
        "public": "true" # Fetch public posts
    }
    try:
        response = requests.get(f"{CRYPTO_PANIC_API_URL}/posts/", params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        time.sleep(2) # Changed delay to 2 seconds
        data = response.json()
        # A successful response should have a "count" or "results"
        if "count" in data or "results" in data:
            print(f"CryptoPanic API ping successful. Found {data.get('count', len(data.get('results', [])))} posts.")
            return True
        else:
            print(f"CryptoPanic API ping failed or key invalid. Response: {data}")
            return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"CryptoPanic API authentication failed (401). Check your API key. {e}")
        else:
            print(f"CryptoPanic API ping HTTP error: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error pinging CryptoPanic API: {e}")
        return False
    except json.JSONDecodeError:
        print(f"Error decoding CryptoPanic API response. Raw: {response.text if response else 'No response'}")
        return False

def fetch_cryptopanic_news_for_coin(coin_symbol: str) -> dict:
    """
    Fetches news posts for a specific coin symbol from CryptoPanic.

    Args:
        coin_symbol (str): The coin symbol (e.g., "BTC", "ETH").

    Returns:
        dict: A dictionary containing a list of news posts under the 'results' key,
              or an 'error' key if an issue occurs.
              Example: {"coin_symbol": "BTC", "results": [{...post_data...}, ...]}}
    """
    if not config.CRYPTO_PANIC_API_KEY or config.CRYPTO_PANIC_API_KEY == "YOUR_CRYPTO_PANIC_API_KEY_HERE":
        return {"coin_symbol": coin_symbol, "error": "CryptoPanic API key not configured."}
    if not coin_symbol:
        return {"coin_symbol": coin_symbol, "error": "Coin symbol not provided."}

    params = {
        "auth_token": config.CRYPTO_PANIC_API_KEY,
        "currencies": coin_symbol.upper(), # API expects uppercase symbol
        "public": "true" # Optional: to get only publicly available posts
    }
    try:
        response = requests.get(f"{CRYPTO_PANIC_API_URL}/posts/", params=params)
        response.raise_for_status()
        time.sleep(2) # Changed delay to 2 seconds
        data = response.json()
        
        # Check if 'results' key exists and is a list, which is expected for successful data fetch
        if "results" in data and isinstance(data["results"], list):
            return {"coin_symbol": coin_symbol, "results": data["results"]}
        elif data.get("count") == 0 and not data.get("results"):
             return {"coin_symbol": coin_symbol, "results": [], "info": f"No posts found for symbol {coin_symbol}"}
        else:
            # Capture any other response structure that isn't an outright error but lacks results
            return {"coin_symbol": coin_symbol, "error": f"Unexpected response structure or no results: {data}"}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {"coin_symbol": coin_symbol, "error": f"CryptoPanic API authentication failed (401). Key: {config.CRYPTO_PANIC_API_KEY[-4:]}"}
        else:
            return {"coin_symbol": coin_symbol, "error": f"CryptoPanic API HTTP error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"coin_symbol": coin_symbol, "error": f"RequestException: {e}"}
    except json.JSONDecodeError:
        return {"coin_symbol": coin_symbol, "error": f"JSONDecodeError. Raw: {response.text if response else 'No response'}"}
    except Exception as e:
        return {"coin_symbol": coin_symbol, "error": f"An unexpected error occurred: {e}"}

def filter_cryptopanic_posts(posts_data: dict, coin_symbol_to_filter: str) -> dict:
    """
    Filters a list of CryptoPanic posts for basic relevance and structure.

    Args:
        posts_data (dict): The raw dictionary returned by fetch_cryptopanic_news_for_coin 
                           (should contain a "results" list and "coin_symbol").
        coin_symbol_to_filter (str): The specific coin symbol (e.g., "BTC") we are targeting.
                                     This is used to double-check relevance.

    Returns:
        dict: A dictionary with {"coin_symbol": symbol, "filtered_results": [list_of_filtered_posts]},
              or an {"error": ...} if input is invalid.
    """
    if "error" in posts_data:
        return posts_data # Pass through previous errors
    
    raw_posts = posts_data.get("results")
    original_coin_symbol = posts_data.get("coin_symbol")

    if raw_posts is None or original_coin_symbol is None:
        return {"coin_symbol": coin_symbol_to_filter, "error": "Invalid input: 'results' or 'coin_symbol' missing from posts_data."}

    if original_coin_symbol.upper() != coin_symbol_to_filter.upper():
        # This case should ideally not happen if fetch_cryptopanic_news_for_coin was called correctly.
        return {"coin_symbol": coin_symbol_to_filter, "error": f"Mismatch: posts fetched for {original_coin_symbol}, but filtering for {coin_symbol_to_filter}."}

    filtered_posts = []
    for post in raw_posts:
        if not isinstance(post, dict):
            # print(f"Skipping non-dict item in posts: {post}") # Optional: for debugging
            continue

        title = post.get("title")
        if not title or not title.strip():
            # print(f"Skipping post with no title: {post.get('id')}") # Optional: for debugging
            continue

        # Additional check: ensure the post explicitly mentions the coin symbol in its currencies field
        # This is often redundant given the API filter but acts as a safeguard or for more precise filtering.
        currency_mentions = post.get("currencies")
        symbol_mentioned = False
        if isinstance(currency_mentions, list):
            for currency_obj in currency_mentions:
                if isinstance(currency_obj, dict) and currency_obj.get("code") == coin_symbol_to_filter.upper():
                    symbol_mentioned = True
                    break
        
        if not symbol_mentioned:
            # print(f"Skipping post not explicitly mentioning currency {coin_symbol_to_filter} in its 'currencies' field: {title}") # Optional
            continue
        
        # Potential future filters: keyword checks in title, minimum vote counts, source reputation, recency, etc.
        
        filtered_posts.append(post)
    
    return {"coin_symbol": coin_symbol_to_filter, "filtered_results": filtered_posts}

def calculate_aggregate_sentiment_from_posts(filtered_posts_data: dict) -> dict:
    """
    Calculates an aggregated sentiment score from a list of filtered CryptoPanic posts.

    Args:
        filtered_posts_data (dict): The dictionary returned by filter_cryptopanic_posts,
                                    containing "coin_symbol" and "filtered_results".

    Returns:
        dict: {"coin_symbol": symbol, 
               "aggregated_sentiment_score": float_score, 
               "articles_processed_for_sentiment": count,
               "articles_with_votes": count}
              or an {"error": ...} if input is invalid or errors occur.
    """
    if "error" in filtered_posts_data:
        return filtered_posts_data # Pass through previous errors

    coin_symbol = filtered_posts_data.get("coin_symbol")
    posts = filtered_posts_data.get("filtered_results")

    if coin_symbol is None or posts is None:
        return {"coin_symbol": coin_symbol, "error": "Invalid input: 'coin_symbol' or 'filtered_results' missing."}

    if not isinstance(posts, list):
        return {"coin_symbol": coin_symbol, "error": "Invalid input: 'filtered_results' is not a list."}

    individual_sentiments = []
    articles_with_votes = 0

    for post in posts:
        if not isinstance(post, dict) or not isinstance(post.get("votes"), dict):
            continue # Skip malformed posts or posts without a votes dictionary

        votes = post["votes"]
        positive_votes = votes.get("positive", 0)
        negative_votes = votes.get("negative", 0)

        if positive_votes > 0 or negative_votes > 0:
            articles_with_votes += 1
            # Score: (P - N) / (P + N + 1) to keep score in [-1, 1] and avoid div by zero if P+N=0 (though caught by condition)
            # The +1 also dampens scores for very low vote counts.
            sentiment_score = (positive_votes - negative_votes) / (positive_votes + negative_votes + 1.0) # Use 1.0 for float division
            individual_sentiments.append(sentiment_score)
    
    aggregated_score = 0.0
    if individual_sentiments: # Check if any sentiments were calculated
        aggregated_score = sum(individual_sentiments) / len(individual_sentiments)
    
    return {
        "coin_symbol": coin_symbol,
        "aggregated_sentiment_score": round(aggregated_score, 4), # Rounded for cleanliness
        "articles_processed_for_sentiment": len(posts),
        "articles_with_votes": articles_with_votes
    }

# --- GDELT v2.0 Integration (File-based functions commented out or to be removed) ---
"""
# def fetch_gdelt_master_file_list() -> str | None:
#     (...)
# def get_latest_gdelt_gkg_url(master_file_content: str) -> str | None:
#     (...)
# def download_and_extract_gdelt_gkg_file(gkg_url: str, download_dir: str, max_lines_to_preview=5) -> pd.DataFrame | None:
#     (...)
# def fetch_latest_gdelt_data(num_lines_preview=5) -> pd.DataFrame | None:
#     (...)
"""

def fetch_gdelt_doc_api_news_sentiment(query: str, timespan: str = "24h", max_records: int = 25) -> dict:
    """
    Fetches news articles and their sentiment (tone) for a given query using GDELT DOC 2.0 API.
    Implements exponential backoff with jitter for rate limiting.

    Args:
        query (str): The search query (e.g., "Bitcoin" OR "BTC").
        timespan (str): The time period to search (e.g., "24h", "3d", "1week", up to "3months").
                        Uses config.GDELT_DOC_API_TIMESPAN by default if not overridden.
        max_records (int): Maximum number of articles to retrieve (default 25, max 250).

    Returns:
        dict: {"query": query, 
               "gdelt_average_tone": float_score, 
               "gdelt_article_count": count,
               "articles": [list_of_article_details_with_tone]}
              or an {"error": ...} if an issue occurs.
    """
    api_timespan = timespan if timespan else config.GDELT_DOC_API_TIMESPAN
    params = {
        "query": query,
        "mode": "artlist", # Request article list
        "format": "json",   # Request JSON output
        "timespan": api_timespan,
        "maxrecords": max_records,
        "sort": "datedesc" # Get most recent first
    }
    
    print(f"Querying GDELT DOC API: query='{query}', timespan='{api_timespan}', maxrecords={max_records}")
    
    max_retries = 5
    base_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(GDELT_DOC_API_URL, params=params, timeout=15) # Increased timeout
            response.raise_for_status()
            # Removed time.sleep(2) here as backoff handles delays
            data = response.json()
            
            articles_data = data.get("articles", [])
            processed_articles = []
            tone_scores = []

            for article in articles_data:
                if not isinstance(article, dict):
                    continue
                
                raw_tone_str = article.get("tone", "")
                article_tone = None
                if raw_tone_str:
                    try:
                        # Tone format: "avg_tone,pos_score,neg_score,polarity,activity_ref_density,self_group_ref_density"
                        article_tone = float(raw_tone_str.split(',')[0])
                        tone_scores.append(article_tone)
                    except (ValueError, IndexError):
                        print(f"Could not parse tone from: {raw_tone_str} for article: {article.get('url')}")
                
                processed_articles.append({
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "domain": article.get("domain"),
                    "seendate": article.get("seendate"),
                    "tone_raw": raw_tone_str,
                    "tone_extracted": article_tone
                })
            
            average_tone = sum(tone_scores) / len(tone_scores) if tone_scores else 0.0
            
            return {
                "query": query,
                "gdelt_average_tone": round(average_tone, 4),
                "gdelt_article_count": len(processed_articles), # Number of articles actually processed
                "articles": processed_articles # List of processed articles with details
            }

        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1) # Exponential backoff with jitter
                    print(f"Rate limited by GDELT. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"Max retries reached for GDELT API after rate limiting.")
                    return {"query": query, "error": f"GDELT DOC API RequestException: {e} (Max retries reached)"}
            else:
                # For other request exceptions, return error immediately
                return {"query": query, "error": f"GDELT DOC API RequestException: {e}"}
        except json.JSONDecodeError:
            return {"query": query, "error": f"GDELT DOC API JSONDecodeError. Raw: {response.text if 'response' in locals() and response else 'No response'}"}
        except Exception as e:
            # Catch any other unexpected errors during the API call or processing
            return {"query": query, "error": f"An unexpected error occurred with GDELT DOC API on attempt {attempt + 1}: {e}"}

    # This part should ideally not be reached if loop completes due to max_retries without returning
    return {"query": query, "error": "GDELT DOC API request failed after multiple retries due to persistent issues (e.g., rate limiting)."}

if __name__ == "__main__":
    print("--- Testing fetch_social_sentiment ---")

    # Test with a known coin symbol
    btc_social = fetch_social_sentiment("BTC")
    print(f"\nSocial sentiment for BTC: {json.dumps(btc_social, indent=4)}")

    eth_social_lower = fetch_social_sentiment("eth")
    print(f"\nSocial sentiment for eth (lowercase): {json.dumps(eth_social_lower, indent=4)}")

    # Test with another known coin
    doge_social = fetch_social_sentiment("DOGE")
    print(f"\nSocial sentiment for DOGE: {json.dumps(doge_social, indent=4)}")

    # Test with an unknown coin symbol
    xyz_social = fetch_social_sentiment("XYZ")
    print(f"\nSocial sentiment for XYZ: {json.dumps(xyz_social, indent=4)}")

    print("\n--- Testing CryptoPanic API Ping ---")
    if ping_cryptopanic():
        print("CryptoPanic API ping test successful!")
    else:
        print("CryptoPanic API ping test failed. Check API key and configuration.")

    print("\n--- Testing fetch_cryptopanic_news_for_coin ---")
    btc_news = fetch_cryptopanic_news_for_coin("BTC")
    if "results" in btc_news:
        print(f"\nFound {len(btc_news['results'])} news posts for BTC.")
        if btc_news['results']:
            print(f"  First BTC news post title: {btc_news['results'][0].get('title')}")
    else:
        print(f"\nError fetching news for BTC: {btc_news.get('error')}")

    # Test with a symbol that might have no news or is less common
    ltc_news = fetch_cryptopanic_news_for_coin("LTC") # Litecoin
    if "results" in ltc_news:
        print(f"\nFound {len(ltc_news['results'])} news posts for LTC.")
        if ltc_news['results']:
            print(f"  First LTC news post title: {ltc_news['results'][0].get('title')}")
        elif ltc_news.get("info"):
             print(f"  Info for LTC: {ltc_news.get('info')}")
    else:
        print(f"\nError fetching news for LTC: {ltc_news.get('error')}")

    # Test with an invalid symbol
    invalid_symbol_news = fetch_cryptopanic_news_for_coin("INVALIDCOINSYMBOL")
    if "results" in invalid_symbol_news:
        print(f"\nFound {len(invalid_symbol_news['results'])} news posts for INVALIDCOINSYMBOL (expected 0 or error).")
    else:
        print(f"\nError/Info for INVALIDCOINSYMBOL: {invalid_symbol_news.get('error') or invalid_symbol_news.get('info')}")

    print("\n--- Testing filter_cryptopanic_posts ---")
    # Use the BTC news fetched earlier for testing the filter
    if "results" in btc_news: # ensure btc_news was fetched successfully
        filtered_btc_news_data = filter_cryptopanic_posts(btc_news, "BTC")
        if "filtered_results" in filtered_btc_news_data:
            print(f"\nBTC news: Original count = {len(btc_news['results'])}, Filtered count = {len(filtered_btc_news_data['filtered_results'])}.")
            if filtered_btc_news_data['filtered_results']:
                print(f"  First filtered BTC news post title: {filtered_btc_news_data['filtered_results'][0].get('title')}")
        else:
            print(f"\nError filtering BTC news: {filtered_btc_news_data.get('error')}")
    else:
        print("\nSkipping filter test for BTC news as initial fetch might have failed or returned no results.")

    # Test filter with potentially empty or error input from fetch
    if "results" in invalid_symbol_news: # This would usually have 0 results
        filtered_invalid_news = filter_cryptopanic_posts(invalid_symbol_news, "INVALIDCOINSYMBOL")
        if "filtered_results" in filtered_invalid_news:
            print(f"\nINVALIDCOINSYMBOL news: Original count = {len(invalid_symbol_news['results'])}, Filtered count = {len(filtered_invalid_news['filtered_results'])} (expected 0).")
        else:
             print(f"\nError filtering INVALIDCOINSYMBOL news: {filtered_invalid_news.get('error')}")
    elif invalid_symbol_news.get("error"):
        # If fetch already returned an error, filter should pass it through or handle it
        filtered_error_news = filter_cryptopanic_posts(invalid_symbol_news, "INVALIDCOINSYMBOL")
        print(f"\nFiltering news known to have fetch error: Result = {json.dumps(filtered_error_news, indent=2)}")

    # Test with a deliberate mismatch for error handling
    mismatched_input = {"coin_symbol": "ETH", "results": btc_news.get("results", [])} # Pretend ETH posts are BTC posts
    filtered_mismatch = filter_cryptopanic_posts(mismatched_input, "BTC")
    print(f"\nFiltering with mismatched symbols (ETH posts, filter for BTC): Error = {filtered_mismatch.get('error')}")

    print("\n--- Testing calculate_aggregate_sentiment_from_posts ---")
    # Use filtered BTC news if available and successful
    if "results" in btc_news and "filtered_results" in filtered_btc_news_data and not filtered_btc_news_data.get("error"):
        btc_sentiment_aggregation = calculate_aggregate_sentiment_from_posts(filtered_btc_news_data)
        print(f"\nBTC Aggregated Sentiment: {json.dumps(btc_sentiment_aggregation, indent=4)}")
    else:
        print("\nSkipping BTC sentiment aggregation test due to previous step failures or no data.")

    # Test with manually crafted data for various scenarios
    test_posts_1 = {
        "coin_symbol": "TESTCOIN1",
        "filtered_results": [
            {"votes": {"positive": 10, "negative": 2}}, # Score: (10-2)/(10+2+1) = 8/13 = 0.615
            {"votes": {"positive": 5, "negative": 5}},  # Score: (5-5)/(5+5+1) = 0/11 = 0
            {"votes": {"positive": 1, "negative": 8}}   # Score: (1-8)/(1+8+1) = -7/10 = -0.7
        ]
    }
    # Expected: (0.615 + 0 - 0.7) / 3 = -0.085 / 3 = -0.0283
    sentiment_test_1 = calculate_aggregate_sentiment_from_posts(test_posts_1)
    print(f"\nTest Case 1 Sentiment: {json.dumps(sentiment_test_1, indent=4)}")

    test_posts_no_votes = {
        "coin_symbol": "TESTCOIN2",
        "filtered_results": [
            {"votes": {"positive": 0, "negative": 0, "important": 5}},
            {"votes": {}} # No positive/negative votes
        ]
    }
    # Expected: Score 0.0, articles_with_votes: 0
    sentiment_test_no_votes = calculate_aggregate_sentiment_from_posts(test_posts_no_votes)
    print(f"\nTest Case No Votes Sentiment: {json.dumps(sentiment_test_no_votes, indent=4)}")

    test_posts_empty = {
        "coin_symbol": "TESTCOIN3",
        "filtered_results": []
    }
    # Expected: Score 0.0, articles_with_votes: 0, articles_processed: 0
    sentiment_test_empty = calculate_aggregate_sentiment_from_posts(test_posts_empty)
    print(f"\nTest Case Empty Posts Sentiment: {json.dumps(sentiment_test_empty, indent=4)}")

    test_posts_error_input = {"coin_symbol": "TESTCOIN4", "error": "Previous error"}
    sentiment_test_error = calculate_aggregate_sentiment_from_posts(test_posts_error_input)
    print(f"\nTest Case Error Input Sentiment: {json.dumps(sentiment_test_error, indent=4)}")

    print("\n--- Testing GDELT DOC 2.0 API Integration ---")
    
    # Test for Bitcoin
    btc_gdelt_query = '"Bitcoin" OR "BTC"'
    btc_gdelt_data = fetch_gdelt_doc_api_news_sentiment(query=btc_gdelt_query, timespan="24h", max_records=10)
    print(f"\nGDELT DOC API data for '{btc_gdelt_query}':")
    print(json.dumps(btc_gdelt_data, indent=4))
    if not btc_gdelt_data.get("error") and btc_gdelt_data.get("articles"):
        print(f"  Sample article title: {btc_gdelt_data['articles'][0].get('title')}")
        print(f"  Sample article tone: {btc_gdelt_data['articles'][0].get('tone_extracted')}")

    # Test for a different query / coin, e.g. Ethereum
    eth_gdelt_query = '"Ethereum" OR "ETH"'
    eth_gdelt_data = fetch_gdelt_doc_api_news_sentiment(query=eth_gdelt_query, timespan="48h", max_records=5)
    print(f"\nGDELT DOC API data for '{eth_gdelt_query}':")
    print(json.dumps(eth_gdelt_data, indent=4))

    # Test for a query that might yield few or no results
    rare_gdelt_query = '"MyNonExistentAltcoinXYZ123"'
    rare_gdelt_data = fetch_gdelt_doc_api_news_sentiment(query=rare_gdelt_query, timespan="7d", max_records=5)
    print(f"\nGDELT DOC API data for '{rare_gdelt_query}':")
    print(json.dumps(rare_gdelt_data, indent=4))

    print("\n--- Test Finished ---") 