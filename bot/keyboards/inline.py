"""
Inline keyboard builders.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Iterable

from db.models import GradeLevel, ExamType, Subject, PlanTemplate


# ──────────────────────────────────────────────────────────────
# Onboarding keyboards
# ──────────────────────────────────────────────────────────────

def grades_kb(grades: List[GradeLevel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in sorted(grades, key=lambda x: x.grade):
        builder.button(text=g.label, callback_data=f"grade:{g.id}")
    builder.adjust(2)
    return builder.as_markup()


def exams_kb(exams: List[ExamType]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for e in exams:
        builder.button(text=e.name, callback_data=f"exam:{e.id}")
    builder.adjust(1)
    return builder.as_markup()


def subjects_multi_kb(
    subjects: List[Subject],
    selected_ids: Iterable[int],
) -> InlineKeyboardMarkup:
    """Множественный выбор предметов: галочка показывает выбранный."""
    selected = set(selected_ids)
    builder = InlineKeyboardBuilder()
    for s in subjects:
        prefix = "✅ " if s.id in selected else "▫️ "
        builder.button(
            text=f"{prefix}{s.name}",
            callback_data=f"subj_toggle:{s.id}",
        )
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✔️ Готово", callback_data="subj_done"),
        InlineKeyboardButton(text="🔄 Сбросить", callback_data="subj_reset"),
    )
    return builder.as_markup()


LEVEL_META = {
    "low":    ("🔵 Низкий",       "базовые задания, минимальный балл"),
    "medium": ("🟢 Средний",      "уверенная сдача, части 1–2"),
    "high":   ("🟠 Высокий",      "сложные задания, хороший балл"),
    "max":    ("🔴 Максимальный", "полное погружение, максимум баллов"),
}


def levels_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, (label, _) in LEVEL_META.items():
        builder.button(text=label, callback_data=f"level:{code}")
    builder.adjust(2)
    return builder.as_markup()


MINUTES_OPTIONS = [15, 30, 45, 60, 90]


def minutes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in MINUTES_OPTIONS:
        builder.button(text=f"⏱ {m} мин", callback_data=f"minutes:{m}")
    builder.adjust(3)
    return builder.as_markup()


# ──────────────────────────────────────────────────────────────
# Plan selection
# ──────────────────────────────────────────────────────────────

def plan_variants_kb(templates: List[PlanTemplate]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in templates:
        builder.button(
            text=f"📋 Вариант {t.variant_index}: {t.title.split('·')[0].strip()}",
            callback_data=f"plan_select:{t.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def confirm_plan_kb(template_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выбрать этот план", callback_data=f"plan_confirm:{template_id}")
    builder.button(text="🔙 Назад к вариантам",  callback_data="plan_back")
    builder.adjust(1)
    return builder.as_markup()


def setup_more_kb() -> InlineKeyboardMarkup:
    """После сохранения плана: предложить настроить план по следующему предмету
    или завершить настройку."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Настроить следующий предмет", callback_data="setup_next")
    builder.button(text="🏁 Завершить настройку",          callback_data="setup_done")
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────────────────────
# Subscribe
# ──────────────────────────────────────────────────────────────

def subscribe_kb(price: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💳 Оплатить {price} ₽ / мес (заглушка)",
        callback_data="pay:premium_month",
    )
    builder.button(
        text=f"💳 Оплатить {price * 10} ₽ / год (заглушка)",
        callback_data="pay:premium_year",
    )
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────────────────────
# Task answer (fallback кнопки + подсказка)
# ──────────────────────────────────────────────────────────────

def task_answer_kb(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Подсказка",        callback_data=f"task_hint:{task_id}")
    builder.button(text="🚫 Пропустить",       callback_data=f"task_skip:{task_id}")
    builder.button(text="👁 Показать ответ",   callback_data=f"task_reveal:{task_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


# ──────────────────────────────────────────────────────────────
# Schedule (рассылка): количество и время
# ──────────────────────────────────────────────────────────────

def schedule_count_kb(current: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in (1, 2, 3):
        mark = " ✓" if n == current else ""
        builder.button(text=f"{n}/день{mark}", callback_data=f"sch_count:{n}")
    builder.adjust(3)
    return builder.as_markup()


def schedule_time_presets_kb(slot_index: int) -> InlineKeyboardMarkup:
    """Кнопки-пресеты времени + возможность ручного ввода."""
    presets = ["07:30", "08:00", "12:00", "15:00", "18:00", "20:00", "21:30"]
    builder = InlineKeyboardBuilder()
    for t in presets:
        builder.button(text=t, callback_data=f"sch_time:{slot_index}:{t}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(
        text="⌨️ Ввести вручную HH:MM",
        callback_data=f"sch_manual:{slot_index}",
    ))
    return builder.as_markup()
