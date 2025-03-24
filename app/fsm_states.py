from aiogram.fsm.state import State, StatesGroup

class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_image = State()
    waiting_for_courses = State()
    confirmation = State()


class ProjectAddState(StatesGroup):
    title = State()
    content = State()


class SpecializationState(StatesGroup):
    waiting_for_specialization_name = State()


class CourseState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course_name = State()