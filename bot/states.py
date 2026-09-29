from aiogram.fsm.state import State, StatesGroup


class BookingSG(StatesGroup):
    service = State()
    master = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


class AdminSG(StatesGroup):
    svc_name = State()
    svc_duration = State()
    svc_price = State()
    master_name = State()
    master_rename = State()
    wh_input = State()
    block_date = State()
    block_time = State()
    set_value = State()
    broadcast = State()
