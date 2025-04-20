import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
from dotenv import load_dotenv

load_dotenv()


# Состояния FSM
class Form(StatesGroup):
    amount = State()
    category = State()
    filter_type = State()
    filter_value = State()
    edit_transaction = State()
    edit_field = State()
    new_value = State()
    delete_confirmation = State()


# Инициализация бота
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()


# Создание базы данных при запуске
async def create_db():
    async with aiosqlite.connect('finance.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                category TEXT,
                date TEXT
            )
        ''')
        await db.commit()


# Главное меню
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="📉 Расход", callback_data="расход")],
        [InlineKeyboardButton(text="📈 Доход", callback_data="доход")],
        [InlineKeyboardButton(text="👀 Просмотр", callback_data="view")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Меню фильтрации
def filter_menu():
    buttons = [
        [InlineKeyboardButton(text="📅 По дате", callback_data="filter_date")],
        [InlineKeyboardButton(text="📆 По месяцу", callback_data="filter_month")],
        [InlineKeyboardButton(text="📅 По году", callback_data="filter_year")],
        [InlineKeyboardButton(text="📉 По расходам", callback_data="filter_расходы")],
        [InlineKeyboardButton(text="📈 По доходам", callback_data="filter_доходы")],
        [InlineKeyboardButton(text="🔍 Все записи", callback_data="filter_all")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Меню действий с транзакцией
def transaction_menu(transaction_id):
    buttons = [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{transaction_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{transaction_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_view")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Меню выбора поля для редактирования
def edit_field_menu(transaction_id):
    buttons = [
        [InlineKeyboardButton(text="Тип", callback_data=f"field_type_{transaction_id}")],
        [InlineKeyboardButton(text="Сумму", callback_data=f"field_amount_{transaction_id}")],
        [InlineKeyboardButton(text="Категорию", callback_data=f"field_category_{transaction_id}")],
        [InlineKeyboardButton(text="Дату", callback_data=f"field_date_{transaction_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_transaction_{transaction_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_transactions(source: Message | CallbackQuery, user_id: int, filter_query=None, filter_value=None):
    query = "SELECT id, type, amount, category, date FROM transactions WHERE user_id = ?"
    params = [user_id]

    if filter_query and filter_value:
        query += f" AND {filter_query}"
        params.append(filter_value)

    query += " ORDER BY date DESC"

    async with aiosqlite.connect('finance.db') as db:
        cursor = await db.execute(query, tuple(params))
        transactions = await cursor.fetchall()

    if not transactions:
        if isinstance(source, Message):
            await source.answer("Нет записей.", reply_markup=main_menu())
        else:
            await source.message.edit_text("Нет записей.", reply_markup=main_menu())
    else:
        buttons = []
        for trans in transactions:
            btn_text = f"{trans[4][:10]} - {trans[1]}: {trans[2]} ({trans[3]})"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"show_{trans[0]}")])

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)

        if isinstance(source, Message):
            await source.answer("📊 Выберите запись для просмотра:", reply_markup=markup)
        else:
            await source.message.edit_text("📊 Выберите запись для просмотра:", reply_markup=markup)


# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "💰 Добро пожаловать в финансовый бот!\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )


# Обработчик кнопки "Расход"
@dp.callback_query(F.data == "расход")
async def expense_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.amount)
    await state.update_data(type="расход")
    await callback.message.edit_text("Введите сумму расхода:")
    await callback.answer()


# Обработчик кнопки "Доход"
@dp.callback_query(F.data == "доход")
async def income_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.amount)
    await state.update_data(type="доход")
    await callback.message.edit_text("Введите сумму дохода:")
    await callback.answer()


# Обработчик ввода суммы
@dp.message(Form.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await state.set_state(Form.category)
        await message.answer("Введите категорию:")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму (положительное число):")


# Обработчик ввода категории
@dp.message(Form.category)
async def process_category(message: Message, state: FSMContext):
    category = message.text
    data = await state.get_data()
    transaction_type = data['type']
    amount = data['amount']
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect('finance.db') as db:
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, category, date) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, transaction_type, amount, category, date)
        )
        await db.commit()

    await message.answer(
        f"✅ {'Расход' if transaction_type == 'расход' else 'Доход'} успешно добавлен:\n"
        f"Сумма: {amount}\n"
        f"Категория: {category}",
        reply_markup=main_menu()
    )
    await state.clear()


# Обработчик кнопки "Просмотр"
@dp.callback_query(F.data == "view")
async def view_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите тип фильтра:",
        reply_markup=filter_menu()
    )
    await callback.answer()


# Обработчики фильтрации
@dp.callback_query(F.data.startswith("filter_"))
async def filter_callback(callback: CallbackQuery, state: FSMContext):
    filter_type = callback.data.split("_")[1]

    if filter_type == "all":
        await show_transactions(callback, callback.from_user.id)
    elif filter_type in ["расходы", "доходы"]:
        transaction_type = "расход" if filter_type == "расходы" else "доход"
        await show_transactions(callback, callback.from_user.id, "type = ?", transaction_type)
    else:
        await state.set_state(Form.filter_value)
        await state.update_data(filter_type=filter_type)
        prompt = {
            "date": "Введите дату в формате ГГГГ-ММ-ДД:",
            "month": "Введите месяц в формате ГГГГ-ММ:",
            "year": "Введите год в формате ГГГГ:"
        }[filter_type]
        await callback.message.edit_text(prompt)

    await callback.answer()


# Обработчик ввода значения фильтра
@dp.message(Form.filter_value)
async def process_filter_value(message: Message, state: FSMContext):
    data = await state.get_data()
    filter_type = data['filter_type']
    filter_value = message.text

    try:
        if filter_type == "date":
            datetime.strptime(filter_value, "%Y-%m-%d")
            query = "date LIKE ?"
            filter_value = f"{filter_value}%"
        elif filter_type == "month":
            datetime.strptime(filter_value, "%Y-%m")
            query = "date LIKE ?"
            filter_value = f"{filter_value}%"
        elif filter_type == "year":
            datetime.strptime(filter_value, "%Y")
            query = "date LIKE ?"
            filter_value = f"{filter_value}%"

        await show_transactions(message, message.from_user.id, query, filter_value)
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте еще раз.")
        return

    await state.clear()


# Обработчик выбора транзакции
@dp.callback_query(F.data.startswith("show_"))
async def show_transaction(callback: CallbackQuery):
    transaction_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect('finance.db') as db:
        cursor = await db.execute(
            "SELECT id, type, amount, category, date FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        transaction = await cursor.fetchone()

    if transaction:
        text = (f"📊 Транзакция #{transaction[0]}:\n\n"
                f"Тип: {transaction[1]}\n"
                f"Сумма: {transaction[2]}\n"
                f"Категория: {transaction[3]}\n"
                f"Дата: {transaction[4]}")

        await callback.message.edit_text(
            text,
            reply_markup=transaction_menu(transaction[0])
        )
    else:
        await callback.message.edit_text("Транзакция не найдена.", reply_markup=main_menu())

    await callback.answer()


# Обработчик кнопки редактирования
@dp.callback_query(F.data.startswith("edit_"))
async def edit_callback(callback: CallbackQuery):
    transaction_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "Выберите поле для редактирования:",
        reply_markup=edit_field_menu(transaction_id)
    )
    await callback.answer()


# Обработчик выбора поля для редактирования
@dp.callback_query(F.data.startswith("field_"))
async def edit_field_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    field = parts[1]
    transaction_id = int(parts[2])

    await state.set_state(Form.new_value)
    await state.update_data(edit_field=field, transaction_id=transaction_id)

    prompts = {
        "type": "Введите новый тип (расход/доход):",
        "amount": "Введите новую сумму:",
        "category": "Введите новую категорию:",
        "date": "Введите новую дату (ГГГГ-ММ-ДД ЧЧ:ММ:СС):"
    }

    await callback.message.edit_text(prompts[field])
    await callback.answer()


# Обработчик ввода нового значения
@dp.message(Form.new_value)
async def process_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    transaction_id = data['transaction_id']
    field = data['edit_field']
    new_value = message.text

    # Валидация данных
    try:
        if field == "amount":
            new_value = float(new_value)
            if new_value <= 0:
                raise ValueError
        elif field == "type":
            if new_value not in ("расход", "доход"):
                raise ValueError
        elif field == "date":
            datetime.strptime(new_value, "%Y-%m-%d %H:%M:%S")

        async with aiosqlite.connect('finance.db') as db:
            await db.execute(
                f"UPDATE transactions SET {field} = ? WHERE id = ?",
                (new_value, transaction_id)
            )
            await db.commit()

        await message.answer("✅ Запись успешно обновлена!")
        await show_transaction_after_edit(message, transaction_id)
    except ValueError:
        await message.answer("Неверный формат данных. Попробуйте еще раз.")
        return

    await state.clear()


async def show_transaction_after_edit(message: Message, transaction_id: int):
    async with aiosqlite.connect('finance.db') as db:
        cursor = await db.execute(
            "SELECT id, type, amount, category, date FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        transaction = await cursor.fetchone()

    if transaction:
        text = (f"📊 Транзакция #{transaction[0]}:\n\n"
                f"Тип: {transaction[1]}\n"
                f"Сумма: {transaction[2]}\n"
                f"Категория: {transaction[3]}\n"
                f"Дата: {transaction[4]}")

        await message.answer(
            text,
            reply_markup=transaction_menu(transaction_id)
        )


# Обработчик кнопки удаления
@dp.callback_query(F.data.startswith("delete_"))
async def delete_callback(callback: CallbackQuery):
    transaction_id = int(callback.data.split("_")[1])

    buttons = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_delete_{transaction_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"back_to_transaction_{transaction_id}")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "Вы уверены, что хотите удалить эту запись?",
        reply_markup=markup
    )
    await callback.answer()


# Обработчик подтверждения удаления
@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    transaction_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect('finance.db') as db:
        await db.execute(
            "DELETE FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        await db.commit()

    await callback.message.edit_text("✅ Запись успешно удалена!", reply_markup=main_menu())
    await callback.answer()


# Обработчик кнопки "Назад" к транзакции
@dp.callback_query(F.data.startswith("back_to_transaction_"))
async def back_to_transaction(callback: CallbackQuery):
    transaction_id = int(callback.data.split("_")[3])

    async with aiosqlite.connect('finance.db') as db:
        cursor = await db.execute(
            "SELECT id, type, amount, category, date FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        transaction = await cursor.fetchone()

    if transaction:
        text = (f"📊 Транзакция #{transaction[0]}:\n\n"
                f"Тип: {transaction[1]}\n"
                f"Сумма: {transaction[2]}\n"
                f"Категория: {transaction[3]}\n"
                f"Дата: {transaction[4]}")

        await callback.message.edit_text(
            text,
            reply_markup=transaction_menu(transaction[0])
        )
    else:
        await callback.message.edit_text("Транзакция не найдена.", reply_markup=main_menu())

    await callback.answer()


# Обработчик кнопки "Назад" к просмотру
@dp.callback_query(F.data == "back_to_view")
async def back_to_view(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите тип фильтра:",
        reply_markup=filter_menu()
    )
    await callback.answer()


# Обработчик кнопки "Назад" в меню
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=main_menu()
    )
    await callback.answer()


# Запуск бота
async def main():
    await create_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())