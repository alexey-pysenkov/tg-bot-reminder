import logging
from datetime import datetime

from aiogram import Router
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from attachments.keyboards import create_sending_case_management_keyboard
from database.db import db
from database.models import Cases

# Настройка логирования
logger = logging.getLogger(__name__)

# Константы
TIME_THRESHOLD_SECONDS = 30  # Пороговое значение в секундах

scheduler = AsyncIOScheduler(executors={'default': AsyncIOExecutor()})
router = Router()


def get_unfinished_cases():
    """Получение незавершенных дел из базы данных."""
    return db.sql_query(
        query=select(Cases)
        .where(Cases.is_finished.is_(False)),
        is_single=False,
    )


def update_case_status(case_id, **fields):
    """Обновление статуса дела."""
    db.sql_query(
        update(Cases)
        .where(Cases.id == case_id)
        .values(**fields),
        is_update=True,
    )


def should_process_repeating_case(case, now):
    """Проверяет, нужно ли обрабатывать повторяющееся дело."""
    deadline = case.deadline_date
    deadline_time = deadline.time()
    current_time = now.time()

    # Если время не совпадает, не обрабатываем
    if deadline_time.hour != current_time.hour:
        return False
    if deadline_time.minute != current_time.minute:
        return False

    # Для ежемесячных - проверяем день месяца
    if case.repeat == 'Ежемесячно' and deadline.day != now.day:
        return False

    # Для еженедельных - проверяем день недели
    if case.repeat == 'Еженедельно' and deadline.weekday() != now.weekday():
        return False

    return True


async def process_nonrepeating_case(bot, case, now):
    """Обработка неповторяющегося дела."""
    deadline = case.deadline_date
    time_diff = (now - deadline).total_seconds()

    if abs(time_diff) <= TIME_THRESHOLD_SECONDS:
        await send_reminder(bot, case)
        update_case_status(case.id, is_finished=True)


async def process_repeating_case(bot, case, now):
    """Обработка повторяющегося дела."""
    if should_process_repeating_case(case, now):
        await send_reminder(bot, case)
        update_case_status(case.id, last_notification=now)


async def check_and_send_reminders(bot):
    """Основная функция проверки и отправки напоминаний."""
    now = datetime.now()
    logger.info(f'Checking reminders at {now}')

    cases = get_unfinished_cases()

    for case_data in cases:
        case = case_data[0]
        logger.info(f'Processing case {case.id} (repeat: {case.repeat})')

        if case.repeat:
            await process_repeating_case(bot, case, now)
        else:
            await process_nonrepeating_case(bot, case, now)


async def send_reminder(bot, case):
    """Отправка напоминания пользователю."""
    management_keyboard = create_sending_case_management_keyboard(case.id)
    formatted_date = case.deadline_date.strftime('%Y-%m-%d %H:%M')
    reminder_msg = '\n'.join([
        f'📅 {formatted_date}',
        f'🔹 {case.name}',
        f'📝 {case.description}',
        f'🔄 Повтор: {case.repeat}',
    ])

    await bot.send_message(
        chat_id=case.user_id,
        text=reminder_msg,
        reply_markup=management_keyboard,
    )
