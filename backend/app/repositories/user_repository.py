from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.repositories.base_repository import BaseRepository
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        stmt = select(self.model).where(self.model.email == email)
        result = db.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_username(self, db: Session, *, username: str) -> Optional[User]:
        stmt = select(self.model).where(self.model.username == username)
        result = db.execute(stmt)
        return result.scalar_one_or_none()

user_repo = UserRepository(User)
