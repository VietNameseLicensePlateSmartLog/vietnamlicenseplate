from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.config.database import get_db
from src.modules.region.controller import RegionController

router = APIRouter(tags=["Regions"])

@router.get("/regions")
def get_regions(db: Session = Depends(get_db)):
    return RegionController.get_regions(db)
