"""
💼 POSITION MANAGER - УПРАВЛЕНИЕ ПОЗИЦИЯМИ
==========================================
Открывает, закрывает, мониторит позиции на BingX.

Модули:
1. OrderExecutor - выполнение ордеров на BingX
2. PositionMonitor - мониторинг и TP
3. TradeLogger - логирование сделок

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import (
    BINGX_API_KEY, BINGX_SECRET_KEY,
    get_effective_config, get_dynamic_tp, get_current_tp_phase,
    TradingConfig, LOGS_DIR, GLOBAL_SAFEGUARDS
)
from scripts.bablobot.signals import Signal, SignalType
from scripts.bablobot.brain_policy import validate_position_action, get_adaptive_tp_for_pair

# =============================================================================
# 📊 DATA STRUCTURES
# =============================================================================

@dataclass
class Position:
    """Позиция"""
    symbol: str
    side: str  # LONG / SHORT
    size: float
    entry_price: float
    mark_price: float
    leverage: int
    margin: float
    pnl: float
    pnl_pct: float
    opened_at: str
    duration_minutes: float = 0

@dataclass
class Order:
    """Ордер"""
    symbol: str
    side: str  # BUY / SELL
    position_side: str  # LONG / SHORT
    order_type: str  # MARKET / LIMIT
    quantity: float
    price: float = 0
    
@dataclass
class TradeResult:
    """Результат сделки"""
    success: bool
    order_id: str = ""
    message: str = ""
    data: Dict[str, Any] = None

# =============================================================================
# 🔧 BINGX API CLIENT
# =============================================================================

class BingXClient:
    """Клиент для BingX API"""
    
    BASE_URL = "https://open-api.bingx.com"
    
    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_key = api_key or BINGX_API_KEY
        self.secret_key = secret_key or BINGX_SECRET_KEY
        
        if not self.api_key or not self.secret_key:
            logger.warning("⚠️ BingX API keys not configured!")
    
    def _sign(self, params: str) -> str:
        """Подписывает запрос"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_timestamp(self) -> int:
        """Возвращает timestamp"""
        return int(time.time() * 1000)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполняет запрос к API"""
        params = params or {}
        params["timestamp"] = self._get_timestamp()
        
        # Формируем строку параметров
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = self._sign(param_str)
        param_str += f"&signature={signature}"
        
        url = f"{self.BASE_URL}{endpoint}?{param_str}"
        headers = {"X-BX-APIKEY": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        return await resp.json()
                elif method == "POST":
                    async with session.post(url, headers=headers, timeout=10) as resp:
                        return await resp.json()
                elif method == "DELETE":
                    async with session.delete(url, headers=headers, timeout=10) as resp:
                        return await resp.json()
            except Exception as e:
                logger.error(f"BingX API error: {e}")
                return {"code": -1, "msg": str(e)}
    
    async def get_balance(self) -> Dict[str, Any]:
        """Получает баланс"""
        response = await self._request("GET", "/openApi/swap/v2/user/balance")
        if response.get("code") == 0:
            return response.get("data", {}).get("balance", {})
        return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Получает открытые позиции"""
        response = await self._request("GET", "/openApi/swap/v2/user/positions")
        if response.get("code") == 0:
            positions = response.get("data", [])
            # Фильтруем только открытые
            return [p for p in positions if float(p.get("positionAmt", 0)) != 0]
        return []
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Получает тикер"""
        response = await self._request(
            "GET",
            "/openApi/swap/v2/quote/ticker",
            {"symbol": symbol}
        )
        if response.get("code") == 0:
            return response.get("data", {})
        return {}
    
    async def place_order(self, order: Order) -> TradeResult:
        """Размещает ордер"""
        params = {
            "symbol": order.symbol,
            "side": order.side,
            "positionSide": order.position_side,
            "type": order.order_type,
            "quantity": order.quantity
        }
        
        if order.order_type == "LIMIT" and order.price:
            params["price"] = order.price
        
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params)
        
        if response.get("code") == 0:
            data = response.get("data", {})
            return TradeResult(
                success=True,
                order_id=str(data.get("orderId", "")),
                message="Order placed",
                data=data
            )
        else:
            return TradeResult(
                success=False,
                message=response.get("msg", "Unknown error"),
                data=response
            )
    
    async def close_position(self, symbol: str, position_side: str, quantity: float) -> TradeResult:
        """Закрывает позицию"""
        # Для закрытия LONG нужен SELL, для SHORT - BUY
        side = "SELL" if position_side == "LONG" else "BUY"
        
        order = Order(
            symbol=symbol,
            side=side,
            position_side=position_side,
            order_type="MARKET",
            quantity=abs(quantity)
        )
        
        return await self.place_order(order)
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Устанавливает leverage"""
        response = await self._request(
            "POST",
            "/openApi/swap/v2/trade/leverage",
            {"symbol": symbol, "side": "BOTH", "leverage": leverage}
        )
        return response.get("code") == 0


# =============================================================================
# 📈 ORDER EXECUTOR
# =============================================================================

class OrderExecutor:
    """
    Исполнитель ордеров
    
    Проверяет условия перед открытием:
    1. Достаточно ли баланса
    2. Не превышен ли лимит позиций
    3. Нет ли уже позиции по этой паре
    """
    
    def __init__(self, client: BingXClient = None):
        self.client = client or BingXClient()
        self.trade_logger = TradeLogger()
    
    async def execute_signal(self, signal: Signal) -> TradeResult:
        """
        Исполняет сигнал - открывает позицию
        
        Args:
            signal: Торговый сигнал
        
        Returns:
            TradeResult
        """
        if signal.blocked:
            return TradeResult(
                success=False,
                message=f"Signal blocked: {signal.block_reason}"
            )
        
        # Проверяем условия
        can_open, reason = await self._can_open_position(signal.symbol)
        if not can_open:
            return TradeResult(success=False, message=reason)
        
        # Рассчитываем размер позиции
        config = get_effective_config()
        balance = await self.client.get_balance()
        available = float(balance.get("availableMargin", 0))
        
        if available < config.get("min_position_usdt", 2):
            return TradeResult(success=False, message="Insufficient balance")
        
        # Размер позиции
        position_size_usdt = min(
            available * config.get("balance_pct", 1.0) / config.get("max_positions", 10),
            available * 0.1  # Max 10% на позицию
        )
        
        # Получаем текущую цену
        ticker = await self.client.get_ticker(signal.symbol)
        current_price = float(ticker.get("lastPrice", 0))
        if current_price == 0:
            return TradeResult(success=False, message="Failed to get price")
        
        # Рассчитываем количество
        quantity = position_size_usdt / current_price
        
        # Устанавливаем leverage
        leverage = config.get("base_leverage", 4)
        await self.client.set_leverage(signal.symbol, leverage)
        
        # Создаём ордер
        position_side = "LONG" if signal.signal_type == SignalType.LONG else "SHORT"
        side = "BUY" if position_side == "LONG" else "SELL"
        
        order = Order(
            symbol=signal.symbol,
            side=side,
            position_side=position_side,
            order_type="MARKET",
            quantity=round(quantity, 4)
        )
        
        # Выполняем
        result = await self.client.place_order(order)
        
        # Логируем
        if result.success:
            await self.trade_logger.log_open(
                symbol=signal.symbol,
                side=position_side,
                entry_price=current_price,
                size=quantity,
                leverage=leverage,
                signal_source=signal.source,
                signal_strength=signal.strength
            )
            logger.info(f"✅ Opened {position_side} {signal.symbol} @ {current_price}")
        else:
            logger.error(f"❌ Failed to open {signal.symbol}: {result.message}")
        
        return result
    
    async def _can_open_position(self, symbol: str) -> Tuple[bool, str]:
        """Проверяет можно ли открыть позицию"""
        config = get_effective_config()
        
        # Получаем текущие позиции
        positions = await self.client.get_positions()
        
        # Проверяем лимит позиций
        if len(positions) >= config.get("max_positions", 10):
            return False, f"Max positions limit ({config.get('max_positions')}) reached"
        
        # Проверяем нет ли уже позиции по этой паре
        for pos in positions:
            if pos.get("symbol") == symbol:
                return False, f"Already have position on {symbol}"
        
        return True, ""


# =============================================================================
# 🔍 POSITION MONITOR
# =============================================================================

class PositionMonitor:
    """
    Мониторинг позиций
    
    - Проверяет TP условия
    - Применяет трёхфазный TP
    - Emergency exit если нужно
    """
    
    def __init__(self, client: BingXClient = None):
        self.client = client or BingXClient()
        self.trade_logger = TradeLogger()
        # Храним время открытия позиций (BingX не возвращает!)
        self.open_times: Dict[str, datetime] = {}
    
    async def check_positions(self) -> List[Dict[str, Any]]:
        """
        Проверяет все позиции и закрывает по TP
        
        Returns:
            List of closed positions
        """
        closed = []
        positions = await self.client.get_positions()
        
        for pos in positions:
            symbol = pos.get("symbol", "")
            
            # Записываем время открытия если новая позиция
            if symbol not in self.open_times:
                self.open_times[symbol] = datetime.utcnow()
            
            # Рассчитываем PnL %
            entry_price = float(pos.get("avgPrice", 0))
            mark_price = float(pos.get("markPrice", 0))
            side = pos.get("positionSide", "LONG")
            quantity = float(pos.get("positionAmt", 0))
            
            if entry_price == 0:
                continue
            
            if side == "LONG":
                pnl_pct = ((mark_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - mark_price) / entry_price) * 100
            
            # Время в позиции
            duration = (datetime.utcnow() - self.open_times[symbol]).total_seconds() / 60
            
            # Получаем динамический TP
            base_tp = get_dynamic_tp()
            adaptive_tp = get_adaptive_tp_for_pair(symbol, base_tp)
            tp_pct = adaptive_tp * 100
            
            # Проверяем TP
            if pnl_pct >= tp_pct:
                # ЗАКРЫВАЕМ!
                result = await self.client.close_position(symbol, side, quantity)
                
                if result.success:
                    # Логируем
                    await self.trade_logger.log_close(
                        symbol=symbol,
                        side=side,
                        entry_price=entry_price,
                        exit_price=mark_price,
                        pnl_pct=pnl_pct,
                        duration_minutes=duration,
                        close_reason="TP"
                    )
                    
                    # Убираем из open_times
                    del self.open_times[symbol]
                    
                    closed.append({
                        "symbol": symbol,
                        "side": side,
                        "pnl_pct": pnl_pct,
                        "duration": duration,
                        "reason": "TP"
                    })
                    
                    logger.info(f"✅ TP hit: {symbol} +{pnl_pct:.2f}% ({duration:.1f} min)")
            
            # Проверяем Emergency Exit
            emergency_time = GLOBAL_SAFEGUARDS.get("emergency_exit_minutes", 180)
            emergency_min_pnl = GLOBAL_SAFEGUARDS.get("emergency_exit_min_pnl", 0.5)
            
            if duration > emergency_time and pnl_pct < emergency_min_pnl:
                # Валидация через brain_policy
                can_close, reason = validate_position_action(
                    "close",
                    {"distance_to_liquidation_pct": 100},  # TODO: получать реальное значение
                    pnl_pct
                )
                
                if can_close:
                    result = await self.client.close_position(symbol, side, quantity)
                    
                    if result.success:
                        await self.trade_logger.log_close(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            exit_price=mark_price,
                            pnl_pct=pnl_pct,
                            duration_minutes=duration,
                            close_reason="EMERGENCY_EXIT"
                        )
                        
                        del self.open_times[symbol]
                        
                        closed.append({
                            "symbol": symbol,
                            "side": side,
                            "pnl_pct": pnl_pct,
                            "duration": duration,
                            "reason": "EMERGENCY_EXIT"
                        })
                        
                        logger.warning(f"⚠️ Emergency exit: {symbol} {pnl_pct:+.2f}% ({duration:.1f} min)")
        
        return closed
    
    async def get_positions_summary(self) -> Dict[str, Any]:
        """Возвращает сводку по позициям"""
        positions = await self.client.get_positions()
        
        if not positions:
            return {"total": 0, "positions": []}
        
        total_pnl = 0
        formatted = []
        
        for pos in positions:
            symbol = pos.get("symbol", "")
            entry_price = float(pos.get("avgPrice", 0))
            mark_price = float(pos.get("markPrice", 0))
            side = pos.get("positionSide", "LONG")
            pnl = float(pos.get("unrealizedProfit", 0))
            
            total_pnl += pnl
            
            # PnL %
            if entry_price > 0:
                if side == "LONG":
                    pnl_pct = ((mark_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - mark_price) / entry_price) * 100
            else:
                pnl_pct = 0
            
            # Время
            duration = 0
            if symbol in self.open_times:
                duration = (datetime.utcnow() - self.open_times[symbol]).total_seconds() / 60
            
            formatted.append({
                "symbol": symbol,
                "side": side,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "duration_minutes": duration
            })
        
        return {
            "total": len(positions),
            "total_pnl": total_pnl,
            "long_count": sum(1 for p in positions if p.get("positionSide") == "LONG"),
            "short_count": sum(1 for p in positions if p.get("positionSide") == "SHORT"),
            "positions": formatted
        }


# =============================================================================
# 📝 TRADE LOGGER
# =============================================================================

class TradeLogger:
    """Логгер сделок"""
    
    def __init__(self):
        self.trades_file = LOGS_DIR / "trades.json"
        self.stats_file = LOGS_DIR / "stats.json"
        
        # Создаём папку если нужно
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_trades(self) -> List[Dict]:
        """Загружает сделки"""
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_trades(self, trades: List[Dict]):
        """Сохраняет сделки"""
        with open(self.trades_file, 'w') as f:
            json.dump(trades, f, indent=2)
    
    async def log_open(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        leverage: int,
        signal_source: str,
        signal_strength: float
    ):
        """Логирует открытие позиции"""
        trades = self._load_trades()
        
        trades.append({
            "id": f"{symbol}_{int(time.time())}",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "size": size,
            "leverage": leverage,
            "signal_source": signal_source,
            "signal_strength": signal_strength,
            "opened_at": datetime.utcnow().isoformat(),
            "status": "OPEN"
        })
        
        self._save_trades(trades)
    
    async def log_close(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        duration_minutes: float,
        close_reason: str
    ):
        """Логирует закрытие позиции"""
        trades = self._load_trades()
        
        # Находим открытую сделку
        for trade in reversed(trades):
            if trade.get("symbol") == symbol and trade.get("status") == "OPEN":
                trade["exit_price"] = exit_price
                trade["pnl_pct"] = pnl_pct
                trade["pnl"] = (exit_price - entry_price) * trade.get("size", 0) * trade.get("leverage", 1)
                if side == "SHORT":
                    trade["pnl"] *= -1
                trade["duration_minutes"] = duration_minutes
                trade["closed_at"] = datetime.utcnow().isoformat()
                trade["close_reason"] = close_reason
                trade["status"] = "CLOSED"
                break
        
        self._save_trades(trades)
        
        # Обновляем статистику
        await self._update_stats(trades)
    
    async def _update_stats(self, trades: List[Dict]):
        """Обновляет статистику"""
        closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
        
        if not closed_trades:
            return
        
        today = datetime.utcnow().date()
        today_trades = [
            t for t in closed_trades
            if datetime.fromisoformat(t.get("closed_at", "2000-01-01")).date() == today
        ]
        
        wins = sum(1 for t in today_trades if t.get("pnl_pct", 0) > 0)
        total = len(today_trades)
        
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_trades": len(closed_trades),
            "trades_today": total,
            "wins_today": wins,
            "win_rate": wins / total if total > 0 else 0,
            "total_pnl_today": sum(t.get("pnl", 0) for t in today_trades),
            "avg_duration_min": sum(t.get("duration_minutes", 0) for t in today_trades) / total if total > 0 else 0
        }
        
        with open(self.stats_file, 'w') as f:
            json.dump(stats, f, indent=2)


# =============================================================================
# 🚀 MAIN TRADING LOOP
# =============================================================================

class TradingLoop:
    """
    Главный торговый цикл
    
    1. Получает сигналы от SignalEngine
    2. Открывает позиции через OrderExecutor
    3. Мониторит позиции через PositionMonitor
    """
    
    def __init__(self):
        self.client = BingXClient()
        self.executor = OrderExecutor(self.client)
        self.monitor = PositionMonitor(self.client)
        self.running = False
    
    async def run(self, signal_engine, interval_seconds: int = 2):
        """
        Запускает торговый цикл
        
        Args:
            signal_engine: SignalEngine instance
            interval_seconds: Интервал проверки
        """
        from scripts.bablobot.signals import SignalEngine
        
        self.running = True
        logger.info("🚀 Trading loop started")
        
        while self.running:
            try:
                # 1. Проверяем позиции на TP
                closed = await self.monitor.check_positions()
                if closed:
                    for c in closed:
                        logger.info(f"📍 Closed: {c['symbol']} {c['pnl_pct']:+.2f}% ({c['reason']})")
                
                # 2. Получаем цены
                prices = await self._get_all_prices()
                
                # 3. Сканируем на сигналы
                signals = await signal_engine.scan_all_pairs(prices)
                
                # 4. Выполняем топ сигнал
                if signals:
                    best_signal = signals[0]
                    if best_signal.strength >= 0.5:  # Минимальная сила
                        result = await self.executor.execute_signal(best_signal)
                        if result.success:
                            logger.info(f"📡 Signal executed: {best_signal.symbol} {best_signal.signal_type.value}")
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(10)
    
    async def _get_all_prices(self) -> Dict[str, float]:
        """Получает цены всех пар"""
        from config.config import DEFAULT_PAIRS
        
        prices = {}
        for symbol in DEFAULT_PAIRS:
            ticker = await self.client.get_ticker(symbol)
            if ticker:
                prices[symbol] = float(ticker.get("lastPrice", 0))
        
        return prices
    
    def stop(self):
        """Останавливает цикл"""
        self.running = False
        logger.info("⏹️ Trading loop stopped")


# =============================================================================
# 🎯 ENTRY POINT
# =============================================================================

async def main():
    """Entry point"""
    from scripts.bablobot.signals import SignalEngine
    
    signal_engine = SignalEngine()
    trading_loop = TradingLoop()
    
    await trading_loop.run(signal_engine)


if __name__ == "__main__":
    asyncio.run(main())
