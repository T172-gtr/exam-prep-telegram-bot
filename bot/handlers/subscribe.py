"""
/subscribe command + payment stub handlers.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import subscribe_kb, MENU_SUBSCRIBE
from db.service import (
    get_or_create_subscription,
    create_payment, activate_subscription,
)
from config import settings

router = Router()

PLAN_DAYS = {
    "premium_month": 30,
    "premium_year":  365,
}
PLAN_PRICES = {
    "premium_month": settings.PREMIUM_PRICE_RUB,
    "premium_year":  settings.PREMIUM_PRICE_RUB * 10,
}
PLAN_NAMES = {
    "premium_month": "Premium (1 месяц)",
    "premium_year":  "Premium (1 год)",
}


@router.message(Command("subscribe"))
@router.message(F.text == MENU_SUBSCRIBE)
async def cmd_subscribe(message: Message, session: AsyncSession) -> None:
    sub = await get_or_create_subscription(session, message.from_user.id)

    if sub.is_active and sub.plan_type != "free":
        expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
        await message.answer(
            f"💎 У тебя уже активна подписка <b>{PLAN_NAMES.get(sub.plan_type, sub.plan_type)}</b>.\n"
            f"Действует до: {expires}",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "💎 <b>Premium-подписка</b>\n\n"
        "✅ Безлимитные задания в день\n"
        "✅ Расширенные планы подготовки\n"
        "✅ Приоритетные обновления базы заданий\n\n"
        f"Бесплатный план: до {settings.FREE_DAILY_LIMIT} заданий/день\n\n"
        "Выбери тариф:",
        reply_markup=subscribe_kb(settings.PREMIUM_PRICE_RUB),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, session: AsyncSession) -> None:
    plan_type = call.data.split(":")[1]
    price     = PLAN_PRICES.get(plan_type, settings.PREMIUM_PRICE_RUB)

    # Create payment record (stub)
    payment = await create_payment(session, call.from_user.id, plan_type, price)

    # Simulate successful payment (stub — no real gateway)
    payment.status      = "success"
    payment.provider_tx_id = f"STUB-{payment.id}"

    days = PLAN_DAYS.get(plan_type, 30)
    await activate_subscription(session, call.from_user.id, plan_type, days)

    await call.message.edit_text(
        f"✅ <b>Оплата прошла успешно!</b> (заглушка)\n\n"
        f"Подписка <b>{PLAN_NAMES[plan_type]}</b> активирована на {days} дней.\n\n"
        "Теперь у тебя нет ограничений на количество заданий в день. 🎉",
        parse_mode="HTML",
    )
    await call.answer("Подписка активирована!", show_alert=True)
