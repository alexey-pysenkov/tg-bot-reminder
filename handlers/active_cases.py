import logging
import os
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from sqlalchemy import delete, select, update, func

from sqlalchemy import or_

from attachments.keyboards import (
    create_case_editing_keyboard,
    create_case_management_keyboard,
    create_cases_keyboard,
    create_files_keyboard,
    get_repeat_keyboard,
)
from database.db import db
from database.models import Cases, File
from filters.callback_data import (
    FileCallback,
    CurrentCaseCallBack,
    ManageCaseCallback,
    EditCaseCallback,
    RepeatCallback,
    ManageSendingCaseCallback,
)
from filters.states import CurrentCasesStates, EditCaseStates
from handlers.messages import FIELD_NAMES

from utils.markdown_utils import escape_markdown

logger = logging.getLogger(__name__)

router = Router()


# Helper functions to reduce repeated expressions
def get_case_by_id(case_id):
    """Get a case by its ID."""
    return db.sql_query(
        select(Cases)
        .where(Cases.id == case_id),
        is_single=True,
    )


def get_case_files(case_id):
    """Get files associated with a case."""
    return db.sql_query(
        select(File)
        .where(File.case_id == case_id),
        is_single=False,
    )


def create_cases_update_query(case_id):
    """Create a base update query for a case."""
    return update(Cases).where(Cases.id == case_id)


def update_case(case_id, **case_fields):
    """Update a case with the given values."""
    db.sql_query(
        create_cases_update_query(case_id).values(**case_fields),
        is_update=True,
    )


@router.message(Command('active_cases'))
async def get_current_cases(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    cases = db.sql_query(
        select(Cases)
        .where(
            Cases.user_id == str(message.from_user.id),
            Cases.is_finished == False,  # noqa: E712
        )
        .order_by(Cases.deadline_date),
        is_single=False,
    )
    cases_keyboard = create_cases_keyboard(cases)
    if cases:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='Ваши текущие напоминания',
            reply_markup=cases_keyboard,
        )
        await state.set_state(CurrentCasesStates.get_current_cases)
    else:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='У вас нет активных напоминаний',
        )


@router.message(Command('today_cases'))
async def get_today_cases(message: Message, state: FSMContext, bot: Bot):
    cases = db.sql_query(
        select(Cases)
        .where(
            Cases.user_id == str(message.from_user.id),
            Cases.is_finished == False,  # noqa: E712
            # Проверяем как deadline_date, так и original_deadline
            or_(
                func.date(Cases.deadline_date) == datetime.today().date(),
                func.date(Cases.original_deadline) == datetime.today().date()
            )
        ),
        is_single=False,
    )
    if cases:
        cases_keyboard = create_cases_keyboard(cases)
        await bot.send_message(
            chat_id=message.from_user.id,
            text='Ваши напоминания на сегодня',
            reply_markup=cases_keyboard,
        )
        await state.set_state(CurrentCasesStates.get_current_cases)
    else:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='У вас нет активных напоминаний на сегодня',
        )


async def show_case_info(
        bot: Bot,
        chat_id: int,
        case_id: int,
        state: FSMContext,
):
    state_data = await state.get_data()

    prev_msg_id = state_data.get('last_msg_id')
    if prev_msg_id:
        await bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)

    case = get_case_by_id(case_id)
    await state.update_data(case=case)

    reminders_msg = '\n'.join([
        f'Дата: {case.deadline_date}',
        f'Название: {case.name}',
        f'Описание: {case.description}',
        f'Повторение: {case.repeat}',
    ])

    management_keyboard = create_case_management_keyboard(case_id)

    new_msg = await bot.send_message(
        chat_id=chat_id,
        text=reminders_msg,
        reply_markup=management_keyboard
    )
    await state.update_data(last_msg_id=new_msg.message_id)
    await state.set_state(CurrentCasesStates.get_case_action)


@router.callback_query(
    CurrentCasesStates.get_current_cases,
    CurrentCaseCallBack.filter(),
)
async def current_case(
        query: CallbackQuery,
        callback_data: FileCallback,
        bot: Bot,
        state: FSMContext,
):
    await bot.delete_message(chat_id=query.message.chat.id,
                             message_id=query.message.message_id)
    case_id = callback_data.case_id
    await show_case_info(bot, query.from_user.id, case_id, state)


@router.callback_query(
    CurrentCasesStates.get_case_action,
    ManageCaseCallback.filter(F.action == 'files'),
)
async def show_files(
        query: CallbackQuery,
        callback_data: ManageCaseCallback,
        bot: Bot,
        state: FSMContext,
):
    case_id = callback_data.case_id
    state_data = await state.get_data()
    name = escape_markdown(state_data.get('case').name)
    files = get_case_files(case_id)
    if files:
        files_keyboard = create_files_keyboard(files)
        await bot.send_message(
            chat_id=query.from_user.id,
            text=f'Файлы к событию _{name}_:',
            reply_markup=files_keyboard,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        await query.answer(
            text='У этого напоминания нет вложений',
        )


@router.callback_query(
    CurrentCasesStates.get_case_action,
    ManageCaseCallback.filter(F.action == 'complete'),
)
async def complete_case(
        query: CallbackQuery,
        callback_data: ManageCaseCallback,
        bot: Bot,
        state: FSMContext,
):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    state_data = await state.get_data()
    name = escape_markdown(state_data.get('case').name)
    case_id = callback_data.case_id
    update_case(case_id, is_finished=True)
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f'Событие _{name}_ отмечено как выполненное',
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@router.callback_query(
    CurrentCasesStates.get_case_action,
    ManageCaseCallback.filter(F.action == 'edit'),
)
async def edit_case(
        query: CallbackQuery,
        callback_data: ManageCaseCallback,
        bot: Bot,
        state: FSMContext,
):
    case_id = callback_data.case_id
    settings = create_case_editing_keyboard(case_id=case_id)
    case = get_case_by_id(case_id)
    await state.update_data(case=case)
    state_data = await state.get_data()
    name = escape_markdown(state_data.get('case').name)
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f'Редактирование напоминания: _{name}_',
        reply_markup=settings,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await state.set_state(EditCaseStates.waiting_for_field_choice)


@router.callback_query(
    EditCaseStates.waiting_for_field_choice,
    EditCaseCallback.filter(),
)
async def process_field_choice(query: CallbackQuery, state: FSMContext, bot: Bot):
    mes_id = query.message.message_id
    await state.update_data(mes_id=mes_id)
    action, field, case_id = query.data.split(':')
    await state.update_data(case_id=case_id)
    await state.update_data(field=field)
    await state.update_data(many_files=False)

    if field == 'deadline_date':
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Выберите новую дату:',
            reply_markup=await SimpleCalendar(
                locale='ru_RU.utf8',
            ).start_calendar(),
        )
        await state.set_state(EditCaseStates.waiting_for_new_date)
    elif field == 'repeat':
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Выберите новую периодичность:',
            reply_markup=await get_repeat_keyboard(),
        )
        await state.set_state(EditCaseStates.waiting_for_new_repeat)
    elif field == 'files':
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Отправьте один файл:',
        )
        await state.set_state(EditCaseStates.editing_files)
    else:
        field_name = FIELD_NAMES.get(field, field)
        await query.message.edit_text(
            text=f'Введите новое {field_name}',
        )
        await state.set_state(EditCaseStates.waiting_for_new_value)


@router.message(EditCaseStates.waiting_for_new_value)
async def update_case_field(message: Message, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    case_id = state_data['case_id']
    field = state_data['field']
    name = escape_markdown(state_data.get('case').name)

    if field == 'name':
        new_value = message.text.strip()
        if is_valid_text(new_value):
            update_case(case_id, name=new_value)
            await message.answer(text='Название напоминания было обновлено')
        else:
            await message.answer(text='Введите корректное название')
    elif field == 'description':
        new_value = message.text.strip()
        if is_valid_text(new_value):
            update_case(case_id, description=new_value)
            await message.answer(text=f'Описание напоминания _{name}_ было обновлено')
        else:
            await message.answer(text='Введите корректное описание')

    await show_case_info(bot, message.from_user.id, case_id, state)


@router.message(EditCaseStates.editing_files)
async def receive_new_files(message: Message, state: FSMContext):
    state_data = await state.get_data()
    case_id = state_data['case_id']
    many_files = state_data.get('many_files', False)

    if message.document or message.photo:
        if not os.path.exists('tmp'):
            os.makedirs('tmp')

        file_info = None
        file_name = None

        if message.document:
            file_info = await message.bot.get_file(message.document.file_id)
            file_name = message.document.file_name
        elif message.photo:
            file_info = await message.bot.get_file(message.photo[-1].file_id)
            file_name = f'photo_{file_info.file_unique_id}.jpg'

        if file_info and file_name:
            file_path = os.path.join('tmp', file_name)
            await message.bot.download_file(file_info.file_path, file_path)

            # Сохраняем информацию о файле во временное хранилище
            attachments = state_data.get('attachments', [])
            attachments.append(f'{file_name}@@@{file_path}')
            await state.update_data(attachments=attachments)

            await message.answer(f'Файл {file_name} успешно загружен')

            if not many_files:
                await state.update_data(many_files=True)
                await message.answer(
                    'Теперь можете загрузить ещё файлы или завершить процесс'
                    ', нажав соответствующую кнопку',
                    # noqa: E501
                    reply_markup=get_done_editing_files_keyboard(case_id),
                )
    else:
        await message.answer(
            'Пожалуйста, прикрепите файл или завершите добавление, нажав кнопку ниже',
            reply_markup=get_done_editing_files_keyboard(case_id),
        )


@router.callback_query(
    EditCaseStates.editing_files,
    EditCaseCallback.filter(F.action == 'done_editing_files'),
)
async def finish_editing_files(
        query: CallbackQuery,
        callback_data: EditCaseCallback,
        state: FSMContext,
        bot: Bot,
):
    state_data = await state.get_data()
    case_id = callback_data.case_id
    new_attachments = state_data.get('attachments', [])

    if not new_attachments:
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Нет новых файлов для добавления',
        )
        await state.clear()
        return

    try:
        db.sql_query(
            delete(File)
            .where(File.case_id == case_id),
            is_delete=True,
        )

        for attachment_info in new_attachments:
            file_name, file_path = attachment_info.split('@@@')
            db.create_object(
                File(
                    file_name=file_name,
                    file_url=file_path,
                    case_id=case_id,
                ),
            )

        await bot.delete_message(
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
        )

        await bot.send_message(
            chat_id=query.from_user.id,
            text='Файлы успешно обновлены',
        )

        await show_case_info(bot, query.from_user.id, case_id, state)
    except Exception as e:
        logger.error(f'Ошибка при обновлении файлов: {e}')
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Произошла ошибка при обновлении файлов',
        )


@router.message(Command('delete_file'))
async def start_delete_file(message: Message, command: CommandObject):
    if command.args is None:
        await message.answer('Ошибка: не переданы аргументы')
        return
    file_name = command.args
    db.sql_query(
        delete(File)
        .where(File.file_name == file_name),
        is_delete=True,
    )
    await message.answer(f'Файл {file_name} был удалён')


@router.callback_query(ManageSendingCaseCallback.filter(F.action == 'files'))
async def handle_sending_case_files(
        query: CallbackQuery,
        callback_data: ManageSendingCaseCallback,
        bot: Bot,
):
    case_id = callback_data.case_id
    files = get_case_files(case_id)
    if files:
        files_keyboard = create_files_keyboard(files)
        await bot.send_message(
            chat_id=query.from_user.id,
            text='Файлы для дела:',
            reply_markup=files_keyboard,
        )
    else:
        await query.answer(
            text='У этого напоминания нет вложений',
        )


@router.callback_query(ManageSendingCaseCallback.filter(F.action == 'complete'))
async def handle_complete_case(
        query: CallbackQuery,
        callback_data: ManageSendingCaseCallback,
):
    case_id = callback_data.case_id

    # Получаем данные о случае из базы
    case = get_case_by_id(case_id)

    # Обновляем статус
    update_case(case_id, is_finished=True)

    # Удаляем сообщение с напоминанием
    await query.message.delete()

    await query.answer(
        text=f'Событие "{case.name}" отмечено как выполненное',
    )


@router.callback_query(
    EditCaseStates.waiting_for_new_date,
    SimpleCalendarCallback.filter(),
)
async def process_new_date_selection(
        callback_query: CallbackQuery,
        callback_data: CallbackData,
        state: FSMContext,
):
    calendar = SimpleCalendar(locale='ru_RU.utf8')
    selected, date = await calendar.process_selection(
        callback_query,
        callback_data,
    )
    if selected:
        await state.update_data(new_date=date.strftime('%Y-%m-%d'))
        await callback_query.message.answer(
            'Введите новое время напоминания в формате ЧЧ:ММ',
        )
        await state.set_state(EditCaseStates.awaiting_new_time)


@router.message(EditCaseStates.awaiting_new_time, F.text)
async def new_time_chosen(message: Message, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    case_id = state_data['case_id']
    case = state_data.get('case')
    new_date_str = state_data.get('new_date')
    new_time_str = message.text.strip()
    name = escape_markdown(case.name)
    mes_id = state_data['mes_id']

    await bot.delete_message(chat_id=message.chat.id, message_id=mes_id)

    try:
        new_datetime = datetime.strptime(
            f'{new_date_str} {new_time_str}', '%Y-%m-%d %H:%M',
        )

        # Для повторяющихся событий обновляем только deadline_date
        if case.repeat:
            update_case(case_id, deadline_date=new_datetime)
        else:
            # Для не повторяющихся обновляем оба поля
            update_case(
                case_id,
                deadline_date=new_datetime,
                original_deadline=new_datetime
            )

        date_str = escape_markdown(str(new_datetime))
        await message.answer(
            text=f'Дата напоминания _{name}_ обновлена на {date_str}',
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await show_case_info(bot, message.from_user.id, case_id, state)
    except ValueError:
        await message.answer(
            'Время введено неправильно. Попробуйте еще раз в формате ЧЧ:ММ',
        )


@router.callback_query(
    EditCaseStates.waiting_for_new_repeat,
    RepeatCallback.filter(),
)
async def process_new_repeat_selection(
        query: CallbackQuery,
        callback_data: RepeatCallback,
        state: FSMContext,
        bot=Bot,
):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    state_data = await state.get_data()
    mes_id = state_data['mes_id']
    await bot.delete_message(chat_id=query.message.chat.id, message_id=mes_id)
    repeat_option = callback_data.repeat_option
    case_id = state_data['case_id']
    case = state_data.get('case')

    if repeat_option == 'Нет':  # Если убираем повторение
        update_case(
            case_id,
            repeat=None,
            deadline_date=case.original_deadline  # Возвращаем исходную дату
        )
    else:
        update_case(case_id, repeat=repeat_option)

    name = escape_markdown(case.name)
    await query.answer(
        text=f'Периодичность напоминания "{name}" обновлена на {repeat_option}',
    )
    await show_case_info(bot, query.from_user.id, case_id, state)


def is_valid_text(text):
    return isinstance(text, str) and text != ''


def get_done_editing_files_keyboard(case_id):
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Готово',
        callback_data=EditCaseCallback(
            action='done_editing_files',
            case_id=case_id,
        ).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()
