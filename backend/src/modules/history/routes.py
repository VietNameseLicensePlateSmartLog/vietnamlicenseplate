from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.config.database import get_db
from src.modules.detection.schemas import DetectionResponse
from src.modules.history.controller import HistoryController

router = APIRouter(tags=["History"])

@router.get("/history", response_model=List[DetectionResponse])
def get_history(user_id: int | None = None, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return HistoryController.get_history(user_id, skip, limit, db)

@router.delete("/history/{id}")
def delete_history(id: int, db: Session = Depends(get_db)):
    return HistoryController.delete_history(id, db)
