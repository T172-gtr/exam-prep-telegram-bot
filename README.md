# ExamBot — Telegram-бот для подготовки к экзаменам

Бот для подготовки к экзаменам (ОГЭ, ЕГЭ, МЦКО, диагностика) для учеников 8–11 классов.
Интерфейс: **русский язык**.

---

## Стек

| Компонент | Версия |
|-----------|--------|
| Python | 3.11+ |
| aiogram | 3.7 |
| SQLAlchemy (async) | 2.0 |
| aiosqlite | 0.20 |
| APScheduler | 3.10 |
| pydantic-settings | 2.5 |

---

## Структура проекта

```
exambot/
├── main.py                      # точка входа
├── config.py                    # настройки (pydantic-settings)
├── requirements.txt
├── .env.example
│
├── db/
│   ├── __init__.py
│   ├── database.py              # engine, async_session, init_db()
│   ├── models.py                # ORM-модели
│   ├── seed.py                  # seed справочников и тестовых заданий
│   └── service.py               # вспомогательные async-функции
│
├── bot/
│   ├── __init__.py
│   ├── states.py                # FSM-состояния
│   ├── handlers/
│   │   ├── __init__.py          # объединяет все роутеры
│   │   ├── start.py             # /start
│   │   ├── onboarding.py        # FSM: класс→экзамен→предмет→уровень→время
│   │   ├── plan.py              # выбор и подтверждение плана
│   │   ├── commands.py          # /profile /progress /today
│   │   ├── tasks.py             # отправка заданий, обработка ответов
│   │   ├── subscribe.py         # /subscribe, заглушка оплаты
│   │   └── admin.py             # /admin /admin_stats /admin_add_task
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── inline.py            # inline-клавиатуры
│   │   └── reply.py             # reply-меню
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── db_session.py        # инжектирует AsyncSession в каждый handler
│   └── filters/
│       ├── __init__.py
│       └── admin.py             # фильтр AdminFilter
│
└── scheduler/
    ├── __init__.py
    └── daily.py                 # APScheduler: ежедневная рассылка заданий
```

---

## Быстрый старт

### 1. Клонировать / перейти в папку

```bash
cd exambot
```

### 2. Создать виртуальное окружение и установить зависимости

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# или .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. Создать `.env`

```bash
cp .env.example .env
```

Заполнить `.env`:

```dotenv
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///./exambot.db
FREE_DAILY_LIMIT=3
PREMIUM_PRICE_RUB=299
TIMEZONE=Europe/Moscow
```

Токен бота получить у [@BotFather](https://t.me/BotFather).

### 4. Запустить

```bash
python main.py
```

При первом запуске:
- автоматически создаётся SQLite база `exambot.db`
- заполняются справочники (классы, экзамены, предметы, шаблоны планов, тестовые задания)
- запускается планировщик

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация + онбординг |
| `/profile` | Профиль пользователя |
| `/progress` | Статистика выполнения заданий |
| `/today` | Получить задание прямо сейчас |
| `/subscribe` | Управление подпиской |
| `/admin` | Панель администратора (только для ADMIN_IDS) |
| `/admin_stats` | Статистика по заданиям |
| `/admin_add_task` | Добавить новое задание (FSM) |

---

## Онбординг

Пошаговый выбор через inline-кнопки:

1. **Класс** — 8, 9, 10, 11
2. **Тип экзамена** — по классу:
   - 8/10: МЦКО или Диагностика
   - 9: ОГЭ
   - 11: ЕГЭ
3. **Предмет** — математика, русский, история и другие (зависит от экзамена)
4. **Целевой уровень**:
   - 🔵 Низкий — базовые задания, минимальный балл
   - 🟢 Средний — уверенная сдача
   - 🟠 Высокий — сложные задания
   - 🔴 Максимальный — полное погружение
5. **Время/день** — 15 / 30 / 45 / 60 / 90 минут
6. **Выбор плана** — из 3 вариантов (классический / интенсивный / тематический)

---

## Ежедневная рассылка

APScheduler отправляет задания в **08:00** по часовому поясу из `TIMEZONE`.

В **00:00** обнуляются счётчики заданий за день и увеличивается номер текущего дня плана.

---

## Подписка

Архитектурная заготовка без реального платёжного шлюза:

- **Бесплатный план**: до `FREE_DAILY_LIMIT` заданий в день
- **Premium (месяц / год)**: безлимитные задания, таблицы `subscriptions` и `payments` заполняются
- При нажатии кнопки оплаты — имитация успешной транзакции (`status="success"`, `provider_tx_id="STUB-N"`)

Для подключения реального шлюза (ЮKassa, Robokassa и т.д.) — заменить заглушку в `bot/handlers/subscribe.py::cb_pay`.

---

## База данных

SQLite, все таблицы создаются автоматически при запуске:

| Таблица | Описание |
|---------|----------|
| `grade_levels` | Классы 8–11 |
| `exam_types` | Типы экзаменов (ОГЭ, ЕГЭ, МЦКО, диагностика) |
| `subjects` | Предметы по экзамену |
| `plan_templates` | Шаблоны планов (1800 вариантов из seed) |
| `tasks` | Задания (21 пример из seed + пополняется через `/admin_add_task`) |
| `users` | Пользователи Telegram |
| `user_plans` | Выбранные планы |
| `user_progress` | Результаты выполнения заданий |
| `subscriptions` | Статус подписки пользователя |
| `payments` | История платежей |

---

## Добавление заданий

**Через команду `/admin_add_task`** (пошаговый FSM в боте):

1. Выбрать ID предмета из списка
2. Указать уровень: `low` / `medium` / `high` / `max`
3. Ввести заголовок, условие, ответ, подсказку
4. Подтвердить

**Программно через seed** — дополнить список `SAMPLE_TASKS` в `db/seed.py` и перезапустить.

---

## Конфигурация `.env`

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `BOT_TOKEN` | — | Токен бота (обязательно) |
| `ADMIN_IDS` | `[]` | ID администраторов через запятую |
| `DATABASE_URL` | `sqlite+aiosqlite:///./exambot.db` | URL базы данных |
| `FREE_DAILY_LIMIT` | `3` | Заданий/день для бесплатных пользователей |
| `PREMIUM_PRICE_RUB` | `299` | Цена месячной подписки (заглушка) |
| `TIMEZONE` | `Europe/Moscow` | Часовой пояс планировщика |

---

## Расширение

- **Реальная оплата**: интегрировать Telegram Payments (Stripe/ЮKassa) в `subscribe.py`
- **Уведомление в кастомное время**: добавить поле `notify_time` в профиль + динамические job'ы APScheduler
- **PostgreSQL**: заменить `DATABASE_URL` на `postgresql+asyncpg://...`
- **Миграции**: добавить Alembic (`alembic init alembic`)
- **Webhook-режим**: заменить `start_polling` на `start_webhook` в `main.py`
