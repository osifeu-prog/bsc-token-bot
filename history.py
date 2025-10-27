from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from datetime import datetime
from config import DATABASE_URL

class History(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: Optional[int] = None
    action: str
    metadata: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

def log_action(telegram_id: int, action: str, metadata: str = None):
    with Session(engine) as s:
        h = History(telegram_id=telegram_id, action=action, metadata=metadata)
        s.add(h)
        s.commit()
        s.refresh(h)
        return h

def get_history(limit: int = 100):
    with Session(engine) as s:
        stmt = select(History).order_by(History.created_at.desc()).limit(limit)
        return s.exec(stmt).all()
