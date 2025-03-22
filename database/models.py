from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Integer, Boolean, String, DateTime, Date, Time, func, ForeignKey, Text


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    # Имя и фамилия из Telegram
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    username: Mapped[str] = mapped_column(String(150), nullable=True)

    # Данные анкеты для карты лояльности
    name: Mapped[str] = mapped_column(String(150), nullable=True)
    surname: Mapped[str] = mapped_column(String(150), nullable=True)
    birth_date: Mapped[Date] = mapped_column(Date, nullable=True)

    gender: Mapped[str] = mapped_column(String(10), nullable=True)
    profession: Mapped[str] = mapped_column(String(40), nullable=True)

    survey: Mapped[list['Survey']] = relationship(back_populates='user',
                                                  cascade='all, delete-orphan')
    feedback: Mapped[list['Feedback']] = relationship(back_populates='user',
                                                  cascade='all, delete-orphan')
    booking: Mapped[list['Booking']] = relationship(back_populates='user',
                                                    cascade='all, delete-orphan')
    loyalty_card: Mapped['LoyaltyCard'] = relationship(back_populates='user', uselist=False,
                                                       cascade='all, delete-orphan')


class Survey(Base):
    __tablename__ = 'survey'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey('user.tg_id'), nullable=False)
    age_group: Mapped[str] = mapped_column(String(40), nullable=True)
    residence: Mapped[str] = mapped_column(String(150), nullable=True)
    company: Mapped[str] = mapped_column(String(150), nullable=True)
    reason: Mapped[str] = mapped_column(String(150), nullable=True)
    advertising_sources: Mapped[str] = mapped_column(String(150), nullable=True)
    visit_frequency: Mapped[str] = mapped_column(String(150), nullable=True)
    purpose: Mapped[str] = mapped_column(String(150), nullable=True)
    food_preferences: Mapped[str] = mapped_column(String(150), nullable=True)
    suggestions: Mapped[str] = mapped_column(String(150), nullable=True)
    atmosphere: Mapped[str] = mapped_column(String(150), nullable=True)
    service_rating: Mapped[str] = mapped_column(String(150), nullable=True)
    improvements: Mapped[str] = mapped_column(String(150), nullable=True)
    obstacles: Mapped[str] = mapped_column(String(150), nullable=True)
    restaurants: Mapped[str] = mapped_column(String(150), nullable=True)
    news: Mapped[str] = mapped_column(String(150), nullable=True)
    wishes: Mapped[str] = mapped_column(String(300), nullable=True)
    recommendation: Mapped[str] = mapped_column(String(300), nullable=True)
    explanation: Mapped[str] = mapped_column(String(300), nullable=True)

    user: Mapped['User'] = relationship(back_populates='survey')


class Feedback(Base):
    __tablename__ = 'feedback'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey('user.tg_id'), nullable=False)
    text_to_chat: Mapped[str] = mapped_column(Text, nullable=True)
    text_to_boss: Mapped[str] = mapped_column(Text, nullable=True)

    user: Mapped['User'] = relationship(back_populates='feedback')


class Booking(Base):
    __tablename__ = 'booking'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey('user.tg_id'), nullable=False)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    select_date: Mapped[Date] = mapped_column(Date, nullable=False)
    select_time: Mapped[Time] = mapped_column(Time, nullable=False)
    select_guests: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_info: Mapped[str] = mapped_column(String(300), nullable=True)
    client_confirm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    admin_confirm: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    admin_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    admin_comment: Mapped[str] = mapped_column(String(300), nullable=True)
    admin_action_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    user: Mapped['User'] = relationship(back_populates='booking')


class LoyaltyCard(Base):
    __tablename__ = 'loyalty_card'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey('user.tg_id'), nullable=False)
    card_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=True )

    user: Mapped['User'] = relationship(back_populates='loyalty_card')
