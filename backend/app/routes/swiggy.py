from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import pandas as pd
import uuid
from datetime import datetime
import io
from app.database import swiggy_jobs_collection, swiggy_results_collection, swiggy_failed_urls_collection, sync_swiggy_jobs_collection
from app.models import ScrapingJob, JobStatus
from app.swiggy_scraper import SwiggyScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/swiggy", tags=["swiggy"])

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file with Swiggy restaurant IDs"""
    try:
        contents = await file.read()
        
        file_size_mb = len(contents) / (1024 * 1024)
        logger.info(f"Uploading Swiggy file: {file.filename}, Size: {file_size_mb:.2f} MB")
        
        if file_size_mb > 10:
            raise HTTPException(status_code=400, detail=f"File too large ({file_size_mb:.2f} MB). Maximum 10 MB allowed.")
        
        try:
            df = pd.read_csv(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
        
        if 'res_id' not in df.columns:
            available_columns = ', '.join(df.columns.tolist())
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must have 'res_id' column. Found columns: {available_columns}"
            )
        
        df = df.dropna(subset=['res_id'])
        res_ids = df['res_id'].astype(str).str.strip().tolist()
        
        seen = set()
        unique_res_ids = []
        for res_id in res_ids:
            if res_id not in seen and res_id:
                seen.add(res_id)
                unique_res_ids.append(res_id)
        
        if not unique_res_ids:
            raise HTTPException(status_code=400, detail="No valid restaurant IDs found in CSV")
        
        job_id = str(uuid.uuid4())
        job = ScrapingJob(
            job_id=job_id,
            platform="swiggy",
            total_urls=len(unique_res_ids),
            processed_urls=0,
            successful_urls=0,
            failed_urls=0,
            status=JobStatus.PENDING
        )
        
        await swiggy_jobs_collection.insert_one(job.dict())
        
        logger.info(f"✅ Created Swiggy job {job_id} with {len(unique_res_ids)} unique URLs (removed {len(res_ids) - len(unique_res_ids)} duplicates)")
        
        return {
            "success": True,
            "job_id": job_id,
            "total_urls": len(unique_res_ids),
            "duplicates_removed": len(res_ids) - len(unique_res_ids),
            "res_ids": unique_res_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

def run_swiggy_scraping_job(job_id: str, res_ids: list):
    """Background task to run Swiggy scraping"""
    try:
        logger.info(f"🚀 Starting Swiggy scraping job {job_id} with {len(res_ids)} URLs")
        scraper = SwiggyScraper(job_id, num_workers=3)
        scraper.run_with_retries(res_ids, max_iterations=3)
        logger.info(f"✅ Completed Swiggy scraping job {job_id}")
    except Exception as e:
        logger.error(f"❌ Swiggy scraping error for job {job_id}: {e}")
        sync_swiggy_jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "updated_at": datetime.utcnow()
                }
            }
        )

@router.post("/start-scraping-with-ids")
async def start_scraping_with_ids(data: dict, background_tasks: BackgroundTasks):
    """Start Swiggy scraping with provided IDs"""
    try:
        job_id = data.get("job_id")
        res_ids = data.get("res_ids", [])
        
        if not job_id or not res_ids:
            raise HTTPException(status_code=400, detail="job_id and res_ids required")
        
        job = await swiggy_jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        background_tasks.add_task(run_swiggy_scraping_job, job_id, res_ids)
        
        logger.info(f"✅ Started Swiggy scraping job {job_id} with {len(res_ids)} URLs")
        
        return {
            "success": True,
            "message": f"Swiggy scraping started for {len(res_ids)} URLs",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get Swiggy scraping job status"""
    try:
        job = await swiggy_jobs_collection.find_one({"job_id": job_id})
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job.pop("_id", None)
        
        successful_count = await swiggy_results_collection.count_documents({
            "job_id": job_id
        })
        
        failed_count = await swiggy_failed_urls_collection.count_documents({
            "job_id": job_id
        })
        
        job['successful_urls'] = successful_count
        job['failed_urls'] = failed_count
        
        return {
            "success": True,
            "job": job
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{job_id}")
async def download_results(job_id: str):
    """Download Swiggy results as CSV"""
    try:
        results = []
        async for result in swiggy_results_collection.find({"job_id": job_id}):
            result.pop("_id", None)
            result.pop("job_id", None)
            result.pop("scraped_at", None)
            results.append(result)
        
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this job")
        
        df = pd.DataFrame(results)
        
        column_order = ['res_id', 'name', 'url', 'address', 'cost']
        df = df[[col for col in column_order if col in df.columns]]
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"📥 Downloaded {len(results)} Swiggy results for job {job_id}")
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=swiggy_results_{timestamp}.csv"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/failed/{job_id}")
async def get_failed_urls(job_id: str):
    """Get failed URLs for a Swiggy job"""
    try:
        failed = []
        async for doc in swiggy_failed_urls_collection.find({"job_id": job_id}):
            doc.pop("_id", None)
            failed.append(doc)
        
        return {
            "success": True,
            "failed_count": len(failed),
            "failed_urls": failed
        }
        
    except Exception as e:
        logger.error(f"Failed URLs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/{job_id}")
async def stop_scraping(job_id: str):
    """Stop a running Swiggy scraping job"""
    try:
        # Update job status to stopped
        result = await swiggy_jobs_collection.update_one(
            {"job_id": job_id, "status": "in_progress"},
            {
                "$set": {
                    "status": "stopped",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Job not found or not in progress")
        
        logger.info(f"🛑 Stopped Swiggy scraping job {job_id}")
        
        return {
            "success": True,
            "message": "Swiggy scraping job stopped successfully",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stop scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/retry-failed/{job_id}")
async def retry_failed_urls(job_id: str, background_tasks: BackgroundTasks):
    """Retry failed Swiggy URLs"""
    try:
        job = await swiggy_jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        successful_ids = set()
        async for doc in swiggy_results_collection.find({"job_id": job_id}):
            successful_ids.add(doc["res_id"])
        
        failed = []
        async for doc in swiggy_failed_urls_collection.find({"job_id": job_id}):
            if doc["res_id"] not in successful_ids:
                failed.append(doc["res_id"])
        
        if not failed:
            return {
                "success": True,
                "message": "No failed URLs to retry - all URLs succeeded!"
            }
        
        logger.info(f"🔄 Retrying {len(failed)} failed Swiggy URLs for job {job_id}")
        
        current_successful = job.get('successful_urls', 0)
        
        await swiggy_jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "processed_urls": current_successful,
                    "failed_urls": len(failed),
                    "status": "in_progress",
                    "current_iteration": 1,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        await swiggy_failed_urls_collection.delete_many({
            "job_id": job_id,
            "res_id": {"$in": failed}
        })
        
        background_tasks.add_task(run_swiggy_scraping_job, job_id, failed)
        
        return {
            "success": True,
            "message": f"Retrying {len(failed)} failed URLs",
            "job_id": job_id,
            "failed_count": len(failed)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry error: {e}")
        raise HTTPException(status_code=500, detail=str(e))