from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import io
import json

from document_processor import DocumentProcessor
from qa_service import QAService
from extraction_service import ExtractionService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize services
document_processor = DocumentProcessor()
qa_service = QAService()
extraction_service = ExtractionService()

# Define Models
class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunk_count: int
    message: str

class QuestionRequest(BaseModel):
    question: str
    document_id: str

class QuestionResponse(BaseModel):
    answer: str
    confidence_score: float
    source_chunks: List[str]
    metadata: Dict[str, Any]

class ExtractRequest(BaseModel):
    document_id: str

class ExtractionResponse(BaseModel):
    document_id: str
    extracted_data: Dict[str, Any]
    confidence_score: float

# Add your routes to the router
@api_router.get("/")
async def root():
    return {"message": "Logistics Document AI System"}

@api_router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a logistics document (PDF, DOCX, TXT)
    """
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".docx", ".txt"]
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        content = await file.read()
        
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Process document: parse, chunk, embed, store
        chunk_count = await document_processor.process_document(
            document_id=document_id,
            filename=file.filename,
            content=content,
            file_type=file_ext
        )
        
        # Store metadata in MongoDB
        doc_metadata = {
            "document_id": document_id,
            "filename": file.filename,
            "file_type": file_ext,
            "upload_time": datetime.now(timezone.utc).isoformat(),
            "chunk_count": chunk_count,
            "status": "ready"
        }
        
        await db.documents.insert_one(doc_metadata)
        
        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="ready",
            chunk_count=chunk_count,
            message="Document processed successfully"
        )
        
    except Exception as e:
        logging.error(f"Error processing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Ask a question about an uploaded document
    """
    try:
        # Check if document exists
        doc = await db.documents.find_one({"document_id": request.document_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get answer using RAG
        result = await qa_service.answer_question(
            document_id=request.document_id,
            question=request.question
        )
        
        return QuestionResponse(
            answer=result["answer"],
            confidence_score=result["confidence_score"],
            source_chunks=result["source_chunks"],
            metadata=result["metadata"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error answering question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/extract", response_model=ExtractionResponse)
async def extract_structured_data(request: ExtractRequest):
    """
    Extract structured shipment data from document
    """
    try:
        # Check if document exists
        doc = await db.documents.find_one({"document_id": request.document_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Extract structured data
        result = await extraction_service.extract_shipment_data(
            document_id=request.document_id
        )
        
        return ExtractionResponse(
            document_id=request.document_id,
            extracted_data=result["extracted_data"],
            confidence_score=result["confidence_score"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error extracting data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()