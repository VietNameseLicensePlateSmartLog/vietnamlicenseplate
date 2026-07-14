from sqlalchemy.orm import Session
from src.modules.region.service import RegionService

class RegionController:
    @staticmethod
    def get_regions(db: Session):
        return RegionService.get_regions(db)
