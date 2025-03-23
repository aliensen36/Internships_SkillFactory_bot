from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Integer, Boolean, String, DateTime, Date, Time, func, ForeignKey, Text
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import func

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

# Модель пользователей
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    username: Mapped[str] = mapped_column(String(150), nullable=True)

    # Внешний ключ на специализацию и курс
    specialization_id: Mapped[int] = mapped_column(ForeignKey('specializations.id'), nullable=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), nullable=True)

    # Связь с специализацией
    specialization: Mapped['Specialization'] = relationship('Specialization', back_populates='users')
    # Связь с курсом
    course: Mapped['Course'] = relationship('Course', back_populates='users')

# Модель специализаций
class Specialization(Base):
    __tablename__ = 'specializations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Связь с пользователями
    users: Mapped[list['User']] = relationship('User', back_populates='specialization')
    # Связь с курсами
    courses: Mapped[list['Course']] = relationship('Course', back_populates='specialization')

# Модель курсов
class Course(Base):
    __tablename__ = 'courses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialization_id: Mapped[int] = mapped_column(Integer, ForeignKey('specializations.id'), nullable=False)

    # Связь с пользователями
    users: Mapped[list['User']] = relationship('User', back_populates='course')
    # Связь с специализацией
    specialization: Mapped['Specialization'] = relationship('Specialization', back_populates='courses')





class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

