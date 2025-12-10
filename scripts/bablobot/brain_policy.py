import json
import logging
from typing import Dict, Any, Tuple

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BrainPolicy")

# SAFETY BOUNDS
SAFETY_BOUNDS = {
    "momentum_threshold_fast": (0.0010, 0.0030),  # 0.10% - 0.30%
    "momentum_threshold_slow": (0.0008, 0.0020),  # 0.08% - 0.20%
    "min_profit_pct": (0.015, 0.060),             # 1.5% - 6.0%
    "max_leverage": (2, 15),                      # 2x - 15x
    "max_positions": (1, 25),                     # 1 - 25
    "balance_pct": (0.1, 1.0)                     # 10% - 100%
}

IMMUTABLE_KEYS = [
    "base_leverage",      # Base leverage is fixed, dynamic handles the rest
    "min_position_usdt",  # Risk management constant
    "telegram_token",
    "telegram_chat_id",
    "api_key",
    "secret_key"
]

def check_drawdown_limits(stats_path: str) -> bool:
    """
    Checks if daily or weekly drawdown limits are reached.
    Returns False if trading should be PAUSED.
    """
    try:
        with open(stats_path, 'r') as f:
            stats = json.load(f)
        
        daily_pnl = stats.get('daily_pnl_pct', 0)
        weekly_pnl = stats.get('weekly_pnl_pct', 0)

        # DD Limits
        if daily_pnl < -0.05: # -5%
            logger.critical(f"🛑 DAILY DRAWDOWN LIMIT REACHED: {daily_pnl*100:.2f}%")
            return False
        
        if weekly_pnl < -0.15: # -15%
            logger.critical(f"🛑 WEEKLY DRAWDOWN LIMIT REACHED: {weekly_pnl*100:.2f}%")
            return False

        return True
    except FileNotFoundError:
        logger.warning("Stats file not found, skipping DD check.")
        return True
    except Exception as e:
        logger.error(f"Error checking DD limits: {e}")
        return True

def validate_and_clip_config(proposed_config: Dict[str, Any], current_config: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
    """
    Validates proposed config changes against safety bounds.
    Returns (safe_config, rejection_reasons).
    """
    safe_config = proposed_config.copy()
    reasons = []

    # 1. Remove immutable keys
    for key in IMMUTABLE_KEYS:
        if key in safe_config:
            del safe_config[key]
            reasons.append(f"Ignored immutable key: {key}")

    # 2. Check bounds
    for key, (min_val, max_val) in SAFETY_BOUNDS.items():
        if key in safe_config:
            val = safe_config[key]
            if val < min_val:
                safe_config[key] = min_val
                reasons.append(f"Clipped {key} to min {min_val} (was {val})")
            elif val > max_val:
                safe_config[key] = max_val
                reasons.append(f"Clipped {key} to max {max_val} (was {val})")

    # 3. Special Rule: Leverage only DOWN
    if "max_leverage" in safe_config:
        current_lev = current_config.get("max_leverage", 15)
        if safe_config["max_leverage"] > current_lev:
            safe_config["max_leverage"] = current_lev
            reasons.append(f"Blocked leverage increase. Max allowed: {current_lev}")

    # 4. Special Rule: TP Phase Protection
    # If Brain tries to set min_profit_pct != 0.0245 (default), it disables phased TP.
    # We allow this but log a warning.
    if "min_profit_pct" in safe_config:
        if safe_config["min_profit_pct"] != 0.0245:
             reasons.append("⚠️ WARNING: Custom min_profit_pct disables Phased TP!")

    return safe_config, reasons
