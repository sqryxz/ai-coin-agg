from datetime import datetime, timezone
import json
import math # For math.log

# Define weights for each metric
# With mentions multiplier, direct mention weights are removed.
# Previous total weight for mentions/gdelt_articles was 0.10 + 0.10 = 0.20
# Redistributing this: +0.05 to volume, market_cap, active_addresses, cp_sentiment.
METRIC_WEIGHTS = {
    "volume": 0.20, # Was 0.15
    "market_cap": 0.20, # Was 0.15
    "active_addresses": 0.20, # Was 0.15
    "etherscan_transaction_count_proxy": 0.10,
    "sentiment_score": 0.20, # CryptoPanic sentiment, was 0.15
    "gdelt_sentiment_score": 0.10,
    # "mentions" and "gdelt_article_count" are no longer directly weighted here.
}

# Placeholder for Volume Momentum component - to be developed when historical data is available to scorer
VOLUME_MOMENTUM_WEIGHT = 0.0 # Not yet active

def _calculate_mention_multiplier(total_mentions: int) -> float:
    """Calculates a sentiment multiplier based on total mentions."""
    if total_mentions < 100:
        return 0.8
    elif total_mentions < 1000:
        return 1.0
    elif total_mentions < 10000:
        return 1.2
    else: # >= 10000
        return 1.5

def _transform_value(metric_name: str, value: float | int) -> float:
    """Applies a transformation to a metric value to somewhat normalize or scale it."""
    if value is None: # Should have been cleaned to 0 or 0.0 by data_cleaner
        value = 0

    # Logarithmic scaling for large-range, non-negative values
    # Mentions and gdelt_article_count are used for multiplier, not directly transformed here for weighting
    if metric_name in ["volume", "market_cap", "active_addresses", "etherscan_transaction_count_proxy"]:
        return math.log(1 + float(value))
    
    elif metric_name == "sentiment_score": # CryptoPanic sentiment, original range -1 to 1
        return (float(value) + 1) / 2 # Rescale from [-1, 1] to [0, 1]
    
    elif metric_name == "gdelt_sentiment_score": # GDELT tone, assume approx -10 to 10
        scaled_value = (float(value) + 10) / 20 # Rescale from approx [-10, 10] to [0, 1]
        return max(0.0, min(scaled_value, 1.0)) # Clamp
    
    return float(value) # Default for any other metric not explicitly transformed

def calculate_coin_score(cleaned_data: dict) -> dict:
    """
    Calculates a composite score for a single coin based on its cleaned data
    using a weighted sum of transformed metrics, with sentiment modulated by mentions.
    Volume momentum is a placeholder for future enhancement.
    """
    symbol = cleaned_data.get("symbol", "UNKNOWN")
    coingecko_id = cleaned_data.get("coingecko_id")
    timestamp = datetime.now(timezone.utc).isoformat()
    
    raw_weighted_score = 0.0
    contributing_metrics = {}

    # Calculate total mentions for sentiment multiplier
    cp_mentions = cleaned_data.get("mentions", 0)
    gdelt_articles = cleaned_data.get("gdelt_article_count", 0)
    total_mentions = cp_mentions + gdelt_articles
    mention_multiplier = _calculate_mention_multiplier(total_mentions)

    contributing_metrics["mention_analysis"] = {
        "cp_mentions": cp_mentions,
        "gdelt_article_count": gdelt_articles,
        "total_mentions": total_mentions,
        "mention_multiplier_for_sentiment": mention_multiplier
    }

    for metric, weight in METRIC_WEIGHTS.items():
        value = cleaned_data.get(metric, 0.0) # Default to 0.0 if somehow missing post-cleaning
        
        transformed_value = _transform_value(metric, value)
        metric_contribution = 0.0

        current_weight = weight
        if metric == "sentiment_score" or metric == "gdelt_sentiment_score":
            metric_contribution = current_weight * mention_multiplier * transformed_value
            # Store effective weight for transparency
            contributing_metrics[metric] = {
                "original_value": value,
                "transformed_value": round(transformed_value, 4),
                "base_weight": current_weight,
                "mention_multiplier_applied": mention_multiplier,
                "effective_weight": round(current_weight * mention_multiplier, 4),
                "contribution": round(metric_contribution, 4)
            }
        else:
            metric_contribution = current_weight * transformed_value
            contributing_metrics[metric] = {
                "original_value": value,
                "transformed_value": round(transformed_value, 4),
                "weight": current_weight,
                "contribution": round(metric_contribution, 4)
            }
        raw_weighted_score += metric_contribution
    
    # --- Volume Momentum (Placeholder) ---
    # This section is a placeholder. True momentum requires historical data.
    # For now, it does not contribute to the score.
    volume_momentum_score_component = 0.0 
    # Potential simple proxy (not used for score yet):
    # current_volume = cleaned_data.get("volume", 0.0)
    # market_cap = cleaned_data.get("market_cap", 0.0)
    # vol_to_mcap_ratio = (current_volume / market_cap) if market_cap > 0 else 0
    contributing_metrics["volume_momentum"] = {
        "status": "Placeholder - Full implementation requires historical volume data.",
        "current_contribution": volume_momentum_score_component,
        "weight_to_be_assigned": VOLUME_MOMENTUM_WEIGHT
    }
    # raw_weighted_score += volume_momentum_score_component * VOLUME_MOMENTUM_WEIGHT # If it were active

    # --- Final Score Scaling ---
    # Max possible raw_weighted_score sum needs re-evaluation with mention multiplier.
    # If M_max=1.5, sentiment weights (0.20+0.10=0.30) * 1.5 = 0.45 for sentiment part.
    # Other weights sum to 0.20+0.20+0.10 = 0.50.
    # Max transformed values for logs (e.g. market_cap, volume, active_addresses) still around 10-28.
    # Example Max Contribution (rough):
    # Volume (log~25, w=0.20) -> 5.0
    # MCap   (log~28, w=0.20) -> 5.6
    # ActiveA(log~14, w=0.20) -> 2.8
    # EthTxC (log~10, w=0.10) -> 1.0 (if applicable)
    # Max Sentiment part (transformed to 1, multiplied by M=1.5, total weight 0.30) -> 0.45
    # Total sum approx: 5.0 + 5.6 + 2.8 + 1.0 + 0.45 = 14.85 (if ERC20 with high tx count)
    # Or without EthTxC: ~13.85
    # Scaling factor: 100 / ~14 = ~7.1
    scaling_factor = 7.0 # Adjusted based on new max raw score estimate
    final_score = raw_weighted_score * scaling_factor
    final_score_clamped = max(0.0, min(final_score, 100.0))
    
    return {
        "coingecko_id": coingecko_id,
        "symbol": symbol,
        "score": round(final_score_clamped, 2),
        "raw_weighted_score": round(raw_weighted_score, 4),
        "mention_multiplier_applied_to_sentiment": mention_multiplier,
        "scaling_factor_applied": scaling_factor,
        "contributing_metrics": contributing_metrics,
        "score_calculation_timestamp_utc": timestamp
    }

if __name__ == "__main__":
    print("--- Testing calculate_coin_score (with Mention Multiplier & Volume Momentum Placeholder) ---")

    # Test cases need to be updated to reflect new structure and metrics
    # Test data should include `mentions` and `gdelt_article_count` for the multiplier.
    test_cases = [
        {
            "name": "High Potential Coin (BTC-like) - High Mentions",
            "data": {
                "coingecko_id": "bitcoin", "symbol": "BTC",
                "volume": 50e9, "market_cap": 1.2e12, "active_addresses": 1e6,
                "etherscan_transaction_count_proxy": 0,
                "mentions": 150000, "sentiment_score": 0.8, # CP transformed: 0.9
                "gdelt_sentiment_score": 2.0, # GDELT transformed: 0.6
                "gdelt_article_count": 5000, # total mentions = 155000 -> M=1.5
                "cleaned_at_utc": "sometime"
            }
        },
        {
            "name": "Mid Potential ERC20 (LINK-like) - Medium Mentions",
            "data": {
                "coingecko_id": "chainlink", "symbol": "LINK",
                "volume": 300e6, "market_cap": 10e9, "active_addresses": 70000,
                "etherscan_transaction_count_proxy": 15000,
                "mentions": 1500, "sentiment_score": 0.6, # CP transformed: 0.8
                "gdelt_sentiment_score": -1.0, # GDELT transformed: 0.45
                "gdelt_article_count": 500, # total mentions = 2000 -> M=1.2
                "cleaned_at_utc": "sometime"
            }
        },
        {
            "name": "Lower Potential - Low Mentions",
            "data": {
                "coingecko_id": "newcoin", "symbol": "NEWC",
                "volume": 1e6, "market_cap": 50e6, "active_addresses": 1000,
                "etherscan_transaction_count_proxy": 50,
                "mentions": 80, "sentiment_score": 0.1, # CP transformed: 0.55
                "gdelt_sentiment_score": -5.0, # GDELT transformed: 0.25
                "gdelt_article_count": 10, # total mentions = 90 -> M=0.8
                "cleaned_at_utc": "sometime"
            }
        },
        {
            "name": "Zeroed/Default Data - Min Mentions",
            "data": {
                "coingecko_id": "failcoin", "symbol": "FAIL",
                "volume": 0, "market_cap": 0, "active_addresses": 0,
                "etherscan_transaction_count_proxy": 0,
                "mentions": 0, "sentiment_score": 0.0, # CP transformed: 0.5
                "gdelt_sentiment_score": 0.0, # GDELT transformed: 0.5
                "gdelt_article_count": 0, # total mentions = 0 -> M=0.8
                "cleaned_at_utc": "sometime", "collection_errors": ["API failed"]
            }
        }
    ]

    # Define all keys the scorer might access from cleaned_data based on METRIC_WEIGHTS and mention calculation
    expected_keys_from_cleaned_data = list(METRIC_WEIGHTS.keys()) + ["mentions", "gdelt_article_count", "coingecko_id", "symbol", "cleaned_at_utc"]

    for i, case in enumerate(test_cases):
        print(f"\n--- Test Case {i+1}: {case['name']} ---")
        
        # Ensure test data provides all necessary fields, defaulting if not in case['data']
        full_test_data = {key: 0 for key in expected_keys_from_cleaned_data if key not in ["coingecko_id", "symbol", "cleaned_at_utc"]} # Default numeric to 0
        full_test_data["coingecko_id"] = None
        full_test_data["symbol"] = "TEST_SYM"
        full_test_data["cleaned_at_utc"] = "timestamp"
        full_test_data.update(case["data"]) # Overwrite with actual test case data
        
        result = calculate_coin_score(full_test_data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert "score" in result, f"Test Case {i+1} failed: 'score' missing"
        assert 0 <= result["score"] <= 100, f"Test Case {i+1} score ({result['score']}) out of range [0, 100]"
        assert "contributing_metrics" in result
        assert "mention_analysis" in result["contributing_metrics"]
        assert "volume_momentum" in result["contributing_metrics"]
        for metric_name in METRIC_WEIGHTS.keys():
            assert metric_name in result["contributing_metrics"], f"Metric {metric_name} missing from contribution details"

    print("\n--- Scorer Test Finished ---") 