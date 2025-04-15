from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from sqlalchemy import select, update

from attachments.keyboards import (
    create_cases_keyboard,
    create_files_keyboard,
    create_finished_case_management_keyboard,
)
from database.db import db
from database.models import Cases, File
from filters.callback_data import FileCallback, CurrentCaseCallBack, ManageCaseCallback
from filters.states import FinishedCasesStates
from utils.markdown_utils import escape_markdown


router = Router()


@router.message(Command('finished_cases'))
async def get_current_cases(message: Message, state: FSMContext, bot: Bot):
    cases_data = db.sql_query(
        select(Cases)
        .where(
            Cases.user_id == str(message.from_user.id),
            Cases.is_finished == True,  # noqa: E712
        )
        .order_by(Cases.deadline_date),
        is_single=False,
    )
    cases_keyboard = create_cases_keyboard(cases_data)
    if not cases_data:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='У вас нет выполненных напоминаний',
        )
        return
    await bot.send_message(
        chat_id=message.from_user.id,
        text='Ваши завершенные напоминания',
        reply_markup=cases_keyboard,
    )
    await state.set_state(FinishedCasesStates.get_current_cases)


@router.callback_query(
    FinishedCasesStates.get_current_cases,
    CurrentCaseCallBack.filter(),
)
async def download_file(
    query: CallbackQuery,
    callback_data: FileCallback,
    bot: Bot,
    state: FSMContext,
):
    case_id = callback_data.case_id
    case = db.sql_query(
        select(Cases)
        .where(Cases.id == case_id),
        is_single=True,
    )
    await state.update_data(case=case)
    reminders_msg = '\n'.join([
        f'Дата: {case.deadline_date}',
        f'Название: {case.name}',
        f'Описание: {case.description}',
        f'Повторение: {case.repeat}',
    ])
    management_keyboard = create_finished_case_management_keyboard(case_id)
    await bot.send_message(
        chat_id=query.from_user.id,
        text=reminders_msg,
        reply_markup=management_keyboard,
    )
    await state.set_state(FinishedCasesStates.get_case_action)


@router.callback_query(
    FinishedCasesStates.get_case_action,
    ManageCaseCallback.filter(F.action == 'files'),
)
async def show_files(query: CallbackQuery, callback_data: ManageCaseCallback, bot: Bot):
    case_id = callback_data.case_id
    files = db.sql_query(
        select(File)
        .where(File.case_id == case_id),
        is_single=False,
    )
    if files:
        files_keyboard = create_files_keyboard(files)
        await bot.send_message(
            chat_id=query.from_user.id, text='Файлы:', reply_markup=files_keyboard,
        )
    else:
        await query.answer(
            text='У этого напоминания нет вложений',
        )


@router.callback_query(
    FinishedCasesStates.get_case_action,
    ManageCaseCallback.filter(F.action == 'restore'),
)
async def ask_restore_date(
    query: CallbackQuery,
    callback_data: ManageCaseCallback,
    state: FSMContext,
):
    case_id = callback_data.case_id
    await state.update_data(case_id=case_id)
    await query.message.answer(
        'На какую дату восстановить напоминание?',
        reply_markup=await SimpleCalendar(locale='ru_RU.utf8').start_calendar(),
    )
    await state.set_state(FinishedCasesStates.waiting_for_restore_date)


@router.callback_query(
    FinishedCasesStates.waiting_for_restore_date,
    SimpleCalendarCallback.filter(),
)
async def restore_case_with_date(
    query: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
):
    selected, date = await SimpleCalendar().process_selection(query, callback_data)
    if selected:
        await query.message.answer(
            'Вы выбрали дату: {}\nТеперь введите время в формате ЧЧ:ММ'.format(
                date.strftime('%d.%m.%Y'),
            ),
        )
        await state.update_data(selected_date=date.strftime('%Y-%m-%d'))
        await state.set_state(FinishedCasesStates.select_time)


@router.message(FinishedCasesStates.select_time, F.text)
async def process_time(message: Message, state: FSMContext, bot: Bot):
    time_str = message.text
    state_data = await state.get_data()
    selected_date = state_data.get('selected_date')
    case_id = state_data.get('case_id')
    name = escape_markdown(state_data.get('case').name)
    try:
        selected_time = datetime.strptime(time_str, '%H:%M').time()
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        full_datetime = datetime.combine(selected_date, selected_time)
        await state.update_data(selected_date=full_datetime.strftime('%Y-%m-%d %H:%M'))
        db.sql_query(
            update(Cases)
            .where(Cases.id == case_id)
            .values(
                is_finished=False,
                deadline_date=full_datetime,
                original_deadline=full_datetime,  # Обновляем оба поля
            ),
            is_update=True,
        )
        date_str = escape_markdown(str(full_datetime))
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'Событие _{name}_ восстановлено на дату {date_str}',
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await state.clear()
    except ValueError:
        await message.answer('Формат времени неверный. Введите время в формате ЧЧ:ММ')
