from datetime import datetime
from typing import Dict

import cv2
from api_config import ApiConfig
import os
import json


def save_to_history(data: Dict):
    try:
        if os.path.exists(ApiConfig.HISTORY_FILE):
            with open(ApiConfig.HISTORY_FILE, "r") as f:
                history = json.load(f)
        else:
            history = []
        
        history.append(data)
        
        with open(ApiConfig.HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Error: {e}")
        
        
def detect_occupancy(frame, model):
    results = model(frame, classes=[0, 56])
    
    chairs = []
    people = []
    
    for result in results:
        for box in result.boxes:
            box_coords = box.xyxy[0].tolist()
            if box.cls == 56:
                chairs.append(box_coords)
            elif box.cls == 0:
                people.append(box_coords)
    
    occupied = []
    free = []
    
    for chair in chairs:
        is_occupied = False
        
        for person in people:
            if bbox_intersection(chair, person):
                is_occupied = True
                break
        
        if is_occupied:
            occupied.append(chair)
        else:
            free.append(chair)
    
    return occupied, free


def bbox_intersection(box1, box2):
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    overlap_x = max(0, min(x2_1, x2_2) - max(x1_1, x1_2))
    overlap_y = max(0, min(y2_1, y2_2) - max(y1_1, y1_2))
    
    return overlap_x > 0 and overlap_y > 0


async def process_video(video_path: str, request_id: str, model):
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Failed to open video")
        
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        result_path = os.path.join(ApiConfig.RESULTS_FOLDER, f"{request_id}_result.mp4")
        out = cv2.VideoWriter(result_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))
        
        total_frames = 0
        total_chairs = 0
        total_free = 0
        total_occupied = 0
        start_time = datetime.now()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            occupied, free = detect_occupancy(frame, model)
            
            for chair in free:
                x1, y1, x2, y2 = map(int, chair)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            for chair in occupied:
                x1, y1, x2, y2 = map(int, chair)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            cv2.putText(frame, f"Free: {len(free)}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Occupied: {len(occupied)}", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            out.write(frame)
            
            total_frames += 1
            total_chairs += len(free) + len(occupied)
            total_free += len(free)
            total_occupied += len(occupied)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        cap.release()
        out.release()
        
        stats = {
            "total_frames": total_frames,
            "total_chairs": total_chairs,
            "total_free_chairs": total_free,
            "total_occupied_chairs": total_occupied,
            "average_free_per_frame": total_free / total_frames if total_frames > 0 else 0,
            "average_occupied_per_frame": total_occupied / total_frames if total_frames > 0 else 0,
            "average_occupancy_rate": total_occupied / total_chairs if total_chairs > 0 else 0,
            "processing_time_seconds": processing_time,
            "video_duration_seconds": total_frames / fps if fps > 0 else 0
        }
        
        return result_path, stats
    except Exception as e:
        print(f"Video processing error: {str(e)}")
        raise
    
async def process_image_file(image_path: str, request_id: str, model):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Failed to read image")
        
        occupied, free = detect_occupancy(img, model)
        
        for chair in free:
            x1, y1, x2, y2 = map(int, chair)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        for chair in occupied:
            x1, y1, x2, y2 = map(int, chair)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        
        result_path = os.path.join(ApiConfig.RESULTS_FOLDER, f"{request_id}_result.jpg")
        cv2.imwrite(result_path, img)
        
        stats = {
            "total_chairs": len(free) + len(occupied),
            "free_chairs": len(free),
            "occupied_chairs": len(occupied),
            "occupancy_rate": len(occupied) / (len(free) + len(occupied)) if (len(free) + len(occupied)) > 0 else 0,
            "processing_time": datetime.now().isoformat(),
            "image_size": f"{img.shape[1]}x{img.shape[0]}"
        }
        
        return result_path, stats
    except Exception as e:
        print(f"Image processing error: {str(e)}")
        raise