"""
FSM state groups.
"""
from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choose_grade    = State()
    choose_exam     = State()
    choose_subjects = State()  # множественный выбор
    choose_level    = State()
    choose_minutes  = State()


class PlanStates(StatesGroup):
    show_variants   = State()
    confirm_plan    = State()
    setup_next      = State()  # настроить следующий предмет в наборе


class ScheduleStates(StatesGroup):
    choose_count   = State()
    enter_times    = State()
    wait_manual    = State()


class AdminStates(StatesGroup):
    wait_task_subject  = State()
    wait_task_level    = State()
    wait_task_title    = State()
    wait_task_body     = State()
    wait_task_answer   = State()
    wait_task_hint     = State()
    wait_task_confirm  = State()
