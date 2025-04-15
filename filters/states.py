from aiogram.fsm.state import State, StatesGroup


# State создания нового события
class NewCaseStates(StatesGroup):
    set_case_name = State()
    add_case_description = State()
    set_case_description = State()
    select_date = State()
    select_time = State()
    set_repeat = State()
    add_attachments = State()
    set_files = State()
    set_case_type = State()
    finish_case = State()


class CurrentCasesStates(StatesGroup):
    get_current_cases = State()
    get_case_action = State()


class EditCaseStates(StatesGroup):
    waiting_for_new_files = State()
    editing_files = State()
    waiting_for_new_date = State()
    waiting_for_new_repeat = State()
    waiting_for_field_choice = State()
    waiting_for_new_value = State()
    awaiting_new_time = State()
    delete_file = State()


class FinishedCasesStates(StatesGroup):
    get_current_cases = State()
    get_case_action = State()
    waiting_for_restore_date = State()
    select_time = State()


class TodayCasesStates(StatesGroup):
    get_current_cases = State()
    get_case_action = State()
