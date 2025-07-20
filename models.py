from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from session_database import Base  # import the Base defined in session_database.py

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    agency: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_id: Mapped[str] = mapped_column(String, index=True)
    pacing_mode: Mapped[str] = mapped_column(String)
    current_turn: Mapped[int] = mapped_column(Integer)

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    in_game_date: Mapped[str] = mapped_column(String, default="1955-05-04")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.session_id"))
    sender: Mapped[str] = mapped_column(String)         # 'user' or 'ai'
    content: Mapped[str] = mapped_column(Text)
    turn_number: Mapped[int] = mapped_column(Integer)
    pacing_mode: Mapped[str] = mapped_column(String)    # e.g. 'green', 'yellow', 'red'
    in_game_date: Mapped[str] = mapped_column(String, default="1955-05-04")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship("Session", back_populates="messages", lazy="selectin")