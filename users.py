from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from config import DATABASE_URL

# מודל משתמש פשוט
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int
    wallet_address: Optional[str] = None

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_user_by_telegram(telegram_id: int):
    with Session(engine) as s:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = s.exec(stmt).first()
        return res

def create_or_update_user(telegram_id: int, wallet_address: str = None):
    with Session(engine) as s:
        user = get_user_by_telegram(telegram_id)
        if not user:
            user = User(telegram_id=telegram_id, wallet_address=wallet_address)
            s.add(user)
            s.commit()
            s.refresh(user)
            return user
        if wallet_address:
            user.wallet_address = wallet_address
            s.add(user)
            s.commit()
            s.refresh(user)
        return user
