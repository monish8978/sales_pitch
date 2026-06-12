from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from celery.result import AsyncResult
from app.tasks.celery_app import celery_app
from app.tasks.pitch_tasks import generate_pitch_task
from app.utils.rate_limiter import rate_limit_ip
from app.utils.logger import get_logger

logger = get_logger("routes_pitch")
router = APIRouter(prefix="/api")

class PitchRequest(BaseModel):
    email: str = Field(..., description="Prospect email address")
    phone: Optional[str] = Field(None, description="Prospect phone number")
    apollo_api_key: Optional[str] = Field(None, description="Optional Apollo API Key override")
    groq_api_key: Optional[str] = Field(None, description="Optional Groq API Key override")
    use_mock: bool = Field(False, description="Force use mock data & models")

import asyncio
import json
from app.utils.rate_limiter import rate_limit_ip, redis_client

@router.post("/generate-pitch", dependencies=[Depends(rate_limit_ip(limit=5, window=60))])
async def trigger_pitch_generation(req: PitchRequest):
    """
    Endpoint to generate pitch. It delegates the workload to Celery workers,
    waits for the result asynchronously without blocking the main event loop,
    and returns the direct response.
    Rate limited to 5 requests per minute per IP.
    """
    email_clean = req.email.strip().lower()
    logger.info(f"Received pitch generation request for email: {email_clean}")
    
    # 1. Check Redis Cache first for instant hit
    cache_key = f"pitch:cache:{email_clean}"
    if redis_client is not None:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for email: {email_clean}. Returning instant result.")
                result = json.loads(cached_data)
                # Tag timing as cache hit
                result["timing"]["apollo_source"] = "cache"
                result["timing"]["llm_source"] = "cache"
                result["timing"]["total_time"] = "0.00s (Cache Hit)"
                return result
        except Exception as e:
            logger.error(f"Failed to read from Redis cache: {e}")

    try:
        # Trigger the Celery task in the background
        task = generate_pitch_task.delay(
            email=req.email,
            phone=req.phone,
            apollo_api_key=req.apollo_api_key,
            groq_api_key=req.groq_api_key,
            use_mock=req.use_mock
        )
        logger.info(f"Cache MISS. Queued Celery task with ID: {task.id}. Waiting for result...")
        
        # Wait for the Celery worker to complete the task without blocking FastAPI's event loop
        result = await asyncio.to_thread(task.get, timeout=180)
        logger.info(f"Task {task.id} completed successfully.")

        # 2. Save result to Redis Cache for future requests
        if redis_client is not None and result:
            try:
                redis_client.setex(cache_key, 86400, json.dumps(result)) # Cache for 24 hours
                logger.info(f"Saved pitch result to Redis cache for email: {email_clean}")
            except Exception as e:
                logger.error(f"Failed to write to Redis cache: {e}")

        return result
    except Exception as e:
        logger.error(f"Failed to generate pitch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate pitch: {str(e)}"
        )

@router.post("/generate-pitch-async", dependencies=[Depends(rate_limit_ip(limit=5, window=60))])
async def trigger_pitch_generation_async(req: PitchRequest):
    """
    Endpoint to trigger pitch generation asynchronously.
    It returns the Celery task_id immediately.
    """
    email_clean = req.email.strip().lower()
    try:
        task_id = "ef5cf8b9-8bde-4ea2-8abf-e885835e6d88"
        
        # Clear/forget previous task result from Redis backend to reset status and clear old data
        try:
            AsyncResult(task_id, app=celery_app).forget()
            logger.info(f"Cleared previous result for task ID: {task_id}")
        except Exception as ex:
            logger.warning(f"Could not clear previous task result: {ex}")

        task = generate_pitch_task.apply_async(
            kwargs={
                "email": req.email,
                "phone": req.phone,
                "apollo_api_key": req.apollo_api_key,
                "groq_api_key": req.groq_api_key,
                "use_mock": req.use_mock
            },
            task_id=task_id
        )
        logger.info(f"Queued Celery task with fixed ID: {task.id}")
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "Task queued successfully. Use GET /api/tasks/{task_id} to poll the status and result."
        }
    except Exception as e:
        logger.error(f"Failed to queue pitch task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue pitch task: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Endpoint to check the status of a pitch generation background task.
    """
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": task_result.status
        }
        
        if task_result.status == "SUCCESS":
            response["result"] = task_result.result
        elif task_result.status == "FAILURE":
            # Safely capture error details
            error_info = task_result.result or task_result.info
            response["error"] = str(error_info) if error_info else "Task execution failed."
            logger.error(f"Task {task_id} failed with error: {error_info}")
            
        return response
    except Exception as e:
        logger.error(f"Failed to fetch task status for {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check task status: {str(e)}"
        )
