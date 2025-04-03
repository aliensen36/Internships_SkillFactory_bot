from aiogram.fsm.state import State, StatesGroup


class StartState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course = State()


class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_project = State()
    waiting_for_courses = State()
    waiting_for_course_search = State()
    confirmation = State()


class ProjectAddState(StatesGroup):
    waiting_for_action = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_benefit = State()
    waiting_for_confirmation = State()



class ProjectEditState(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_benefit = State()


class ProjectDeleteState(StatesGroup):
    waiting_for_delete = State()
    waiting_for_confirmation = State()


class SpecializationState(StatesGroup):
    waiting_for_action = State()
    waiting_for_name = State()


class CourseState(StatesGroup):
    waiting_for_action = State()
    waiting_for_specialization = State()
    waiting_for_course = State()

class ChangeCourseState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course = State()

