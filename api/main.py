import pandas as pd
from api_config import ApiConfig
import logging
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from ultralytics import YOLO
from utils import *
import uuid
from datetime import datetime
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

os.makedirs(ApiConfig.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ApiConfig.RESULTS_FOLDER, exist_ok=True)


try:
    model = YOLO("yolov8n.pt")
    logger.info("Модель загружена")
except Exception as e:
    logger.error(f"Ошибка загрузки модели: {str(e)}")
    raise

@app.post("/process/")
async def process_file(file: UploadFile = File(...)):
    try:
        request_id = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1]
        file_path = os.path.join(ApiConfig.UPLOAD_FOLDER, f"{request_id}.{file_ext}")
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        is_video = file_ext.lower() in ["mp4", "avi", "mov"]
        
        if is_video:
            result_path, stats = await process_video(file_path, request_id, model)
        else:
            result_path, stats = await process_image_file(file_path, request_id, model)
        
        stats_path = os.path.join(ApiConfig.RESULTS_FOLDER, f"{request_id}_stats.json")
        with open(stats_path, "w") as f:
            json.dump(stats, f)
        
        save_to_history({
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "original_file": file_path,
            "result_file": result_path,
            "is_video": is_video,
            "stats": stats
        })
        
        return JSONResponse({
            "status": "success",
            "request_id": request_id,
            "result_path": result_path,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Ошибка обработки: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/history/")
async def get_history():
    try:
        if not os.path.exists(ApiConfig.HISTORY_FILE):
            return JSONResponse([])
        
        with open(ApiConfig.HISTORY_FILE, "r") as f:
            history = json.load(f)
        
        return JSONResponse(history)
    except Exception as e:
        logger.error(f"Ошибка в отображении истории: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/")
async def generate_report():
    try:
        if not os.path.exists(ApiConfig.HISTORY_FILE):
            raise HTTPException(status_code=404, detail="No history available")
        
        with open(ApiConfig.HISTORY_FILE, "r") as f:
            history = json.load(f)
        
        data = []
        for entry in history:
            stats = entry.get("stats", {})
            data.append({
                "ID": entry["request_id"],
                "Дата": entry["timestamp"],
                "Тип файла": "Видео" if entry.get("is_video", False) else "Изображение",
                "Всего стульев": stats.get("total_chairs", "N/A"),
                "Свободных": stats.get("free_chairs", stats.get("total_free_chairs", "N/A")),
                "Занято": stats.get("occupied_chairs", stats.get("total_occupied_chairs", "N/A")),
                "Процент занятых": f"{stats.get('occupancy_rate', stats.get('average_occupancy_rate', 0))*100:.1f}%",
                "Время обработки": stats.get("processing_time_seconds", "N/A"),
                "Путь до файла": entry["original_file"]
            })
        
        df = pd.DataFrame(data)
        report_path = os.path.join(ApiConfig.RESULTS_FOLDER, "report.xlsx")
        df.to_excel(report_path, index=False)
        
        return FileResponse(
            report_path,
            filename="occupancy_report.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"Ошибка в формировании отчета: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/result/{request_id}")
async def get_result(request_id: str):
    try:
        results = os.listdir(ApiConfig.RESULTS_FOLDER)
        result_files = [f for f in results if f.startswith(request_id) and "_result" in f]
        
        if not result_files:
            raise HTTPException(status_code=404, detail="Result not found")
        
        result_file = result_files[0]
        result_path = os.path.join(ApiConfig.RESULTS_FOLDER, result_file)
        
        if result_file.endswith(".jpg"):
            media_type = "image/jpeg"
        elif result_file.endswith(".mp4"):
            media_type = "video/mp4"
        else:
            media_type = "application/octet-stream"
        
        return FileResponse(result_path, media_type=media_type)
    except Exception as e:
        logger.error(f"Result retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")