import asyncio
import json
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv

from birthday_scheduler import setup_scheduler

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SENDER_ID = int(os.getenv("SENDER_ID"))
RECEIVER_ID = int(os.getenv("RECEIVER_ID"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- FSM состояния ---
class WaitingContent(StatesGroup):
    text = State()
    photo = State()
    video = State()

# --- Хелперы для storage.json ---
STORAGE_FILE = "storage.json"

def load_storage() -> dict:
    if not os.path.exists(STORAGE_FILE):
        return {}
    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_storage(data: dict):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Удалить сообщение без ошибки если уже удалено ---
async def safe_delete(chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# --- Постоянная клавиатура внизу экрана ---
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎉 Выбрать поздравление"), KeyboardButton(text="📋 Статус")]
        ],
        resize_keyboard=True  # подгоняем под размер экрана
    )

# --- Клавиатура выбора типа ---
def congrats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Текст", callback_data="type_text"),
        InlineKeyboardButton(text="🖼 Фото",  callback_data="type_photo"),
        InlineKeyboardButton(text="🎬 Видео", callback_data="type_video"),
    ]])

# --- Клавиатура управления сохранённым поздравлением ---
def manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Изменить", callback_data="manage_edit"),
        InlineKeyboardButton(text="🗑 Удалить",  callback_data="manage_delete"),
    ]])

# --- /start от мамы — тихо активируем ---
@dp.message(Command("start"), F.from_user.id == RECEIVER_ID)
async def mama_start(message: Message):
    storage = load_storage()
    storage["mama_activated"] = True
    save_storage(storage)
    logger.info("Мама активировала бота")

# --- /start от Felix — показываем клавиатуру ---
@dp.message(Command("start"), F.from_user.id == SENDER_ID)
async def felix_start(message: Message):
    await message.answer("Привет! Используй кнопки ниже 👇", reply_markup=main_keyboard())

# --- /test — вручную вызвать меню выбора (только Felix) ---
@dp.message(Command("test"), F.from_user.id == SENDER_ID)
async def test_cmd(message: Message, state: FSMContext):
    await state.clear()
    await safe_delete(message.chat.id, message.message_id)
    sent = await bot.send_message(
        message.chat.id,
        "Выбери тип поздравления:",
        reply_markup=congrats_keyboard()
    )
    await state.update_data(menu_msg_id=sent.message_id)

# --- Обработчик кнопки "Выбрать поздравление" ---
@dp.message(F.text == "🎉 Выбрать поздравление", F.from_user.id == SENDER_ID)
async def btn_choose(message: Message, state: FSMContext):
    await state.clear()
    await safe_delete(message.chat.id, message.message_id)
    sent = await bot.send_message(
        message.chat.id,
        "Выбери тип поздравления:",
        reply_markup=congrats_keyboard()
    )
    await state.update_data(menu_msg_id=sent.message_id)

# --- Обработчик кнопки "Статус" ---
@dp.message(F.text == "📋 Статус", F.from_user.id == SENDER_ID)
async def btn_status(message: Message):
    await safe_delete(message.chat.id, message.message_id)
    storage = load_storage()
    congrats = storage.get("congrats")
    if not congrats:
        await bot.send_message(message.chat.id, "❌ Поздравление не сохранено.")
        return
    ctype = congrats["type"]
    if ctype == "text":
        preview = f"📝 Текст:\n{congrats['content']}"
    elif ctype == "photo":
        preview = f"🖼 Фото" + (f" с подписью: {congrats['caption']}" if congrats.get("caption") else " без подписи")
    else:
        preview = f"🎬 Видео" + (f" с подписью: {congrats['caption']}" if congrats.get("caption") else " без подписи")
    await bot.send_message(
        message.chat.id,
        f"✅ Сохранено поздравление:\n{preview}",
        reply_markup=manage_keyboard()
    )

# --- /status — посмотреть что сохранено ---
@dp.message(Command("status"), F.from_user.id == SENDER_ID)
async def status_cmd(message: Message):
    await safe_delete(message.chat.id, message.message_id)
    storage = load_storage()
    congrats = storage.get("congrats")
    if not congrats:
        await bot.send_message(message.chat.id, "❌ Поздравление не сохранено.")
        return
    ctype = congrats["type"]
    if ctype == "text":
        preview = f"📝 Текст:\n{congrats['content']}"
    elif ctype == "photo":
        preview = f"🖼 Фото" + (f" с подписью: {congrats['caption']}" if congrats.get("caption") else " без подписи")
    else:
        preview = f"🎬 Видео" + (f" с подписью: {congrats['caption']}" if congrats.get("caption") else " без подписи")
    await bot.send_message(
        message.chat.id,
        f"✅ Сохранено поздравление:\n{preview}",
        reply_markup=manage_keyboard()
    )

# --- Callback: Изменить поздравление ---
@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "manage_edit")
async def manage_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete(callback.message.chat.id, callback.message.message_id)
    sent = await bot.send_message(
        callback.message.chat.id,
        "Выбери новый тип поздравления:",
        reply_markup=congrats_keyboard()
    )
    await state.update_data(menu_msg_id=sent.message_id)

# --- Callback: Удалить поздравление ---
@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "manage_delete")
async def manage_delete(callback: CallbackQuery):
    await callback.answer()
    storage = load_storage()
    storage.pop("congrats", None)
    save_storage(storage)
    await callback.message.edit_text("🗑 Поздравление удалено. Маме уйдёт дефолтное сообщение если не добавишь новое.")
    logger.info("Поздравление удалено пользователем")

# --- Callback: выбор типа поздравления ---
@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_text")
async def choose_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete(callback.message.chat.id, callback.message.message_id)
    sent = await bot.send_message(callback.message.chat.id, "Напиши текст поздравления:")
    await state.update_data(prompt_msg_id=sent.message_id)
    await state.set_state(WaitingContent.text)

@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_photo")
async def choose_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete(callback.message.chat.id, callback.message.message_id)
    sent = await bot.send_message(callback.message.chat.id, "Отправь фото и подпись (или только фото):")
    await state.update_data(prompt_msg_id=sent.message_id)
    await state.set_state(WaitingContent.photo)

@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_video")
async def choose_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete(callback.message.chat.id, callback.message.message_id)
    sent = await bot.send_message(callback.message.chat.id, "Отправь видео и подпись (или только видео):")
    await state.update_data(prompt_msg_id=sent.message_id)
    await state.set_state(WaitingContent.video)

# --- Приём текста ---
@dp.message(WaitingContent.text, F.from_user.id == SENDER_ID)
async def receive_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await safe_delete(message.chat.id, data.get("prompt_msg_id"))
    await safe_delete(message.chat.id, message.message_id)
    storage = load_storage()
    storage["congrats"] = {"type": "text", "content": message.text}
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: текст")
    await bot.send_message(message.chat.id, "✅ Сохранено! Мама получит поздравление 20 марта в 8:00\n\nЧтобы изменить или удалить — /status", reply_markup=main_keyboard())

# --- Приём фото ---
@dp.message(WaitingContent.photo, F.photo, F.from_user.id == SENDER_ID)
async def receive_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await safe_delete(message.chat.id, data.get("prompt_msg_id"))
    await safe_delete(message.chat.id, message.message_id)
    storage = load_storage()
    storage["congrats"] = {
        "type": "photo",
        "file_id": message.photo[-1].file_id,
        "caption": message.caption or ""
    }
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: фото")
    await bot.send_message(message.chat.id, "✅ Сохранено! Мама получит поздравление 20 марта в 8:00\n\nЧтобы изменить или удалить — /status", reply_markup=main_keyboard())

# --- Приём видео ---
@dp.message(WaitingContent.video, F.video, F.from_user.id == SENDER_ID)
async def receive_video(message: Message, state: FSMContext):
    data = await state.get_data()
    await safe_delete(message.chat.id, data.get("prompt_msg_id"))
    await safe_delete(message.chat.id, message.message_id)
    storage = load_storage()
    storage["congrats"] = {
        "type": "video",
        "file_id": message.video.file_id,
        "caption": message.caption or ""
    }
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: видео")
    await bot.send_message(message.chat.id, "✅ Сохранено! Мама получит поздравление 20 марта в 8:00\n\nЧтобы изменить или удалить — /status", reply_markup=main_keyboard())

async def run_bot():
    logger.info("Бот запущен")
    await dp.start_polling(bot)

async def run_web():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"HTTP сервер запущен на порту {port}")
    await asyncio.Event().wait()

async def main():
    scheduler = setup_scheduler(bot)
    scheduler.start()
    await asyncio.gather(run_web(), run_bot())

if __name__ == "__main__":
    asyncio.run(main())
