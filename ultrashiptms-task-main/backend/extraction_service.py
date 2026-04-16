import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from typing import Dict, Any
import json
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage
from document_processor import DocumentProcessor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

class ExtractionService:
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.warning("EMERGENT_LLM_KEY not found in environment")
    
    async def extract_shipment_data(self, document_id: str) -> Dict[str, Any]:
        try:
            full_text = self.document_processor.get_full_text(document_id)
            
            prompt = f"""Extract the following shipment information from the logistics document below. 
Return ONLY a valid JSON object with these exact fields (use null for missing values):

{{
  "shipment_id": "string or null",
  "shipper": "string or null",
  "consignee": "string or null",
  "pickup_datetime": "string or null",
  "delivery_datetime": "string or null",
  "equipment_type": "string or null",
  "mode": "string or null",
  "rate": "number or null",
  "currency": "string or null",
  "weight": "string or null",
  "carrier_name": "string or null"
}}

Document text:
{full_text}

Extract the data and return ONLY the JSON object, no other text:"""
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=str(uuid.uuid4()),
                system_message="You are a data extraction assistant. Extract structured data from logistics documents and return valid JSON only."
            ).with_model("gemini", "gemini-2.5-flash")
            
            user_message = UserMessage(text=prompt)
            raw = await chat.send_message(user_message)
            
            try:
                cleaned = raw.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                
                extracted_data = json.loads(cleaned)
                
                total_fields = 11
                filled_fields = sum(1 for v in extracted_data.values() if v is not None)
                confidence = filled_fields / total_fields
                
                return {
                    "extracted_data": extracted_data,
                    "confidence_score": round(confidence, 2)
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}\nResponse: {raw}")
                return {
                    "extracted_data": {
                        "shipment_id": None, "shipper": None, "consignee": None,
                        "pickup_datetime": None, "delivery_datetime": None,
                        "equipment_type": None, "mode": None, "rate": None,
                        "currency": None, "weight": None, "carrier_name": None
                    },
                    "confidence_score": 0.0
                }
            
        except Exception as e:
            logger.error(f"Error in extraction service: {str(e)}")
            raise
