import time
import redis
from fastapi import Request, HTTPException
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("rate_limiter")

# Initialize Redis client lazily or immediately
try:
    # We parse the redis_url to construct connection
    redis_client = redis.Redis.from_url(settings.redis_url, socket_timeout=2.0)
    # Ping to check connection
    redis_client.ping()
    logger.info("Connected to Redis successfully for Rate Limiting.")
except Exception as e:
    logger.error(f"Failed to connect to Redis for Rate Limiting: {e}. Falling back to default allowance.")
    redis_client = None

# In-memory fallback in case Redis goes down
in_memory_cache = {}

def rate_limit_ip(limit: int = settings.rate_limit_requests, window: int = settings.rate_limit_window_seconds):
    """
    FastAPI dependency for IP rate limiting.
    Uses a Redis ZSET (sliding window) to track request rate.
    """
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        
        # Unique key for tracking
        key = f"rate_limit:{client_ip}:{endpoint}"
        now = time.time()
        
        # If Redis is not available, use simple in-memory fallback
        if redis_client is None:
            try:
                # Basic in-memory sliding window
                if key not in in_memory_cache:
                    in_memory_cache[key] = []
                
                # Filter out expired timestamps
                in_memory_cache[key] = [t for t in in_memory_cache[key] if now - t < window]
                
                if len(in_memory_cache[key]) >= limit:
                    logger.warning(f"Rate limit exceeded (Fallback) for IP: {client_ip} on endpoint: {endpoint}")
                    raise HTTPException(
                        status_code=429, 
                        detail="Too many requests. Please wait before retrying."
                    )
                
                in_memory_cache[key].append(now)
                return
            except HTTPException:
                raise
            except Exception as ex:
                logger.error(f"Error in fallback rate limiter: {ex}")
                return # Fail open if fallback also fails
        
        try:
            # Redis ZSET sliding window implementation
            pipe = redis_client.pipeline()
            # Remove timestamps older than window
            pipe.zremrangebyscore(key, 0, now - window)
            # Count elements in ZSET
            pipe.zcard(key)
            # Add current timestamp
            pipe.zadd(key, {str(now): now})
            # Set key expiration to ensure cleanup
            pipe.expire(key, window + 10)
            
            # Execute pipeline
            _, request_count, _, _ = pipe.execute()
            
            if request_count > limit:
                logger.warning(f"Rate limit exceeded for IP: {client_ip} on endpoint: {endpoint} ({request_count}/{limit})")
                raise HTTPException(
                    status_code=429, 
                    detail="Too many requests. Please wait before retrying."
                )
                
        except HTTPException:
            raise
        except redis.RedisError as re:
            logger.error(f"Redis error during rate limiting check: {re}. Allowing request through.")
            # If Redis connection drops mid-session, do not block users
            return
            
    return dependency
