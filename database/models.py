import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Integer, Boolean, String, DateTime, Date, Time, func, ForeignKey, Text, select
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import func
from typing import Optional, List
from sqlalchemy.ext.hybrid import hybrid_property

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

    broadcasts: Mapped[List['Broadcast']] = relationship(
        secondary='broadcast_course_association',
        back_populates='courses',
        viewonly=True
    )
    broadcast_associations: Mapped[List['BroadcastCourseAssociation']] = relationship(
        back_populates='course',
        cascade='all, delete-orphan',
        passive_deletes=True
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



class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    benefit: Mapped[str] = mapped_column(Text, nullable=True)
    example: Mapped[str] = mapped_column(Text, nullable=True)
    raw_description: Mapped[str] = mapped_column(Text, nullable=True)  # Оригинальное описание с URL
    raw_benefit: Mapped[str] = mapped_column(Text, nullable=True)  # Оригинальные бенефиты с URL
    raw_example: Mapped[str] = mapped_column(Text, nullable=True)  # Оригинальные примеры с URL

    broadcasts: Mapped[List["Broadcast"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan"
    )
    broadcast_course_links: Mapped[List['BroadcastCourseAssociation']] = relationship(
        back_populates='project',
        cascade="all, delete-orphan",
        passive_deletes=True
    )


# Модель рассылки
class Broadcast(Base):
    __tablename__ = 'broadcasts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped[Optional["Project"]] = relationship(
        back_populates="broadcasts"
    )

    course_associations: Mapped[List["BroadcastCourseAssociation"]] = relationship(
        back_populates="broadcast",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    courses: Mapped[List["Course"]] = relationship(
        secondary="broadcast_course_association",
        back_populates="broadcasts",
        viewonly=True
    )

    # course_ids: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    async def set_course_ids(self, ids: List[int], session: AsyncSession):
        """Установить список ID курсов и создать ассоциации"""
        self.course_ids = json.dumps(ids)

        self.course_associations.clear()

        for course_id in ids:
            course = await session.get(Course, course_id)
            if not course:
                continue

            association = BroadcastCourseAssociation(
                course_id=course_id,
                project_id=self.project_id
            )
            self.course_associations.append(association)

    async def get_course_ids(self, session):
        await session.refresh(self, ['course_associations'])
        return [ca.course_id for ca in self.course_associations]

    async def get_recipients(self, session: AsyncSession) -> List[User]:
        course_ids = await self.get_course_ids(session)
        result = await session.execute(
            select(User).where(User.course_id.in_(course_ids)))
        return result.scalars().all()

    async def set_image_path(self, image_filename: str):
        """Метод для установки пути к изображению в базе данных."""
        # Путь к изображению относительно директории проекта
        image_dir = 'media/images/'  # Папка для хранения изображений
        self.image_path = os.path.join(image_dir, image_filename)

    async def get_image_url(self):
        """Метод для получения полного пути к изображению (если необходимо)."""
        return self.image_path


class BroadcastCourseAssociation(Base):
    __tablename__ = 'broadcast_course_association'

    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey('broadcasts.id', ondelete="CASCADE"),
        primary_key=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey('courses.id', ondelete="CASCADE"),
        primary_key=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete="CASCADE"),
        nullable=True
    )

    broadcast: Mapped["Broadcast"] = relationship(back_populates="course_associations")
    course: Mapped["Course"] = relationship(back_populates="broadcast_associations")
    project: Mapped["Project"] = relationship(back_populates="broadcast_course_links")
