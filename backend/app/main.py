from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, List, Optional
from enum import Enum
import uvicorn
import uuid
import datetime

# Create FastAPI instance
app = FastAPI(
    title="Orchids Challenge API",
    description="A starter FastAPI template for the Orchids Challenge backend",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#  MODELS
class CloneStatus(str, Enum):
    PENDING = "pending"
    SCRAPING = "scraping" 
    PROCESSING = "processing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class CloneRequest(BaseModel):
    url: HttpUrl

class CloneJob(BaseModel):
    job_id: str
    status: CloneStatus
    url: str
    progress: int
    created_at: str
    error_message: Optional[str] = None
    result_data: Optional[Dict] = None
    

class CloneResponse(BaseModel):
    job_id: str
    status: CloneStatus
    message: str

# db
jobs_db: Dict[str, CloneJob] = {}


# clone website
@app.post("/api/clone", response_model=CloneResponse) 
async def clone_url(request: CloneRequest, background_tasks: BackgroundTasks):
    try:
        job_id = str(uuid.uuid())
        
        job = CloneJob(
            job_id=job_id,
            status=CloneStatus.PENDING,
            url=str(request.url),
            progress=0,
            created_at=datetime.now()
        )
        
        # Store job
        jobs_db[job_id] = job
        
        # Start background processing
        background_tasks.add_task(process_clone_job, job_id, str(request.url))
        
        return CloneResponse(
            job_id=job_id,
            status=CloneStatus.PENDING,
            message="Cloning process started"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start cloning: {str(e)}")
    
async def process_clone_job(job_id: str, url: HttpUrl):
    try:
        jobs_db[job_id].status = CloneStatus.SCRAPING
        jobs_db[job_id].progress = 10
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process cloning: {str(e)}")
    

 # returns status of job_id
@app.get("/api/clone/{job_id}/status")

# result
@app.get("api/clone/{job_id}/result")

# preview
@app.get("api/clone/{job_id}/preview")

# websocket
@app.websocket("/ws/clone/{job_id}")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")

# Delete item
# @app.delete("/items/{item_id}")
# async def delete_item(item_id: int):
#     for i, item in enumerate(items_db):
#         if item.id == item_id:
#             deleted_item = items_db.pop(i)
#             return {"message": f"Item {item_id} deleted successfully", "deleted_item": deleted_item}
#     return {"error": "Item not found"}


def main():
    """Run the application"""
    uvicorn.run(
        "hello:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
