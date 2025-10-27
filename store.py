from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from config import DATABASE_URL
from datetime import datetime

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_telegram_id: int
    name: str
    price_slh: float
    image_ipfs: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

def add_product(owner_telegram_id: int, name: str, price_slh: float, image_ipfs: str = None):
    with Session(engine) as s:
        p = Product(owner_telegram_id=owner_telegram_id, name=name, price_slh=price_slh, image_ipfs=image_ipfs)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p

def list_products(owner_telegram_id: int):
    with Session(engine) as s:
        stmt = select(Product).where(Product.owner_telegram_id == owner_telegram_id)
        return s.exec(stmt).all()

def get_product(product_id: int):
    with Session(engine) as s:
        stmt = select(Product).where(Product.id == product_id)
        return s.exec(stmt).first()
