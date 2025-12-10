"""
📈 POST-TRADE TRACKER - ОТСЛЕЖИВАНИЕ ЦЕНЫ ПОСЛЕ ЗАКРЫТИЯ
=======================================================
После закрытия позиции отслеживает куда пошла цена.

ЗАЧЕМ:
- Понять оптимальный TP
- Если цена продолжает идти в нашу сторону → увеличить TP
- Если разворачивается → TP правильный

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import json
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import aiohttp

logger = logging.getLogger(__name__)

# =============================================================================
# 📊 CONFIG
# =============================================================================

TRACKING_CONFIG = {
    "enabled": True,
    "track_minutes": [1, 5, 15, 30, 60],  # Когда проверять цену
    "max_tracking_minutes": 60
}

LOGS_DIR = Path("/workspace/user_data/logs")
POST_TRADE_LOG = LOGS_DIR / "post_trade_log.json"

# =============================================================================
# 📈 POST-TRADE TRACKER CLASS
# =============================================================================

class PostTradeTracker:
    """
    Отслеживает цену после закрытия позиции
    
    После TP записывает:
    - Цену через 1/5/15/30/60 минут
    - Определяет: continued / reversed / sideways
    """
    
    def __init__(self):
        self.active_tracks: Dict[str, Dict] = {}  # track_id: data
        self.results: List[Dict] = []
        
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_results()
        
        logger.info("📈 PostTradeTracker initialized")
    
    def _load_results(self):
        """Загружает результаты"""
        if POST_TRADE_LOG.exists():
            try:
                with open(POST_TRADE_LOG, 'r') as f:
                    self.results = json.load(f)
            except:
                self.results = []
    
    def _save_results(self):
        """Сохраняет результаты"""
        with open(POST_TRADE_LOG, 'w') as f:
            json.dump(self.results, f, indent=2)
    
    async def start_tracking(
        self,
        symbol: str,
        side: str,
        exit_price: float,
        pnl_pct: float,
        tp_pct: float
    ):
        """
        Начинает отслеживание после закрытия
        
        Args:
            symbol: Торговая пара
            side: LONG / SHORT
            exit_price: Цена закрытия
            pnl_pct: PnL в процентах
            tp_pct: TP который был установлен
        """
        if not TRACKING_CONFIG["enabled"]:
            return
        
        track_id = f"{symbol}_{int(time.time())}"
        
        self.active_tracks[track_id] = {
            "symbol": symbol,
            "side": side,
            "exit_price": exit_price,
            "exit_time": datetime.utcnow().isoformat(),
            "pnl_pct": pnl_pct,
            "tp_pct": tp_pct,
            "price_checks": {}
        }
        
        logger.info(f"📈 Started tracking {symbol} (exit: ${exit_price})")
        
        # Запускаем фоновое отслеживание
        asyncio.create_task(self._track_prices(track_id))
    
    async def _track_prices(self, track_id: str):
        """Фоновое отслеживание цен"""
        track_data = self.active_tracks.get(track_id)
        if not track_data:
            return
        
        symbol = track_data["symbol"]
        exit_price = track_data["exit_price"]
        side = track_data["side"]
        
        for minutes in TRACKING_CONFIG["track_minutes"]:
            # Ждём
            await asyncio.sleep(minutes * 60)
            
            # Получаем текущую цену
            current_price = await self._get_price(symbol)
            
            if current_price:
                # Рассчитываем изменение
                if exit_price > 0:
                    change_pct = ((current_price - exit_price) / exit_price) * 100
                else:
                    change_pct = 0
                
                # Для SHORT инвертируем
                if "SHORT" in side.upper():
                    change_pct = -change_pct
                
                track_data["price_checks"][f"{minutes}m"] = {
                    "price": current_price,
                    "change_pct": round(change_pct, 3),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                logger.info(f"📊 {symbol} after {minutes}m: {change_pct:+.2f}%")
        
        # Анализируем результат
        result = self._analyze_tracking(track_id)
        self.results.append(result)
        self._save_results()
        
        # Удаляем из активных
        del self.active_tracks[track_id]
        
        logger.info(f"✅ Tracking complete for {symbol}: {result['outcome']}")
    
    async def _get_price(self, symbol: str) -> Optional[float]:
        """Получает текущую цену"""
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
            params = {"symbol": symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            return float(data.get("data", {}).get("lastPrice", 0))
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
        
        return None
    
    def _analyze_tracking(self, track_id: str) -> Dict[str, Any]:
        """Анализирует результат отслеживания"""
        track_data = self.active_tracks.get(track_id, {})
        checks = track_data.get("price_checks", {})
        
        # Получаем последнее изменение
        final_change = 0
        for key in ["60m", "30m", "15m", "5m", "1m"]:
            if key in checks:
                final_change = checks[key].get("change_pct", 0)
                break
        
        # Определяем outcome
        if final_change > 1.0:
            outcome = "continued"  # Цена продолжила в нашу сторону
        elif final_change < -1.0:
            outcome = "reversed"  # Развернулась против нас
        else:
            outcome = "sideways"  # Боковик
        
        # Рекомендация
        if outcome == "continued":
            recommendation = "INCREASE_TP"
        elif outcome == "reversed":
            recommendation = "KEEP_TP"
        else:
            recommendation = "MONITOR"
        
        return {
            "track_id": track_id,
            "symbol": track_data.get("symbol"),
            "side": track_data.get("side"),
            "exit_price": track_data.get("exit_price"),
            "exit_time": track_data.get("exit_time"),
            "original_pnl_pct": track_data.get("pnl_pct"),
            "original_tp_pct": track_data.get("tp_pct"),
            "price_checks": checks,
            "final_change_pct": final_change,
            "outcome": outcome,
            "recommendation": recommendation,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по post-trade tracking"""
        if not self.results:
            return {"total": 0}
        
        continued = sum(1 for r in self.results if r.get("outcome") == "continued")
        reversed_count = sum(1 for r in self.results if r.get("outcome") == "reversed")
        sideways = sum(1 for r in self.results if r.get("outcome") == "sideways")
        
        avg_final_change = sum(r.get("final_change_pct", 0) for r in self.results) / len(self.results)
        
        return {
            "total": len(self.results),
            "continued": continued,
            "reversed": reversed_count,
            "sideways": sideways,
            "continued_pct": continued / len(self.results) * 100,
            "reversed_pct": reversed_count / len(self.results) * 100,
            "avg_final_change_pct": round(avg_final_change, 2),
            "recommendation": "INCREASE_TP" if continued > reversed_count else "KEEP_TP"
        }
    
    def get_recommendation(self) -> Dict[str, Any]:
        """Возвращает рекомендацию по TP"""
        stats = self.get_statistics()
        
        if stats["total"] < 10:
            return {
                "action": "COLLECT_MORE_DATA",
                "message": f"Нужно больше данных ({stats['total']}/10)",
                "confidence": 0.3
            }
        
        if stats["continued_pct"] > 60:
            return {
                "action": "INCREASE_TP",
                "message": f"Цена продолжает движение в {stats['continued_pct']:.0f}% случаев",
                "suggested_increase": "+0.5%",
                "confidence": 0.7
            }
        
        if stats["reversed_pct"] > 50:
            return {
                "action": "DECREASE_TP",
                "message": f"Цена разворачивается в {stats['reversed_pct']:.0f}% случаев",
                "suggested_decrease": "-0.3%",
                "confidence": 0.6
            }
        
        return {
            "action": "KEEP_TP",
            "message": "TP оптимален (sideways/mixed)",
            "confidence": 0.5
        }


# =============================================================================
# 🚀 SINGLETON
# =============================================================================

_tracker_instance: Optional[PostTradeTracker] = None

def get_post_trade_tracker() -> PostTradeTracker:
    """Возвращает singleton экземпляр"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PostTradeTracker()
    return _tracker_instance
