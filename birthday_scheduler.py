import json
import logging
import os

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

SENDER_ID   = int(os.getenv("SENDER_ID", "0"))
RECEIVER_ID = int(os.getenv("RECEIVER_ID", "0"))
RENDER_URL  = os.getenv("RENDER_URL", "")
STORAGE_FILE = "storage.json"
TZ = timezone("Europe/Moscow")

# --- Storage хелперы (дублируем чтобы scheduler был независимым) ---
def load_storage() -> dict:
    if not os.path.exists(STORAGE_FILE):
        return {}
    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_storage(data: dict):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def congrats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Текст", callback_data="type_text"),
        InlineKeyboardButton(text="🖼 Фото",  callback_data="type_photo"),
        InlineKeyboardButton(text="🎬 Видео", callback_data="type_video"),
    ]])

# --- Напоминания 17/18/19 марта ---
async def remind(bot: Bot, text: str):
    storage = load_storage()
    if storage.get("congrats"):
        # Поздравление уже сохранено — не беспокоим
        return
    await bot.send_message(SENDER_ID, text, reply_markup=congrats_keyboard())
    logger.info(f"Напоминание отправлено: {text[:40]}")

# --- Отправка маме 20 марта в 8:00 ---
async def send_congrats(bot: Bot):
    storage = load_storage()
    mama_activated = storage.get("mama_activated", False)
    congrats = storage.get("congrats")

    header = "🎉✨ С Днём Рождения! ✨🎉"
    footer  = "\n\nС любовью, Игорь 💙"

    # Если мама не нажала /start — предупреждаем Felix
    if not mama_activated:
        await bot.send_message(
            SENDER_ID,
            "⚠️ Мама не активировала бота — поздравление не было отправлено."
        )
        logger.info("Мама не активировала бота, поздравление не отправлено")
        return

    if not congrats:
        # Дефолтное поздравление
        default = (
            "🎉✨ С Днём Рождения, мамочка! ✨🎉\n"
            "Желаю тебе счастья, здоровья и всего самого лучшего!\n"
            "С любовью, Игорь 💙"
        )
        await bot.send_message(RECEIVER_ID, default)
        await bot.send_message(
            SENDER_ID,
            "📨 Маме отправлено дефолтное поздравление (ты не успел добавить своё)"
        )
        logger.info("Маме отправлено дефолтное поздравление")
    else:
        ctype = congrats["type"]

        if ctype == "text":
            await bot.send_message(
                RECEIVER_ID,
                f"{header}\n\n{congrats['content']}{footer}"
            )

        elif ctype == "photo":
            cap_part = f"\n{congrats['caption']}" if congrats.get("caption") else ""
            await bot.send_photo(
                RECEIVER_ID,
                photo=congrats["file_id"],
                caption=f"{header}{cap_part}{footer}"
            )

        elif ctype == "video":
            cap_part = f"\n{congrats['caption']}" if congrats.get("caption") else ""
            await bot.send_video(
                RECEIVER_ID,
                video=congrats["file_id"],
                caption=f"{header}{cap_part}{footer}"
            )

        await bot.send_message(SENDER_ID, "📨 Поздравление отправлено маме!")
        logger.info("Маме отправлено кастомное поздравление")

    # Очищаем storage — бот готов к следующему году
    save_storage({})
    logger.info("storage.json очищен")

# --- Keep-alive: пингуем свой /health каждые 10 минут ---
async def keep_alive_ping():
    if not RENDER_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{RENDER_URL}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                logger.info(f"Keep-alive ping → {resp.status}")
    except Exception as e:
        logger.warning(f"Keep-alive ping failed: {e}")

# --- Регистрация всех задач ---
def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TZ)

    # Напоминания в 10:00 MSK
    scheduler.add_job(
        remind,
        CronTrigger(month=3, day=17, hour=10, minute=0, timezone=TZ),
        args=[bot, "🎂 До дня рождения мамы 3 дня! Как поздравим?"]
    )
    scheduler.add_job(
        remind,
        CronTrigger(month=3, day=18, hour=10, minute=0, timezone=TZ),
        args=[bot, "⏰ До дня рождения мамы 2 дня! Ещё не выбрал поздравление."]
    )
    scheduler.add_job(
        remind,
        CronTrigger(month=3, day=19, hour=10, minute=0, timezone=TZ),
        args=[bot, "⚠️ Завтра день рождения мамы! Последний шанс добавить поздравление."]
    )

    # Отправка маме в 8:00 MSK
    scheduler.add_job(
        send_congrats,
        CronTrigger(month=3, day=20, hour=8, minute=0, timezone=TZ),
        args=[bot]
    )

    # Keep-alive каждые 10 минут
    scheduler.add_job(keep_alive_ping, "interval", minutes=10)

    return scheduler
