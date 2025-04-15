from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from filters.callback_data import (
    CurrentCaseCallBack,
    FileCallback,
    NewCaseFinishWithFilesCallback,
    NewCaseInterfaceCallback,
)


main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='/new_case')],
        [
            KeyboardButton(text='/active_cases'),
            KeyboardButton(text='/finished_cases'),
            KeyboardButton(text='/today_cases'),
        ],
        [KeyboardButton(text='/stop')],
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите пункт меню',
)

YES_NO = [
    (
        'Да',
        NewCaseInterfaceCallback(
            case_description_option=True,
            case_files_option=True,
        ),
    ),
    (
        'Нет',
        NewCaseInterfaceCallback(
            case_description_option=False,
            case_files_option=False,
        ),
    ),
]

DONE_KEY = [('Готово', NewCaseFinishWithFilesCallback(finish_case=True))]


async def yes_no_kb():
    builder = InlineKeyboardBuilder()
    for (title, callback_data) in YES_NO:
        builder.button(text=title, callback_data=callback_data)
    return builder.adjust(1, 1).as_markup()


async def get_repeat_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='Ежедневно', callback_data='repeat:Ежедневно')
    builder.button(text='Еженедельно', callback_data='repeat:Еженедельно')
    builder.button(text='Ежемесячно', callback_data='repeat:Ежемесячно')
    builder.button(text='Без напоминаний', callback_data='repeat:Без напоминаний')
    return builder.adjust(1).as_markup()


async def set_new_case_with_files():
    builder = InlineKeyboardBuilder()
    for (title, callback_data) in DONE_KEY:
        builder.button(text=title, callback_data=callback_data)
    return builder.adjust(1).as_markup()


def create_cases_keyboard(cases):
    builder = InlineKeyboardBuilder()
    for case_row in cases:
        case = case_row[0]
        case_id = case.id
        button_text = f'{case.name} {case.deadline_date}'
        callback_data = CurrentCaseCallBack(case_id=case_id)
        builder.button(text=button_text, callback_data=callback_data)
    builder.adjust(1)
    return builder.as_markup()


def create_files_keyboard(files):
    builder = InlineKeyboardBuilder()
    for file_row in files:
        doc = file_row[0]
        file_id = doc.id
        button_text = doc.file_name
        callback_data = FileCallback(file_id=file_id)
        builder.button(text=button_text, callback_data=callback_data)
    builder.adjust(2)
    return builder.as_markup()


def create_case_management_keyboard(case_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='Выполнить', callback_data=f'manage_case:complete:{case_id}')
    builder.button(text='Файлы', callback_data=f'manage_case:files:{case_id}')
    builder.button(text='Редактировать', callback_data=f'manage_case:edit:{case_id}')
    builder.button(text='Удалить', callback_data=f'manage_case:delete:{case_id}')
    builder.adjust(2, 2)
    return builder.as_markup()


def create_finished_case_management_keyboard(case_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='Файлы', callback_data=f'manage_case:files:{case_id}')
    builder.button(text='Восстановить', callback_data=f'manage_case:restore:{case_id}')
    builder.button(text='Удалить', callback_data=f'manage_case:delete:{case_id}')
    builder.adjust(3)
    return builder.as_markup()


def create_case_editing_keyboard(case_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='Название', callback_data=f'edit_case:name:{case_id}')
    builder.button(text='Описание', callback_data=f'edit_case:description:{case_id}')
    builder.button(text='Дата', callback_data=f'edit_case:deadline_date:{case_id}')
    builder.button(text='Повторение', callback_data=f'edit_case:repeat:{case_id}')
    builder.button(text='Файлы', callback_data=f'edit_case:files:{case_id}')
    builder.adjust(1)
    return builder.as_markup()


def create_sending_case_management_keyboard(case_id):
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Выполнить',
        callback_data=f'manage_sending_case:complete:{case_id}',
    )
    builder.button(text='Файлы', callback_data=f'manage_sending_case:files:{case_id}')
    builder.adjust(2)
    return builder.as_markup()
