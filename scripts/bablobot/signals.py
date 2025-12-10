"""
📡 SIGNAL ENGINE - ГЕНЕРАЦИЯ ТОРГОВЫХ СИГНАЛОВ
=============================================
Анализирует данные и генерирует сигналы LONG/SHORT.

Модули:
1. Momentum Detector - импульсные сигналы
2. BTC Trend Guard - блокировка по тренду BTC
3. Spot Flow Signals - сигналы по давлению покупок/продаж
4. Time Phase Filter - фильтрация по времени суток

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import json
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import (
    get_effective_config, get_current_tp_phase, 
    BTC_TREND_GUARD, DEFAULT_PAIRS, WHITELIST_PAIRS, BLACKLIST_PAIRS,
    DATA_DIR, LOGS_DIR
)

# =============================================================================
# 📊 SIGNAL TYPES
# =============================================================================

class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class SignalStrength(Enum):
    WEAK = 0.3
    MEDIUM = 0.6
    STRONG = 0.9

@dataclass
class Signal:
    """Торговый сигнал"""
    timestamp: str
    symbol: str
    signal_type: SignalType
    strength: float  # 0-1
    source: str  # momentum, spot_flow, etc.
    reason: str
    data: Dict[str, Any]
    blocked: bool = False
    block_reason: str = ""

# =============================================================================
# 🚦 BTC TREND GUARD
# =============================================================================

class BTCTrendGuard:
    """
    BTC TREND GUARD - блокирует сигналы по тренду BTC
    
    - BTC +1.5%/час → блокируем SHORT
    - BTC -1.5%/час → блокируем LONG
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = BTC_TREND_GUARD.get("cache_seconds", 60)
        self.threshold = BTC_TREND_GUARD.get("threshold_pct", 1.5)
        self.enabled = BTC_TREND_GUARD.get("enabled", True)
    
    async def get_btc_trend(self) -> Tuple[float, str]:
        """
        Получает текущий тренд BTC
        
        Returns:
            Tuple[change_pct, trend]: (изменение за час, тренд)
        """
        # Проверяем кеш
        if self.cache.get("btc_trend"):
            cache_time = self.cache.get("cache_time", 0)
            if time.time() - cache_time < self.cache_ttl:
                return self.cache["btc_trend"], self.cache["trend_direction"]
        
        try:
            # Читаем из btc_watcher данных
            btc_file = DATA_DIR / "btc_watcher" / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
            
            if btc_file.exists():
                with open(btc_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        if last_line:
                            data = json.loads(last_line)
                            change_1h = data.get("btc_change_1h", 0)
                            
                            # Определяем направление тренда
                            if change_1h > self.threshold:
                                trend = "BULLISH"
                            elif change_1h < -self.threshold:
                                trend = "BEARISH"
                            else:
                                trend = "NEUTRAL"
                            
                            # Кешируем
                            self.cache["btc_trend"] = change_1h
                            self.cache["trend_direction"] = trend
                            self.cache["cache_time"] = time.time()
                            
                            return change_1h, trend
            
            return 0.0, "UNKNOWN"
            
        except Exception as e:
            logger.error(f"BTCTrendGuard error: {e}")
            return 0.0, "ERROR"
    
    def is_blocked_by_btc_trend(self, signal_type: SignalType) -> Tuple[bool, str]:
        """
        Проверяет заблокирован ли сигнал трендом BTC
        
        Returns:
            Tuple[blocked, reason]
        """
        if not self.enabled:
            return False, ""
        
        btc_change = self.cache.get("btc_trend", 0)
        trend = self.cache.get("trend_direction", "UNKNOWN")
        
        # BTC растёт - блокируем SHORT
        if trend == "BULLISH" and signal_type == SignalType.SHORT:
            return True, f"BTC +{btc_change:.2f}%/h > {self.threshold}% → SHORT blocked"
        
        # BTC падает - блокируем LONG
        if trend == "BEARISH" and signal_type == SignalType.LONG:
            return True, f"BTC {btc_change:.2f}%/h < -{self.threshold}% → LONG blocked"
        
        return False, ""


# =============================================================================
# 📈 MOMENTUM DETECTOR
# =============================================================================

class MomentumDetector:
    """
    Детектор импульсных сигналов
    
    Fast: >0.18% за 15 секунд
    Slow: >0.12% за 60 секунд
    """
    
    def __init__(self):
        self.price_cache: Dict[str, List[Tuple[float, float]]] = {}  # symbol: [(timestamp, price)]
        self.max_history = 120  # 2 минуты истории
    
    def add_price(self, symbol: str, price: float):
        """Добавляет цену в историю"""
        if symbol not in self.price_cache:
            self.price_cache[symbol] = []
        
        self.price_cache[symbol].append((time.time(), price))
        
        # Очищаем старые данные
        cutoff = time.time() - self.max_history
        self.price_cache[symbol] = [
            (t, p) for t, p in self.price_cache[symbol] if t > cutoff
        ]
    
    def detect_momentum(self, symbol: str) -> Optional[Signal]:
        """Детектирует импульс"""
        config = get_effective_config()
        fast_threshold = config.get("momentum_threshold_fast", 0.0018)
        slow_threshold = config.get("momentum_threshold_slow", 0.0012)
        
        prices = self.price_cache.get(symbol, [])
        if len(prices) < 2:
            return None
        
        current_time, current_price = prices[-1]
        
        # Fast momentum (15s)
        fast_change = self._calc_change(prices, 15)
        if abs(fast_change) >= fast_threshold * 100:
            signal_type = SignalType.LONG if fast_change > 0 else SignalType.SHORT
            return Signal(
                timestamp=datetime.utcnow().isoformat(),
                symbol=symbol,
                signal_type=signal_type,
                strength=min(abs(fast_change) / (fast_threshold * 100 * 2), 1.0),
                source="momentum_fast",
                reason=f"Fast momentum: {fast_change:+.3f}% in 15s",
                data={"change_pct": fast_change, "window": 15}
            )
        
        # Slow momentum (60s)
        slow_change = self._calc_change(prices, 60)
        if abs(slow_change) >= slow_threshold * 100:
            signal_type = SignalType.LONG if slow_change > 0 else SignalType.SHORT
            return Signal(
                timestamp=datetime.utcnow().isoformat(),
                symbol=symbol,
                signal_type=signal_type,
                strength=min(abs(slow_change) / (slow_threshold * 100 * 2), 1.0) * 0.8,
                source="momentum_slow",
                reason=f"Slow momentum: {slow_change:+.3f}% in 60s",
                data={"change_pct": slow_change, "window": 60}
            )
        
        return None
    
    def _calc_change(self, prices: List[Tuple[float, float]], window_seconds: int) -> float:
        """Рассчитывает изменение за период"""
        if not prices:
            return 0.0
        
        current_time, current_price = prices[-1]
        cutoff = current_time - window_seconds
        
        old_prices = [(t, p) for t, p in prices if t <= cutoff]
        if not old_prices:
            return 0.0
        
        _, old_price = old_prices[-1]
        
        if old_price == 0:
            return 0.0
        
        return ((current_price - old_price) / old_price) * 100


# =============================================================================
# 💰 SPOT FLOW SIGNALS
# =============================================================================

class SpotFlowSignals:
    """
    Сигналы на основе BUY/SELL pressure
    
    BUY pressure > 60% → LONG signal
    SELL pressure > 60% → SHORT signal
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 120  # 2 minutes
    
    async def get_spot_flow_signal(self, symbol: str) -> Optional[Signal]:
        """Получает сигнал по spot flow"""
        try:
            # Читаем последние данные spot_flow
            today = datetime.utcnow().strftime("%Y-%m-%d")
            flow_file = DATA_DIR / "spot_flow" / f"{today}.jsonl"
            
            if not flow_file.exists():
                return None
            
            with open(flow_file, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return None
                
                last_line = lines[-1].strip()
                if not last_line:
                    return None
                
                data = json.loads(last_line)
            
            pairs_data = data.get("pairs", {})
            pair_flow = pairs_data.get(symbol, {})
            
            if not pair_flow:
                return None
            
            buy_pct = pair_flow.get("buy_pct", 50)
            sell_pct = pair_flow.get("sell_pct", 50)
            pressure = pair_flow.get("pressure", "NEUTRAL")
            
            # Генерируем сигнал
            if pressure == "BUY_PRESSURE" and buy_pct > 65:
                return Signal(
                    timestamp=datetime.utcnow().isoformat(),
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=min((buy_pct - 50) / 50, 1.0),
                    source="spot_flow",
                    reason=f"BUY pressure: {buy_pct:.1f}%",
                    data={"buy_pct": buy_pct, "sell_pct": sell_pct}
                )
            
            elif pressure == "SELL_PRESSURE" and sell_pct > 65:
                return Signal(
                    timestamp=datetime.utcnow().isoformat(),
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=min((sell_pct - 50) / 50, 1.0),
                    source="spot_flow",
                    reason=f"SELL pressure: {sell_pct:.1f}%",
                    data={"buy_pct": buy_pct, "sell_pct": sell_pct}
                )
            
            return None
            
        except Exception as e:
            logger.error(f"SpotFlowSignals error: {e}")
            return None


# =============================================================================
# ⏰ TIME PHASE FILTER
# =============================================================================

class TimePhaseFilter:
    """
    Фильтрация сигналов по времени суток
    
    - Ночь (00-08 UTC): AGGRESSIVE, LONG+SHORT
    - День (08-16 UTC): LONG_ONLY, БЕЗ SHORT!
    - Вечер (16-24 UTC): CONSERVATIVE, spread>0.25%
    """
    
    def filter_by_time_phase(self, signal: Signal) -> Signal:
        """Применяет фильтр по времени"""
        phase = get_current_tp_phase()
        phase_name = phase.get("name", "unknown")
        
        # Днём блокируем SHORT
        if phase_name == "day" and signal.signal_type == SignalType.SHORT:
            signal.blocked = True
            signal.block_reason = "Day phase: SHORT blocked (LONG_ONLY mode)"
        
        # Вечером снижаем силу сигнала
        if phase_name == "evening":
            signal.strength *= 0.75
        
        # Ночью усиливаем
        if phase_name == "night":
            signal.strength = min(signal.strength * 1.25, 1.0)
        
        return signal


# =============================================================================
# 🎯 SIGNAL ENGINE
# =============================================================================

class SignalEngine:
    """
    ГЛАВНЫЙ ДВИЖОК СИГНАЛОВ
    
    Объединяет все детекторы и фильтры.
    """
    
    def __init__(self):
        self.btc_guard = BTCTrendGuard()
        self.momentum = MomentumDetector()
        self.spot_flow = SpotFlowSignals()
        self.time_filter = TimePhaseFilter()
        
        # Cooldowns
        self.signal_cooldowns: Dict[str, float] = {}  # symbol: last_signal_time
        self.cooldown_seconds = 60
        
        # Blocks from Brain
        self.signal_blocks: Dict[str, Dict] = {}
        self._load_signal_blocks()
        
        logger.info("🎯 SignalEngine initialized")
    
    def _load_signal_blocks(self):
        """Загружает блокировки сигналов от Brain"""
        try:
            blocks_file = LOGS_DIR / "signal_blocks.json"
            if blocks_file.exists():
                with open(blocks_file, 'r') as f:
                    self.signal_blocks = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load signal blocks: {e}")
    
    async def process_price_update(self, symbol: str, price: float) -> Optional[Signal]:
        """
        Обрабатывает обновление цены и генерирует сигнал
        
        Args:
            symbol: Торговая пара
            price: Текущая цена
        
        Returns:
            Signal если есть, иначе None
        """
        # Добавляем цену в историю
        self.momentum.add_price(symbol, price)
        
        # Проверяем cooldown
        if not self._check_cooldown(symbol):
            return None
        
        # Проверяем blacklist
        if symbol in BLACKLIST_PAIRS:
            return None
        
        signals = []
        
        # 1. Momentum signal
        momentum_signal = self.momentum.detect_momentum(symbol)
        if momentum_signal:
            signals.append(momentum_signal)
        
        # 2. Spot Flow signal (для whitelist пар)
        if symbol in WHITELIST_PAIRS:
            spot_signal = await self.spot_flow.get_spot_flow_signal(symbol)
            if spot_signal:
                signals.append(spot_signal)
        
        if not signals:
            return None
        
        # Выбираем лучший сигнал
        best_signal = max(signals, key=lambda s: s.strength)
        
        # Применяем фильтры
        best_signal = await self._apply_filters(best_signal)
        
        # Обновляем cooldown
        if not best_signal.blocked:
            self.signal_cooldowns[symbol] = time.time()
        
        return best_signal
    
    async def _apply_filters(self, signal: Signal) -> Signal:
        """Применяет все фильтры к сигналу"""
        
        # 1. BTC Trend Guard
        await self.btc_guard.get_btc_trend()  # Обновляем кеш
        blocked, reason = self.btc_guard.is_blocked_by_btc_trend(signal.signal_type)
        if blocked:
            signal.blocked = True
            signal.block_reason = reason
            return signal
        
        # 2. Time Phase Filter
        signal = self.time_filter.filter_by_time_phase(signal)
        if signal.blocked:
            return signal
        
        # 3. Brain blocks
        self._load_signal_blocks()
        
        if signal.signal_type == SignalType.LONG:
            block = self.signal_blocks.get("block_long", {})
        else:
            block = self.signal_blocks.get("block_short", {})
        
        if block.get("active"):
            expires = block.get("expires", "")
            if expires and datetime.fromisoformat(expires) > datetime.utcnow():
                signal.blocked = True
                signal.block_reason = f"Brain blocked: {block.get('reason', 'unknown')}"
        
        return signal
    
    def _check_cooldown(self, symbol: str) -> bool:
        """Проверяет cooldown для пары"""
        last_signal = self.signal_cooldowns.get(symbol, 0)
        return time.time() - last_signal >= self.cooldown_seconds
    
    async def scan_all_pairs(self, prices: Dict[str, float]) -> List[Signal]:
        """
        Сканирует все пары и возвращает сигналы
        
        Args:
            prices: Dict[symbol, price]
        
        Returns:
            List[Signal] - все активные сигналы
        """
        signals = []
        
        for symbol, price in prices.items():
            signal = await self.process_price_update(symbol, price)
            if signal and not signal.blocked:
                signals.append(signal)
        
        # Сортируем по силе
        signals.sort(key=lambda s: s.strength, reverse=True)
        
        return signals
    
    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус движка"""
        return {
            "btc_trend": {
                "change": self.btc_guard.cache.get("btc_trend", 0),
                "direction": self.btc_guard.cache.get("trend_direction", "UNKNOWN")
            },
            "time_phase": get_current_tp_phase(),
            "cooldowns_active": len([
                s for s, t in self.signal_cooldowns.items()
                if time.time() - t < self.cooldown_seconds
            ]),
            "signal_blocks": self.signal_blocks,
            "pairs_tracked": len(self.momentum.price_cache)
        }


# =============================================================================
# 🚀 USAGE EXAMPLE
# =============================================================================

async def demo():
    """Демо работы Signal Engine"""
    engine = SignalEngine()
    
    # Симулируем обновления цен
    prices = {
        "ETH-USDT": 3500.0,
        "SOL-USDT": 220.0,
        "WIF-USDT": 3.5,
    }
    
    # Первый прогон
    for symbol, price in prices.items():
        engine.momentum.add_price(symbol, price)
    
    # Симулируем движение
    await asyncio.sleep(1)
    prices["ETH-USDT"] *= 1.002  # +0.2%
    prices["WIF-USDT"] *= 1.005  # +0.5%
    
    signals = await engine.scan_all_pairs(prices)
    
    for signal in signals:
        print(f"📡 {signal.symbol}: {signal.signal_type.value} "
              f"(strength={signal.strength:.2f}, source={signal.source})")
        if signal.blocked:
            print(f"   ⛔ BLOCKED: {signal.block_reason}")
    
    print("\n📊 Engine status:", engine.get_status())


if __name__ == "__main__":
    asyncio.run(demo())
