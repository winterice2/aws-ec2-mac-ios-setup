# 🎯 КНОПКА БАБЛО - Автономная Торговая Экосистема v2.0

> **Проект Павла (@dxbatr) - 13+ лет в крипте**  
> AI архитектура и исполнение by Claude

---

## 🧠 ECOSYSTEM BRAIN - Автономный Мозг

Система которая **ДУМАЕТ** как топовая LLM:
- Собирает ВСЕ данные из всех источников
- Анализирует контекст с помощью Gemini AI
- Принимает решения автономно
- Когда не может решить - записывает в feedback

### 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    ECOSYSTEM BRAIN v2.0                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Data        │  │ Signal      │  │ Position    │          │
│  │ Collectors  │→ │ Engine      │→ │ Manager     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         ↓                ↓                ↓                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              GEMINI AI (2.5 Flash)                  │    │
│  │  - Анализ каждые 15 мин                             │    │
│  │  - Изменение config                                 │    │
│  │  - Блокировка сигналов                              │    │
│  └─────────────────────────────────────────────────────┘    │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              BRAIN POLICY (железные правила)        │    │
│  │  - Safety Bounds                                    │    │
│  │  - Rate Limits                                      │    │
│  │  - Emergency Safeguards                             │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 📊 Уровни Развития

| Уровень | Описание | Статус |
|---------|----------|--------|
| **1** | Brain меняет config_override.json, закрывает позиции | ✅ READY |
| **2** | WebSocket, видит каждый тик, блокирует сигналы | ✅ READY |
| **3** | ML модель, полная автономия | 🔄 TODO |

---

## 🚀 Быстрый Старт

### 1. Настройка окружения

```bash
# Клонируем репозиторий
git clone <repo_url>
cd workspace

# Копируем и заполняем .env
cp .env.example .env
nano .env  # Вставьте API ключи
```

### 2. Запуск

```bash
# Только основной бот
docker-compose up -d

# + Мониторинг BTC/ETH и объёмов
docker-compose --profile watcher up -d

# + Brain (автономный мозг)
docker-compose --profile brain up -d

# ВСЁ
docker-compose --profile full up -d
```

### 3. Проверка

```bash
# Логи бота
docker logs bablobot_live -f

# Логи Brain
docker logs bablobot_brain -f

# Статистика
cat user_data/logs/stats.json | jq
```

---

## 📁 Структура Проекта

```
/workspace/
├── config/
│   ├── config.py              # Центральный конфиг
│   └── config_override.json   # Brain пишет сюда
│
├── scripts/
│   ├── bablobot/
│   │   ├── ecosystem_brain.py # 🧠 Автономный мозг
│   │   ├── brain_policy.py    # 🔒 Железные правила
│   │   ├── data_collectors.py # 📊 Сбор данных
│   │   ├── signals.py         # 📡 Генерация сигналов
│   │   ├── position_manager.py# 💼 Управление позициями
│   │   └── websocket_layer.py # 🌐 Real-time данные
│   │
│   └── analyze_waves.py       # 📈 Анализ рынка
│
├── user_data/
│   ├── logs/
│   │   ├── ecosystem_feedback/
│   │   │   ├── errors/        # ❌ Ошибки
│   │   │   ├── unsolved/      # ❓ Нерешённые проблемы
│   │   │   ├── needs/         # 📝 Что нужно добавить
│   │   │   └── decisions/     # ⚡ Решения Brain
│   │   │
│   │   ├── daily_analysis/    # Ежедневные отчёты
│   │   ├── trades.json        # История сделок
│   │   ├── stats.json         # Статистика
│   │   └── brain.log          # Лог Brain
│   │
│   └── data/
│       ├── btc_watcher/       # BTC/ETH данные
│       ├── volume/            # Объёмы торгов
│       ├── spot_flow/         # BUY/SELL pressure
│       └── lag_data/          # WebSocket raw data
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🎯 Ключевые Модули

### 🧠 Ecosystem Brain (`ecosystem_brain.py`)

Автономный мозг системы:
- Собирает ВСЕ данные каждые 15 минут
- Анализирует через Gemini AI
- Принимает решения и выполняет
- Записывает проблемы в feedback

```python
# Запуск
python -m scripts.bablobot.ecosystem_brain
```

### 🔒 Brain Policy (`brain_policy.py`)

Железные правила которые Brain НЕ МОЖЕТ нарушить:
- **SAFETY_BOUNDS**: пределы значений параметров
- **Rate Limits**: max 2 изменения в час
- **Emergency Safeguards**: автопауза при DD

### 📊 Data Collectors (`data_collectors.py`)

| Коллектор | Интервал | Что собирает |
|-----------|----------|--------------|
| BTCWatcher | 60s | BTC/ETH цены, изменения, алерты |
| VolumeCollector | 5min | Объёмы по всем парам |
| SpotFlowCollector | 2min | BUY/SELL pressure |
| PositionsCollector | 30s | Текущие позиции |
| StatsCollector | 60s | Торговая статистика |

### 📡 Signal Engine (`signals.py`)

Модули сигналов:
- **Momentum Detector**: импульсы >0.18%/15s
- **BTC Trend Guard**: блокировка по тренду BTC
- **Spot Flow Signals**: по давлению покупок/продаж
- **Time Phase Filter**: фильтр по времени суток

### 💼 Position Manager (`position_manager.py`)

- Открытие позиций через BingX API
- Мониторинг TP (трёхфазный)
- Emergency Exit
- Логирование сделок

### 🌐 WebSocket Layer (`websocket_layer.py`)

Real-time данные:
- Тики каждые 100ms
- Сделки в реальном времени
- Детекция спайков цены/объёма

---

## ⚙️ Конфигурация

### Трёхфазный TP (по UTC)

| Фаза | Время | TP | Режим |
|------|-------|-----|-------|
| 🌙 Ночь | 00-08 | 2.45% | AGGRESSIVE, LONG+SHORT |
| ☀️ День | 08-16 | 2.20% | LONG_ONLY (без SHORT!) |
| 🌆 Вечер | 16-24 | 2.80% | CONSERVATIVE |

### BTC Trend Guard

- BTC +1.5%/час → блокируем SHORT
- BTC -1.5%/час → блокируем LONG
- Кешируется на 60 сек

### Safety Bounds

```python
SAFETY_BOUNDS = {
    "momentum_threshold_fast": {"min": 0.001, "max": 0.003},
    "momentum_threshold_slow": {"min": 0.0008, "max": 0.002},
    "min_profit_pct": {"min": 0.015, "max": 0.06, "protected": True},
    "max_leverage": {"min": 2, "max": 15, "only_down": True},
    "max_positions": {"min": 5, "max": 24}
}
```

---

## 📈 Мониторинг и Анализ

### Анализ рынка

```bash
# Ручной запуск
python scripts/analyze_waves.py

# Внутри Docker
docker exec bablobot_live python3 /app/scripts/analyze_waves.py

# Последний отчёт
cat user_data/logs/daily_analysis/latest.json | jq
```

### Логи

```bash
# Brain решения
tail -f user_data/logs/brain.log

# Brain audit (JSONL)
tail user_data/logs/brain_audit.jsonl

# Ошибки экосистемы
ls user_data/logs/ecosystem_feedback/errors/

# Нерешённые проблемы
ls user_data/logs/ecosystem_feedback/unsolved/
```

---

## 🔐 Gemini API

| Модель | Назначение | Стоимость |
|--------|------------|-----------|
| gemini-2.5-flash | Brain 24/7 | $0.30/1M in + $2.50/1M out |
| gemini-2.5-pro | R&D анализ | $1.25/1M in + $10/1M out |
| gemini-3-pro-preview | Глубокий анализ | $2/1M in + $12/1M out |

API Key: Задан по умолчанию, €1034 кредитов Google Cloud

---

## 🛡️ Принципы Работы

### Главный принцип
> **Не закрывать позиции в минусе если нет угрозы ликвидации!**

Крипта волатильная - позиция может быть -90% и откатиться.

### Feedback Loop

1. Экосистема работает автономно
2. Когда не может решить проблему - записывает в feedback
3. Мы видим feedback и добавляем новый код
4. Экосистема становится умнее
5. Повторяем

---

## 📊 Торговые Пары

### Whitelist (приоритет)
WIF, SUI, NEAR, FET, ARB, SOL, DOGE, BNB

### Blacklist (медленные "якоря")
LTC, UNI, SEI, XRP, POL, ATOM, CRV

---

## 🚨 Emergency

### Автопауза
- Daily DD > -5% → автопауза
- Weekly DD > -15% → автопауза
- 3 ухудшения подряд → блок Brain

### Emergency Exit
- Позиция > 180 мин И PnL < 0.5% → FORCE CLOSE

---

## 📞 Контакты

**Владелец:** Павел (@dxbatr)  
**AI Architect:** Claude

---

## 📜 Лицензия

Проприетарный код. Все права защищены.
