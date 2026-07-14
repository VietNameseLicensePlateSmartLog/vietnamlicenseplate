from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class DetectionBase(BaseModel):
    plate_text: str
    plate_confidence: float
    alt_text: Optional[str] = None
    alt_confidence: Optional[float] = None
    image_path: Optional[str] = None
    source_type: str = "camera"

class DetectionCreate(DetectionBase):
    pass

class DetectionResponse(DetectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PlatePrediction(BaseModel):
    bbox: List[int]
    text: str
    conf: float
