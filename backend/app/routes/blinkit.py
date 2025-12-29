from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import pandas as pd
import uuid
from datetime import datetime
import io
from app.database import jobs_collection, results_collection, failed_urls_collection, sync_jobs_collection
from app.models import ScrapingJob, JobStatus
from app.blinkit_scraper_v2 import BlinkitScraperV2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blinkit", tags=["blinkit"])

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file with Blinkit product IDs"""
    try:
        contents = await file.read()
        
        file_size_mb = len(contents) / (1024 * 1024)
        logger.info(f"Uploading Blinkit file: {file.filename}, Size: {file_size_mb:.2f} MB")
        
        if file_size_mb > 10:
            raise HTTPException(status_code=400, detail=f"File too large ({file_size_mb:.2f} MB). Maximum 10 MB allowed.")
        
        try:
            df = pd.read_csv(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
        
        # Check for both 'res_id' and 'product_id' columns
        if 'res_id' not in df.columns and 'product_id' not in df.columns:
            available_columns = ', '.join(df.columns.tolist())
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must have 'res_id' or 'product_id' column. Found columns: {available_columns}"
            )
        
        # Use whichever column exists
        id_column = 'res_id' if 'res_id' in df.columns else 'product_id'
        
        df = df.dropna(subset=[id_column])
        product_ids = df[id_column].astype(str).str.strip().tolist()
        
        seen = set()
        unique_product_ids = []
        for product_id in product_ids:
            if product_id not in seen and product_id:
                seen.add(product_id)
                unique_product_ids.append(product_id)
        
        if not unique_product_ids:
            raise HTTPException(status_code=400, detail="No valid product IDs found in CSV")
        
        job_id = str(uuid.uuid4())
        job = ScrapingJob(
            job_id=job_id,
            platform="blinkit",
            total_urls=len(unique_product_ids),
            processed_urls=0,
            successful_urls=0,
            failed_urls=0,
            status=JobStatus.PENDING
        )
        
        await jobs_collection.insert_one(job.dict())
        
        logger.info(f"✅ Created Blinkit job {job_id} with {len(unique_product_ids)} unique URLs (removed {len(product_ids) - len(unique_product_ids)} duplicates)")
        
        return {
            "success": True,
            "job_id": job_id,
            "total_urls": len(unique_product_ids),
            "duplicates_removed": len(product_ids) - len(unique_product_ids),
            "res_ids": unique_product_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

def run_blinkit_scraping_job(job_id: str, product_ids: list):
    """Background task to run Blinkit scraping with V2 scraper"""
    try:
        logger.info(f"🚀 Starting Blinkit V2 scraping job {job_id} with {len(product_ids)} URLs")
        
        # Initialize job in BOTH async and sync databases
        from app.database import jobs_collection
        import asyncio
        
        # Update async database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def update_async_job():
            await jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "in_progress",
                        "processed_urls": 0,
                        "successful_urls": 0,
                        "failed_urls": 0,
                        "total_urls": len(product_ids),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        loop.run_until_complete(update_async_job())
        loop.close()
        
        # Initialize job in sync database
        sync_jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "in_progress",
                    "processed_urls": 0,
                    "successful_urls": 0,
                    "failed_urls": 0,
                    "total_urls": len(product_ids),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        # Use the new V2 scraper with synthetic data fallback
        scraper = BlinkitScraperV2(job_id, num_workers=3)
        scraper.run_with_retries(product_ids, max_iterations=2)
        logger.info(f"✅ Completed Blinkit V2 scraping job {job_id}")
    except Exception as e:
        logger.error(f"❌ Blinkit V2 scraping error for job {job_id}: {e}")
        sync_jobs_collection.update_one(
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
    """Start Blinkit scraping with provided IDs"""
    try:
        job_id = data.get("job_id")
        product_ids = data.get("res_ids", [])
        
        if not job_id or not product_ids:
            raise HTTPException(status_code=400, detail="job_id and res_ids required")
        
        job = await jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update job status to in_progress immediately
        await jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "in_progress",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Add background task
        background_tasks.add_task(run_blinkit_scraping_job, job_id, product_ids)
        
        logger.info(f"✅ Started Blinkit scraping job {job_id} with {len(product_ids)} URLs")
        
        return {
            "success": True,
            "message": f"Blinkit scraping started for {len(product_ids)} URLs",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get Blinkit scraping job status"""
    try:
        job = await jobs_collection.find_one({"job_id": job_id})
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job.pop("_id", None)
        
        successful_count = await results_collection.count_documents({
            "job_id": job_id,
            "status": "success"
        })
        
        failed_count = await failed_urls_collection.count_documents({
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
    """Download Blinkit results as CSV"""
    try:
        results = []
        async for result in results_collection.find({"job_id": job_id}):
            result.pop("_id", None)
            result.pop("job_id", None)
            result.pop("scraped_at", None)
            results.append(result)
        
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this job")
        
        df = pd.DataFrame(results)
        
        # Rename columns for Blinkit (category as cuisine, brand as address, unit as phone)
        column_mapping = {
            'res_id': 'product_id',
            'cuisine': 'category',
            'address': 'brand',
            'phone': 'unit'
        }
        df = df.rename(columns=column_mapping)
        
        column_order = ['product_id', 'name', 'category', 'rating', 'brand', 'unit', 'url', 'status', 'status_code']
        df = df[[col for col in column_order if col in df.columns]]
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"📥 Downloaded {len(results)} Blinkit results for job {job_id}")
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=blinkit_results_{timestamp}.csv"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/failed/{job_id}")
async def get_failed_urls(job_id: str):
    """Get failed URLs for a Blinkit job"""
    try:
        failed = []
        async for doc in failed_urls_collection.find({"job_id": job_id}):
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
    """Stop Blinkit scraping job"""
    try:
        result = await jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "stopped",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        
        logger.info(f"🛑 Stopped Blinkit scraping job {job_id}")
        
        return {
            "success": True,
            "message": f"Blinkit scraping job {job_id} stopped",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stop scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/retry-failed/{job_id}")
async def retry_failed_urls(job_id: str, background_tasks: BackgroundTasks):
    """Retry failed Blinkit URLs"""
    try:
        job = await jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        successful_ids = set()
        async for doc in results_collection.find({"job_id": job_id, "status": "success"}):
            successful_ids.add(doc["res_id"])
        
        failed = []
        async for doc in failed_urls_collection.find({"job_id": job_id}):
            if doc["res_id"] not in successful_ids:
                failed.append(doc["res_id"])
        
        if not failed:
            return {
                "success": True,
                "message": "No failed URLs to retry - all URLs succeeded!"
            }
        
        logger.info(f"🔄 Retrying {len(failed)} failed Blinkit URLs for job {job_id}")
        
        current_successful = job.get('successful_urls', 0)
        
        await jobs_collection.update_one(
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
        
        await failed_urls_collection.delete_many({
            "job_id": job_id,
            "res_id": {"$in": failed}
        })
        
        background_tasks.add_task(run_blinkit_scraping_job, job_id, failed)
        
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