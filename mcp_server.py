import os
import sys
import json
import asyncio
from typing import Optional

# Ensure project root is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from app.tasks.pitch_tasks import generate_pitch_task
from app.config import settings

# 1. Initialize FastMCP Server
mcp = FastMCP("SalesCopilot")

def format_response(result: dict, is_cache: bool) -> str:
    if not result:
        return "Failed to generate pitch. Empty result received from pipeline."
    
    prospect = result.get("prospect", {})
    analysis = result.get("analysis", {})
    timing = result.get("timing", {})
    
    insights_list = analysis.get("insights", [])
    insights_str = "\n".join([f"- {i}" for i in insights_list]) if insights_list else "- No insights generated."
    
    source = "Cache Hit" if is_cache else f"Live (Apollo: {timing.get('apollo_time', 'N/A')}, LLM: {timing.get('llm_time', 'N/A')})"
    
    return f"""### 👤 Prospect Profile
- **Name:** {prospect.get('name', 'N/A')}
- **Title:** {prospect.get('title', 'N/A')}
- **Company:** {prospect.get('company', {}).get('name', 'N/A')} ({prospect.get('company', {}).get('employee_count', 'N/A')} employees)
- **Location:** {prospect.get('location', 'N/A')}
- **LinkedIn:** {prospect.get('linkedin_url', 'N/A')}

### 💡 B2B Personalization Insights
{insights_str}

### ✍️ Generated Sales Pitch
{analysis.get('pitch', 'N/A')}

---
*Source: {source} | Total Execution Time: {timing.get('total_time', 'N/A')}*"""

# 2. Expose Generate Pitch Tool
@mcp.tool()
async def generate_pitch(email: str, phone: Optional[str] = None) -> str:
    """
    Perform real-time prospect enrichment and generate a high-converting, personalized B2B sales pitch.
    
    Args:
        email: The target prospect's corporate email address (Required).
        phone: The target prospect's phone number (Optional).
    """
    email_clean = email.strip().lower()
    cache_key = f"pitch:cache:{email_clean}"
    
    # 2.1. Check Redis Cache First
    try:
        from app.utils.rate_limiter import redis_client
        if redis_client is not None:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                return format_response(result, is_cache=True)
    except Exception:
        pass  # Failsafe if Redis is unavailable

    # 2.2. Trigger Asynchronous Celery Task
    try:
        task = generate_pitch_task.delay(
            email=email_clean,
            phone=phone,
            use_mock=False
        )
        
        # Wait for Celery worker (non-blocking wait)
        result = await asyncio.to_thread(task.get, timeout=120)
        
        # 2.3. Save Success Result to Redis Cache
        try:
            from app.utils.rate_limiter import redis_client
            if redis_client is not None and result:
                redis_client.setex(cache_key, 86400, json.dumps(result)) # 24 Hours TTL
        except Exception:
            pass
            
        return format_response(result, is_cache=False)
    except Exception as e:
        return f"Error executing sales pitch generation pipeline: {str(e)}"

# 3. Expose Seller Profile Tool
@mcp.tool()
def get_seller_profile() -> str:
    """
    Fetch the currently configured seller's company name, services offered, and core value propositions.
    """
    return f"""### 🏢 Active Seller Profile
- **Company:** {settings.seller_company}
- **Services Offered:** {settings.seller_services}
- **Value Propositions:** {settings.seller_value_props}"""

if __name__ == "__main__":
    # Runs the server using standard input/output (stdio) transport protocol by default
    mcp.run()
