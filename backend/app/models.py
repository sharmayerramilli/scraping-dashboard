from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapingJob(BaseModel):
    job_id: str
    platform: str = "zomato"
    total_urls: int
    processed_urls: int = 0
    successful_urls: int = 0
    failed_urls: int = 0
    status: JobStatus = JobStatus.PENDING
    current_iteration: int = 1
    max_iterations: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ScrapingResult(BaseModel):
    job_id: str
    res_id: str
    name: Optional[str] = None
    url: str
    address: Optional[str] = None
    cost: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

class FailedURL(BaseModel):
    job_id: str
    res_id: str
    url: str
    status_code: Optional[int] = None
    error_message: str
    retry_count: int = 0
    last_attempt: datetime = Field(default_factory=datetime.utcnow)  