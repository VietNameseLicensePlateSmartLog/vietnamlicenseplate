from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.modules.region.models import Region

class RegionService:
    @staticmethod
    def get_regions(db: Session):
        regions = db.query(Region).filter(Region.is_active == True).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "location": r.location,
                "is_active": r.is_active
            }
            for r in regions
        ]
