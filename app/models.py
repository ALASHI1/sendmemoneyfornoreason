from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    google_sub: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    picture_url: str = ""
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    payment_links: List["PaymentLink"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class PaymentLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    sort_order: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="payment_links")
