from datetime import datetime, timezone
import json

REQUIRED_METRICS_FOR_SCORING = [
    "price", 
    "volume", 
    "active_addresses", 
    "mentions", 
    "sentiment_score"
]

def calculate_coin_score(cleaned_data: dict) -> dict:
    """
    Calculates a score for a single coin based on its cleaned data.

    Args:
        cleaned_data (dict): The cleaned data dictionary from data_cleaner.py.

    Returns:
        dict: A dictionary containing the symbol, score, and scoring details.
    """
    symbol = cleaned_data.get("symbol", "UNKNOWN")
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Check for eligibility
    is_eligible = True
    for metric in REQUIRED_METRICS_FOR_SCORING:
        if cleaned_data.get(metric) is None:
            is_eligible = False
            break

    if not is_eligible:
        return {
            "symbol": symbol,
            "score": 0.0,
            "base_sentiment_on_scoring": None,
            "bonuses_applied": ["ineligible_missing_required_metrics"],
            "score_calculation_timestamp_utc": timestamp
        }

    # Eligible for scoring
    current_score = 0.0
    bonuses_applied = []
    
    base_sentiment = cleaned_data.get("sentiment_score", 0.0) # Should be present due to eligibility check
    current_score = base_sentiment 

    # Mentions bonus
    mentions = cleaned_data.get("mentions")
    if mentions is not None:
        if mentions > 50000:
            current_score += 0.10
            bonuses_applied.append("mentions_high (>{})".format(50000))
        elif mentions > 10000:
            current_score += 0.05
            bonuses_applied.append("mentions_medium (>{})".format(10000))

    # Active Addresses bonus
    active_addresses = cleaned_data.get("active_addresses")
    if active_addresses is not None:
        if active_addresses > 200000:
            current_score += 0.10
            bonuses_applied.append("active_addresses_high (>{})".format(200000))
        elif active_addresses > 50000:
            current_score += 0.05
            bonuses_applied.append("active_addresses_medium (>{})".format(50000))
            
    # Transaction Volume bonus
    transaction_volume_usd = cleaned_data.get("transaction_volume_usd")
    if transaction_volume_usd is not None:
        if transaction_volume_usd > 500000000:
            current_score += 0.10
            bonuses_applied.append("tx_volume_high (>{})".format(500000000))
        elif transaction_volume_usd > 100000000:
            current_score += 0.05
            bonuses_applied.append("tx_volume_medium (>{})".format(100000000))

    # Clamp the score between 0.0 and 1.0
    final_score = max(0.0, min(current_score, 1.0))
    
    return {
        "symbol": symbol,
        "score": final_score,
        "base_sentiment_on_scoring": base_sentiment,
        "bonuses_applied": bonuses_applied if bonuses_applied else ["none"],
        "score_calculation_timestamp_utc": timestamp
    }

if __name__ == "__main__":
    print("--- Testing calculate_coin_score ---")

    test_cases = [
        {
            "name": "Eligible - High Score Potential",
            "data": {
                "symbol": "BTC", "price": 60000, "volume": 5e10, 
                "active_addresses": 250000, "mentions": 60000, 
                "sentiment_score": 0.8, "transaction_volume_usd": 6e8,
                "cleaned_at_utc": "sometime"
            },
            "expected_base_sentiment": 0.8,
            "expected_bonuses_toContain": ["mentions_high", "active_addresses_high", "tx_volume_high"]
            # Expected score: 0.8 (sentiment) + 0.1 (mentions) + 0.1 (active_addr) + 0.1 (tx_vol) = 1.1, clamped to 1.0
        },
        {
            "name": "Eligible - Mid Score Potential",
            "data": {
                "symbol": "ETH", "price": 4000, "volume": 2e10, 
                "active_addresses": 60000, "mentions": 15000, 
                "sentiment_score": 0.6, "transaction_volume_usd": 1.5e8,
                "cleaned_at_utc": "sometime"
            },
            "expected_base_sentiment": 0.6,
            "expected_bonuses_toContain": ["mentions_medium", "active_addresses_medium", "tx_volume_medium"]
            # Expected score: 0.6 + 0.05 + 0.05 + 0.05 = 0.75
        },
        {
            "name": "Eligible - Only Sentiment (low other metrics)",
            "data": {
                "symbol": "ADA", "price": 1, "volume": 1e9, 
                "active_addresses": 10000, "mentions": 1000, 
                "sentiment_score": 0.5, "transaction_volume_usd": 1e7,
                "cleaned_at_utc": "sometime"
            },
            "expected_base_sentiment": 0.5,
            "expected_bonuses_toContain": ["none"]
            # Expected score: 0.5 (no bonuses meet thresholds)
        },
        {
            "name": "Ineligible - Missing Price",
            "data": {
                "symbol": "XYZ", "price": None, "volume": 5e7, 
                "active_addresses": 500, "mentions": 50, 
                "sentiment_score": 0.9, "transaction_volume_usd": 1e6,
                "cleaned_at_utc": "sometime"
            },
            "expected_score": 0.0,
            "expected_bonuses_toContain": ["ineligible_missing_required_metrics"]
        },
        {
            "name": "Eligible - Score would be negative from sentiment (test clamping min)",
            "data": {
                "symbol": "NEG", "price": 10, "volume": 1e8,
                "active_addresses": 1000, "mentions": 100,
                "sentiment_score": -0.5, # Hypothetical if sentiment could be negative
                "transaction_volume_usd": 1e6,
                "cleaned_at_utc": "sometime"
            },
            "expected_base_sentiment": -0.5,
            "expected_bonuses_toContain": ["none"]
            # Expected score: -0.5, clamped to 0.0
        },
        {
            "name": "Eligible - All None for bonus categories, only sentiment",
            "data": {
                "symbol": "SENTONLY", "price": 100, "volume": 1e9, 
                "active_addresses": 10000, "mentions": 1000, 
                "sentiment_score": 0.77, 
                "transaction_volume_usd": None, # Explicitly None for a bonus category
                "cleaned_at_utc": "sometime"
            },
            "expected_base_sentiment": 0.77,
            "expected_bonuses_toContain": ["none"]
            # Expected score: 0.77
        }
    ]

    for i, case in enumerate(test_cases):
        print(f"\n--- Test Case {i+1}: {case['name']} ---")
        result = calculate_coin_score(case["data"])
        print(json.dumps(result, indent=4))
        
        # Basic validation for key fields
        assert "score" in result, f"Test Case {i+1} failed: 'score' missing"
        assert "base_sentiment_on_scoring" in result, f"Test Case {i+1} failed: 'base_sentiment_on_scoring' missing"
        assert "bonuses_applied" in result, f"Test Case {i+1} failed: 'bonuses_applied' missing"
        assert "score_calculation_timestamp_utc" in result, f"Test Case {i+1} failed: 'timestamp' missing"
        
        if "expected_score" in case:
            assert result["score"] == case["expected_score"], \
                f"Test Case {i+1} score mismatch: Expected {case['expected_score']}, Got {result['score']}"
        
        if "expected_base_sentiment" in case and result["base_sentiment_on_scoring"] is not None:
             assert abs(result["base_sentiment_on_scoring"] - case["expected_base_sentiment"]) < 0.001, \
                f"Test Case {i+1} base_sentiment mismatch: Expected {case['expected_base_sentiment']}, Got {result['base_sentiment_on_scoring']}"
        elif "expected_base_sentiment" in case and result["base_sentiment_on_scoring"] is None and case["expected_base_sentiment"] is not None:
            print(f"WARN Test Case {i+1}: Expected base_sentiment {case['expected_base_sentiment']} but got None (might be OK if ineligible)")
        
        if "expected_bonuses_toContain" in case:
            for bonus_keyword in case["expected_bonuses_toContain"]:
                found_bonus = any(bonus_keyword in applied_bonus for applied_bonus in result["bonuses_applied"])
                assert found_bonus, f"Test Case {i+1}: Expected bonus containing '{bonus_keyword}' not found in {result['bonuses_applied']}"

    print("\n--- Scorer Test Finished ---") 