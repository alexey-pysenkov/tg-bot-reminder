import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from database.db import db
from database.models import Base
from handlers import active_cases, any, finished_cases, new_case, user
from scheduler import check_and_send_reminders, router, scheduler

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Подключение роутеров
dp.include_routers(
    user.router,
    new_case.router,
    active_cases.router,
    finished_cases.router,
    any.router,
    router,
)


async def main():
    # Создаём таблицы в базе данных
    Base.metadata.create_all(bind=db.engine)

    # Добавление задачи для планировщика (напоминания)
    scheduler.add_job(check_and_send_reminders, 'interval', seconds=60, args=[bot])
    scheduler.start()  # Начинаем работу с планировщиком

    # Удаляем webhook, чтобы начать получать обновления через long-polling
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем polling для получения сообщений
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
