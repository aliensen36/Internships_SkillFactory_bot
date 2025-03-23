# Список курсов
COURSE_TITLES = {
    "PDEV": "Python-разработчик (PDEV)",
    "PDEVPRO": "Python-разработчик PRO (PDEVPRO)",
    "AI": "Разработчик искусственного интеллекта (AI)",
    "DS": "Data Scientist (DS)",
    "ML": "Machine Learning Engineer (ML)",
    "DA": "Аналитик данных (DA)",
    "BI": "BI-аналитик (BI)",
    "QAE": "Инженер по тестированию (QAE)",
    "JDEV": "Java-разработчик (JDEV)",
    "FDEV": "Frontend-разработчик (FDEV)",
    "FSDEV": "Fullstack-разработчик (FSDEV)",
    "PWS": "Веб-разработчик на Python (PWS)",
}


# Преобразуем словарь в список курсов
courses = [(name, f"course_{code}") for code, name in COURSE_TITLES.items()]
change_courses = [(name, f"change_course_{code}") for code, name in COURSE_TITLES.items()]


# Список направлений
SPECIALIZATIONS = {
    "dev": "Разработка",
    "qa": "Тестирование",
    "ds": "Аналитика и Data Science",
    "design": "Дизайн",
    "marketing": "Менеджмент и маркетинг в IT",
    "education": "Высшее образование",
}
