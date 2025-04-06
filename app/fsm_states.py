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
    waiting_for_project_selection = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_benefit = State()
    waiting_for_confirmation = State()


class ProjectDeleteState(StatesGroup):
    waiting_for_delete = State()
    waiting_for_confirmation = State()


class SpecializationState(StatesGroup):
    waiting_for_action = State()
    waiting_for_name = State()


class SpecializationAddState(StatesGroup):
    waiting_for_name = State()
    waiting_for_confirmation = State()


class SpecializationEditState(StatesGroup):
    waiting_for_specialization_selection = State()
    waiting_for_name = State()
    waiting_for_confirmation = State()


class SpecializationDeleteState(StatesGroup):
    waiting_for_delete = State()
    waiting_for_confirmation = State()


class CourseState(StatesGroup):
    waiting_for_action = State()
    waiting_for_specialization = State()
    waiting_for_name = State()


class CourseAddState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_name = State()
    waiting_for_confirmation = State()


class CourseEditState(StatesGroup):
    waiting_for_specialization_selection = State()
    waiting_for_course_selection = State()
    waiting_for_name = State()
    waiting_for_confirmation = State()


class CourseDeleteState(StatesGroup):
    waiting_for_delete = State()
    waiting_for_confirmation = State()


class ChangeCourseState(StatesGroup):
    waiting_for_specialization = State()
    waiting_for_course = State()