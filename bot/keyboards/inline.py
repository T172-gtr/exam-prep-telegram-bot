"""
Inline keyboard builders.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List

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


def subjects_kb(subjects: List[Subject]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in subjects:
        builder.button(text=s.name, callback_data=f"subject:{s.id}")
    builder.adjust(2)
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
# Task answer
# ──────────────────────────────────────────────────────────────

def task_answer_kb(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Верно",         callback_data=f"task_ans:{task_id}:correct")
    builder.button(text="❌ Неверно",       callback_data=f"task_ans:{task_id}:wrong")
    builder.button(text="💡 Подсказка",     callback_data=f"task_hint:{task_id}")
    builder.button(text="👁 Показать ответ", callback_data=f"task_reveal:{task_id}")
    builder.adjust(2, 2)
    return builder.as_markup()
