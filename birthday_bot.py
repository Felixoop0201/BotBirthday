import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

# --- Клавиатура выбора типа ---
def congrats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Текст", callback_data="type_text"),
        InlineKeyboardButton(text="🖼 Фото",  callback_data="type_photo"),
        InlineKeyboardButton(text="🎬 Видео", callback_data="type_video"),
    ]])

# --- /start от мамы — тихо активируем ---
@dp.message(Command("start"), F.from_user.id == RECEIVER_ID)
async def mama_start(message: Message):
    storage = load_storage()
    storage["mama_activated"] = True
    save_storage(storage)
    logger.info("Мама активировала бота")

# --- /test — вручную вызвать меню выбора (только Felix) ---
@dp.message(Command("test"), F.from_user.id == SENDER_ID)
async def test_cmd(message: Message):
    await message.answer("Выбери тип поздравления:", reply_markup=congrats_keyboard())

# --- Callback: выбор типа поздравления (только Felix) ---
@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_text")
async def choose_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напиши текст поздравления:")
    await state.set_state(WaitingContent.text)

@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_photo")
async def choose_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Отправь фото и подпись (или только фото):")
    await state.set_state(WaitingContent.photo)

@dp.callback_query(F.from_user.id == SENDER_ID, F.data == "type_video")
async def choose_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Отправь видео и подпись (или только видео):")
    await state.set_state(WaitingContent.video)

# --- Приём текста ---
@dp.message(WaitingContent.text, F.from_user.id == SENDER_ID)
async def receive_text(message: Message, state: FSMContext):
    storage = load_storage()
    storage["congrats"] = {"type": "text", "content": message.text}
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: текст")
    await message.answer("✅ Сохранено! Мама получит поздравление 20 марта в 8:00")

# --- Приём фото ---
@dp.message(WaitingContent.photo, F.photo, F.from_user.id == SENDER_ID)
async def receive_photo(message: Message, state: FSMContext):
    storage = load_storage()
    storage["congrats"] = {
        "type": "photo",
        "file_id": message.photo[-1].file_id,  # берём максимальное разрешение
        "caption": message.caption or ""
    }
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: фото")
    await message.answer("✅ Сохранено! Мама получит поздравление 20 марта в 8:00")

# --- Приём видео ---
@dp.message(WaitingContent.video, F.video, F.from_user.id == SENDER_ID)
async def receive_video(message: Message, state: FSMContext):
    storage = load_storage()
    storage["congrats"] = {
        "type": "video",
        "file_id": message.video.file_id,
        "caption": message.caption or ""
    }
    save_storage(storage)
    await state.clear()
    logger.info("Поздравление сохранено: видео")
    await message.answer("✅ Сохранено! Мама получит поздравление 20 марта в 8:00")

async def main():
    # Запускаем планировщик
    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
