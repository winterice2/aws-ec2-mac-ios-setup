"""
🔒 BRAIN POLICY - ЖЕЛЕЗНЫЕ ПРАВИЛА КОТОРЫЕ BRAIN НЕ МОЖЕТ НАРУШИТЬ
==================================================================
Brain живёт в железной клетке этих правил.
Все решения Brain проходят через enforce_brain_policy() ОБЯЗАТЕЛЬНО.

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# 🔒 SAFETY BOUNDS - ЖЁСТКИЕ ПРЕДЕЛЫ
# =============================================================================

SAFETY_BOUNDS = {
    # Signal thresholds
    "momentum_threshold_fast": {"min": 0.001, "max": 0.003, "default": 0.0018},
    "momentum_threshold_slow": {"min": 0.0008, "max": 0.002, "default": 0.0012},
    
    # Take Profit - КРИТИЧЕСКИ ВАЖНО!
    "min_profit_pct": {"min": 0.015, "max": 0.06, "default": 0.0245, "protected": True},
    
    # Leverage - ТОЛЬКО ВНИЗ!
    "max_leverage": {"min": 2, "max": 15, "default": 6, "only_down": True},
    "base_leverage": {"min": 2, "max": 10, "default": 4, "only_down": True},
    
    # Position sizing
    "max_positions": {"min": 5, "max": 24, "default": 10},
    "balance_pct": {"min": 0.5, "max": 1.0, "default": 1.0},
    "min_position_usdt": {"min": 2, "max": 50, "default": 2},
    
    # Cooldowns
    "position_cooldown": {"min": 60, "max": 600, "default": 300},
    "signal_cooldown": {"min": 30, "max": 300, "default": 60}
}

# =============================================================================
# 🚫 FORBIDDEN ACTIONS - ЗАПРЕЩЁННЫЕ ДЕЙСТВИЯ
# =============================================================================

FORBIDDEN_ACTIONS = [
    "delete_all_data",
    "reset_stats", 
    "disable_all_safeguards",
    "set_leverage_above_15",
    "set_balance_above_100",
    "disable_tp_phases",
    "modify_safety_bounds",
    "access_api_keys",
    "execute_shell_command"
]

# =============================================================================
# 📊 RATE LIMITS - ОГРАНИЧЕНИЯ СКОРОСТИ
# =============================================================================

RATE_LIMITS = {
    "config_changes_per_hour": 2,
    "position_closes_per_hour": 10,
    "alerts_per_hour": 20,
    "gemini_calls_per_hour": 20
}

# =============================================================================
# 🔴 EMERGENCY THRESHOLDS
# =============================================================================

EMERGENCY_THRESHOLDS = {
    "daily_dd_pct": -5.0,
    "weekly_dd_pct": -15.0,
    "position_dd_pct": -30.0,
    "max_position_time_minutes": 180,
    "consecutive_losses_to_block": 3
}

# =============================================================================
# 📜 POLICY STATE
# =============================================================================

@dataclass
class PolicyState:
    """Состояние политики"""
    config_changes_this_hour: int = 0
    last_config_change: Optional[datetime] = None
    consecutive_degradations: int = 0
    brain_blocked: bool = False
    block_reason: str = ""
    last_check: Optional[datetime] = None

_policy_state = PolicyState()
_policy_state_file = Path("/workspace/user_data/logs/policy_state.json")


def _load_policy_state():
    """Загружает состояние политики"""
    global _policy_state
    try:
        if _policy_state_file.exists():
            with open(_policy_state_file, 'r') as f:
                data = json.load(f)
                _policy_state.config_changes_this_hour = data.get("config_changes_this_hour", 0)
                _policy_state.consecutive_degradations = data.get("consecutive_degradations", 0)
                _policy_state.brain_blocked = data.get("brain_blocked", False)
                _policy_state.block_reason = data.get("block_reason", "")
                if data.get("last_config_change"):
                    _policy_state.last_config_change = datetime.fromisoformat(data["last_config_change"])
    except Exception as e:
        logger.error(f"Failed to load policy state: {e}")


def _save_policy_state():
    """Сохраняет состояние политики"""
    try:
        _policy_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_policy_state_file, 'w') as f:
            json.dump({
                "config_changes_this_hour": _policy_state.config_changes_this_hour,
                "last_config_change": _policy_state.last_config_change.isoformat() if _policy_state.last_config_change else None,
                "consecutive_degradations": _policy_state.consecutive_degradations,
                "brain_blocked": _policy_state.brain_blocked,
                "block_reason": _policy_state.block_reason,
                "last_check": datetime.utcnow().isoformat()
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save policy state: {e}")


# =============================================================================
# 🔧 ENFORCE FUNCTIONS
# =============================================================================

def enforce_brain_policy(
    proposed_changes: Dict[str, Any],
    current_config: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    🔒 ГЛАВНАЯ ФУНКЦИЯ ENFORCE - ВСЕ РЕШЕНИЯ BRAIN ПРОХОДЯТ ЧЕРЕЗ НЕЁ
    
    Args:
        proposed_changes: Предложенные Brain изменения
        current_config: Текущий конфиг
    
    Returns:
        Tuple[applied_changes, reasons]: Применённые изменения и причины обрезки
    """
    _load_policy_state()
    
    applied = {}
    reasons = {}
    
    # Проверка блокировки Brain
    if _policy_state.brain_blocked:
        logger.warning(f"⛔ Brain BLOCKED: {_policy_state.block_reason}")
        return {}, {"blocked": _policy_state.block_reason}
    
    # Проверка rate limit
    if not _check_rate_limit():
        reasons["rate_limit"] = f"Превышен лимит изменений ({RATE_LIMITS['config_changes_per_hour']}/час)"
        return {}, reasons
    
    for param, proposed_value in proposed_changes.items():
        # Пропускаем служебные поля
        if param.startswith("_"):
            continue
        
        # Проверка на запрещённые действия
        if param in FORBIDDEN_ACTIONS:
            reasons[param] = "FORBIDDEN - запрещённое действие"
            logger.warning(f"🚫 Forbidden action blocked: {param}")
            continue
        
        # Проверка SAFETY_BOUNDS
        if param in SAFETY_BOUNDS:
            bounds = SAFETY_BOUNDS[param]
            original_value = proposed_value
            
            # Приведение к пределам
            if isinstance(proposed_value, (int, float)):
                proposed_value = max(bounds["min"], min(bounds["max"], proposed_value))
            
            # Проверка only_down для leverage
            if bounds.get("only_down"):
                current_value = current_config.get(param, bounds["default"])
                if proposed_value > current_value:
                    proposed_value = current_value
                    reasons[param] = f"only_down: {original_value} → {proposed_value}"
            
            # Проверка protected (min_profit_pct)
            if bounds.get("protected"):
                # Разрешаем изменять только если явно указано
                if abs(proposed_value - bounds["default"]) > 0.001:
                    logger.warning(f"⚠️ Protected param modified: {param} = {proposed_value}")
            
            # Проверка на изменение
            if original_value != proposed_value:
                if param not in reasons:
                    reasons[param] = f"bounded: {original_value} → {proposed_value}"
            
            applied[param] = proposed_value
        else:
            # Неизвестный параметр - пропускаем
            reasons[param] = "UNKNOWN - параметр не в SAFETY_BOUNDS"
            logger.warning(f"⚠️ Unknown param ignored: {param}")
    
    # Обновляем состояние
    if applied:
        _policy_state.config_changes_this_hour += 1
        _policy_state.last_config_change = datetime.utcnow()
        _save_policy_state()
    
    return applied, reasons


def _check_rate_limit() -> bool:
    """Проверяет rate limit на изменения"""
    now = datetime.utcnow()
    
    # Сбрасываем счётчик если прошёл час
    if _policy_state.last_config_change:
        if (now - _policy_state.last_config_change).total_seconds() > 3600:
            _policy_state.config_changes_this_hour = 0
    
    return _policy_state.config_changes_this_hour < RATE_LIMITS["config_changes_per_hour"]


def check_degradation(new_metrics: Dict[str, float], old_metrics: Dict[str, float]) -> bool:
    """
    Проверяет ухудшение метрик после изменения Brain
    
    Returns:
        True если метрики ухудшились
    """
    degradation_detected = False
    
    # Проверка win_rate
    if new_metrics.get("win_rate", 1.0) < old_metrics.get("win_rate", 1.0) * 0.9:
        degradation_detected = True
    
    # Проверка pnl
    if new_metrics.get("pnl_per_hour", 0) < old_metrics.get("pnl_per_hour", 0) * 0.8:
        degradation_detected = True
    
    if degradation_detected:
        _policy_state.consecutive_degradations += 1
        
        # Блокируем Brain после 3 ухудшений подряд
        if _policy_state.consecutive_degradations >= EMERGENCY_THRESHOLDS["consecutive_losses_to_block"]:
            block_brain("3 consecutive degradations detected")
    else:
        _policy_state.consecutive_degradations = 0
    
    _save_policy_state()
    return degradation_detected


def block_brain(reason: str):
    """Блокирует Brain"""
    _policy_state.brain_blocked = True
    _policy_state.block_reason = reason
    _save_policy_state()
    logger.error(f"⛔ BRAIN BLOCKED: {reason}")


def unblock_brain():
    """Разблокирует Brain"""
    _policy_state.brain_blocked = False
    _policy_state.block_reason = ""
    _policy_state.consecutive_degradations = 0
    _save_policy_state()
    logger.info("✅ Brain unblocked")


def is_brain_blocked() -> Tuple[bool, str]:
    """Проверяет заблокирован ли Brain"""
    _load_policy_state()
    return _policy_state.brain_blocked, _policy_state.block_reason


def get_policy_state() -> Dict[str, Any]:
    """Возвращает текущее состояние политики"""
    _load_policy_state()
    return {
        "config_changes_this_hour": _policy_state.config_changes_this_hour,
        "last_config_change": _policy_state.last_config_change.isoformat() if _policy_state.last_config_change else None,
        "consecutive_degradations": _policy_state.consecutive_degradations,
        "brain_blocked": _policy_state.brain_blocked,
        "block_reason": _policy_state.block_reason,
        "rate_limit_remaining": RATE_LIMITS["config_changes_per_hour"] - _policy_state.config_changes_this_hour
    }


# =============================================================================
# 🚨 EMERGENCY CHECKS
# =============================================================================

def check_emergency_conditions(
    daily_pnl_pct: float,
    weekly_pnl_pct: float,
    worst_position_pnl_pct: float
) -> Tuple[bool, str]:
    """
    Проверяет экстренные условия
    
    Returns:
        Tuple[emergency_triggered, reason]
    """
    if daily_pnl_pct < EMERGENCY_THRESHOLDS["daily_dd_pct"]:
        return True, f"Daily DD: {daily_pnl_pct:.2f}% < {EMERGENCY_THRESHOLDS['daily_dd_pct']}%"
    
    if weekly_pnl_pct < EMERGENCY_THRESHOLDS["weekly_dd_pct"]:
        return True, f"Weekly DD: {weekly_pnl_pct:.2f}% < {EMERGENCY_THRESHOLDS['weekly_dd_pct']}%"
    
    if worst_position_pnl_pct < EMERGENCY_THRESHOLDS["position_dd_pct"]:
        return True, f"Position DD: {worst_position_pnl_pct:.2f}% < {EMERGENCY_THRESHOLDS['position_dd_pct']}%"
    
    return False, ""


def validate_position_action(
    action: str,
    position: Dict[str, Any],
    current_pnl_pct: float
) -> Tuple[bool, str]:
    """
    Валидирует действие с позицией
    
    Правило: НЕ закрывать позиции в минусе если нет угрозы ликвидации!
    """
    if action == "close":
        # Не закрываем в минусе если не критично
        if current_pnl_pct < 0:
            distance_to_liquidation = position.get("distance_to_liquidation_pct", 100)
            
            # Разрешаем закрытие только если близко к ликвидации
            if distance_to_liquidation > 5:  # >5% до ликвидации
                return False, f"BLOCKED: PnL={current_pnl_pct:.2f}% < 0, но до ликвидации {distance_to_liquidation:.1f}%"
            
            logger.warning(f"⚠️ Force close allowed: близко к ликвидации ({distance_to_liquidation:.1f}%)")
    
    return True, ""


# =============================================================================
# 📊 ADAPTIVE TP VALIDATION
# =============================================================================

def get_adaptive_tp_for_pair(pair: str, base_tp: float) -> float:
    """
    Возвращает адаптивный TP для пары
    
    Волатильные пары: +50% к TP
    Тяжёлые пары: -30% к TP
    """
    # Волатильные пары (быстрые, высокий TP)
    volatile_pairs = ["WIF-USDT", "FET-USDT", "DOGE-USDT", "SUI-USDT"]
    
    # Тяжёлые пары (медленные, низкий TP)
    heavy_pairs = ["BNB-USDT", "ETH-USDT", "ARB-USDT", "SOL-USDT"]
    
    if pair in volatile_pairs:
        return min(base_tp * 1.5, SAFETY_BOUNDS["min_profit_pct"]["max"])
    elif pair in heavy_pairs:
        return max(base_tp * 0.7, SAFETY_BOUNDS["min_profit_pct"]["min"])
    
    return base_tp


# =============================================================================
# 🔧 UTILITY FUNCTIONS
# =============================================================================

def reset_hourly_counters():
    """Сбрасывает почасовые счётчики (вызывать по cron)"""
    global _policy_state
    _policy_state.config_changes_this_hour = 0
    _save_policy_state()
    logger.info("📊 Hourly counters reset")


def get_safety_bounds() -> Dict[str, Dict]:
    """Возвращает все safety bounds"""
    return SAFETY_BOUNDS.copy()


def get_rate_limits() -> Dict[str, int]:
    """Возвращает все rate limits"""
    return RATE_LIMITS.copy()


def log_policy_violation(violation_type: str, details: Dict[str, Any]):
    """Логирует нарушение политики"""
    violations_file = Path("/workspace/user_data/logs/policy_violations.jsonl")
    violations_file.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": violation_type,
        "details": details
    }
    
    with open(violations_file, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    logger.warning(f"🚨 Policy violation: {violation_type}")
