from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy import delete, select

from database.db import db
from database.models import Cases, File
from filters.callback_data import FileCallback, ManageCaseCallback


router = Router()


@router.callback_query(FileCallback.filter())
async def download_file(query: CallbackQuery, callback_data: FileCallback, bot: Bot):
    file_id = callback_data.file_id
    user_file = db.sql_query(
        select(File)
        .where(File.id == file_id),
        is_single=True,
    )

    with open(user_file.file_url, 'rb') as f:
        file_bytes = f.read()

    await bot.send_document(
        chat_id=query.from_user.id,
        document=BufferedInputFile(file_bytes, filename=user_file.file_name),
    )


@router.callback_query(ManageCaseCallback.filter(F.action == 'delete'))
async def delete_case(
    query: CallbackQuery,
    callback_data: ManageCaseCallback,
    bot: Bot,
    state: FSMContext,
):
    state_data = await state.get_data()
    name = state_data.get('case')
    await bot.delete_message(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
    )
    case_id = callback_data.case_id
    # Сначала удаляем все связанные файлы
    db.sql_query(
        delete(File)
        .where(File.case_id == case_id),
        is_delete=True,
    )
    # Затем удаляем сам кейс
    db.sql_query(
        delete(Cases)
        .where(Cases.id == case_id),
        is_delete=True,
    )
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f'Событие _{name.name}_ удалено',
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.clear()
