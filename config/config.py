"""
🔧 BABLOBOT CONFIGURATION - ЦЕНТРАЛЬНЫЙ КОНФИГ ЭКОСИСТЕМЫ
=========================================================
Все параметры системы в одном месте.
Brain может менять только через config_override.json
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# =============================================================================
# 📁 PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
USER_DATA_DIR = BASE_DIR / "user_data"
LOGS_DIR = USER_DATA_DIR / "logs"
DATA_DIR = USER_DATA_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

# Feedback directories
FEEDBACK_DIR = LOGS_DIR / "ecosystem_feedback"
ERRORS_DIR = FEEDBACK_DIR / "errors"
UNSOLVED_DIR = FEEDBACK_DIR / "unsolved"
NEEDS_DIR = FEEDBACK_DIR / "needs"
DECISIONS_DIR = FEEDBACK_DIR / "decisions"

# Data directories
SPOT_FLOW_DIR = DATA_DIR / "spot_flow"
BTC_WATCHER_DIR = DATA_DIR / "btc_watcher"
VOLUME_DIR = DATA_DIR / "volume"
LAG_DATA_DIR = DATA_DIR / "lag_data"

# =============================================================================
# 🔑 API KEYS (from environment)
# =============================================================================
BINGX_API_KEY = os.environ.get("BINGX_API_KEY", "")
BINGX_SECRET_KEY = os.environ.get("BINGX_SECRET_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCyEuXhUu7DqM1MMzZrAgHrxFNvUbZy2AY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# =============================================================================
# 📊 TRADING PAIRS
# =============================================================================
DEFAULT_PAIRS = [
    "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT", "DOGE-USDT",
    "ADA-USDT", "AVAX-USDT", "DOT-USDT", "LINK-USDT", "MATIC-USDT",
    "UNI-USDT", "ATOM-USDT", "LTC-USDT", "ETC-USDT", "FIL-USDT",
    "ARB-USDT", "OP-USDT", "APT-USDT", "NEAR-USDT", "SUI-USDT",
    "WIF-USDT", "FET-USDT", "SEI-USDT", "INJ-USDT"
]

# Gemini Analysis Results (09.12.2024)
WHITELIST_PAIRS = ["WIF-USDT", "SUI-USDT", "NEAR-USDT", "FET-USDT", 
                   "ARB-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT"]
BLACKLIST_PAIRS = ["LTC-USDT", "UNI-USDT", "SEI-USDT", "XRP-USDT", 
                   "POL-USDT", "ATOM-USDT", "CRV-USDT"]  # Медленные "якоря"

# =============================================================================
# 💰 TRADING PARAMETERS
# =============================================================================
class TradingConfig:
    # Position sizing
    balance_pct: float = 1.0  # 100% баланса
    min_position_usdt: float = 2.0
    max_positions: int = 10  # Снижено с 23 (рекомендация Gemini)
    
    # Leverage
    base_leverage: int = 4
    max_leverage: int = 6
    wins_to_increase: int = 2  # После 2 wins - увеличиваем leverage
    
    # Take Profit - Three Phase System
    min_profit_pct: float = 0.0245  # 2.45% - БАЗОВЫЙ TP (НЕ МЕНЯТЬ!)
    
    # Draw Down - ОТКЛЮЧЕНО (позиции висят до TP или ликвидации)
    soft_dd_pct: float = 0.0  # Отключено
    hard_dd_pct: float = 0.0  # Отключено
    
    # Signal thresholds
    momentum_threshold_fast: float = 0.0018  # 0.18% за 15s
    momentum_threshold_slow: float = 0.0012  # 0.12% за 60s
    signal_lookback_fast: int = 15  # seconds
    signal_lookback_slow: int = 60  # seconds
    
    # Cooldowns
    position_cooldown: int = 300  # 5 min между позициями на одной паре
    signal_cooldown: int = 60  # 1 min между сигналами

# =============================================================================
# ⏰ TIME-BASED TP PHASES (UTC)
# =============================================================================
TP_PHASES = {
    "night": {  # 00:00-08:00 UTC
        "start_hour": 0,
        "end_hour": 8,
        "tp_pct": 0.0245,  # 2.45%
        "mode": "AGGRESSIVE",
        "leverage_mult": 1.25,  # x5 effective
        "allow_short": True
    },
    "day": {  # 08:00-16:00 UTC
        "start_hour": 8,
        "end_hour": 16,
        "tp_pct": 0.0220,  # 2.20%
        "mode": "LONG_ONLY",
        "leverage_mult": 1.0,  # x4 effective
        "allow_short": False  # БЕЗ SHORT днём!
    },
    "evening": {  # 16:00-24:00 UTC
        "start_hour": 16,
        "end_hour": 24,
        "tp_pct": 0.0280,  # 2.80%
        "mode": "CONSERVATIVE",
        "leverage_mult": 0.75,  # x3 effective
        "allow_short": True
    }
}

# =============================================================================
# 🛡️ BTC TREND GUARD
# =============================================================================
BTC_TREND_GUARD = {
    "enabled": True,
    "threshold_pct": 1.5,  # ±1.5%/час
    "lookback_minutes": 60,
    "cache_seconds": 60,
    "block_long_on_drop": True,  # BTC -1.5%/час → блокируем LONG
    "block_short_on_pump": True  # BTC +1.5%/час → блокируем SHORT
}

# =============================================================================
# 🧠 BRAIN CONFIGURATION
# =============================================================================
BRAIN_CONFIG = {
    "enabled": True,
    "model": "gemini-2.5-flash",  # Продакшн модель
    "temperature": 0.2,
    "max_tokens": 2048,
    "interval_minutes": 15,  # Каждые 15 минут
    "max_changes_per_hour": 2,
    "safety_mode": "BLOCK_NONE"
}

# R&D Analysis (раз в день)
RD_ANALYSIS_CONFIG = {
    "model": "gemini-2.5-pro",  # Мощная модель для анализа
    "fallback_model": "gemini-3-pro-preview",
    "max_tokens": 8192,
    "run_hour_utc": 0  # Запускать в полночь UTC
}

# =============================================================================
# 🔒 SAFETY BOUNDS (Brain не может выйти за пределы)
# =============================================================================
SAFETY_BOUNDS = {
    "momentum_threshold_fast": {"min": 0.001, "max": 0.003},  # 0.10% - 0.30%
    "momentum_threshold_slow": {"min": 0.0008, "max": 0.002},  # 0.08% - 0.20%
    "min_profit_pct": {"min": 0.015, "max": 0.06},  # 1.5% - 6%
    "max_leverage": {"min": 2, "max": 15, "only_down": True},  # Только вниз!
    "max_positions": {"min": 5, "max": 24}
}

# =============================================================================
# 🚨 GLOBAL SAFEGUARDS (вне Brain)
# =============================================================================
GLOBAL_SAFEGUARDS = {
    "daily_dd_limit_pct": -5.0,  # -5% → автопауза
    "weekly_dd_limit_pct": -15.0,  # -15% → автопауза
    "consecutive_losses_to_block": 3,  # 3 ухудшения подряд → блок Brain
    "emergency_exit_minutes": 180,  # >180 мин и PnL<0.5% → FORCE CLOSE
    "emergency_exit_min_pnl": 0.5
}

# =============================================================================
# 📊 VOLATILITY WATCHER
# =============================================================================
VOLATILITY_CONFIG = {
    "enabled": False,  # Пока отключено - нужны данные
    "atr_threshold_pct": 25.0,  # 25% ATR
    "spike_threshold_pct": 15.0,  # 15% spike
    "lookback_minutes": 30,
    "time_zones": {
        "night": {"start": 0, "end": 9, "atr": 15.0, "spike": 10.0},
        "day": {"start": 9, "end": 21, "atr": 25.0, "spike": 15.0},
        "evening": {"start": 21, "end": 24, "atr": 20.0, "spike": 12.0}
    }
}

# =============================================================================
# 🔧 CONFIG OVERRIDE LOADER
# =============================================================================
def load_config_override() -> Dict[str, Any]:
    """Загружает override параметры от Brain"""
    override_path = CONFIG_DIR / "config_override.json"
    if override_path.exists():
        try:
            with open(override_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def get_effective_config() -> Dict[str, Any]:
    """Возвращает эффективный конфиг с учётом override"""
    base = {
        "momentum_threshold_fast": TradingConfig.momentum_threshold_fast,
        "momentum_threshold_slow": TradingConfig.momentum_threshold_slow,
        "min_profit_pct": TradingConfig.min_profit_pct,
        "max_leverage": TradingConfig.max_leverage,
        "max_positions": TradingConfig.max_positions,
        "base_leverage": TradingConfig.base_leverage,
    }
    override = load_config_override()
    
    # Применяем override с проверкой bounds
    for key, value in override.items():
        if key in SAFETY_BOUNDS:
            bounds = SAFETY_BOUNDS[key]
            if bounds.get("only_down") and key == "max_leverage":
                # Leverage только вниз
                value = min(value, base.get(key, value))
            value = max(bounds["min"], min(bounds["max"], value))
        base[key] = value
    
    return base

def get_current_tp_phase() -> Dict[str, Any]:
    """Возвращает текущую фазу TP на основе UTC времени"""
    current_hour = datetime.utcnow().hour
    
    for phase_name, phase_config in TP_PHASES.items():
        if phase_config["start_hour"] <= current_hour < phase_config["end_hour"]:
            return {"name": phase_name, **phase_config}
    
    # Fallback to night
    return {"name": "night", **TP_PHASES["night"]}

def get_dynamic_tp() -> float:
    """Возвращает динамический TP для текущей фазы"""
    override = load_config_override()
    
    # Если Brain установил свой TP - используем его
    if "min_profit_pct" in override and override["min_profit_pct"] != 0.0245:
        return override["min_profit_pct"]
    
    # Иначе используем трёхфазный TP
    phase = get_current_tp_phase()
    return phase["tp_pct"]
