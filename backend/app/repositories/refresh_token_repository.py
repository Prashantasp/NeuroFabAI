from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.repositories.base_repository import BaseRepository
from app.models.refresh_token import RefreshToken
from pydantic import BaseModel
from datetime import datetime

class RefreshTokenCreate(BaseModel):
    user_id: str
    hashed_token: str
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class RefreshTokenUpdate(BaseModel):
    revoked: bool

class RefreshTokenRepository(BaseRepository[RefreshToken, RefreshTokenCreate, RefreshTokenUpdate]):
    def get_by_token(self, db: Session, *, hashed_token: str) -> Optional[RefreshToken]:
        stmt = select(self.model).where(self.model.hashed_token == hashed_token)
        result = db.execute(stmt)
        return result.scalar_one_or_none()

    def revoke_token(self, db: Session, *, token_id: str) -> None:
        stmt = update(self.model).where(self.model.id == token_id).values(revoked=True)
        db.execute(stmt)
        db.commit()
        
    def revoke_all_for_user(self, db: Session, *, user_id: str) -> None:
        stmt = update(self.model).where(self.model.user_id == user_id).values(revoked=True)
        db.execute(stmt)
        db.commit()

refresh_token_repo = RefreshTokenRepository(RefreshToken)
