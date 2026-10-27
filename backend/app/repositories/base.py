"""
Base Repository class providing standard session operations
"""

from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.orm import Session
from backend.app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: str) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        return self.db.query(self.model).offset(offset).limit(limit).all()
