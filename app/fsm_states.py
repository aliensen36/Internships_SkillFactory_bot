from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_project = State()
    waiting_for_courses = State()
    waiting_for_course_search = State()
    confirmation = State()


class ProjectAddState(StatesGroup):
    title = State()
    content = State()


class SpecializationState(StatesGroup):
    waiting_for_specialization_name = State()


class CourseState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course = State()

class ChangeCourseState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course = State()

# Состояния для меню
class MenuState(StatesGroup):
    main_menu = State()
    level_1_menu = State()
    level_2_menu = State()
    level_3_menu = State()
    level_4_menu = State()