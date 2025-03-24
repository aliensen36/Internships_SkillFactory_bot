import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Integer, Boolean, String, DateTime, Date, Time, func, ForeignKey, Text, select
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import func
from typing import Optional, List

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

    # Связи
    broadcasts: Mapped[List['Broadcast']] = relationship(
        'Broadcast',
        secondary='broadcast_course_association',
        back_populates='courses',
        lazy='selectin'
    )
    users: Mapped[list['User']] = relationship(
        'User',
        back_populates='course',
        lazy='selectin'
    )
    specialization: Mapped['Specialization'] = relationship(
        'Specialization',
        back_populates='courses',
        lazy='joined'
    )

    def __repr__(self):
        return f"Course(id={self.id}, name='{self.name}')"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


# Модель рассылки
class Broadcast(Base):
    __tablename__ = 'broadcasts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    # Для SQLite используем JSON-сериализацию вместо ARRAY
    course_ids: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # JSON-строка с массивом ID курсов

    # Связь с курсами
    courses: Mapped[List['Course']] = relationship(
        'Course',
        secondary='broadcast_course_association',
        back_populates='broadcasts'
    )

    def set_course_ids(self, ids: List[int]):
        """Установить список ID курсов"""
        self.course_ids = json.dumps(ids)

    def get_course_ids(self) -> List[int]:
        """Получить список ID курсов"""
        return json.loads(self.course_ids) if self.course_ids else []

    async def get_recipients(self, session: AsyncSession) -> List[User]:
        """Получить список пользователей для рассылки"""
        result = await session.execute(
            select(User).where(User.course_id.in_(self.get_course_ids())))
        return result.scalars().all()


class BroadcastCourseAssociation(Base):
    __tablename__ = 'broadcast_course_association'

    broadcast_id: Mapped[int] = mapped_column(ForeignKey('broadcasts.id'), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), primary_key=True)
