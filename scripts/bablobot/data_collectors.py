"""
📊 DATA COLLECTORS - СБОР ВСЕХ ДАННЫХ РЫНКА
==========================================
Собирает данные из всех источников для Brain.

Коллекторы:
1. BTCWatcher - BTC/ETH цены и изменения
2. VolumeCollector - объёмы торгов
3. SpotFlowCollector - BUY/SELL pressure
4. PositionsCollector - текущие позиции с BingX
5. StatsCollector - торговая статистика

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
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import (
    BINGX_API_KEY, BINGX_SECRET_KEY, 
    DATA_DIR, LOGS_DIR, DEFAULT_PAIRS,
    BTC_WATCHER_DIR, VOLUME_DIR, SPOT_FLOW_DIR
)

# =============================================================================
# 🔧 BASE COLLECTOR
# =============================================================================

class BaseCollector:
    """Базовый класс для коллекторов"""
    
    def __init__(self, name: str, output_dir: Path, interval_seconds: int = 60):
        self.name = name
        self.output_dir = output_dir
        self.interval_seconds = interval_seconds
        self.last_collect_time = None
        self.collect_count = 0
        self.error_count = 0
        
        # Создаём директорию
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📊 {self.name} initialized (interval: {interval_seconds}s)")
    
    async def collect(self) -> Dict[str, Any]:
        """Override в дочерних классах"""
        raise NotImplementedError
    
    async def save(self, data: Dict[str, Any]):
        """Сохраняет данные в JSONL файл"""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            filepath = self.output_dir / f"{today}.jsonl"
            
            data["_collector"] = self.name
            data["_timestamp"] = datetime.utcnow().isoformat()
            
            with open(filepath, 'a') as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            
            self.collect_count += 1
            self.last_collect_time = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"{self.name} save error: {e}")
            self.error_count += 1
    
    async def run(self):
        """Запускает цикл сбора данных"""
        logger.info(f"🚀 {self.name} started")
        
        while True:
            try:
                data = await self.collect()
                if data:
                    await self.save(data)
                    
            except Exception as e:
                logger.error(f"{self.name} error: {e}")
                self.error_count += 1
            
            await asyncio.sleep(self.interval_seconds)


# =============================================================================
# 📈 BTC WATCHER - BTC/ETH мониторинг
# =============================================================================

class BTCWatcher(BaseCollector):
    """
    Мониторинг BTC и ETH каждые 60 секунд
    Ключевой индикатор всего рынка!
    """
    
    def __init__(self):
        super().__init__("BTCWatcher", BTC_WATCHER_DIR, interval_seconds=60)
        self.price_history: Dict[str, List[float]] = {"BTC": [], "ETH": []}
        self.max_history = 60  # 60 точек = 1 час
    
    async def collect(self) -> Dict[str, Any]:
        """Собирает данные BTC и ETH"""
        async with aiohttp.ClientSession() as session:
            try:
                # BingX API для BTC и ETH
                btc_data = await self._get_ticker(session, "BTC-USDT")
                eth_data = await self._get_ticker(session, "ETH-USDT")
                
                # Обновляем историю
                if btc_data.get("price"):
                    self.price_history["BTC"].append(btc_data["price"])
                    if len(self.price_history["BTC"]) > self.max_history:
                        self.price_history["BTC"].pop(0)
                
                if eth_data.get("price"):
                    self.price_history["ETH"].append(eth_data["price"])
                    if len(self.price_history["ETH"]) > self.max_history:
                        self.price_history["ETH"].pop(0)
                
                # Расчёт изменений
                btc_change_1h = self._calc_change(self.price_history["BTC"], 60)
                btc_change_15m = self._calc_change(self.price_history["BTC"], 15)
                eth_change_1h = self._calc_change(self.price_history["ETH"], 60)
                eth_change_15m = self._calc_change(self.price_history["ETH"], 15)
                
                # Определяем market bias
                market_bias = self._determine_bias(btc_change_1h, eth_change_1h)
                
                # Определяем волатильность
                volatility = self._determine_volatility(btc_change_15m, eth_change_15m)
                
                # Алерты
                alerts = []
                if abs(btc_change_15m) > 2:
                    alerts.append(f"⚠️ BTC {btc_change_15m:+.2f}% за 15 мин!")
                if abs(btc_change_15m) > 3:
                    alerts.append(f"🚨 BTC {btc_change_15m:+.2f}% за 15 мин - АЛЕРТ!")
                if abs(btc_change_1h) > 5:
                    alerts.append(f"💀 BTC {btc_change_1h:+.2f}% за час - АЛЬТЫ ПОЛЕТЯТ!")
                
                return {
                    "btc_price": btc_data.get("price", 0),
                    "btc_change_1h": btc_change_1h,
                    "btc_change_15m": btc_change_15m,
                    "btc_change_24h": btc_data.get("change_24h", 0),
                    "btc_volume_24h": btc_data.get("volume_24h", 0),
                    "eth_price": eth_data.get("price", 0),
                    "eth_change_1h": eth_change_1h,
                    "eth_change_15m": eth_change_15m,
                    "eth_change_24h": eth_data.get("change_24h", 0),
                    "market_bias": market_bias,
                    "volatility": volatility,
                    "alerts": alerts
                }
                
            except Exception as e:
                logger.error(f"BTCWatcher collect error: {e}")
                return {"error": str(e)}
    
    async def _get_ticker(self, session: aiohttp.ClientSession, symbol: str) -> Dict[str, Any]:
        """Получает тикер с BingX"""
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
            params = {"symbol": symbol}
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0:
                        ticker = data.get("data", {})
                        return {
                            "price": float(ticker.get("lastPrice", 0)),
                            "change_24h": float(ticker.get("priceChangePercent", 0)),
                            "volume_24h": float(ticker.get("volume", 0))
                        }
        except Exception as e:
            logger.error(f"Get ticker error for {symbol}: {e}")
        
        return {}
    
    def _calc_change(self, prices: List[float], periods: int) -> float:
        """Рассчитывает изменение цены за N периодов"""
        if len(prices) < 2:
            return 0.0
        
        actual_periods = min(periods, len(prices))
        if actual_periods < 2:
            return 0.0
        
        old_price = prices[-actual_periods]
        new_price = prices[-1]
        
        if old_price == 0:
            return 0.0
        
        return ((new_price - old_price) / old_price) * 100
    
    def _determine_bias(self, btc_change: float, eth_change: float) -> str:
        """Определяет bias рынка"""
        avg_change = (btc_change + eth_change) / 2
        
        if avg_change > 1.0:
            return "BULLISH"
        elif avg_change < -1.0:
            return "BEARISH"
        else:
            return "SIDEWAYS"
    
    def _determine_volatility(self, btc_15m: float, eth_15m: float) -> str:
        """Определяет волатильность"""
        max_change = max(abs(btc_15m), abs(eth_15m))
        
        if max_change > 3:
            return "HIGH"
        elif max_change > 1:
            return "MEDIUM"
        else:
            return "LOW"


# =============================================================================
# 📊 VOLUME COLLECTOR - Объёмы торгов
# =============================================================================

class VolumeCollector(BaseCollector):
    """
    Мониторинг объёмов торгов по всем парам
    Резкий рост объёма = подтверждение движения
    """
    
    def __init__(self, pairs: List[str] = None):
        super().__init__("VolumeCollector", VOLUME_DIR, interval_seconds=300)  # 5 min
        self.pairs = pairs or DEFAULT_PAIRS
        self.volume_history: Dict[str, List[float]] = {}
    
    async def collect(self) -> Dict[str, Any]:
        """Собирает объёмы по всем парам"""
        async with aiohttp.ClientSession() as session:
            try:
                volumes = {}
                
                for pair in self.pairs:
                    ticker = await self._get_ticker(session, pair)
                    if ticker:
                        volume_24h = ticker.get("volume_24h", 0)
                        
                        # Обновляем историю
                        if pair not in self.volume_history:
                            self.volume_history[pair] = []
                        self.volume_history[pair].append(volume_24h)
                        if len(self.volume_history[pair]) > 24:  # 24 точки = 2 часа
                            self.volume_history[pair].pop(0)
                        
                        # Расчёт изменения объёма
                        volume_change = self._calc_volume_change(pair)
                        
                        volumes[pair] = {
                            "volume_24h": volume_24h,
                            "volume_change_pct": volume_change,
                            "price": ticker.get("price", 0),
                            "change_24h": ticker.get("change_24h", 0)
                        }
                
                # Топ по объёму
                sorted_by_volume = sorted(
                    volumes.items(),
                    key=lambda x: x[1].get("volume_24h", 0),
                    reverse=True
                )
                top_volume = [p[0] for p in sorted_by_volume[:5]]
                
                # Топ по росту объёма (потенциальные пампы)
                sorted_by_growth = sorted(
                    volumes.items(),
                    key=lambda x: x[1].get("volume_change_pct", 0),
                    reverse=True
                )
                volume_spikes = [p[0] for p in sorted_by_growth if p[1].get("volume_change_pct", 0) > 50][:5]
                
                return {
                    "pairs": volumes,
                    "top_volume": top_volume,
                    "volume_spikes": volume_spikes,
                    "total_volume_24h": sum(v.get("volume_24h", 0) for v in volumes.values())
                }
                
            except Exception as e:
                logger.error(f"VolumeCollector error: {e}")
                return {"error": str(e)}
    
    async def _get_ticker(self, session: aiohttp.ClientSession, symbol: str) -> Dict[str, Any]:
        """Получает тикер"""
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
            params = {"symbol": symbol}
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0:
                        ticker = data.get("data", {})
                        return {
                            "price": float(ticker.get("lastPrice", 0)),
                            "change_24h": float(ticker.get("priceChangePercent", 0)),
                            "volume_24h": float(ticker.get("quoteVolume", 0))
                        }
        except Exception as e:
            pass
        return {}
    
    def _calc_volume_change(self, pair: str) -> float:
        """Рассчитывает изменение объёма"""
        history = self.volume_history.get(pair, [])
        if len(history) < 2:
            return 0.0
        
        old_avg = sum(history[:-1]) / len(history[:-1]) if len(history) > 1 else history[0]
        new_volume = history[-1]
        
        if old_avg == 0:
            return 0.0
        
        return ((new_volume - old_avg) / old_avg) * 100


# =============================================================================
# 💰 SPOT FLOW COLLECTOR - BUY/SELL Pressure
# =============================================================================

class SpotFlowCollector(BaseCollector):
    """
    Анализ BUY/SELL pressure на споте
    Ключевой опережающий индикатор!
    """
    
    def __init__(self, pairs: List[str] = None):
        super().__init__("SpotFlowCollector", SPOT_FLOW_DIR, interval_seconds=120)  # 2 min
        self.pairs = pairs or DEFAULT_PAIRS[:10]  # Топ 10 пар
    
    async def collect(self) -> Dict[str, Any]:
        """Собирает spot flow данные"""
        async with aiohttp.ClientSession() as session:
            try:
                flows = {}
                
                for pair in self.pairs:
                    # Получаем последние сделки
                    trades = await self._get_recent_trades(session, pair)
                    
                    if trades:
                        # Анализируем BUY/SELL
                        buy_volume = sum(t["volume"] for t in trades if t["side"] == "BUY")
                        sell_volume = sum(t["volume"] for t in trades if t["side"] == "SELL")
                        total_volume = buy_volume + sell_volume
                        
                        if total_volume > 0:
                            buy_pct = (buy_volume / total_volume) * 100
                            sell_pct = (sell_volume / total_volume) * 100
                        else:
                            buy_pct = 50
                            sell_pct = 50
                        
                        # Определяем pressure
                        if buy_pct > 60:
                            pressure = "BUY_PRESSURE"
                        elif sell_pct > 60:
                            pressure = "SELL_PRESSURE"
                        else:
                            pressure = "NEUTRAL"
                        
                        flows[pair] = {
                            "buy_volume": buy_volume,
                            "sell_volume": sell_volume,
                            "buy_pct": round(buy_pct, 1),
                            "sell_pct": round(sell_pct, 1),
                            "pressure": pressure,
                            "trades_count": len(trades)
                        }
                
                # Общий market flow
                total_buy = sum(f.get("buy_volume", 0) for f in flows.values())
                total_sell = sum(f.get("sell_volume", 0) for f in flows.values())
                total = total_buy + total_sell
                
                if total > 0:
                    market_buy_pct = (total_buy / total) * 100
                else:
                    market_buy_pct = 50
                
                if market_buy_pct > 55:
                    market_pressure = "BULLISH"
                elif market_buy_pct < 45:
                    market_pressure = "BEARISH"
                else:
                    market_pressure = "NEUTRAL"
                
                return {
                    "pairs": flows,
                    "market_buy_pct": round(market_buy_pct, 1),
                    "market_pressure": market_pressure,
                    "buy_pressure_pairs": [p for p, f in flows.items() if f.get("pressure") == "BUY_PRESSURE"],
                    "sell_pressure_pairs": [p for p, f in flows.items() if f.get("pressure") == "SELL_PRESSURE"]
                }
                
            except Exception as e:
                logger.error(f"SpotFlowCollector error: {e}")
                return {"error": str(e)}
    
    async def _get_recent_trades(self, session: aiohttp.ClientSession, symbol: str) -> List[Dict]:
        """Получает последние сделки"""
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/trades"
            params = {"symbol": symbol, "limit": 100}
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0:
                        trades = []
                        for t in data.get("data", []):
                            trades.append({
                                "price": float(t.get("price", 0)),
                                "volume": float(t.get("qty", 0)),
                                "side": "BUY" if t.get("side") == "BUY" else "SELL",
                                "timestamp": t.get("time", 0)
                            })
                        return trades
        except Exception as e:
            pass
        return []


# =============================================================================
# 📍 POSITIONS COLLECTOR - Позиции с BingX
# =============================================================================

class PositionsCollector(BaseCollector):
    """
    Сбор данных о текущих позициях с BingX API
    """
    
    def __init__(self):
        super().__init__("PositionsCollector", LOGS_DIR, interval_seconds=30)
        self.api_key = BINGX_API_KEY
        self.secret_key = BINGX_SECRET_KEY
    
    async def collect(self) -> Dict[str, Any]:
        """Собирает данные о позициях"""
        if not self.api_key or not self.secret_key:
            return {"error": "API keys not configured"}
        
        try:
            positions = await self._fetch_positions()
            
            if positions:
                # Статистика
                total_pnl = sum(p.get("unrealizedProfit", 0) for p in positions)
                long_count = sum(1 for p in positions if p.get("positionSide") == "LONG")
                short_count = sum(1 for p in positions if p.get("positionSide") == "SHORT")
                
                worst_pnl = min(p.get("unrealizedProfit", 0) for p in positions) if positions else 0
                best_pnl = max(p.get("unrealizedProfit", 0) for p in positions) if positions else 0
                
                # Форматируем позиции
                formatted = []
                for p in positions:
                    formatted.append({
                        "symbol": p.get("symbol", ""),
                        "side": p.get("positionSide", ""),
                        "size": float(p.get("positionAmt", 0)),
                        "entry_price": float(p.get("avgPrice", 0)),
                        "mark_price": float(p.get("markPrice", 0)),
                        "pnl": float(p.get("unrealizedProfit", 0)),
                        "pnl_pct": self._calc_pnl_pct(p),
                        "leverage": int(p.get("leverage", 1)),
                        "margin": float(p.get("positionValue", 0)) / int(p.get("leverage", 1))
                    })
                
                return {
                    "positions": formatted,
                    "total": len(positions),
                    "total_pnl": total_pnl,
                    "long_count": long_count,
                    "short_count": short_count,
                    "worst_pnl": worst_pnl,
                    "best_pnl": best_pnl
                }
            
            return {"positions": [], "total": 0}
            
        except Exception as e:
            logger.error(f"PositionsCollector error: {e}")
            return {"error": str(e)}
    
    async def _fetch_positions(self) -> List[Dict]:
        """Получает позиции с BingX"""
        try:
            timestamp = int(time.time() * 1000)
            params = f"timestamp={timestamp}"
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                params.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            url = f"https://open-api.bingx.com/openApi/swap/v2/user/positions?{params}&signature={signature}"
            headers = {"X-BX-APIKEY": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            # Фильтруем только открытые позиции
                            return [p for p in data.get("data", []) if float(p.get("positionAmt", 0)) != 0]
            
        except Exception as e:
            logger.error(f"Fetch positions error: {e}")
        
        return []
    
    def _calc_pnl_pct(self, position: Dict) -> float:
        """Рассчитывает PnL в процентах"""
        try:
            entry = float(position.get("avgPrice", 0))
            mark = float(position.get("markPrice", 0))
            side = position.get("positionSide", "LONG")
            
            if entry == 0:
                return 0.0
            
            if side == "LONG":
                return ((mark - entry) / entry) * 100
            else:
                return ((entry - mark) / entry) * 100
                
        except Exception:
            return 0.0
    
    async def save(self, data: Dict[str, Any]):
        """Сохраняет в positions.json"""
        try:
            filepath = self.output_dir / "positions.json"
            data["_timestamp"] = datetime.utcnow().isoformat()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.collect_count += 1
            self.last_collect_time = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"PositionsCollector save error: {e}")


# =============================================================================
# 📈 STATS COLLECTOR - Торговая статистика
# =============================================================================

class StatsCollector(BaseCollector):
    """
    Сбор торговой статистики из trades.json
    """
    
    def __init__(self):
        super().__init__("StatsCollector", LOGS_DIR, interval_seconds=60)
    
    async def collect(self) -> Dict[str, Any]:
        """Собирает статистику"""
        try:
            trades_file = LOGS_DIR / "trades.json"
            
            if not trades_file.exists():
                return {}
            
            with open(trades_file, 'r') as f:
                trades = json.load(f)
            
            if not isinstance(trades, list):
                trades = [trades] if trades else []
            
            # Фильтруем сделки за сегодня
            today = datetime.utcnow().date()
            today_trades = [
                t for t in trades
                if datetime.fromisoformat(t.get("timestamp", "2000-01-01")).date() == today
            ]
            
            # Статистика
            total_trades = len(today_trades)
            wins = sum(1 for t in today_trades if t.get("pnl", 0) > 0)
            losses = sum(1 for t in today_trades if t.get("pnl", 0) < 0)
            
            win_rate = wins / total_trades if total_trades > 0 else 0
            total_pnl = sum(t.get("pnl", 0) for t in today_trades)
            
            # Средняя длительность
            durations = [t.get("duration_minutes", 0) for t in today_trades if t.get("duration_minutes")]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Сделок в час
            hours_passed = datetime.utcnow().hour + 1
            trades_per_hour = total_trades / hours_passed if hours_passed > 0 else 0
            
            # Лучшие и худшие пары
            pair_pnl = {}
            for t in today_trades:
                pair = t.get("symbol", "unknown")
                pair_pnl[pair] = pair_pnl.get(pair, 0) + t.get("pnl", 0)
            
            best_pair = max(pair_pnl, key=pair_pnl.get) if pair_pnl else ""
            worst_pair = min(pair_pnl, key=pair_pnl.get) if pair_pnl else ""
            
            return {
                "trades_today": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_pnl_today": total_pnl,
                "avg_trade_duration_min": avg_duration,
                "trades_per_hour": trades_per_hour,
                "best_pair": best_pair,
                "worst_pair": worst_pair,
                "pair_pnl": pair_pnl
            }
            
        except Exception as e:
            logger.error(f"StatsCollector error: {e}")
            return {"error": str(e)}
    
    async def save(self, data: Dict[str, Any]):
        """Сохраняет в stats.json"""
        try:
            filepath = self.output_dir / "stats.json"
            data["_timestamp"] = datetime.utcnow().isoformat()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.collect_count += 1
            
        except Exception as e:
            logger.error(f"StatsCollector save error: {e}")


# =============================================================================
# 🚀 RUN ALL COLLECTORS
# =============================================================================

async def run_all_collectors():
    """Запускает все коллекторы параллельно"""
    collectors = [
        BTCWatcher(),
        VolumeCollector(),
        SpotFlowCollector(),
        PositionsCollector(),
        StatsCollector()
    ]
    
    logger.info(f"🚀 Starting {len(collectors)} collectors...")
    
    tasks = [asyncio.create_task(c.run()) for c in collectors]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(run_all_collectors())
