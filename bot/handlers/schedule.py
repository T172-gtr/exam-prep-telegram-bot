"""
Настройки рассылки задач: количество в день + время каждой рассылки.
"""
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import ScheduleStates
from bot.keyboards import (
    schedule_count_kb, schedule_time_presets_kb, main_menu_kb,
    MENU_SCHEDULE,
)
from db.service import get_user, update_user_profile

router = Router()

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _normalize_time(value: str) -> str | None:
    """Нормализует HH:MM, отбрасывая пробелы. Возвращает None если невалидно."""
    value = value.strip()
    m = TIME_RE.match(value)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))
    return f"{hh:02d}:{mm:02d}"


def _format_times(times: list[str]) -> str:
    return ", ".join(times) if times else "не задано"


# ── Вход в настройку рассылки ────────────────────────────────

@router.message(Command("schedule"))
@router.message(F.text == MENU_SCHEDULE)
async def cmd_schedule(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await get_user(session, message.from_user.id)
    if user is None:
        await message.answer("Сначала используй /start.")
        return

    current_times = [t for t in (user.notify_times or "08:00").split(",") if t]
    text = (
        "📅 <b>Настройки рассылки</b>\n\n"
        f"Сейчас: <b>{user.notify_count}</b> в день — {_format_times(current_times)}\n\n"
        "Сколько раз в день присылать задания?"
    )
    await state.set_state(ScheduleStates.choose_count)
    await message.answer(text, reply_markup=schedule_count_kb(user.notify_count),
                          parse_mode="HTML")


# ── Шаг 1: количество рассылок ───────────────────────────────

@router.callback_query(ScheduleStates.choose_count, F.data.startswith("sch_count:"))
async def cb_count(call: CallbackQuery, state: FSMContext) -> None:
    count = int(call.data.split(":")[1])
    if count not in (1, 2, 3):
        await call.answer("Допустимо 1, 2 или 3", show_alert=True)
        return
    await state.update_data(count=count, times=[], slot=0)
    await state.set_state(ScheduleStates.enter_times)
    await call.message.edit_text(
        f"Хорошо, <b>{count}</b> в день.\n\n"
        f"Выбери время рассылки №1 (или введи вручную HH:MM):",
        reply_markup=schedule_time_presets_kb(0),
        parse_mode="HTML",
    )
    await call.answer()


# ── Шаг 2: время через пресет ────────────────────────────────

@router.callback_query(ScheduleStates.enter_times, F.data.startswith("sch_time:"))
async def cb_time_preset(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, slot_str, time_str = call.data.split(":", 2)
    slot = int(slot_str)
    norm = _normalize_time(time_str)
    if norm is None:
        await call.answer("Неверный формат времени", show_alert=True)
        return

    data = await state.get_data()
    times: list[str] = list(data.get("times", []))
    if slot != len(times):
        # рассинхронизация — игнор
        await call.answer()
        return
    times.append(norm)
    await state.update_data(times=times, slot=slot + 1)
    await _ask_next_slot_or_finish(call, state, session)


# ── Шаг 2b: ручной ввод ─────────────────────────────────────

@router.callback_query(ScheduleStates.enter_times, F.data.startswith("sch_manual:"))
async def cb_manual_prompt(call: CallbackQuery, state: FSMContext) -> None:
    slot = int(call.data.split(":")[1])
    await state.update_data(manual_slot=slot)
    await state.set_state(ScheduleStates.wait_manual)
    await call.message.answer(
        f"⌨️ Введи время в формате HH:MM (например, 08:15) для рассылки №{slot + 1}:"
    )
    await call.answer()


@router.message(ScheduleStates.wait_manual)
async def msg_manual_time(message: Message, state: FSMContext, session: AsyncSession) -> None:
    norm = _normalize_time(message.text or "")
    if norm is None:
        await message.answer("⚠️ Не понял время. Формат: HH:MM, например 08:15.")
        return

    data = await state.get_data()
    times: list[str] = list(data.get("times", []))
    slot = int(data.get("manual_slot", len(times)))
    if slot != len(times):
        await message.answer("⚠️ Состояние сбито, начни заново через /schedule.")
        await state.clear()
        return
    times.append(norm)
    await state.update_data(times=times, slot=slot + 1, manual_slot=None)
    await state.set_state(ScheduleStates.enter_times)
    await _ask_next_slot_or_finish_msg(message, state, session)


# ── Хелперы перехода между слотами ───────────────────────────

async def _ask_next_slot_or_finish(call: CallbackQuery, state: FSMContext,
                                    session: AsyncSession) -> None:
    data = await state.get_data()
    count: int = data["count"]
    times: list[str] = list(data.get("times", []))
    if len(times) >= count:
        await _save_and_finish(call.message, state, session, times, count)
        await call.answer()
        return
    next_slot = len(times)
    await call.message.edit_text(
        f"Принято: {', '.join(times)}.\n\n"
        f"Выбери время рассылки №{next_slot + 1}:",
        reply_markup=schedule_time_presets_kb(next_slot),
    )
    await call.answer()


async def _ask_next_slot_or_finish_msg(message: Message, state: FSMContext,
                                        session: AsyncSession) -> None:
    data = await state.get_data()
    count: int = data["count"]
    times: list[str] = list(data.get("times", []))
    if len(times) >= count:
        await _save_and_finish(message, state, session, times, count)
        return
    next_slot = len(times)
    await message.answer(
        f"Принято: {', '.join(times)}.\n\n"
        f"Выбери время рассылки №{next_slot + 1}:",
        reply_markup=schedule_time_presets_kb(next_slot),
    )


async def _save_and_finish(target: Message, state: FSMContext, session: AsyncSession,
                            times: list[str], count: int) -> None:
    # сортируем и убираем дубликаты, сохраняя порядок «раннее → позднее»
    unique = sorted(set(times))
    times_str = ",".join(unique)
    await update_user_profile(
        session, target.chat.id,
        notify_count=len(unique),
        notify_times=times_str,
        notify_time=unique[0],  # legacy поле
    )
    await state.clear()
    await target.answer(
        f"✅ Рассылка настроена: <b>{len(unique)}</b> раз(а) в день — "
        f"<b>{_format_times(unique)}</b>.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
