import json
import os
import random
from datetime import datetime, timedelta

LOG_DIR = "user_data/logs"
ANALYSIS_DIR = os.path.join(LOG_DIR, "daily_analysis")

def ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(ANALYSIS_DIR, exist_ok=True)

def generate_stats():
    stats = {
        "total_pnl_usdt": 26.93,
        "total_pnl_pct": 0.031,
        "daily_pnl_pct": 0.012,  # Positive day
        "weekly_pnl_pct": 0.045,
        "win_rate": 1.0,         # 100% WR as per context
        "total_trades": 131,
        "active_positions": 23,
        "timestamp": datetime.utcnow().isoformat()
    }
    with open(os.path.join(LOG_DIR, "stats.json"), 'w') as f:
        json.dump(stats, f, indent=2)
    print("Generated stats.json")

def generate_market_analysis():
    # Simulating a "Night Scalp" environment
    analysis = {
        "meta": {
            "version": "6.0",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        },
        "market_state": {
            "bias": "SIDEWAYS",
            "volatility": "LOW",
            "condition": "PERFECT_FOR_SCALP"
        },
        "recommendations": {
            "best_hours": ["00", "01", "02", "03", "04", "05", "06", "07"],
            "worst_hours": ["08", "09"], # Market open volatility
            "top_pairs": ["WIF", "SUI", "NEAR", "AAVE"]
        },
        "conclusions": [
            "Market is in a stable sideways channel.",
            "BTC Volatility is low (<1.5% hourly).",
            "Perfect conditions for mean reversion strategies."
        ]
    }
    
    # Save as timestamped and latest
    filename = f"{datetime.utcnow().strftime('%Y-%m-%d_%H')}.json"
    with open(os.path.join(ANALYSIS_DIR, filename), 'w') as f:
        json.dump(analysis, f, indent=2)
    with open(os.path.join(ANALYSIS_DIR, "latest.json"), 'w') as f:
        json.dump(analysis, f, indent=2)
    print("Generated daily_analysis/latest.json")

def generate_post_trade_log():
    log = {
        "recent_trades": [
            {"pair": "WIF-USDT", "exit_reason": "TP", "post_exit_1h_price_change": -0.02, "verdict": "GOOD_EXIT"}, # Price dropped after we sold
            {"pair": "SUI-USDT", "exit_reason": "TP", "post_exit_1h_price_change": 0.05, "verdict": "TOO_EARLY"}   # Price pumped after we sold
        ]
    }
    with open(os.path.join(LOG_DIR, "post_trade_log.json"), 'w') as f:
        json.dump(log, f, indent=2)
    print("Generated post_trade_log.json")

def generate_config_override():
    # Initial empty or basic config
    config = {
        "min_profit_pct": 0.0245,
        "max_leverage": 6
    }
    with open("scripts/bablobot/config_override.json", 'w') as f:
        json.dump(config, f, indent=2)
    print("Generated config_override.json")

if __name__ == "__main__":
    ensure_dirs()
    generate_stats()
    generate_market_analysis()
    generate_post_trade_log()
    generate_config_override()
