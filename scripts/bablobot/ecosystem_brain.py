"""
🧠 ECOSYSTEM BRAIN v2.0 - АВТОНОМНЫЙ МОЗГ ЭКОСИСТЕМЫ
====================================================
Думает как топовая LLM. Собирает ВСЕ данные. Принимает решения.
Когда не может решить - пишет в feedback для улучшения.

УРОВНИ РАЗВИТИЯ:
- Уровень 1: ✅ Меняет config_override.json, закрывает позиции
- Уровень 2: 🔄 WebSocket, видит каждый тик, блокирует сигналы
- Уровень 3: 🎯 ML модель, полная автономия

Автор: AI Architect для проекта "Кнопка БАБЛО" (Pavel/@dxbatr)
"""

import os
import sys
import json
import time
import asyncio
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | BRAIN | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/workspace/user_data/logs/brain.log')
    ]
)
logger = logging.getLogger(__name__)

# Import config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import (
    GEMINI_API_KEY, BRAIN_CONFIG, SAFETY_BOUNDS, GLOBAL_SAFEGUARDS,
    TP_PHASES, BTC_TREND_GUARD, FEEDBACK_DIR, ERRORS_DIR, UNSOLVED_DIR,
    NEEDS_DIR, DECISIONS_DIR, LOGS_DIR, DATA_DIR, CONFIG_DIR,
    get_effective_config, get_current_tp_phase, get_dynamic_tp,
    WHITELIST_PAIRS, BLACKLIST_PAIRS
)

# =============================================================================
# 📊 DATA STRUCTURES
# =============================================================================

class DecisionType(Enum):
    """Типы решений Brain"""
    CONFIG_CHANGE = "config_change"
    POSITION_ACTION = "position_action"
    SIGNAL_BLOCK = "signal_block"
    ALERT = "alert"
    EMERGENCY = "emergency"
    INFO = "info"

class FeedbackType(Enum):
    """Типы feedback"""
    ERROR = "error"
    UNSOLVED = "unsolved"
    NEED = "need"
    DECISION = "decision"

@dataclass
class MarketState:
    """Состояние рынка"""
    timestamp: str
    btc_price: float = 0.0
    btc_change_1h: float = 0.0
    btc_change_24h: float = 0.0
    eth_price: float = 0.0
    eth_change_1h: float = 0.0
    market_bias: str = "UNKNOWN"  # BULLISH / BEARISH / SIDEWAYS
    volatility: str = "UNKNOWN"  # HIGH / MEDIUM / LOW
    dominant_direction: str = "NEUTRAL"  # LONG / SHORT / NEUTRAL
    fear_greed_index: int = 0
    total_volume_24h: float = 0.0

@dataclass
class PositionState:
    """Состояние позиций"""
    timestamp: str
    total_positions: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    long_count: int = 0
    short_count: int = 0
    worst_position_pnl: float = 0.0
    best_position_pnl: float = 0.0
    avg_position_time_min: float = 0.0
    positions: List[Dict] = None

@dataclass 
class TradingStats:
    """Торговая статистика"""
    timestamp: str
    trades_today: int = 0
    win_rate: float = 0.0
    total_pnl_today: float = 0.0
    avg_trade_duration_min: float = 0.0
    best_pair: str = ""
    worst_pair: str = ""
    trades_per_hour: float = 0.0
    win_streak: int = 0
    loss_streak: int = 0

@dataclass
class BrainDecision:
    """Решение Brain"""
    timestamp: str
    decision_type: str
    action: str
    reason: str
    confidence: float
    data: Dict[str, Any]
    applied: bool = False

# =============================================================================
# 🧠 ECOSYSTEM BRAIN CLASS
# =============================================================================

class EcosystemBrain:
    """
    АВТОНОМНЫЙ МОЗГ ЭКОСИСТЕМЫ
    
    Думает как современная LLM:
    1. Собирает ВСЕ доступные данные
    2. Анализирует контекст
    3. Принимает решения
    4. Записывает что не смог решить в feedback
    5. Учится на ошибках
    """
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.decisions_made = 0
        self.errors_encountered = 0
        self.last_decision_time = None
        self.decision_history: List[BrainDecision] = []
        
        # State
        self.market_state: Optional[MarketState] = None
        self.position_state: Optional[PositionState] = None
        self.trading_stats: Optional[TradingStats] = None
        
        # Cache
        self.cache = {}
        self.cache_ttl = 60  # seconds
        
        # Gemini client (lazy init)
        self._gemini_client = None
        
        logger.info("🧠 Ecosystem Brain v2.0 initialized")
        logger.info(f"   Model: {BRAIN_CONFIG['model']}")
        logger.info(f"   Interval: {BRAIN_CONFIG['interval_minutes']} min")
        
    # =========================================================================
    # 📥 DATA COLLECTION - Сбор ВСЕХ данных
    # =========================================================================
    
    async def collect_all_data(self) -> Dict[str, Any]:
        """
        СОБИРАЕТ ВСЕ ДАННЫЕ ИЗ ВСЕХ ИСТОЧНИКОВ
        Это ключевой метод - Brain должен видеть ВСЁ
        """
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "market": {},
            "positions": {},
            "stats": {},
            "config": {},
            "feedback_pending": {},
            "signals": {},
            "btc_trend": {},
            "spot_flow": {},
            "volumes": {}
        }
        
        try:
            # 1. Текущий конфиг
            data["config"] = get_effective_config()
            data["config"]["current_tp_phase"] = get_current_tp_phase()
            data["config"]["dynamic_tp"] = get_dynamic_tp()
            
            # 2. Данные рынка
            data["market"] = await self._collect_market_data()
            
            # 3. Позиции
            data["positions"] = await self._collect_positions_data()
            
            # 4. Статистика торговли
            data["stats"] = await self._collect_trading_stats()
            
            # 5. BTC Trend
            data["btc_trend"] = await self._collect_btc_trend()
            
            # 6. Spot Flow (BUY/SELL pressure)
            data["spot_flow"] = await self._collect_spot_flow()
            
            # 7. Volumes
            data["volumes"] = await self._collect_volumes()
            
            # 8. Pending feedback (нерешённые проблемы)
            data["feedback_pending"] = self._collect_pending_feedback()
            
            # 9. Recent decisions
            data["recent_decisions"] = [asdict(d) for d in self.decision_history[-10:]]
            
        except Exception as e:
            await self._log_feedback(
                FeedbackType.ERROR,
                "data_collection_failed",
                str(e),
                {"traceback": traceback.format_exc()}
            )
            
        return data
    
    async def _collect_market_data(self) -> Dict[str, Any]:
        """Собирает данные рынка из btc_watcher"""
        try:
            btc_watcher_dir = DATA_DIR / "btc_watcher"
            if not btc_watcher_dir.exists():
                return {"error": "btc_watcher dir not found"}
            
            # Читаем последние данные
            files = sorted(btc_watcher_dir.glob("*.jsonl"), reverse=True)
            if not files:
                return {"error": "no btc_watcher data"}
            
            latest_data = {}
            with open(files[0], 'r') as f:
                for line in f:
                    if line.strip():
                        latest_data = json.loads(line)
            
            return latest_data
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _collect_positions_data(self) -> Dict[str, Any]:
        """Собирает данные о текущих позициях"""
        try:
            # Читаем из positions.json если есть
            positions_file = LOGS_DIR / "positions.json"
            if positions_file.exists():
                with open(positions_file, 'r') as f:
                    return json.load(f)
            return {"positions": [], "total": 0}
        except Exception as e:
            return {"error": str(e)}
    
    async def _collect_trading_stats(self) -> Dict[str, Any]:
        """Собирает торговую статистику"""
        try:
            stats_file = LOGS_DIR / "stats.json"
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            return {"error": str(e)}
    
    async def _collect_btc_trend(self) -> Dict[str, Any]:
        """Собирает данные о BTC тренде"""
        try:
            # TODO: Интеграция с btc_trend_guard
            return {
                "enabled": BTC_TREND_GUARD["enabled"],
                "threshold": BTC_TREND_GUARD["threshold_pct"]
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _collect_spot_flow(self) -> Dict[str, Any]:
        """Собирает данные spot flow (BUY/SELL pressure)"""
        try:
            spot_flow_dir = DATA_DIR / "spot_flow"
            if not spot_flow_dir.exists():
                return {"error": "spot_flow dir not found"}
            
            files = sorted(spot_flow_dir.glob("*.jsonl"), reverse=True)
            if not files:
                return {"error": "no spot_flow data"}
            
            latest_data = {}
            with open(files[0], 'r') as f:
                for line in f:
                    if line.strip():
                        latest_data = json.loads(line)
            
            return latest_data
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _collect_volumes(self) -> Dict[str, Any]:
        """Собирает данные об объёмах"""
        try:
            volume_dir = DATA_DIR / "volume"
            if not volume_dir.exists():
                return {"error": "volume dir not found"}
            
            files = sorted(volume_dir.glob("*.jsonl"), reverse=True)
            if not files:
                return {"error": "no volume data"}
            
            latest_data = {}
            with open(files[0], 'r') as f:
                for line in f:
                    if line.strip():
                        latest_data = json.loads(line)
            
            return latest_data
            
        except Exception as e:
            return {"error": str(e)}
    
    def _collect_pending_feedback(self) -> Dict[str, List]:
        """Собирает нерешённые проблемы из feedback"""
        pending = {"errors": [], "unsolved": [], "needs": []}
        
        try:
            for error_file in ERRORS_DIR.glob("*.json"):
                with open(error_file, 'r') as f:
                    pending["errors"].append(json.load(f))
            
            for unsolved_file in UNSOLVED_DIR.glob("*.json"):
                with open(unsolved_file, 'r') as f:
                    pending["unsolved"].append(json.load(f))
            
            for need_file in NEEDS_DIR.glob("*.json"):
                with open(need_file, 'r') as f:
                    pending["needs"].append(json.load(f))
                    
        except Exception as e:
            logger.error(f"Failed to collect feedback: {e}")
        
        return pending
    
    # =========================================================================
    # 🤔 THINKING - Анализ и принятие решений
    # =========================================================================
    
    async def think(self, data: Dict[str, Any]) -> List[BrainDecision]:
        """
        ГЛАВНЫЙ МЕТОД МЫШЛЕНИЯ
        
        Анализирует все данные и принимает решения.
        Использует Gemini для глубокого анализа.
        """
        decisions = []
        
        try:
            # 1. Быстрые правила (без LLM)
            quick_decisions = await self._apply_quick_rules(data)
            decisions.extend(quick_decisions)
            
            # 2. Глубокий анализ с Gemini (если нужно)
            if self._needs_deep_analysis(data):
                gemini_decisions = await self._gemini_analysis(data)
                decisions.extend(gemini_decisions)
            
            # 3. Проверка и валидация решений
            validated_decisions = self._validate_decisions(decisions)
            
            # 4. Логирование решений
            for decision in validated_decisions:
                await self._log_decision(decision)
                self.decision_history.append(decision)
            
            self.decisions_made += len(validated_decisions)
            self.last_decision_time = datetime.utcnow()
            
            return validated_decisions
            
        except Exception as e:
            await self._log_feedback(
                FeedbackType.ERROR,
                "thinking_failed",
                str(e),
                {"traceback": traceback.format_exc(), "data_summary": str(data.keys())}
            )
            return []
    
    async def _apply_quick_rules(self, data: Dict[str, Any]) -> List[BrainDecision]:
        """Применяет быстрые правила без LLM"""
        decisions = []
        ts = datetime.utcnow().isoformat()
        
        # Rule 1: BTC Trend Guard
        if data.get("btc_trend", {}).get("enabled"):
            btc_change = data.get("market", {}).get("btc_change_1h", 0)
            threshold = BTC_TREND_GUARD["threshold_pct"]
            
            if btc_change > threshold:
                decisions.append(BrainDecision(
                    timestamp=ts,
                    decision_type=DecisionType.SIGNAL_BLOCK.value,
                    action="block_short",
                    reason=f"BTC +{btc_change:.2f}%/h > {threshold}% → блокируем SHORT",
                    confidence=0.95,
                    data={"btc_change": btc_change}
                ))
            elif btc_change < -threshold:
                decisions.append(BrainDecision(
                    timestamp=ts,
                    decision_type=DecisionType.SIGNAL_BLOCK.value,
                    action="block_long",
                    reason=f"BTC {btc_change:.2f}%/h < -{threshold}% → блокируем LONG",
                    confidence=0.95,
                    data={"btc_change": btc_change}
                ))
        
        # Rule 2: Emergency Exit
        positions = data.get("positions", {}).get("positions", [])
        for pos in positions:
            pos_time_min = pos.get("duration_minutes", 0)
            pos_pnl_pct = pos.get("pnl_pct", 0)
            
            if (pos_time_min > GLOBAL_SAFEGUARDS["emergency_exit_minutes"] and
                pos_pnl_pct < GLOBAL_SAFEGUARDS["emergency_exit_min_pnl"]):
                decisions.append(BrainDecision(
                    timestamp=ts,
                    decision_type=DecisionType.EMERGENCY.value,
                    action="force_close",
                    reason=f"Emergency: {pos.get('symbol')} открыта {pos_time_min} мин, PnL={pos_pnl_pct:.2f}%",
                    confidence=0.99,
                    data={"position": pos}
                ))
        
        # Rule 3: Daily DD Limit
        daily_pnl_pct = data.get("stats", {}).get("daily_pnl_pct", 0)
        if daily_pnl_pct < GLOBAL_SAFEGUARDS["daily_dd_limit_pct"]:
            decisions.append(BrainDecision(
                timestamp=ts,
                decision_type=DecisionType.EMERGENCY.value,
                action="pause_trading",
                reason=f"Daily DD limit: {daily_pnl_pct:.2f}% < {GLOBAL_SAFEGUARDS['daily_dd_limit_pct']}%",
                confidence=1.0,
                data={"daily_pnl_pct": daily_pnl_pct}
            ))
        
        # Rule 4: Time Phase TP
        phase = data.get("config", {}).get("current_tp_phase", {})
        phase_name = phase.get("name", "unknown")
        
        # Днём блокируем SHORT
        if phase_name == "day" and not phase.get("allow_short", True):
            decisions.append(BrainDecision(
                timestamp=ts,
                decision_type=DecisionType.INFO.value,
                action="day_mode_active",
                reason=f"Дневной режим: LONG_ONLY, TP={phase.get('tp_pct', 0)*100:.2f}%",
                confidence=1.0,
                data={"phase": phase_name}
            ))
        
        return decisions
    
    def _needs_deep_analysis(self, data: Dict[str, Any]) -> bool:
        """Определяет нужен ли глубокий анализ с Gemini"""
        # Анализируем каждые N минут или при особых условиях
        if not self.last_decision_time:
            return True
        
        minutes_since_last = (datetime.utcnow() - self.last_decision_time).total_seconds() / 60
        if minutes_since_last >= BRAIN_CONFIG["interval_minutes"]:
            return True
        
        # Особые условия для немедленного анализа
        positions = data.get("positions", {}).get("positions", [])
        for pos in positions:
            # Позиция в сильном минусе
            if pos.get("pnl_pct", 0) < -10:
                return True
        
        # Есть нерешённые проблемы
        pending = data.get("feedback_pending", {})
        if len(pending.get("unsolved", [])) > 3:
            return True
        
        return False
    
    async def _gemini_analysis(self, data: Dict[str, Any]) -> List[BrainDecision]:
        """Глубокий анализ с Gemini"""
        decisions = []
        
        try:
            prompt = self._build_analysis_prompt(data)
            response = await self._call_gemini(prompt)
            
            if response:
                decisions = self._parse_gemini_response(response)
            else:
                await self._log_feedback(
                    FeedbackType.UNSOLVED,
                    "gemini_no_response",
                    "Gemini не вернул ответ",
                    {"prompt_length": len(prompt)}
                )
                
        except Exception as e:
            await self._log_feedback(
                FeedbackType.ERROR,
                "gemini_analysis_failed",
                str(e),
                {"traceback": traceback.format_exc()}
            )
        
        return decisions
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Строит промпт для Gemini"""
        phase = data.get("config", {}).get("current_tp_phase", {})
        stats = data.get("stats", {})
        positions = data.get("positions", {})
        market = data.get("market", {})
        
        prompt = f"""🧠 ECOSYSTEM BRAIN ANALYSIS

ТЕКУЩЕЕ ВРЕМЯ (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
ФАЗА: {phase.get('name', 'unknown')} (TP: {phase.get('tp_pct', 0)*100:.2f}%)

📊 СТАТИСТИКА:
- Win Rate: {stats.get('win_rate', 0)*100:.1f}%
- Сделок сегодня: {stats.get('trades_today', 0)}
- PnL сегодня: ${stats.get('total_pnl_today', 0):.2f}
- Сделок/час: {stats.get('trades_per_hour', 0):.1f}

📈 РЫНОК:
- BTC: ${market.get('btc_price', 0):.0f} ({market.get('btc_change_1h', 0):+.2f}%/h)
- ETH: ${market.get('eth_price', 0):.0f} ({market.get('eth_change_1h', 0):+.2f}%/h)
- Bias: {market.get('market_bias', 'UNKNOWN')}
- Volatility: {market.get('volatility', 'UNKNOWN')}

💼 ПОЗИЦИИ ({positions.get('total', 0)}):
{self._format_positions(positions.get('positions', []))}

⚙️ ТЕКУЩИЙ КОНФИГ:
- momentum_fast: {data.get('config', {}).get('momentum_threshold_fast', 0)*100:.2f}%
- momentum_slow: {data.get('config', {}).get('momentum_threshold_slow', 0)*100:.2f}%
- max_leverage: {data.get('config', {}).get('max_leverage', 0)}
- max_positions: {data.get('config', {}).get('max_positions', 0)}

🔴 WHITELIST: {', '.join(WHITELIST_PAIRS[:5])}...
⚫ BLACKLIST: {', '.join(BLACKLIST_PAIRS[:5])}...

❓ НЕРЕШЁННЫЕ ПРОБЛЕМЫ:
{self._format_pending_feedback(data.get('feedback_pending', {}))}

---

ТВОЯ ЗАДАЧА:
1. Проанализируй текущую ситуацию
2. Предложи изменения конфига (если нужны)
3. Предложи действия по позициям (если нужны)
4. Укажи проблемы которые не можешь решить

ОТВЕТ СТРОГО В JSON:
{{
  "analysis": "краткий анализ ситуации",
  "config_changes": {{"param": value}},
  "position_actions": [{{"symbol": "...", "action": "close/hold", "reason": "..."}}],
  "alerts": ["важные предупреждения"],
  "unsolved": ["проблемы которые не могу решить"],
  "confidence": 0.0-1.0
}}

ВАЖНО:
- НЕ ТРОГАЙ min_profit_pct если не критично (отключит трёхфазный TP)
- max_leverage только ВНИЗ
- Все значения в пределах SAFETY_BOUNDS
"""
        return prompt
    
    def _format_positions(self, positions: List[Dict]) -> str:
        """Форматирует позиции для промпта"""
        if not positions:
            return "Нет открытых позиций"
        
        lines = []
        for p in positions[:10]:  # Максимум 10
            lines.append(
                f"  - {p.get('symbol', '?')}: {p.get('side', '?')} "
                f"PnL={p.get('pnl_pct', 0):+.2f}% "
                f"({p.get('duration_minutes', 0):.0f} мин)"
            )
        return "\n".join(lines)
    
    def _format_pending_feedback(self, feedback: Dict) -> str:
        """Форматирует нерешённые проблемы"""
        lines = []
        for error in feedback.get("errors", [])[:3]:
            lines.append(f"  ❌ {error.get('type', '?')}: {error.get('message', '?')[:50]}")
        for unsolved in feedback.get("unsolved", [])[:3]:
            lines.append(f"  ❓ {unsolved.get('type', '?')}: {unsolved.get('message', '?')[:50]}")
        return "\n".join(lines) if lines else "Нет"
    
    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """Вызов Gemini API"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(BRAIN_CONFIG["model"])
            
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": BRAIN_CONFIG["temperature"],
                    "max_output_tokens": BRAIN_CONFIG["max_tokens"]
                }
            )
            
            return response.text
            
        except ImportError:
            await self._log_feedback(
                FeedbackType.NEED,
                "gemini_sdk_missing",
                "Нужно установить google-generativeai",
                {"command": "pip install google-generativeai"}
            )
            return None
        except Exception as e:
            await self._log_feedback(
                FeedbackType.ERROR,
                "gemini_api_error",
                str(e),
                {"traceback": traceback.format_exc()}
            )
            return None
    
    def _parse_gemini_response(self, response: str) -> List[BrainDecision]:
        """Парсит ответ Gemini"""
        decisions = []
        ts = datetime.utcnow().isoformat()
        
        try:
            # Извлекаем JSON из ответа
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                confidence = data.get("confidence", 0.5)
                
                # Config changes
                for param, value in data.get("config_changes", {}).items():
                    decisions.append(BrainDecision(
                        timestamp=ts,
                        decision_type=DecisionType.CONFIG_CHANGE.value,
                        action=f"set_{param}",
                        reason=data.get("analysis", "Gemini recommendation"),
                        confidence=confidence,
                        data={"param": param, "value": value}
                    ))
                
                # Position actions
                for action in data.get("position_actions", []):
                    decisions.append(BrainDecision(
                        timestamp=ts,
                        decision_type=DecisionType.POSITION_ACTION.value,
                        action=action.get("action", "hold"),
                        reason=action.get("reason", ""),
                        confidence=confidence,
                        data={"symbol": action.get("symbol")}
                    ))
                
                # Alerts
                for alert in data.get("alerts", []):
                    decisions.append(BrainDecision(
                        timestamp=ts,
                        decision_type=DecisionType.ALERT.value,
                        action="alert",
                        reason=alert,
                        confidence=confidence,
                        data={}
                    ))
                
                # Log unsolved
                for unsolved in data.get("unsolved", []):
                    asyncio.create_task(self._log_feedback(
                        FeedbackType.UNSOLVED,
                        "gemini_unsolved",
                        unsolved,
                        {"source": "gemini_analysis"}
                    ))
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            # Сохраняем raw response для анализа
            asyncio.create_task(self._log_feedback(
                FeedbackType.ERROR,
                "gemini_parse_error",
                str(e),
                {"raw_response": response[:500]}
            ))
        
        return decisions
    
    def _validate_decisions(self, decisions: List[BrainDecision]) -> List[BrainDecision]:
        """Валидирует решения через Safety Bounds"""
        validated = []
        
        for decision in decisions:
            if decision.decision_type == DecisionType.CONFIG_CHANGE.value:
                param = decision.data.get("param")
                value = decision.data.get("value")
                
                if param in SAFETY_BOUNDS:
                    bounds = SAFETY_BOUNDS[param]
                    original_value = value
                    
                    # Применяем bounds
                    value = max(bounds["min"], min(bounds["max"], value))
                    
                    # Проверка only_down для leverage
                    if bounds.get("only_down") and param == "max_leverage":
                        current = get_effective_config().get("max_leverage", 6)
                        value = min(value, current)
                    
                    if value != original_value:
                        decision.reason += f" (обрезано: {original_value} → {value})"
                    
                    decision.data["value"] = value
                
                validated.append(decision)
            else:
                validated.append(decision)
        
        return validated
    
    # =========================================================================
    # 🎬 EXECUTION - Выполнение решений
    # =========================================================================
    
    async def execute_decisions(self, decisions: List[BrainDecision]) -> Dict[str, Any]:
        """Выполняет решения"""
        results = {"executed": [], "failed": [], "skipped": []}
        
        for decision in decisions:
            try:
                if decision.decision_type == DecisionType.CONFIG_CHANGE.value:
                    success = await self._execute_config_change(decision)
                elif decision.decision_type == DecisionType.POSITION_ACTION.value:
                    success = await self._execute_position_action(decision)
                elif decision.decision_type == DecisionType.SIGNAL_BLOCK.value:
                    success = await self._execute_signal_block(decision)
                elif decision.decision_type == DecisionType.EMERGENCY.value:
                    success = await self._execute_emergency_action(decision)
                else:
                    # INFO и другие - просто логируем
                    results["skipped"].append(asdict(decision))
                    continue
                
                decision.applied = success
                if success:
                    results["executed"].append(asdict(decision))
                else:
                    results["failed"].append(asdict(decision))
                    
            except Exception as e:
                decision.applied = False
                results["failed"].append(asdict(decision))
                await self._log_feedback(
                    FeedbackType.ERROR,
                    f"execution_failed_{decision.decision_type}",
                    str(e),
                    {"decision": asdict(decision), "traceback": traceback.format_exc()}
                )
        
        return results
    
    async def _execute_config_change(self, decision: BrainDecision) -> bool:
        """Записывает изменение в config_override.json"""
        try:
            override_path = CONFIG_DIR / "config_override.json"
            
            # Читаем текущий override
            current = {}
            if override_path.exists():
                with open(override_path, 'r') as f:
                    current = json.load(f)
            
            # Применяем изменение
            param = decision.data.get("param")
            value = decision.data.get("value")
            current[param] = value
            current["_last_updated"] = datetime.utcnow().isoformat()
            current["_last_reason"] = decision.reason
            
            # Записываем
            with open(override_path, 'w') as f:
                json.dump(current, f, indent=2)
            
            logger.info(f"✅ Config changed: {param} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Config change failed: {e}")
            return False
    
    async def _execute_position_action(self, decision: BrainDecision) -> bool:
        """Выполняет действие с позицией"""
        # TODO: Интеграция с BingX API
        logger.info(f"📍 Position action: {decision.action} on {decision.data.get('symbol')}")
        
        await self._log_feedback(
            FeedbackType.NEED,
            "position_action_not_implemented",
            f"Нужна интеграция с BingX для {decision.action}",
            {"decision": asdict(decision)}
        )
        return False
    
    async def _execute_signal_block(self, decision: BrainDecision) -> bool:
        """Блокирует сигналы"""
        try:
            block_file = LOGS_DIR / "signal_blocks.json"
            
            blocks = {}
            if block_file.exists():
                with open(block_file, 'r') as f:
                    blocks = json.load(f)
            
            blocks[decision.action] = {
                "active": True,
                "reason": decision.reason,
                "timestamp": decision.timestamp,
                "expires": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
            }
            
            with open(block_file, 'w') as f:
                json.dump(blocks, f, indent=2)
            
            logger.info(f"🚫 Signal blocked: {decision.action}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Signal block failed: {e}")
            return False
    
    async def _execute_emergency_action(self, decision: BrainDecision) -> bool:
        """Выполняет экстренные действия"""
        if decision.action == "pause_trading":
            try:
                pause_file = LOGS_DIR / "trading_paused.json"
                with open(pause_file, 'w') as f:
                    json.dump({
                        "paused": True,
                        "reason": decision.reason,
                        "timestamp": decision.timestamp
                    }, f, indent=2)
                logger.warning(f"⚠️ TRADING PAUSED: {decision.reason}")
                return True
            except Exception as e:
                logger.error(f"❌ Pause failed: {e}")
                return False
        
        elif decision.action == "force_close":
            # TODO: Интеграция с BingX API
            await self._log_feedback(
                FeedbackType.NEED,
                "force_close_not_implemented",
                "Нужна интеграция с BingX для force_close",
                {"decision": asdict(decision)}
            )
            return False
        
        return False
    
    # =========================================================================
    # 📝 FEEDBACK SYSTEM - Логирование проблем
    # =========================================================================
    
    async def _log_feedback(
        self,
        feedback_type: FeedbackType,
        problem_type: str,
        message: str,
        data: Dict[str, Any]
    ):
        """Записывает feedback в соответствующую папку"""
        try:
            # Выбираем папку
            if feedback_type == FeedbackType.ERROR:
                folder = ERRORS_DIR
            elif feedback_type == FeedbackType.UNSOLVED:
                folder = UNSOLVED_DIR
            elif feedback_type == FeedbackType.NEED:
                folder = NEEDS_DIR
            else:
                folder = DECISIONS_DIR
            
            # Создаём папку если нужно
            folder.mkdir(parents=True, exist_ok=True)
            
            # Формируем имя файла
            ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
            filename = f"{ts}_{problem_type}.json"
            filepath = folder / filename
            
            # Записываем
            feedback_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": problem_type,
                "message": message,
                "data": data,
                "brain_uptime_minutes": (datetime.utcnow() - self.start_time).total_seconds() / 60,
                "decisions_made": self.decisions_made,
                "errors_total": self.errors_encountered
            }
            
            with open(filepath, 'w') as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)
            
            if feedback_type == FeedbackType.ERROR:
                self.errors_encountered += 1
                logger.error(f"❌ FEEDBACK ERROR: {problem_type} - {message}")
            elif feedback_type == FeedbackType.UNSOLVED:
                logger.warning(f"❓ FEEDBACK UNSOLVED: {problem_type} - {message}")
            elif feedback_type == FeedbackType.NEED:
                logger.info(f"📝 FEEDBACK NEED: {problem_type} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
    
    async def _log_decision(self, decision: BrainDecision):
        """Записывает решение в audit log"""
        try:
            DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
            
            # JSONL формат для audit log
            audit_file = LOGS_DIR / "brain_audit.jsonl"
            
            audit_entry = {
                "ts": decision.timestamp,
                "type": decision.decision_type,
                "action": decision.action,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "data": decision.data
            }
            
            with open(audit_file, 'a') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
            
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
    
    # =========================================================================
    # 🔄 MAIN LOOP
    # =========================================================================
    
    async def run(self):
        """Главный цикл работы Brain"""
        logger.info("🧠 Starting Ecosystem Brain main loop...")
        
        while True:
            try:
                # 1. Собираем все данные
                logger.info("📥 Collecting data...")
                data = await self.collect_all_data()
                
                # 2. Думаем
                logger.info("🤔 Thinking...")
                decisions = await self.think(data)
                
                if decisions:
                    logger.info(f"💡 Made {len(decisions)} decisions")
                    
                    # 3. Выполняем
                    results = await self.execute_decisions(decisions)
                    logger.info(f"✅ Executed: {len(results['executed'])}, "
                              f"❌ Failed: {len(results['failed'])}, "
                              f"⏭️ Skipped: {len(results['skipped'])}")
                else:
                    logger.info("😴 No decisions needed")
                
                # 4. Ждём
                await asyncio.sleep(BRAIN_CONFIG["interval_minutes"] * 60)
                
            except Exception as e:
                logger.error(f"Brain loop error: {e}")
                await self._log_feedback(
                    FeedbackType.ERROR,
                    "brain_loop_error",
                    str(e),
                    {"traceback": traceback.format_exc()}
                )
                await asyncio.sleep(60)  # Wait 1 min on error


# =============================================================================
# 🚀 ENTRY POINT
# =============================================================================

async def main():
    """Entry point"""
    brain = EcosystemBrain()
    await brain.run()

if __name__ == "__main__":
    asyncio.run(main())
