from aiogram.filters.callback_data import CallbackData


# class UserInterfaceCallback(CallbackData, prefix='user-ui'):
#     pass


class UserBackCallback(CallbackData, prefix='user_back'):
    is_back: bool


# Опции сценария создания нового события
class NewCaseInterfaceCallback(CallbackData, prefix='new_case-ui'):
    case_description_option: bool
    case_files_option: bool


class NewCaseFinishWithFilesCallback(CallbackData, prefix='new_case-finish_files'):
    finish_case: bool


class RepeatCallback(CallbackData, prefix='repeat'):
    repeat_option: str


class FileCallback(CallbackData, prefix='file'):
    file_id: int


class CurrentCaseCallBack(CallbackData, prefix='cur_case'):
    case_id: int


class ManageCaseCallback(CallbackData, prefix='manage_case'):
    action: str
    case_id: int


class ManageSendingCaseCallback(CallbackData, prefix='manage_sending_case'):
    action: str
    case_id: int


class EditCaseCallback(CallbackData, prefix='edit_case'):
    action: str
    case_id: int
