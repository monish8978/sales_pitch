import os
import time
import httpx
import json
from typing import Dict, Any, Optional
from groq import Groq
from app.tasks.celery_app import celery_app
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger("pitch_tasks")

# Reusable global HTTP client to leverage TCP/TLS connection pooling (Keep-Alive)
http_client = httpx.Client(timeout=15.0)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def generate_pitch_task(self, email: str, phone: str, apollo_api_key: Optional[str] = None, groq_api_key: Optional[str] = None, use_mock: bool = False) -> Dict[str, Any]:
    """
    Celery task that performs the live Apollo lookup and Groq pitch generation.
    It reads seller company profiles and value propositions dynamically from settings.
    """
    logger.info(f"Starting live pitch generation task for {email}")
    start_total = time.perf_counter()

    # 1. APOLLO LOOKUP STEP
    start_apollo = time.perf_counter()
    apollo_key = apollo_api_key or settings.apollo_api_key

    if not apollo_key:
        raise ValueError("APOLLO_API_KEY is not set.")

    try:
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_key
        }
        payload = {
            "email": email,
            "phone": phone,
            "reveal_personal_emails": settings.reveal_personal_emails,
            "reveal_phone_number": settings.reveal_phone_number
        }
        
        response = http_client.post(settings.apollo_match_url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Apollo API Error {response.status_code}: {response.text}")
            
        data = response.json()
        person = data.get("person", {})
        if not person:
            raise Exception("Apollo API matched but no person was found.")
            
        company_info = person.get("organization", {})
        prospect_data = {
            "name": person.get("name", "Unknown Prospect"),
            "title": person.get("title", "Executive"),
            "company": {
                "name": company_info.get("name", "Unknown Company"),
                "industry": company_info.get("industry", "Technology"),
                "employee_count": company_info.get("estimated_num_employees", 100)
            },
            "linkedin_url": person.get("linkedin_url", ""),
            "location": f"{person.get('city', '')}, {person.get('state', '')}, {person.get('country', '')}".strip(", "),
            "seniority": person.get("seniority", "Senior"),
            "photo_url": person.get("photo_url", "")
        }
    except Exception as e:
        logger.error(f"Apollo Lookup failed: {e}")
        raise e

    apollo_time = time.perf_counter() - start_apollo

    # 2. LLM GENERATION STEP
    start_llm = time.perf_counter()
    groq_key = groq_api_key or settings.groq_api_key
    
    if not groq_key:
        raise ValueError("GROQ_API_KEY is not set.")

    try:
        client = Groq(api_key=groq_key)
        
        seller_brief = f"""
- Company Name: {settings.seller_company}
- Services Offered: {settings.seller_services}
- Value Propositions & Differentiators: {settings.seller_value_props}
"""
        
        prompt = f"""
You are an elite B2B Sales Development Representative (SDR) specializing in highly personalized outbound outreach. 
Your goal is to write a high-converting prospect analysis and outreach pitch using the provided prospect intelligence and seller capabilities.

=== PROSPECT INTELLIGENCE (APOLLO.IO) ===
Name: {prospect_data['name']}
Title: {prospect_data['title']}
Seniority: {prospect_data['seniority']}
Location: {prospect_data['location']}
Company Name: {prospect_data['company']['name']}
Company Industry: {prospect_data['company']['industry']}
Estimated Employees: {prospect_data['company']['employee_count']}

=== SELLER BRIEF (YOUR COMPANY) ===
{seller_brief}

=== OUTCOMES REQUIRED ===
1. **summary**: A highly strategic, 2-sentence breakdown of the prospect's responsibilities, their company's core focus, and their likely primary business challenge.
2. **insights**: Exactly 3 high-impact, single-line bullets (MAXIMUM 8 words each) mapping the prospect's situation to a seller benefit. Use the format: "Category: Benefit".
3. **pitch**: A highly conversational, professional 60-second outreach script starting with a contextual hook, presenting the value, referencing credibility metrics, and ending with a low-friction interest-based CTA.

=== STRICT RESPONSE RULES ===
- Each item in the "insights" list MUST be a single line under 8 words.
- DO NOT write explanations, paragraphs, or long sentences in "insights".

=== EXAMPLE OF TARGET OUTPUT STRUCTURE ===
{{
  "summary": "Mohammad is the Director of Tech at C-Zentrix, an IT firm with 180 employees. He is likely managing local hiring limitations and engineering delivery timelines.",
  "insights": [
    "Cost Savings: Save 60% compared to local hiring.",
    "Rapid Onboarding: Deploy offshore teams in 1-2 weeks.",
    "Proven Quality: ISO-certified developers with 20+ years track record."
  ],
  "pitch": "Hi Mohammad, I noticed you are leading technology at C-Zentrix. Scaling software delivery without blowing up overhead is a tough balance..."
}}

Return your response strictly as a JSON object matching the example structure above.
"""
        chat_completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a professional B2B sales assistant. You write short, high-converting copy. You respond only with a strictly formatted JSON object matching the few-shot structure. Each item in the 'insights' array MUST be a single, short, one-line bullet point under 8 words (e.g. 'Cost Savings: Save 60% compared to local hiring')."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=800
        )
        
        content = chat_completion.choices[0].message.content
        llm_output = json.loads(content)
    except Exception as e:
        logger.error(f"Groq LLM generation failed: {e}")
        # Retry task if possible, else raise
        self.retry(exc=e)

    llm_time = time.perf_counter() - start_llm
    total_time = time.perf_counter() - start_total

    result = {
        "prospect": prospect_data,
        "analysis": llm_output,
        "timing": {
            "apollo_time": f"{apollo_time:.2f}s",
            "llm_time": f"{llm_time:.2f}s",
            "total_time": f"{total_time:.2f}s",
            "apollo_source": "live",
            "llm_source": "live"
        }
    }
    logger.info(f"Task completed successfully for {email}")
    return result
