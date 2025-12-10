"""
📊 SPREAD TRACKER - ОТСЛЕЖИВАНИЕ СПРЕДОВ МЕЖДУ БИРЖАМИ
=====================================================
Мониторит спреды между биржами для Third Observer.

ЗАЧЕМ:
- Найти арбитражные возможности
- Проверить "edge" перед открытием
- Логирование для анализа

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
import aiohttp

logger = logging.getLogger(__name__)

# =============================================================================
# 📊 CONFIG
# =============================================================================

SPREAD_CONFIG = {
    "enabled": True,
    "min_edge_pct": 0.1,  # Минимальный edge для входа
    "exchanges": ["bingx", "binance"],  # Биржи для сравнения
    "check_interval_seconds": 30
}

LOGS_DIR = Path("/workspace/user_data/logs")
SPREAD_LOG = LOGS_DIR / "spread_log.json"

# =============================================================================
# 📈 SPREAD TRACKER CLASS
# =============================================================================

class SpreadTracker:
    """
    Отслеживает спреды между биржами
    
    Third Observer проверяет:
    - Есть ли edge между BingX и Binance
    - Стоит ли открывать позицию
    """
    
    def __init__(self):
        self.spreads: Dict[str, List[Dict]] = {}  # symbol: [spreads]
        self.max_history = 100
        
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("📊 SpreadTracker initialized")
    
    async def get_bingx_price(self, symbol: str) -> Optional[float]:
        """Получает цену с BingX"""
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
            params = {"symbol": symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            return float(data.get("data", {}).get("lastPrice", 0))
        except Exception as e:
            logger.error(f"BingX price error for {symbol}: {e}")
        
        return None
    
    async def get_binance_price(self, symbol: str) -> Optional[float]:
        """Получает цену с Binance"""
        try:
            # Конвертируем символ (ETH-USDT -> ETHUSDT)
            binance_symbol = symbol.replace("-", "")
            url = f"https://fapi.binance.com/fapi/v1/ticker/price"
            params = {"symbol": binance_symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("price", 0))
        except Exception as e:
            logger.error(f"Binance price error for {symbol}: {e}")
        
        return None
    
    async def check_spread(self, symbol: str) -> Dict[str, Any]:
        """
        Проверяет спред между биржами
        
        Returns:
            Dict с данными о спреде
        """
        bingx_price = await self.get_bingx_price(symbol)
        binance_price = await self.get_binance_price(symbol)
        
        if not bingx_price or not binance_price:
            return {
                "symbol": symbol,
                "error": "Failed to get prices",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Рассчитываем спред
        spread_pct = ((bingx_price - binance_price) / binance_price) * 100
        
        spread_data = {
            "symbol": symbol,
            "bingx_price": bingx_price,
            "binance_price": binance_price,
            "spread_pct": round(spread_pct, 4),
            "abs_spread_pct": round(abs(spread_pct), 4),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Сохраняем в историю
        if symbol not in self.spreads:
            self.spreads[symbol] = []
        
        self.spreads[symbol].append(spread_data)
        
        if len(self.spreads[symbol]) > self.max_history:
            self.spreads[symbol] = self.spreads[symbol][-self.max_history:]
        
        return spread_data
    
    def should_open_on_bingx(
        self,
        symbol: str,
        side: str
    ) -> Tuple[bool, str, float]:
        """
        Third Observer - проверяет стоит ли открывать на BingX
        
        Args:
            symbol: Торговая пара
            side: LONG / SHORT
        
        Returns:
            Tuple[should_open, reason, edge_pct]
        """
        if not SPREAD_CONFIG["enabled"]:
            return True, "Spread check disabled", 0.0
        
        history = self.spreads.get(symbol, [])
        if not history:
            return True, "No spread data", 0.0
        
        latest = history[-1]
        spread_pct = latest.get("spread_pct", 0)
        abs_spread = latest.get("abs_spread_pct", 0)
        
        # Проверяем edge
        min_edge = SPREAD_CONFIG["min_edge_pct"]
        
        if side.upper() == "LONG":
            # Для LONG хотим купить дешевле
            # Если BingX дешевле Binance (spread < 0) - хорошо
            if spread_pct < -min_edge:
                return True, f"BingX cheaper by {abs_spread:.3f}%", abs_spread
            elif spread_pct > min_edge:
                return False, f"BingX more expensive by {spread_pct:.3f}%", -spread_pct
        
        elif side.upper() == "SHORT":
            # Для SHORT хотим продать дороже
            # Если BingX дороже Binance (spread > 0) - хорошо
            if spread_pct > min_edge:
                return True, f"BingX higher by {spread_pct:.3f}%", spread_pct
            elif spread_pct < -min_edge:
                return False, f"BingX lower by {abs_spread:.3f}%", spread_pct
        
        # Нейтральный спред - открываем
        return True, f"Neutral spread ({spread_pct:.3f}%)", 0.0
    
    def get_average_spread(self, symbol: str, periods: int = 20) -> float:
        """Возвращает средний спред за N периодов"""
        history = self.spreads.get(symbol, [])
        if not history:
            return 0.0
        
        recent = history[-periods:]
        spreads = [h.get("abs_spread_pct", 0) for h in recent]
        
        return sum(spreads) / len(spreads) if spreads else 0.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по спредам"""
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "pairs_tracked": len(self.spreads),
            "by_pair": {}
        }
        
        for symbol, history in self.spreads.items():
            if history:
                spreads = [h.get("abs_spread_pct", 0) for h in history]
                stats["by_pair"][symbol] = {
                    "data_points": len(history),
                    "avg_spread": round(sum(spreads) / len(spreads), 4),
                    "max_spread": round(max(spreads), 4),
                    "min_spread": round(min(spreads), 4),
                    "latest": history[-1].get("spread_pct", 0)
                }
        
        return stats
    
    async def run(self, pairs: List[str], interval: int = None):
        """
        Запускает цикл мониторинга спредов
        
        Args:
            pairs: Список пар для мониторинга
            interval: Интервал проверки (секунды)
        """
        interval = interval or SPREAD_CONFIG["check_interval_seconds"]
        
        logger.info(f"🚀 SpreadTracker started for {len(pairs)} pairs")
        
        while True:
            for symbol in pairs:
                try:
                    await self.check_spread(symbol)
                except Exception as e:
                    logger.error(f"Spread check error for {symbol}: {e}")
                
                await asyncio.sleep(1)  # Небольшая задержка между парами
            
            # Сохраняем логи
            self._save_log()
            
            await asyncio.sleep(interval)
    
    def _save_log(self):
        """Сохраняет лог спредов"""
        try:
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "statistics": self.get_statistics()
            }
            
            with open(SPREAD_LOG, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save spread log: {e}")


# =============================================================================
# 🚀 SINGLETON
# =============================================================================

_tracker_instance: Optional[SpreadTracker] = None

def get_spread_tracker() -> SpreadTracker:
    """Возвращает singleton экземпляр"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = SpreadTracker()
    return _tracker_instance


# =============================================================================
# 🎯 ENTRY POINT
# =============================================================================

async def main():
    """Entry point"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.config import DEFAULT_PAIRS
    
    tracker = SpreadTracker()
    await tracker.run(DEFAULT_PAIRS[:10])  # Топ 10 пар


if __name__ == "__main__":
    asyncio.run(main())
