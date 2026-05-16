"""
General commands: /profile, /progress, /today, /help + кнопки меню.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    main_menu_kb, main_menu_inline_kb,
    MENU_MAIN, MENU_SUPPORT, MENU_HELP,
    MENU_PROGRESS, MENU_TODAY, MENU_SUBJECTS,
)
from db.service import (
    get_user, get_active_plans, count_progress,
    get_grade, get_exam_type, get_user_subjects,
    get_or_create_subscription,
)
from bot.handlers.tasks import send_today_task
from bot.handlers.schedule import cmd_schedule

router = Router()


HELP_TEXT = (
    "ℹ️ <b>Справка</b>\n\n"
    "Бот помогает готовиться к ОГЭ/ЕГЭ/МЦКО/диагностикам.\n\n"
    "<b>Основные команды:</b>\n"
    "/start — приветствие и меню\n"
    "/menu — показать главное меню\n"
    "/setup — настроить подготовку заново (класс/экзамен/предметы)\n"
    "/profile — твой профиль и выбранные предметы\n"
    "/progress — статистика выполнения\n"
    "/today — получить задание прямо сейчас\n"
    "/schedule — настроить количество и время рассылок\n"
    "/subscribe — подписка Premium\n"
    "/help — эта справка\n\n"
    "<b>Как ответить на задание:</b> просто пришли ответ текстом — "
    "бот сравнит его с эталоном и сразу скажет, верно или нет."
)

SUPPORT_TEXT = (
    "🆘 <b>Поддержка</b>\n\n"
    "Если у тебя возникли вопросы или проблемы с ботом — напиши нам:\n\n"
    "📩 @exam_bot_support\n\n"
    "Мы ответим в течение 24 часов."
)


# ── /help ────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == MENU_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())


# ── «📋 Меню» — открывает inline-подменю ─────────────────────

@router.message(F.text == MENU_MAIN)
@router.message(Command("menu"))
async def cmd_show_menu(message: Message) -> None:
    await message.answer(
        "📋 <b>Главное меню</b>\n\nВыбери раздел:",
        reply_markup=main_menu_inline_kb(),
        parse_mode="HTML",
    )


# ── Обработчики inline-кнопок подменю ────────────────────────

@router.callback_query(F.data == "menu:subjects")
async def cb_menu_subjects(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    subjs = await get_user_subjects(session, call.from_user.id)
    plans = await get_active_plans(session, call.from_user.id)
    if not subjs:
        await call.message.answer(
            "Пока не выбрано ни одного предмета. "
            "Нажми «🎯 Настроить подготовку» в меню или /setup."
        )
        return
    plan_by_subj = {p.template.subject_id: p for p in plans}
    lines = ["📚 <b>Мои предметы</b>"]
    for us in subjs:
        s = us.subject
        p = plan_by_subj.get(s.id)
        if p:
            plan_title = p.template.title.split("·")[0].strip()
            lines.append(
                f"• <b>{s.name}</b> — план «{plan_title}», "
                f"день {p.current_day}/{p.template.total_days}"
            )
        else:
            lines.append(f"• <b>{s.name}</b> — план не настроен")
    lines.append("")
    lines.append("Чтобы изменить набор предметов — /setup (сбросит планы).")
    await call.message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "menu:setup")
async def cb_menu_setup(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "Используй команду /setup для настройки подготовки."
    )


@router.callback_query(F.data == "menu:today")
async def cb_menu_today(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    await send_today_task(call.message, session)


@router.callback_query(F.data == "menu:schedule")
async def cb_menu_schedule(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    await cmd_schedule(call.message, session)


@router.callback_query(F.data == "menu:progress")
async def cb_menu_progress(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    stats = await count_progress(session, call.from_user.id)
    plans = await get_active_plans(session, call.from_user.id)
    total   = stats["total"]
    correct = stats["correct"]
    pct     = round(correct / total * 100) if total else 0
    plan_lines = []
    for p in plans:
        plan_title = p.template.title.split("·")[0].strip()
        plan_lines.append(
            f"• <b>{p.template.subject.name}</b> — «{plan_title}», "
            f"день {p.current_day}/{p.template.total_days}"
        )
    plan_info = ("\n\n📋 Активные планы:\n" + "\n".join(plan_lines)) if plan_lines else ""
    await call.message.answer(
        f"📈 <b>Прогресс</b>\n\n"
        f"Всего ответов: <b>{total}</b>\n"
        f"Верно: <b>{correct}</b> ({pct}%)"
        f"{plan_info}",
        parse_mode="HTML",
    )


# ── «🆘 Поддержка» ────────────────────────────────────────────

@router.message(F.text == MENU_SUPPORT)
async def cmd_support(message: Message) -> None:
    await message.answer(SUPPORT_TEXT, parse_mode="HTML")


# ── /profile ─────────────────────────────────────────────────

@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    user = await get_user(session, message.from_user.id)
    if user is None or not user.onboarded:
        await message.answer(
            "Профиль ещё не настроен. Нажми «📋 Меню» → «🎯 Настроить подготовку» или /setup.",
            reply_markup=main_menu_kb(),
        )
        return

    grade   = await get_grade(session, user.grade_id)     if user.grade_id     else None
    exam    = await get_exam_type(session, user.exam_type_id) if user.exam_type_id else None
    subjs   = await get_user_subjects(session, user.id)
    sub     = await get_or_create_subscription(session, user.id)

    level_labels = {
        "low":    "🔵 Низкий",
        "medium": "🟢 Средний",
        "high":   "🟠 Высокий",
        "max":    "🔴 Максимальный",
    }
    sub_status = "💎 Premium" if sub.is_active and sub.plan_type != "free" else "🆓 Бесплатно"
    subj_names = ", ".join(us.subject.name for us in subjs) or "—"
    times = user.notify_times or "08:00"

    lines = [
        "👤 <b>Профиль</b>",
        f"Имя: {user.full_name or '—'}",
        f"Класс: {grade.label if grade else '—'}",
        f"Экзамен: {exam.name if exam else '—'}",
        f"Предметы: {subj_names}",
        f"Уровень: {level_labels.get(user.target_level, '—')}",
        f"Время/день: {user.daily_minutes or '—'} мин",
        f"Рассылка: {user.notify_count}×/день — {times}",
        f"Подписка: {sub_status}",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /progress ────────────────────────────────────────────────

@router.message(Command("progress"))
@router.message(F.text == MENU_PROGRESS)
async def cmd_progress(message: Message, session: AsyncSession) -> None:
    stats = await count_progress(session, message.from_user.id)
    plans = await get_active_plans(session, message.from_user.id)

    total   = stats["total"]
    correct = stats["correct"]
    pct     = round(correct / total * 100) if total else 0

    plan_lines = []
    for p in plans:
        plan_title = p.template.title.split("·")[0].strip()
        plan_lines.append(
            f"• <b>{p.template.subject.name}</b> — «{plan_title}», "
            f"день {p.current_day}/{p.template.total_days}"
        )
    plan_info = ("\n\n📋 Активные планы:\n" + "\n".join(plan_lines)) if plan_lines else ""

    await message.answer(
        f"📈 <b>Прогресс</b>\n\n"
        f"Всего ответов: <b>{total}</b>\n"
        f"Верно: <b>{correct}</b> ({pct}%)"
        f"{plan_info}",
        parse_mode="HTML",
    )


# ── /today ───────────────────────────────────────────────────

@router.message(Command("today"))
@router.message(F.text == MENU_TODAY)
async def cmd_today(message: Message, session: AsyncSession) -> None:
    await send_today_task(message, session)
