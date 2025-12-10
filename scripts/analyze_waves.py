#!/usr/bin/env python3
"""
📊 ANALYZE WAVES v6.0 - ПОЛНАЯ КАРТИНА РЫНКА
============================================
Анализирует все данные и генерирует полный отчёт.

ЗАПУСК:
  python scripts/analyze_waves.py
  
  # Внутри Docker:
  docker exec bablobot_live python3 /app/scripts/analyze_waves.py

СОХРАНЯЕТ В:
  user_data/logs/daily_analysis/YYYY-MM-DD_HH.json
  user_data/logs/daily_analysis/latest.json

Автор: AI Architect для проекта "Кнопка БАБЛО"
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | ANALYZER | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Setup paths
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

LOGS_DIR = BASE_DIR / "user_data" / "logs"
DATA_DIR = BASE_DIR / "user_data" / "data"
OUTPUT_DIR = LOGS_DIR / "daily_analysis"

# =============================================================================
# 📊 ANALYZER CLASS
# =============================================================================

class WaveAnalyzer:
    """Анализатор рыночных волн и торговых данных"""
    
    VERSION = "6.0"
    
    def __init__(self):
        self.trades: List[Dict] = []
        self.stats: Dict[str, Any] = {}
        self.positions: List[Dict] = []
        self.btc_data: List[Dict] = []
        self.volume_data: List[Dict] = []
        self.spot_flow_data: List[Dict] = []
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_data(self, period_hours: int = 24):
        """Загружает все данные за период"""
        logger.info(f"📥 Loading data for last {period_hours} hours...")
        
        cutoff = datetime.utcnow() - timedelta(hours=period_hours)
        
        # Trades
        self.trades = self._load_trades(cutoff)
        logger.info(f"   Trades: {len(self.trades)}")
        
        # Stats
        self.stats = self._load_stats()
        
        # BTC data
        self.btc_data = self._load_jsonl_data(DATA_DIR / "btc_watcher", cutoff)
        logger.info(f"   BTC data points: {len(self.btc_data)}")
        
        # Volume data
        self.volume_data = self._load_jsonl_data(DATA_DIR / "volume", cutoff)
        logger.info(f"   Volume data points: {len(self.volume_data)}")
        
        # Spot flow data
        self.spot_flow_data = self._load_jsonl_data(DATA_DIR / "spot_flow", cutoff)
        logger.info(f"   Spot flow data points: {len(self.spot_flow_data)}")
    
    def _load_trades(self, cutoff: datetime) -> List[Dict]:
        """Загружает сделки"""
        trades_file = LOGS_DIR / "trades.json"
        if not trades_file.exists():
            return []
        
        try:
            with open(trades_file, 'r') as f:
                all_trades = json.load(f)
            
            if not isinstance(all_trades, list):
                all_trades = [all_trades] if all_trades else []
            
            # Фильтруем по времени
            filtered = []
            for t in all_trades:
                try:
                    ts = t.get("closed_at") or t.get("opened_at")
                    if ts:
                        trade_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        if trade_time.replace(tzinfo=None) >= cutoff:
                            filtered.append(t)
                except:
                    pass
            
            return filtered
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            return []
    
    def _load_stats(self) -> Dict[str, Any]:
        """Загружает статистику"""
        stats_file = LOGS_DIR / "stats.json"
        if stats_file.exists():
            try:
                with open(stats_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _load_jsonl_data(self, directory: Path, cutoff: datetime) -> List[Dict]:
        """Загружает данные из JSONL файлов"""
        if not directory.exists():
            return []
        
        data = []
        for file in sorted(directory.glob("*.jsonl")):
            try:
                with open(file, 'r') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line)
                            ts = entry.get("_timestamp")
                            if ts:
                                try:
                                    entry_time = datetime.fromisoformat(ts)
                                    if entry_time >= cutoff:
                                        data.append(entry)
                                except:
                                    data.append(entry)
            except Exception as e:
                logger.error(f"Failed to load {file}: {e}")
        
        return data
    
    def analyze(self) -> Dict[str, Any]:
        """Выполняет полный анализ"""
        logger.info("🔍 Analyzing data...")
        
        result = {
            "meta": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": self.VERSION,
                "period_hours": 24
            },
            "summary": self._analyze_summary(),
            "market_state": self._analyze_market_state(),
            "direction_by_hour": self._analyze_direction_by_hour(),
            "pairs_detailed": self._analyze_pairs(),
            "pairs_ranking": self._rank_pairs(),
            "waves": self._analyze_waves(),
            "period_analysis": self._analyze_periods(),
            "btc_correlation": self._analyze_btc_correlation(),
            "recommendations": self._generate_recommendations(),
            "conclusions": self._generate_conclusions(),
            "alerts": self._generate_alerts()
        }
        
        return result
    
    def _analyze_summary(self) -> Dict[str, Any]:
        """Сводка по сделкам"""
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        
        if not closed:
            return {
                "trades_total": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_duration_min": 0
            }
        
        wins = sum(1 for t in closed if t.get("pnl_pct", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        avg_duration = sum(t.get("duration_minutes", 0) for t in closed) / len(closed)
        
        # Сделок в час
        hours_span = 24
        if closed:
            first_ts = min(t.get("opened_at", "") for t in closed if t.get("opened_at"))
            last_ts = max(t.get("closed_at", "") for t in closed if t.get("closed_at"))
            if first_ts and last_ts:
                try:
                    first = datetime.fromisoformat(first_ts)
                    last = datetime.fromisoformat(last_ts)
                    hours_span = max((last - first).total_seconds() / 3600, 1)
                except:
                    pass
        
        return {
            "trades_total": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": wins / len(closed) if closed else 0,
            "total_pnl": total_pnl,
            "total_pnl_pct": sum(t.get("pnl_pct", 0) for t in closed),
            "avg_duration_min": avg_duration,
            "trades_per_hour": len(closed) / hours_span,
            "best_trade_pnl": max(t.get("pnl_pct", 0) for t in closed) if closed else 0,
            "worst_trade_pnl": min(t.get("pnl_pct", 0) for t in closed) if closed else 0
        }
    
    def _analyze_market_state(self) -> Dict[str, Any]:
        """Анализ текущего состояния рынка"""
        if not self.btc_data:
            return {"bias": "UNKNOWN", "volatility": "UNKNOWN"}
        
        latest = self.btc_data[-1] if self.btc_data else {}
        
        btc_change = latest.get("btc_change_1h", 0)
        eth_change = latest.get("eth_change_1h", 0)
        
        # Bias
        avg_change = (btc_change + eth_change) / 2
        if avg_change > 1.0:
            bias = "BULLISH"
        elif avg_change < -1.0:
            bias = "BEARISH"
        else:
            bias = "SIDEWAYS"
        
        # Volatility
        if self.btc_data and len(self.btc_data) > 10:
            changes = [d.get("btc_change_1h", 0) for d in self.btc_data[-20:]]
            volatility_score = sum(abs(c) for c in changes) / len(changes)
            if volatility_score > 2:
                volatility = "HIGH"
            elif volatility_score > 0.5:
                volatility = "MEDIUM"
            else:
                volatility = "LOW"
        else:
            volatility = "UNKNOWN"
        
        return {
            "bias": bias,
            "volatility": volatility,
            "btc_price": latest.get("btc_price", 0),
            "btc_change_1h": btc_change,
            "eth_price": latest.get("eth_price", 0),
            "eth_change_1h": eth_change,
            "alerts": latest.get("alerts", [])
        }
    
    def _analyze_direction_by_hour(self) -> Dict[str, Any]:
        """Анализ направлений по часам"""
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        
        by_hour = defaultdict(lambda: {"long": 0, "short": 0, "pnl": 0})
        
        for t in closed:
            try:
                ts = t.get("closed_at") or t.get("opened_at")
                if ts:
                    hour = datetime.fromisoformat(ts).hour
                    side = t.get("side", "LONG").upper()
                    if "LONG" in side:
                        by_hour[hour]["long"] += 1
                    else:
                        by_hour[hour]["short"] += 1
                    by_hour[hour]["pnl"] += t.get("pnl", 0)
            except:
                pass
        
        # Определяем доминантное направление
        total_long = sum(h["long"] for h in by_hour.values())
        total_short = sum(h["short"] for h in by_hour.values())
        
        if total_long > total_short * 1.5:
            dominant = "LONG"
        elif total_short > total_long * 1.5:
            dominant = "SHORT"
        else:
            dominant = "MIXED"
        
        return {
            "by_hour": dict(by_hour),
            "total_long": total_long,
            "total_short": total_short,
            "dominant": dominant,
            "conclusion": f"Преобладает {dominant} ({total_long}L / {total_short}S)"
        }
    
    def _analyze_pairs(self) -> Dict[str, Dict]:
        """Детальный анализ по парам"""
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        
        pairs = defaultdict(lambda: {
            "trades": 0,
            "wins": 0,
            "pnl": 0,
            "avg_duration": 0,
            "durations": []
        })
        
        for t in closed:
            symbol = t.get("symbol", "unknown")
            pairs[symbol]["trades"] += 1
            if t.get("pnl_pct", 0) > 0:
                pairs[symbol]["wins"] += 1
            pairs[symbol]["pnl"] += t.get("pnl", 0)
            pairs[symbol]["durations"].append(t.get("duration_minutes", 0))
        
        result = {}
        for symbol, data in pairs.items():
            avg_dur = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0
            
            # Определяем характер пары
            if avg_dur < 15:
                character = "SCALP"
            elif avg_dur < 30:
                character = "FAST"
            elif avg_dur < 60:
                character = "NORMAL"
            else:
                character = "ANCHOR"
            
            result[symbol] = {
                "trades": data["trades"],
                "wins": data["wins"],
                "win_rate": data["wins"] / data["trades"] if data["trades"] > 0 else 0,
                "pnl": data["pnl"],
                "avg_duration_min": avg_dur,
                "character": character
            }
        
        return result
    
    def _rank_pairs(self) -> List[Dict]:
        """Рейтинг пар по эффективности"""
        pairs_data = self._analyze_pairs()
        
        ranked = []
        for symbol, data in pairs_data.items():
            # Score = PnL / время (эффективность $/мин)
            if data["avg_duration_min"] > 0:
                score = data["pnl"] / data["avg_duration_min"]
            else:
                score = 0
            
            ranked.append({
                "symbol": symbol,
                "score": score,
                "trades": data["trades"],
                "win_rate": data["win_rate"],
                "pnl": data["pnl"],
                "character": data["character"]
            })
        
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked
    
    def _analyze_waves(self) -> List[Dict]:
        """Анализ 2-часовых волн"""
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        
        waves = defaultdict(lambda: {"trades": 0, "pnl": 0, "directions": []})
        
        for t in closed:
            try:
                ts = t.get("closed_at") or t.get("opened_at")
                if ts:
                    hour = datetime.fromisoformat(ts).hour
                    wave_id = hour // 2  # 2-часовые блоки
                    waves[wave_id]["trades"] += 1
                    waves[wave_id]["pnl"] += t.get("pnl", 0)
                    waves[wave_id]["directions"].append(t.get("side", "LONG"))
            except:
                pass
        
        result = []
        for wave_id, data in sorted(waves.items()):
            long_count = sum(1 for d in data["directions"] if "LONG" in d.upper())
            short_count = len(data["directions"]) - long_count
            
            if data["pnl"] > 0 and data["trades"] > 2:
                character = "PROFITABLE"
            elif data["pnl"] < 0:
                character = "LOSING"
            else:
                character = "NEUTRAL"
            
            result.append({
                "wave_id": wave_id,
                "hours": f"{wave_id*2:02d}-{wave_id*2+2:02d}",
                "trades": data["trades"],
                "pnl": data["pnl"],
                "long": long_count,
                "short": short_count,
                "character": character
            })
        
        return result
    
    def _analyze_periods(self) -> Dict[str, Dict]:
        """Анализ по периодам (ночь/день/вечер)"""
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        
        periods = {
            "night": {"hours": "00-08", "trades": 0, "wins": 0, "pnl": 0, "durations": []},
            "day": {"hours": "08-16", "trades": 0, "wins": 0, "pnl": 0, "durations": []},
            "evening": {"hours": "16-24", "trades": 0, "wins": 0, "pnl": 0, "durations": []}
        }
        
        for t in closed:
            try:
                ts = t.get("closed_at") or t.get("opened_at")
                if ts:
                    hour = datetime.fromisoformat(ts).hour
                    
                    if 0 <= hour < 8:
                        period = "night"
                    elif 8 <= hour < 16:
                        period = "day"
                    else:
                        period = "evening"
                    
                    periods[period]["trades"] += 1
                    if t.get("pnl_pct", 0) > 0:
                        periods[period]["wins"] += 1
                    periods[period]["pnl"] += t.get("pnl", 0)
                    periods[period]["durations"].append(t.get("duration_minutes", 0))
            except:
                pass
        
        for period in periods.values():
            period["win_rate"] = period["wins"] / period["trades"] if period["trades"] > 0 else 0
            period["avg_duration"] = sum(period["durations"]) / len(period["durations"]) if period["durations"] else 0
            del period["durations"]
        
        return periods
    
    def _analyze_btc_correlation(self) -> Dict[str, Any]:
        """Анализ корреляции с BTC"""
        if not self.btc_data or not self.trades:
            return {"correlation": "UNKNOWN"}
        
        # Упрощённый анализ - сравниваем направления
        btc_ups = sum(1 for d in self.btc_data if d.get("btc_change_1h", 0) > 0)
        btc_downs = len(self.btc_data) - btc_ups
        
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        long_wins = sum(1 for t in closed if t.get("side", "").upper() == "LONG" and t.get("pnl_pct", 0) > 0)
        short_wins = sum(1 for t in closed if t.get("side", "").upper() == "SHORT" and t.get("pnl_pct", 0) > 0)
        
        return {
            "btc_up_periods": btc_ups,
            "btc_down_periods": btc_downs,
            "long_wins": long_wins,
            "short_wins": short_wins,
            "recommendation": "Follow BTC trend" if btc_ups > btc_downs else "Contrarian might work"
        }
    
    def _generate_recommendations(self) -> Dict[str, Any]:
        """Генерирует рекомендации"""
        periods = self._analyze_periods()
        pairs_ranking = self._rank_pairs()
        
        # Лучшие часы
        best_period = max(periods.items(), key=lambda x: x[1].get("pnl", 0))
        worst_period = min(periods.items(), key=lambda x: x[1].get("pnl", 0))
        
        return {
            "best_period": best_period[0],
            "best_period_hours": best_period[1]["hours"],
            "worst_period": worst_period[0],
            "top_pairs": [p["symbol"] for p in pairs_ranking[:5]],
            "problem_pairs": [p["symbol"] for p in pairs_ranking[-3:] if p["pnl"] < 0],
            "action_items": self._generate_action_items()
        }
    
    def _generate_action_items(self) -> List[str]:
        """Генерирует список действий"""
        items = []
        
        summary = self._analyze_summary()
        if summary.get("win_rate", 0) < 0.9:
            items.append("⚠️ Win rate < 90% - проверить стратегию")
        
        periods = self._analyze_periods()
        for period, data in periods.items():
            if data.get("pnl", 0) < 0:
                items.append(f"⚠️ {period} в минусе - рассмотреть отключение")
        
        pairs_ranking = self._rank_pairs()
        for pair in pairs_ranking[-3:]:
            if pair.get("pnl", 0) < 0:
                items.append(f"❌ {pair['symbol']} убыточна - добавить в blacklist?")
        
        if not items:
            items.append("✅ Всё работает отлично!")
        
        return items
    
    def _generate_conclusions(self) -> List[str]:
        """Генерирует выводы"""
        conclusions = []
        
        summary = self._analyze_summary()
        conclusions.append(f"📊 Всего сделок: {summary.get('trades_total', 0)}")
        conclusions.append(f"📈 Win Rate: {summary.get('win_rate', 0)*100:.1f}%")
        conclusions.append(f"💰 Total PnL: ${summary.get('total_pnl', 0):.2f}")
        conclusions.append(f"⏱️ Avg duration: {summary.get('avg_duration_min', 0):.1f} min")
        
        market = self._analyze_market_state()
        conclusions.append(f"🎯 Market: {market.get('bias', 'UNKNOWN')} / {market.get('volatility', 'UNKNOWN')}")
        
        return conclusions
    
    def _generate_alerts(self) -> List[str]:
        """Генерирует алерты"""
        alerts = []
        
        # BTC alerts
        market = self._analyze_market_state()
        if market.get("alerts"):
            alerts.extend(market["alerts"])
        
        # Performance alerts
        summary = self._analyze_summary()
        if summary.get("win_rate", 1) < 0.8:
            alerts.append("🚨 Win Rate падает!")
        
        return alerts
    
    def save_report(self, report: Dict[str, Any]):
        """Сохраняет отчёт"""
        ts = datetime.utcnow().strftime("%Y-%m-%d_%H")
        
        # По времени
        filepath = OUTPUT_DIR / f"{ts}.json"
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Latest
        latest_path = OUTPUT_DIR / "latest.json"
        with open(latest_path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📁 Report saved: {filepath}")
        logger.info(f"📁 Latest updated: {latest_path}")


# =============================================================================
# 🚀 ENTRY POINT
# =============================================================================

def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze trading waves")
    parser.add_argument("--period", type=int, default=24, help="Period in hours")
    args = parser.parse_args()
    
    analyzer = WaveAnalyzer()
    analyzer.load_data(period_hours=args.period)
    
    report = analyzer.analyze()
    analyzer.save_report(report)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 WAVE ANALYSIS COMPLETE")
    print("="*60)
    
    for conclusion in report.get("conclusions", []):
        print(conclusion)
    
    print("\n📋 Recommendations:")
    recs = report.get("recommendations", {})
    print(f"   Best period: {recs.get('best_period', 'N/A')}")
    print(f"   Top pairs: {', '.join(recs.get('top_pairs', [])[:3])}")
    
    print("\n⚠️ Action items:")
    for item in recs.get("action_items", []):
        print(f"   {item}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
