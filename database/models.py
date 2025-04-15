from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Users(Base):
    __tablename__ = 'users'

    id = Column(String(100), primary_key=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))


class Cases(Base):
    __tablename__ = 'cases'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.id'))
    name = Column(String(100))
    start_date = Column(DateTime, nullable=False)
    description = Column(String(100))
    deadline_date = Column(DateTime, nullable=True)
    repeat = Column(String(100))  # 'Ежедневно', 'Еженедельно', 'Ежемесячно' или NULL
    is_finished = Column(Boolean, default=False)
    last_notification = Column(DateTime)  # Добавляем новое поле
    original_deadline = Column(DateTime)  # Добавляем новое поле


class File(Base):  # noqa: WPS110
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'))
    file_name = Column(String(100))
    file_url = Column(String(100))
