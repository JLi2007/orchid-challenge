from fastapi import FastAPI
from fastapi import WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, List
import uvicorn

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

# Pydantic models

class CloneRequest(BaseModel):
    url: str

class CloneJob(BaseModel):
    job_id: str
    status: str  # "pending", "scraping", "processing", "generating", "completed", "failed"
    url: str
    progress: int
    created_at: str


# clone website
@app.post("/api/clone") 

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
