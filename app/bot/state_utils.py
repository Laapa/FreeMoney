from aiogram.fsm.context import FSMContext


async def clear_admin_state(state: FSMContext) -> None:
    current = await state.get_state()
    if current and current.startswith("AdminStates:"):
        await state.clear()
