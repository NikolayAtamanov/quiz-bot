import asyncio
import aiosqlite
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import F

# Импортируем вопросы
from quize_boT import quiz_data

logging.basicConfig(level=logging.INFO)
logging.info(f"Loaded {len(quiz_data)} questions from quize_boT.py")

API_TOKEN = '8266037326:AAFdRxkjdwsfYGU_r4rOUeAqAL5ZeXJvE5w'
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DB_NAME = 'quiz_bot.db'


def generate_options_keyboard(answer_options):
    """Генерирует inline-клавиатуру"""
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(answer_options):
        builder.add(
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"answer:{i}"
            )
        )
    builder.adjust(1)
    return builder.as_markup()


async def create_table():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quiz_state (
                user_id INTEGER PRIMARY KEY,
                question_index INTEGER,
                score INTEGER DEFAULT 0
            )
        ''')
        # Если таблица уже есть, проверяем наличие колонки score
        async with db.execute("PRAGMA table_info(quiz_state)") as cursor:
            columns = [row[1] async for row in cursor]
            if "score" not in columns:
                await db.execute("ALTER TABLE quiz_state ADD COLUMN score INTEGER DEFAULT 0")
        await db.commit()


async def get_quiz_state(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT question_index, score FROM quiz_state WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else (0, 0)


async def update_quiz_state(user_id: int, index: int, score: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT OR REPLACE INTO quiz_state (user_id, question_index, score) VALUES (?, ?, ?)',
            (user_id, index, score)
        )
        await db.commit()


async def get_question(message: types.Message | types.CallbackQuery, user_id):
    """Отправляем пользователю текущий вопрос"""
    current_index, _ = await get_quiz_state(user_id)

    if current_index >= len(quiz_data):
        _, last_score = await get_quiz_state(user_id)
        await (message.answer if isinstance(message, types.Message) else message.message.answer)(
            f"Квиз завершён! Ваш последний результат: {last_score} из {len(quiz_data)}.\nНачните заново /quiz"
        )
        return

    q = quiz_data[current_index]
    kb = generate_options_keyboard(q["options"])

    if isinstance(message, types.CallbackQuery):
        await message.message.answer(q["question"], reply_markup=kb)
    else:
        await message.answer(q["question"], reply_markup=kb)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    await message.answer(
        "Добро пожаловать в квиз! Нажми кнопку 'Начать игру' или введи /quiz",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


async def new_quiz(message: types.Message):
    user_id = message.from_user.id
    # Сбрасываем игру
    await update_quiz_state(user_id, 0, 0)
    await get_question(message, user_id)


@dp.message(F.text == "Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    await message.answer("Давайте начнём квиз!")
    await new_quiz(message)


@dp.callback_query(F.data.startswith("answer:"))
async def handle_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    current_index, current_score = await get_quiz_state(user_id)
    selected = int(callback.data.split(":")[1])
    selected_text = quiz_data[current_index]["options"][selected]

    # Убираем клавиатуру
    await callback.bot.edit_message_reply_markup(
        chat_id=user_id,
        message_id=callback.message.message_id,
        reply_markup=None
    )
    await callback.message.answer(f"Вы выбрали: {selected_text}")

    correct_index = quiz_data[current_index]["correct_option"]
    correct_text = quiz_data[current_index]["options"][correct_index]

    if selected == correct_index:
        current_score += 1
        await callback.message.answer("Верно!")
    else:
        await callback.message.answer(f"Неправильно. Правильный ответ: {correct_text}")

    current_index += 1
    await update_quiz_state(user_id, current_index, current_score)

    await get_question(callback, user_id)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = message.from_user.id
    _, last_score = await get_quiz_state(user_id)
    await message.answer(f"Ваш последний результат: {last_score} из {len(quiz_data)}.")


async def main():
    await create_table()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
