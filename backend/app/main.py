import os
from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
import uvicorn
import uuid
from dotenv import load_dotenv

load_dotenv

from webscape import ScrapingResult, WebScrape

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
    url: str

class CloneJob(BaseModel):
    job_id: str
    status: CloneStatus
    url: str
    progress: int
    created_at: str
    completed_at: Optional[str] = None 
    error_message: Optional[str] = None
    result_data: Optional[Dict] = None
    

class CloneResponse(BaseModel):
    job_id: str
    status: CloneStatus
    message: str

# db
jobs_db: Dict[str, CloneJob] = {}

#WEBSOCKET MANAGER
class ConnectionManager:
    def __init__(self):
        # maps job_id → active WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[job_id] = websocket

    def disconnect(self, job_id: str):
        # clean up when done
        if job_id in self.active_connections:
            del self.active_connections[job_id]

    async def send_update(self, job_id: str, data: dict):        
        # Sends a JSON dict down the socket for job_id, if still connected.

        ws = self.active_connections.get(job_id)
        if ws:
            await ws.send_json(data)

manager = ConnectionManager()

# Initialize scraper
scraper = WebScrape(
    use_browserbase=False,  # Set to True with API key for production
    browserbase_api_key=os.getenv("BROWSERBASE_KEY")  # Add your Browserbase API key here
)

# clone website
@app.post("/api/clone", response_model=CloneResponse) 
async def clone_url(clone_request: CloneRequest, background_tasks: BackgroundTasks):
    try:
        job_id = str(uuid.uuid4())
        
        job = CloneJob(
            job_id=job_id,
            status  =CloneStatus.PENDING,
            url=str(clone_request.url),
            progress=0,
            created_at=str(datetime.now())
        )
        
        # Store job
        jobs_db[job_id] = job
        
        # Start background processing
        background_tasks.add_task(process_clone_job, job_id, str(clone_request.url))
        
        return CloneResponse(
            job_id=job_id,
            status=CloneStatus.PENDING,
            message="Cloning process started"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start cloning: {str(e)}")

# PROCESS CLONE JOB
async def process_clone_job(job_id: str, url: str):
    try:
        # Update job status
        jobs_db[job_id].status = CloneStatus.SCRAPING
        jobs_db[job_id].progress = 10
        
        await manager.send_update(
            job_id,
            {
                "status": jobs_db[job_id].status.value,
                "progress": jobs_db[job_id].progress,
            }
        )
        
        # Step 1: Scrape the website
        scraping_result = await scraper.scrape_website(url)
        
        if not scraping_result.success:
            jobs_db[job_id].status = CloneStatus.FAILED
            jobs_db[job_id].progress = 0
            jobs_db[job_id].error_message = scraping_result.error_message
            
            await manager.send_update(
                job_id,
                {
                    "status": jobs_db[job_id].status.value,
                    "progress": jobs_db[job_id].progress,
                    "error_message": jobs_db[job_id].error_message 
                }
            )
                    
            return
        
        # Update progress
        jobs_db[job_id].progress = 50
        jobs_db[job_id].status = CloneStatus.PROCESSING
        
        await manager.send_update(
            job_id,
            {
                "status": jobs_db[job_id].status.value,
                "progress": jobs_db[job_id].progress,
            }
        )
        
        # Step 2: Process the scraped data for LLM
        processed_data = await process_scraping_data(scraping_result)
        
        # Update progress
        jobs_db[job_id].progress = 70
        jobs_db[job_id].status = CloneStatus.GENERATING
        
        await manager.send_update(
            job_id,
            {
                "status": jobs_db[job_id].status.value,
                "progress": jobs_db[job_id].progress,
            }
        )
        
        # Step 3: Generate HTML with LLM (placeholder for now)
        generated_html = await generate_html_with_llm(processed_data)
        
        # Update job as completed
        jobs_db[job_id].status = CloneStatus.COMPLETED
        jobs_db[job_id].progress = 100
        
        await manager.send_update(
            job_id,
            {
                "status": jobs_db[job_id].status.value,
                "progress": jobs_db[job_id].progress,
            }
        )
                    
        jobs_db[job_id].completed_at = datetime.now()
        jobs_db[job_id].result_data = {
            "original_url": url,
            "generated_html": generated_html,
            "scraping_metadata": {
                "colors_found": len(scraping_result.color_palette),
                "images_found": len(scraping_result.assets.get("images", [])),
                "fonts_found": len(scraping_result.typography.get("fonts", [])),
                "screenshots_taken": list(scraping_result.screenshots.keys())
            }
        }
        
    except Exception as e:
        # Handle any errors
        jobs_db[job_id].status = CloneStatus.FAILED
        jobs_db[job_id].progress = 0
        jobs_db[job_id].error_message = str(e)
        jobs_db[job_id].completed_at = datetime.now()
        
        await manager.send_update(
            job_id,
            {
                "status": jobs_db[job_id].status.value,
                "progress": jobs_db[job_id].progress,
                "error_message": jobs_db[job_id].error_message 
            }
        )

async def process_scraping_data(scraping_result: ScrapingResult) -> Dict:
    """Process scraped data for LLM consumption"""
    return {
        "url": scraping_result.url,
        "screenshots": scraping_result.screenshots,
        "dom_structure": scraping_result.dom_structure[:10000],  # Limit size
        "color_palette": scraping_result.color_palette,
        "typography": scraping_result.typography,
        "layout_info": scraping_result.layout_info,
        "css_info": scraping_result.extracted_css,
        "metadata": scraping_result.metadata,
        "raw_html": scraping_result.raw_html
    }
    
async def generate_html_with_llm(processed_data: Dict) -> str:
    """Generate HTML using LLM (placeholder implementation)"""
    # TODO: Implement LLM integration here
    # This is where you'll call Claude/GPT with the processed data
    
    # For now, return a simple HTML template
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cloned Website</title>
        <style>
            body {{
                font-family: {processed_data['typography'].get('fonts', ['Arial'])[0] if processed_data['typography'].get('fonts') else 'Arial'};
                background-color: {processed_data['color_palette'][0] if processed_data['color_palette'] else '#ffffff'};
            }}
        </style>
    </head>
    <body>
        <h1>Website Clone</h1>
        <p>Original URL: {processed_data['url']}</p>
        <p>Colors found: {len(processed_data['color_palette'])}</p>
        <p>Fonts found: {len(processed_data['typography'].get('fonts', []))}</p>
        <!-- LLM-generated content will go here -->
    </body>
    </html>
    """
    

#  # returns status of job_id
# @app.get("/api/clone/{job_id}/status", response_model=CloneJob)
# async def get_clone_status(job_id: str):
#     if job_id not in jobs_db:
#         raise HTTPException(status_code=404, detail="Job not found")
    
#     return jobs_db[job_id]

# result
@app.get("api/clone/{job_id}/result")
async def get_clone_result(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    
    if job.status != CloneStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed. Current status: {job.status}")
    
    if not job.result_data:
        raise HTTPException(status_code=500, detail="No result data available")
    
    return{
        "job_id": job_id,
        "original_url": job.result_data["original_url"],
        "generated_html": job.result_data["generated_html"],
        "metadata": job.result_data["scraping_metadata"]
    }

# delete job
@app.delete("/api/clone/{job_id}")
async def delete_clone_job(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    del jobs_db[job_id]
    return {"message": f"Job {job_id} deleted successfully"}
        

# health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "website-cloner-api",
        "active_jobs": len([job for job in jobs_db.values() if job.status not in [CloneStatus.COMPLETED, CloneStatus.FAILED]])
    }

# websocket
@app.websocket("/ws/clone/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)

    try:
        while True:
            # We don't actually need the client to send any payload—
            # we only want to keep the socket open so the server can push.
            # However, if the client ever sends a ping or text, we can ignore it:
            await websocket.receive_text()
    except Exception:
        # if client disconnects, or any error, clean up:
        pass
    finally:
        manager.disconnect(job_id)
       
# root
@app.get("/")
async def root():
    return {
        "message": "Website Cloner API", 
        "status": "running",
        "endpoints": {
            "start_clone": "POST /api/clone",
            "check_status": "GET /api/clone/{job_id}/status", 
            "get_result": "GET /api/clone/{job_id}/result"
        }
    }

# RUN APPLICATION
def main():
    uvicorn.run(
        "hello:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
