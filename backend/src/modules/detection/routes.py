from fastapi import APIRouter, Depends, UploadFile, File, WebSocket, BackgroundTasks
from sqlalchemy.orm import Session
from src.core.config.database import get_db
from src.modules.detection.controller import PredictController

router = APIRouter(tags=["Prediction"])

@router.post("/predict-image")
async def predict_image(
    file: UploadFile = File(...),
    user_id: int | None = None,
    region_id: int | None = None,
    db: Session = Depends(get_db)
):
    return await PredictController.predict_image(file, user_id, region_id, db)

@router.post("/predict-video")
async def predict_video(
    file: UploadFile = File(...),
    user_id: int | None = None,
    region_id: int | None = None,
    db: Session = Depends(get_db)
):
    return await PredictController.predict_video(file, user_id, region_id, db)

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    return await PredictController.get_task_status(task_id, db)

@router.get("/tasks/{task_id}/download")
async def download_task_result(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await PredictController.download_task_result(task_id, background_tasks, db)

@router.get("/tasks/{task_id}/preview")
async def get_preview_frame(task_id: str):
    return await PredictController.get_preview_frame(task_id)

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    return await PredictController.cancel_task(task_id, db)

@router.websocket("/ws/lpr")
async def websocket_lpr(websocket: WebSocket):
    await PredictController.handle_websocket(websocket)

@router.websocket("/ws/lpr-ip")
async def websocket_lpr_ip(websocket: WebSocket):
    """WebSocket nhận diện biển số từ IP camera — backend tự đọc frame."""
    await PredictController.handle_websocket_ip(websocket)
