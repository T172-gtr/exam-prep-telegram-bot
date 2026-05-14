"""
Task delivery and answer tracking handlers.

- Доставка задания берёт первый предмет, по которому ещё есть невыполненные
  задания на текущем уровне. Если у пользователя несколько активных планов,
  предметы перебираются по очереди (round-robin по id плана).
- Картинка к заданию (image_url / image_file_id) отправляется как фото,
  если поле задано.
- Ответ принимается текстом — нормализуется и сравнивается с
  correct_answer / acceptable_answers. После ответа active_task_id сбрасывается,
  пользователю показывается результат + объяснение.
"""
import logging
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import task_answer_kb
from db.service import (
    get_user, get_active_plans, get_next_task, get_task,
    get_or_create_subscription, record_progress,
    update_user_profile,
)
from config import settings

logger = logging.getLogger(__name__)
router = Router()


# ──────────────────────────────────────────────────────────────
# Нормализация ответа
# ──────────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\sа-яёА-ЯЁ.,/+\-=²³½¾]+", re.UNICODE)


def normalize_answer(value: str) -> str:
    """Привести строку к каноничной форме для сравнения."""
    if value is None:
        return ""
    s = value.strip().lower()
    s = s.replace("ё", "е")
    s = s.replace(",", ".")
    s = s.replace(" ", "")
    s = _PUNCT_RE.sub("", s)
    return s


def check_answer(task, user_answer: str) -> bool:
    """True если ответ пользователя совпадает с эталоном."""
    target = task.correct_answer or task.answer
    if not target:
        return False
    candidates = [target]
    if task.acceptable_answers:
        candidates += [c for c in task.acceptable_answers.split("|") if c.strip()]
    u = normalize_answer(user_answer)
    return any(u == normalize_answer(c) for c in candidates)


# ──────────────────────────────────────────────────────────────
# Доставка задания
# ──────────────────────────────────────────────────────────────

async def _pick_next_task_for_user(session: AsyncSession, user_id: int):
    """Перебирает активные планы пользователя и возвращает (plan, task)
    для первого предмета, по которому ещё остались невыполненные задания.

    Возвращает (None, None) если по всем предметам задания исчерпаны.
    """
    plans = await get_active_plans(session, user_id)
    for plan in plans:
        task = await get_next_task(
            session,
            user_id      = user_id,
            subject_id   = plan.template.subject_id,
            target_level = plan.template.target_level,
        )
        if task is not None:
            return plan, task
    return None, None


async def _send_task(target, session: AsyncSession, plan, task, prefix: str = "📚 <b>Задание</b>") -> None:
    """Отправить задание в чат + сохранить active_task_id для автопроверки."""
    text_parts = [
        prefix,
        "─────────────────",
        f"<b>{task.title}</b>",
        "",
        task.body,
    ]
    if task.source_url:
        text_parts.append("")
        text_parts.append(f"🔗 Источник: {task.source_url}")
    text_parts.append("")
    text_parts.append("✍️ Пришли ответ текстом — я проверю автоматически.")
    text = "\n".join(text_parts)

    # отправляем фото, если есть
    photo = task.image_file_id or task.image_url
    try:
        if photo:
            await target.bot.send_photo(
                chat_id=target.chat.id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=task_answer_kb(task.id),
            )
        else:
            await target.answer(
                text,
                reply_markup=task_answer_kb(task.id),
                parse_mode="HTML",
            )
    except Exception as exc:
        logger.warning("Failed to send photo task %s, falling back to text: %s", task.id, exc)
        await target.answer(
            text + (f"\n\n🖼 (изображение по адресу: {task.image_url})" if task.image_url else ""),
            reply_markup=task_answer_kb(task.id),
            parse_mode="HTML",
        )

    # запоминаем активную задачу, чтобы любой следующий текст считался ответом
    plan.tasks_sent_today += 1
    await update_user_profile(session, target.chat.id, active_task_id=task.id)


async def send_today_task(message: Message, session: AsyncSession) -> None:
    """Команда /today и кнопка «📝 Задание сейчас»."""
    user = await get_user(session, message.chat.id)
    if user is None or not user.onboarded:
        await message.answer(
            "У тебя ещё нет настройки подготовки. "
            "Нажми «🎯 Настроить подготовку» или /setup."
        )
        return

    plans = await get_active_plans(session, message.chat.id)
    if not plans:
        await message.answer(
            "Нет активных планов. Открой «🎯 Настроить подготовку» или /setup."
        )
        return

    # free-лимит — по сумме отправленных за день всех планов
    sub = await get_or_create_subscription(session, message.chat.id)
    is_premium = sub.is_active and sub.plan_type != "free"
    total_today = sum(p.tasks_sent_today for p in plans)
    if not is_premium and total_today >= settings.FREE_DAILY_LIMIT:
        await message.answer(
            f"🔒 Достигнут лимит бесплатных заданий ({settings.FREE_DAILY_LIMIT}/день).\n"
            "Оформи подписку Premium для безлимита: /subscribe"
        )
        return

    plan, task = await _pick_next_task_for_user(session, message.chat.id)
    if task is None:
        await message.answer(
            "🏆 Похоже, по выбранным предметам и уровню задания закончились.\n\n"
            "Что можно сделать:\n"
            "• сменить предмет/план через «🎯 Настроить подготовку» (/setup);\n"
            "• подождать пополнения базы заданий — мы регулярно её обновляем."
        )
        return

    await _send_task(message, session, plan, task,
                     prefix=f"📚 <b>Задание · {plan.template.subject.name}</b>")


# ──────────────────────────────────────────────────────────────
# Автоматическая проверка ответа (текстом)
# ──────────────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def auto_check_answer(message: Message, session: AsyncSession) -> None:
    """Любое текстовое сообщение трактуется как ответ на active_task_id."""
    user = await get_user(session, message.from_user.id)
    if user is None or not user.active_task_id:
        # игнорируем — никакого активного задания нет
        return

    task = await get_task(session, user.active_task_id)
    if task is None:
        await update_user_profile(session, user.id, active_task_id=None)
        return

    is_correct = check_answer(task, message.text)
    await record_progress(session, user.id, task.id,
                          is_correct=is_correct, user_answer=message.text)
    await update_user_profile(session, user.id, active_task_id=None)

    if is_correct:
        text = "✅ <b>Верно!</b>"
    else:
        target_answer = task.correct_answer or task.answer or "—"
        text = f"❌ <b>Неверно.</b>\n💡 Правильный ответ: <b>{target_answer}</b>"
    if task.explanation:
        text += f"\n\n📘 {task.explanation}"
    elif task.hint:
        text += f"\n\n📎 Подсказка: {task.hint}"

    await message.answer(text, parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
# Fallback-кнопки (подсказка / показать ответ / пропустить)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_hint:"))
async def cb_task_hint(call: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(call.data.split(":")[1])
    task    = await get_task(session, task_id)
    if task and task.hint:
        await call.answer(f"💡 {task.hint}", show_alert=True)
    else:
        await call.answer("Подсказка недоступна.", show_alert=True)


@router.callback_query(F.data.startswith("task_reveal:"))
async def cb_task_reveal(call: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(call.data.split(":")[1])
    task    = await get_task(session, task_id)
    target_answer = (task.correct_answer or task.answer) if task else None
    if target_answer:
        await call.answer(f"Ответ: {target_answer}", show_alert=True)
        await record_progress(session, call.from_user.id, task_id,
                              is_correct=False, user_answer="<reveal>")
        await update_user_profile(session, call.from_user.id, active_task_id=None)
    else:
        await call.answer("Ответ недоступен.", show_alert=True)


@router.callback_query(F.data.startswith("task_skip:"))
async def cb_task_skip(call: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(call.data.split(":")[1])
    await record_progress(session, call.from_user.id, task_id,
                          is_correct=False, user_answer="<skip>")
    await update_user_profile(session, call.from_user.id, active_task_id=None)
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer("⏭ Задание пропущено. Используй /today для следующего.")
    await call.answer()
