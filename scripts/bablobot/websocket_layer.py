"""
🌐 WEBSOCKET LAYER - REAL-TIME ДАННЫЕ
=====================================
WebSocket подключение к BingX для получения данных в реальном времени.

Потоки:
1. Ticker Stream - цены всех пар каждые 100ms
2. Trades Stream - сделки в реальном времени
3. Depth Stream - стакан ордеров (опционально)

УРОВЕНЬ 2 ЭКОСИСТЕМЫ:
- Brain видит каждый тик
- Brain может блокировать сигналы мгновенно
- Минимальная задержка

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import os
import sys
import json
import time
import asyncio
import websockets
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Coroutine
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import DEFAULT_PAIRS, DATA_DIR, LOGS_DIR

# =============================================================================
# 📊 DATA STRUCTURES
# =============================================================================

@dataclass
class TickData:
    """Тик данные"""
    symbol: str
    price: float
    timestamp: int
    volume_24h: float = 0
    change_24h: float = 0

@dataclass
class TradeData:
    """Данные сделки"""
    symbol: str
    price: float
    quantity: float
    side: str  # BUY / SELL
    timestamp: int

# =============================================================================
# 🌐 BINGX WEBSOCKET CLIENT
# =============================================================================

class BingXWebSocket:
    """
    WebSocket клиент для BingX
    
    Подключается к потокам данных и вызывает callbacks.
    """
    
    WS_URL = "wss://open-api-swap.bingx.com/swap-market"
    
    def __init__(self, pairs: List[str] = None):
        self.pairs = pairs or DEFAULT_PAIRS
        self.ws = None
        self.running = False
        
        # Callbacks
        self.on_tick: Optional[Callable[[TickData], Coroutine]] = None
        self.on_trade: Optional[Callable[[TradeData], Coroutine]] = None
        self.on_error: Optional[Callable[[Exception], Coroutine]] = None
        
        # Stats
        self.messages_received = 0
        self.last_message_time = None
        self.reconnect_count = 0
        
        logger.info(f"🌐 BingXWebSocket initialized for {len(self.pairs)} pairs")
    
    async def connect(self):
        """Подключается к WebSocket"""
        self.running = True
        
        while self.running:
            try:
                async with websockets.connect(self.WS_URL, ping_interval=20) as ws:
                    self.ws = ws
                    logger.info("✅ WebSocket connected")
                    
                    # Подписываемся на потоки
                    await self._subscribe()
                    
                    # Обрабатываем сообщения
                    await self._handle_messages()
                    
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self.on_error:
                    await self.on_error(e)
                
                self.reconnect_count += 1
                logger.info(f"Reconnecting in 5s... (attempt {self.reconnect_count})")
                await asyncio.sleep(5)
    
    async def _subscribe(self):
        """Подписывается на потоки данных"""
        # Подписка на тикеры
        for pair in self.pairs:
            # Ticker stream
            ticker_sub = {
                "id": f"ticker_{pair}",
                "reqType": "sub",
                "dataType": f"{pair}@ticker"
            }
            await self.ws.send(json.dumps(ticker_sub))
            
            # Trades stream (опционально, для spot flow)
            trades_sub = {
                "id": f"trades_{pair}",
                "reqType": "sub",
                "dataType": f"{pair}@trade"
            }
            await self.ws.send(json.dumps(trades_sub))
            
            await asyncio.sleep(0.1)  # Небольшая задержка между подписками
        
        logger.info(f"📡 Subscribed to {len(self.pairs) * 2} streams")
    
    async def _handle_messages(self):
        """Обрабатывает входящие сообщения"""
        async for message in self.ws:
            try:
                # BingX отправляет gzip сжатые данные
                if isinstance(message, bytes):
                    message = gzip.decompress(message).decode('utf-8')
                
                data = json.loads(message)
                
                # Pong на ping
                if data.get("ping"):
                    await self.ws.send(json.dumps({"pong": data["ping"]}))
                    continue
                
                # Обрабатываем данные
                await self._process_message(data)
                
                self.messages_received += 1
                self.last_message_time = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Message processing error: {e}")
    
    async def _process_message(self, data: Dict[str, Any]):
        """Обрабатывает сообщение по типу"""
        data_type = data.get("dataType", "")
        
        # Ticker data
        if "@ticker" in data_type:
            await self._handle_ticker(data)
        
        # Trade data
        elif "@trade" in data_type:
            await self._handle_trade(data)
    
    async def _handle_ticker(self, data: Dict[str, Any]):
        """Обрабатывает тикер"""
        try:
            ticker = data.get("data", {})
            
            tick = TickData(
                symbol=ticker.get("s", ""),
                price=float(ticker.get("c", 0)),  # Close price
                timestamp=int(ticker.get("E", 0)),
                volume_24h=float(ticker.get("v", 0)),
                change_24h=float(ticker.get("P", 0))
            )
            
            if self.on_tick and tick.price > 0:
                await self.on_tick(tick)
                
        except Exception as e:
            logger.error(f"Ticker handling error: {e}")
    
    async def _handle_trade(self, data: Dict[str, Any]):
        """Обрабатывает сделку"""
        try:
            trades = data.get("data", [])
            if not isinstance(trades, list):
                trades = [trades]
            
            for t in trades:
                trade = TradeData(
                    symbol=t.get("s", ""),
                    price=float(t.get("p", 0)),
                    quantity=float(t.get("q", 0)),
                    side="BUY" if t.get("m") == False else "SELL",
                    timestamp=int(t.get("T", 0))
                )
                
                if self.on_trade and trade.price > 0:
                    await self.on_trade(trade)
                    
        except Exception as e:
            logger.error(f"Trade handling error: {e}")
    
    async def disconnect(self):
        """Отключается от WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()
        logger.info("🔌 WebSocket disconnected")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        return {
            "connected": self.ws is not None and not self.ws.closed if self.ws else False,
            "messages_received": self.messages_received,
            "last_message": self.last_message_time.isoformat() if self.last_message_time else None,
            "reconnect_count": self.reconnect_count,
            "pairs_count": len(self.pairs)
        }


# =============================================================================
# 📈 REAL-TIME DATA PROCESSOR
# =============================================================================

class RealTimeDataProcessor:
    """
    Обработчик real-time данных
    
    - Агрегирует тики
    - Детектирует паттерны
    - Вызывает Signal Engine
    """
    
    def __init__(self):
        self.ticks: Dict[str, List[TickData]] = {}  # symbol: [ticks]
        self.trades: Dict[str, List[TradeData]] = {}  # symbol: [trades]
        self.max_ticks = 1000  # Максимум тиков на пару
        self.max_trades = 500
        
        # Callbacks
        self.on_price_update: Optional[Callable[[str, float], Coroutine]] = None
        self.on_volume_spike: Optional[Callable[[str, float], Coroutine]] = None
        self.on_price_spike: Optional[Callable[[str, float, str], Coroutine]] = None
        
        # Thresholds
        self.volume_spike_threshold = 2.0  # 2x average
        self.price_spike_threshold = 0.5  # 0.5% за секунду
        
        logger.info("📊 RealTimeDataProcessor initialized")
    
    async def process_tick(self, tick: TickData):
        """Обрабатывает тик"""
        symbol = tick.symbol
        
        # Добавляем в историю
        if symbol not in self.ticks:
            self.ticks[symbol] = []
        
        self.ticks[symbol].append(tick)
        
        # Обрезаем историю
        if len(self.ticks[symbol]) > self.max_ticks:
            self.ticks[symbol] = self.ticks[symbol][-self.max_ticks:]
        
        # Вызываем callback
        if self.on_price_update:
            await self.on_price_update(symbol, tick.price)
        
        # Детектим спайки
        await self._detect_price_spike(symbol)
    
    async def process_trade(self, trade: TradeData):
        """Обрабатывает сделку"""
        symbol = trade.symbol
        
        # Добавляем в историю
        if symbol not in self.trades:
            self.trades[symbol] = []
        
        self.trades[symbol].append(trade)
        
        # Обрезаем историю
        if len(self.trades[symbol]) > self.max_trades:
            self.trades[symbol] = self.trades[symbol][-self.max_trades:]
        
        # Детектим спайки объёма
        await self._detect_volume_spike(symbol)
    
    async def _detect_price_spike(self, symbol: str):
        """Детектирует резкое движение цены"""
        ticks = self.ticks.get(symbol, [])
        if len(ticks) < 10:
            return
        
        # Последняя секунда
        now = time.time() * 1000
        recent = [t for t in ticks if now - t.timestamp < 1000]
        
        if len(recent) < 2:
            return
        
        first_price = recent[0].price
        last_price = recent[-1].price
        
        if first_price == 0:
            return
        
        change_pct = abs((last_price - first_price) / first_price) * 100
        direction = "UP" if last_price > first_price else "DOWN"
        
        if change_pct >= self.price_spike_threshold:
            if self.on_price_spike:
                await self.on_price_spike(symbol, change_pct, direction)
    
    async def _detect_volume_spike(self, symbol: str):
        """Детектирует спайк объёма"""
        trades = self.trades.get(symbol, [])
        if len(trades) < 50:
            return
        
        # Средний объём за последние 50 сделок
        avg_volume = sum(t.quantity for t in trades[-50:-10]) / 40 if len(trades) > 50 else 0
        
        # Текущий объём за последние 10 сделок
        recent_volume = sum(t.quantity for t in trades[-10:]) / 10 if trades else 0
        
        if avg_volume > 0 and recent_volume > avg_volume * self.volume_spike_threshold:
            if self.on_volume_spike:
                await self.on_volume_spike(symbol, recent_volume / avg_volume)
    
    def get_recent_prices(self, symbol: str, count: int = 100) -> List[float]:
        """Возвращает последние цены"""
        ticks = self.ticks.get(symbol, [])
        return [t.price for t in ticks[-count:]]
    
    def get_buy_sell_ratio(self, symbol: str, seconds: int = 60) -> Tuple[float, float]:
        """Возвращает соотношение BUY/SELL"""
        trades = self.trades.get(symbol, [])
        now = time.time() * 1000
        recent = [t for t in trades if now - t.timestamp < seconds * 1000]
        
        if not recent:
            return 50.0, 50.0
        
        buy_volume = sum(t.quantity for t in recent if t.side == "BUY")
        sell_volume = sum(t.quantity for t in recent if t.side == "SELL")
        total = buy_volume + sell_volume
        
        if total == 0:
            return 50.0, 50.0
        
        return (buy_volume / total) * 100, (sell_volume / total) * 100


# Импорт Tuple для type hints
from typing import Tuple


# =============================================================================
# 🎯 REAL-TIME SIGNAL ENGINE
# =============================================================================

class RealTimeSignalEngine:
    """
    Signal Engine с real-time данными
    
    УРОВЕНЬ 2: Brain видит каждый тик и может мгновенно реагировать
    """
    
    def __init__(self):
        self.ws = BingXWebSocket()
        self.processor = RealTimeDataProcessor()
        
        # Импортируем Signal Engine
        from scripts.bablobot.signals import SignalEngine, Signal, SignalType
        self.signal_engine = SignalEngine()
        
        # Callbacks
        self.on_signal: Optional[Callable[[Signal], Coroutine]] = None
        
        # Setup callbacks
        self.ws.on_tick = self._on_tick
        self.ws.on_trade = self._on_trade
        self.processor.on_price_spike = self._on_price_spike
        self.processor.on_volume_spike = self._on_volume_spike
        
        logger.info("🎯 RealTimeSignalEngine initialized")
    
    async def _on_tick(self, tick: TickData):
        """Обрабатывает тик"""
        await self.processor.process_tick(tick)
        
        # Передаём в Signal Engine
        signal = await self.signal_engine.process_price_update(tick.symbol, tick.price)
        
        if signal and not signal.blocked and self.on_signal:
            await self.on_signal(signal)
    
    async def _on_trade(self, trade: TradeData):
        """Обрабатывает сделку"""
        await self.processor.process_trade(trade)
    
    async def _on_price_spike(self, symbol: str, change_pct: float, direction: str):
        """Обрабатывает спайк цены"""
        logger.warning(f"⚡ Price spike: {symbol} {change_pct:+.2f}% {direction}")
        
        # Можно генерировать экстренный сигнал
        # TODO: Интеграция с Brain для быстрой реакции
    
    async def _on_volume_spike(self, symbol: str, multiplier: float):
        """Обрабатывает спайк объёма"""
        logger.info(f"📊 Volume spike: {symbol} x{multiplier:.1f}")
        
        # Объём растёт = подтверждение движения
        # TODO: Усиление сигналов при высоком объёме
    
    async def start(self):
        """Запускает real-time engine"""
        logger.info("🚀 Starting RealTimeSignalEngine...")
        await self.ws.connect()
    
    async def stop(self):
        """Останавливает"""
        await self.ws.disconnect()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        return {
            "websocket": self.ws.get_stats(),
            "signal_engine": self.signal_engine.get_status(),
            "pairs_with_data": len(self.processor.ticks)
        }


# =============================================================================
# 📝 LAG DATA LOGGER
# =============================================================================

class LagDataLogger:
    """
    Логгер данных для анализа лага
    
    Сохраняет raw WebSocket данные для последующего анализа
    """
    
    def __init__(self):
        self.output_dir = DATA_DIR / "lag_data"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.messages_logged = 0
    
    async def log(self, data: Dict[str, Any]):
        """Логирует данные"""
        today = datetime.utcnow().strftime("%Y-%m-%d_%H")
        filepath = self.output_dir / f"{today}.jsonl"
        
        data["_logged_at"] = datetime.utcnow().isoformat()
        
        with open(filepath, 'a') as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        
        self.messages_logged += 1


# =============================================================================
# 🚀 ENTRY POINT
# =============================================================================

async def main():
    """Entry point"""
    engine = RealTimeSignalEngine()
    
    # Callback для сигналов
    async def handle_signal(signal):
        logger.info(f"📡 SIGNAL: {signal.symbol} {signal.signal_type.value} "
                   f"(strength={signal.strength:.2f})")
    
    engine.on_signal = handle_signal
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
