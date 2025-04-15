import os
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from attachments import keyboards as kb
from attachments import messages as msg
from database.db import db
from database.models import Cases, File
from filters.callback_data import (
    NewCaseFinishWithFilesCallback,
    NewCaseInterfaceCallback,
    RepeatCallback,
)
from filters.states import NewCaseStates

from utils.markdown_utils import escape_markdown


router = Router()


# Обработчик команды /new_case
@router.message(Command('new_case'))
async def enter(message: Message, state: FSMContext, bot=Bot):
    await bot.send_message(
        chat_id=message.from_user.id,
        text='Введите название события',
    )
    await state.set_state(NewCaseStates.set_case_name)


# Получаем text введённый пользователем = название события
@router.message(NewCaseStates.set_case_name, F.text)
async def choose_case_description(message: Message, state: FSMContext, bot=Bot):
    # в data состояния добавляем поле name, для названия события
    await state.update_data(name=message.text)
    # в data состояния добавляем поле attachments, пока что пустое, для файлов
    attachments = []
    await state.update_data(attachments=attachments)
    await bot.send_message(
        chat_id=message.from_user.id,
        text='Хотите добавить описание?',
        reply_markup=await kb.yes_no_kb(),
    )
    await state.set_state(NewCaseStates.add_case_description)


# С описанием
@router.callback_query(
    NewCaseStates.add_case_description,
    NewCaseInterfaceCallback.filter(F.case_description_option == True),  # noqa: E712
)
async def set_case_description(query: CallbackQuery, state: FSMContext, bot=Bot):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    state_data = await state.get_data()
    name = escape_markdown(state_data.get('name'))
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f'Напишите описание к событию _{name}_',
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await state.set_state(NewCaseStates.set_case_description)


@router.message(NewCaseStates.set_case_description, F.text)
async def set_case_date(message: Message, state: FSMContext, bot=Bot):
    await state.update_data(description=message.text)
    await bot.send_message(
        chat_id=message.from_user.id,
        text='Описанию быть!\nВыберите дату',
        reply_markup=await SimpleCalendar(locale='ru_RU.utf8').start_calendar(),
    )
    await state.set_state(NewCaseStates.select_date)


# Без описания
@router.callback_query(
    NewCaseStates.add_case_description,
    NewCaseInterfaceCallback.filter(F.case_description_option == False),  # noqa: E712
)
async def skip_case_description(query: CallbackQuery, state: FSMContext, bot=Bot):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    description = ''
    await state.update_data(description=description)
    await bot.send_message(
        chat_id=query.from_user.id,
        text='Продолжаем без описания\nВыберите дату',
        reply_markup=await SimpleCalendar(locale='ru_RU.utf8').start_calendar(),
    )
    await state.set_state(NewCaseStates.select_date)


# Выбор даты и времени
@router.callback_query(NewCaseStates.select_date, SimpleCalendarCallback.filter())
async def process_calendar(
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
        # в data состояния добавляем поле selected_date
        await state.update_data(selected_date=date.strftime('%Y-%m-%d'))
        await state.set_state(NewCaseStates.select_time)


@router.message(NewCaseStates.select_time, F.text)
async def process_time(message: Message, state: FSMContext, bot: Bot):
    time_str = message.text.strip()
    state_data = await state.get_data()
    selected_date_str = state_data.get('selected_date')

    try:
        selected_time = datetime.strptime(time_str, '%H:%M').time()
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        full_datetime = datetime.combine(selected_date, selected_time)

        await state.update_data(selected_date=full_datetime.strftime('%Y-%m-%d %H:%M'))
        await bot.send_message(
            chat_id=message.from_user.id,
            text='Выберите частоту напоминания',
            reply_markup=await kb.get_repeat_keyboard(),
        )
        await state.set_state(NewCaseStates.set_repeat)

    except ValueError:
        await message.answer('Формат времени неверный. Введите время в формате ЧЧ:ММ')


# Устанавливаем выбранную в клавиатуре get_repeat_keyboard периодичность напоминаний
@router.callback_query(NewCaseStates.set_repeat, RepeatCallback.filter())
async def set_repeat(
    query: CallbackQuery,
    callback_data: RepeatCallback,
    state: FSMContext,
    bot=Bot,
):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    repeat_option = callback_data.repeat_option

    await state.update_data(repeat=repeat_option)
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f'Выбранная Вами частота напоминания: {repeat_option}',
    )
    await bot.send_message(
        chat_id=query.from_user.id,
        text=msg.NEW_CASE_FILES,
        reply_markup=await kb.yes_no_kb(),
    )
    await state.set_state(NewCaseStates.add_attachments)


# Без файлов (Финиш для создания нового события при таком сценарии)
@router.callback_query(
    NewCaseStates.add_attachments,
    NewCaseInterfaceCallback.filter(F.case_files_option == False),  # noqa: E712
)
async def new_case(query: CallbackQuery, state: FSMContext, bot=Bot):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    user_id = query.from_user.id
    state_data = await state.get_data()
    selected_date = state_data['selected_date']
    run_date = datetime.strptime(selected_date, '%Y-%m-%d %H:%M')

    db.create_object(
        Cases(
            user_id=user_id,
            name=state_data['name'],
            start_date=datetime.now(),
            last_notification=datetime.now(),  # Добавляем
            description=state_data['description'],
            deadline_date=run_date,
            original_deadline=run_date,  # Добавляем
            repeat=state_data['repeat'],
        ),
    )

    await bot.send_message(
        chat_id=query.from_user.id,
        text='Событие добавлено!',
        reply_markup=kb.main_kb,
    )
    await state.clear()


# С файлами
@router.callback_query(
    NewCaseStates.add_attachments,
    NewCaseInterfaceCallback.filter(F.case_files_option),
)
async def case_files(query: CallbackQuery, state: FSMContext, bot=Bot):
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    pick = await bot.send_message(
        chat_id=query.from_user.id,
        text='Прикрепите все необходимые файлы и нажмите, как всё будет загружено',
        reply_markup=await kb.set_new_case_with_files(),
    )
    await state.update_data(bot_message_id=pick.message_id)
    await state.set_state(NewCaseStates.set_files)


@router.message(NewCaseStates.set_files)
async def set_files(message: Message, state: FSMContext, bot: Bot):
    state_data = await state.get_data()

    tmp_directory = 'tmp'
    if not os.path.exists(tmp_directory):
        os.makedirs(tmp_directory)

    file_path = None
    file_name = None

    if message.document:
        file_info = await message.bot.get_file(message.document.file_id)
        file_path = os.path.join(tmp_directory, file_info.file_unique_id)
        file_name = message.document.file_name

    elif message.photo:
        file_info = await message.bot.get_file(message.photo[-1].file_id)
        file_name = f'photo_{file_info.file_unique_id}.jpg'
        file_path = os.path.join(tmp_directory, file_name)

    if file_path and file_name:
        await message.bot.download_file(file_info.file_path, file_path)

        attachments = state_data.get('attachments', [])
        attachment_info = f'{file_name}@@@{file_path}'
        attachments.append(attachment_info)
        await state.update_data(attachments=attachments)

        await message.answer(f'Файл {file_name} успешно загружен')

    else:
        await message.answer(
            'Прикрепите файл или завершите добавление, нажав на кнопку',
            reply_markup=await kb.set_new_case_with_files(),
        )


@router.callback_query(
    NewCaseStates.set_files,
    NewCaseFinishWithFilesCallback.filter(F.finish_case == True),  # noqa: E712
)
async def finish_case_creation(query: CallbackQuery, state: FSMContext, bot=Bot):
    await bot.delete_message(
        chat_id=query.from_user.id,
        message_id=query.message.message_id,
    )
    state_data = await state.get_data()
    user_id = query.from_user.id
    selected_date = state_data['selected_date']
    run_date = datetime.strptime(selected_date, '%Y-%m-%d %H:%M')

    case = db.create_object(
        Cases(
            user_id=user_id,
            name=state_data['name'],
            start_date=datetime.now(),
            last_notification=datetime.now(),  # Добавляем
            description=state_data['description'],
            deadline_date=run_date,
            original_deadline=run_date,  # Добавляем
            repeat=state_data['repeat'],
        ),
    )

    for attachment_info in state_data['attachments']:
        file_name, file_url = attachment_info.split('@@@')
        db.create_object(
            File(
                file_name=file_name,
                file_url=file_url,
                case_id=case,
            ),
        )

    await bot.send_message(
        chat_id=query.from_user.id,
        text='Событие добавлено!',
        reply_markup=kb.main_kb,
    )
    await state.clear()
