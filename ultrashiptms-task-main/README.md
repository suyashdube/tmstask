# Logistics Document AI - RAG-based Q&A System

A POC AI system that allows users to upload logistics documents (PDF, DOCX, TXT) and interact with them using natural language questions. Built to simulate an AI assistant inside a Transportation Management System (TMS).

## Live Demo

**Hosted UI:** https://cargo-insight-5.preview.emergentagent.com

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │  Upload   │  │   Chat Q&A   │  │  Source Viewer   │  │
│   │  & JSON   │  │  Interface   │  │    Panel         │  │
│   │  Extract  │  │              │  │                  │  │
│   └──────────┘  └──────────────┘  └──────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (REST API)
┌───────────────────────▼─────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │  Document   │  │  QA Service │  │  Extraction       │  │
│  │  Processor  │  │  (RAG)     │  │  Service          │  │
│  └──────┬─────┘  └─────┬──────┘  └────────┬──────────┘  │
│         │              │                   │             │
│  ┌──────▼─────┐  ┌─────▼──────┐  ┌────────▼──────────┐  │
│  │ Pure Python │  │  Gemini    │  │  Gemini 2.5       │  │
│  │ TF-IDF     │  │  2.5 Flash │  │  Flash            │  │
│  │ Vectorizer │  │  (via LLM) │  │  (via LLM)        │  │
│  └────────────┘  └────────────┘  └───────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
                ┌───────▼───────┐
                │   MongoDB     │
                │  (metadata)   │
                └───────────────┘
```

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React + Tailwind CSS | 3-panel dashboard UI |
| Backend | FastAPI (Python) | REST API server |
| LLM | Gemini 2.5 Flash | Q&A generation & structured extraction |
| Embeddings | Pure Python TF-IDF | Document vectorization (no ML deps) |
| Vector Search | Cosine similarity | Chunk retrieval |
| Database | MongoDB | Document metadata storage |
| File Storage | Disk (pickle) | Chunked document + vector index persistence |

---

## Chunking Strategy

- **Method:** Sentence-boundary chunking with a 500-character target per chunk
- **How it works:** Text is split on sentence boundaries (`. `), then sentences are grouped into chunks that stay under the character limit
- **Rationale:** Preserves semantic coherence of sentences while keeping chunks manageable for retrieval. Logistics documents have structured sections (shipper info, rates, dates) that naturally align with sentence boundaries.

---

## Retrieval Method

- **Algorithm:** TF-IDF (Term Frequency-Inverse Document Frequency) with cosine similarity
- **Implementation:** Pure Python — no scikit-learn, numpy, or heavy ML libraries needed
- **Process:**
  1. Document chunks are tokenized (lowercase, stop words removed)
  2. TF-IDF vectors are built per chunk using document frequency statistics
  3. At query time, the query is vectorized with the same IDF weights
  4. Cosine similarity is computed between query vector and all chunk vectors
  5. Top-k (default 3) most similar chunks are returned as context for the LLM

---

## Guardrails Approach

The system implements multiple guardrails to prevent hallucination:

1. **Retrieval similarity threshold:** If the top retrieved chunk has zero similarity to the query, the system flags it as "not found"
2. **Confidence threshold (0.15):** If the computed confidence score falls below 15%, the system refuses to answer and returns: *"I cannot confidently answer this question based on the provided document."*
3. **Uncertainty phrase detection:** If the LLM response contains phrases like "not found", "not mentioned", "cannot determine", the confidence is penalized by 60%
4. **Context-only instruction:** The LLM prompt explicitly instructs: *"Answer ONLY using information from the context above. If the answer is not in the context, say 'Not found in document'"*

---

## Confidence Scoring Method

Confidence is calculated as a composite score:

```
base_confidence = (top_similarity * 0.7) + (avg_similarity * 0.3)
scaled = min(1.0, base_confidence * 2.5)   # Scale TF-IDF range to 0-1

# Penalties applied:
if answer contains uncertainty phrases:  confidence *= 0.4
elif answer is very short (<20 chars):   confidence *= 0.6
else:                                    confidence = scaled
```

| Score Range | Label | Meaning |
|-------------|-------|---------|
| 70-100% | HIGH (green) | Strong retrieval match, confident answer |
| 40-69% | MEDIUM (yellow) | Partial match, answer likely correct |
| 0-39% | LOW (red) | Weak match, answer may be unreliable |

---

## Failure Cases & Limitations

1. **TF-IDF limitations:** Keyword-based matching misses semantic similarity (e.g., "cost" vs "rate" may not match well)
2. **Short documents:** With only 1-2 chunks, retrieval is less discriminating
3. **Scanned PDFs:** PyPDF2 cannot OCR image-based PDFs — only text-based PDFs are supported
4. **Complex tables:** Tabular data in PDFs may not extract cleanly
5. **Multi-document queries:** System processes one document at a time; cross-document questions are not supported
6. **LLM rate limits:** Gemini API may return 503 errors during high demand

---

## Improvement Ideas

1. **Dense embeddings:** Replace TF-IDF with OpenAI `text-embedding-3-small` or Cohere embeddings for semantic understanding
2. **Hybrid retrieval:** Combine TF-IDF keyword search with dense embeddings (BM25 + vector)
3. **OCR support:** Add Tesseract or cloud OCR for scanned PDF documents
4. **Multi-document support:** Allow uploading multiple documents and querying across them
5. **Chat history:** Persist conversation in MongoDB for multi-turn follow-up questions
6. **Chunk overlap:** Add overlapping windows between chunks to avoid losing context at boundaries
7. **Re-ranking:** Add a cross-encoder re-ranker after initial retrieval to improve precision
8. **Batch extraction:** Process multiple BOLs and export a consolidated CSV/Excel

---

## API Endpoints

### `POST /api/upload`
Upload and process a logistics document.

**Request:** `multipart/form-data` with `file` field (PDF, DOCX, or TXT)

**Response:**
```json
{
  "document_id": "uuid-string",
  "filename": "bill_of_lading.pdf",
  "status": "ready",
  "chunk_count": 5,
  "message": "Document processed successfully"
}
```

### `POST /api/ask`
Ask a question about an uploaded document.

**Request:**
```json
{
  "question": "What is the carrier rate?",
  "document_id": "uuid-string"
}
```

**Response:**
```json
{
  "answer": "The total rate is $2,450.00",
  "confidence_score": 0.45,
  "source_chunks": ["...relevant text excerpts..."],
  "metadata": {
    "retrieval_count": 3,
    "top_similarity": 0.28
  }
}
```

### `POST /api/extract`
Extract structured shipment data as JSON.

**Request:**
```json
{
  "document_id": "uuid-string"
}
```

**Response:**
```json
{
  "document_id": "uuid-string",
  "extracted_data": {
    "shipment_id": "BOL-2024-5678",
    "shipper": "ABC Manufacturing Inc.",
    "consignee": "XYZ Distribution Center",
    "pickup_datetime": "January 16, 2024 at 08:00 AM",
    "delivery_datetime": "January 19, 2024 at 02:00 PM",
    "equipment_type": "53' Dry Van",
    "mode": "Truckload (TL)",
    "rate": 2450.00,
    "currency": "USD",
    "weight": "18,500 lbs",
    "carrier_name": "National Freight Lines"
  },
  "confidence_score": 1.0
}
```

---

## Running Locally

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **Yarn**
- **MongoDB** running locally on `mongodb://localhost:27017`

### 1. Clone the repository

```bash
git clone <repository-url>
cd <project-folder>
```

### 2. Set up the backend

```bash
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Edit .env file and set your keys:
#   MONGO_URL="mongodb://localhost:27017"
#   DB_NAME="logistics_ai"
#   CORS_ORIGINS="*"
#   EMERGENT_LLM_KEY="your-emergent-key-here"
#
# To get an Emergent LLM key:
#   Sign up at https://emergent.sh, go to Profile -> Universal Key
#
# Alternatively, replace emergentintegrations LLM calls in
# qa_service.py and extraction_service.py with direct google-generativeai calls
# using your own Gemini API key from https://aistudio.google.com/app/apikey

# Start the backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Set up the frontend

```bash
cd frontend

# Install dependencies
yarn install

# Configure environment variables
# Edit .env file:
#   REACT_APP_BACKEND_URL=http://localhost:8001

# Start the frontend
yarn start
```

### 4. Open the app

Navigate to **http://localhost:3000** in your browser.

### 5. Test with sample document

Create a sample Bill of Lading as `sample_bol.txt`:

```
BILL OF LADING

Shipment ID: BOL-2024-5678
Date: January 15, 2024

SHIPPER:
ABC Manufacturing Inc.
1234 Industrial Parkway
Chicago, IL 60601

CONSIGNEE:
XYZ Distribution Center
5678 Warehouse Drive
Los Angeles, CA 90001

CARRIER INFORMATION:
Carrier Name: National Freight Lines

SHIPMENT DETAILS:
Pickup Date/Time: January 16, 2024 at 08:00 AM
Delivery Date/Time: January 19, 2024 at 02:00 PM
Equipment Type: 53' Dry Van
Mode: Truckload (TL)

RATE INFORMATION:
Total Rate: $2,450.00
Currency: USD
Weight: 18,500 lbs
```

Upload it via the UI, then try asking:
- "What is the total rate?"
- "When is pickup scheduled?"
- "Who is the consignee?"

### 6. Test via cURL

```bash
# Upload
curl -X POST http://localhost:8001/api/upload -F "file=@sample_bol.txt"

# Ask (replace DOC_ID with the document_id from upload response)
curl -X POST http://localhost:8001/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the carrier rate?", "document_id": "DOC_ID"}'

# Extract
curl -X POST http://localhost:8001/api/extract \
  -H "Content-Type: application/json" \
  -d '{"document_id": "DOC_ID"}'
```

---

## Project Structure

```
/app
├── backend/
│   ├── server.py                 # FastAPI app with /api/upload, /api/ask, /api/extract
│   ├── document_processor.py     # Text extraction, chunking, TF-IDF vectorization
│   ├── qa_service.py             # RAG Q&A with guardrails & confidence scoring
│   ├── extraction_service.py     # Structured JSON extraction via LLM
│   ├── requirements.txt          # Python dependencies
│   ├── .env                      # Backend environment variables
│   └── document_storage/         # Persisted document chunks (pickle files)
│
├── frontend/
│   ├── src/
│   │   ├── App.js                # Main 3-panel dashboard component
│   │   ├── App.css               # Component styles
│   │   ├── index.css             # Global styles + Tailwind + fonts
│   │   └── components/ui/        # Shadcn UI components
│   ├── .env                      # Frontend environment variables
│   ├── package.json              # Node dependencies
│   └── tailwind.config.js        # Tailwind configuration
│
└── README.md                     # This file
```

---

## Environment Variables

### Backend (`/backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URL` | Yes | MongoDB connection string |
| `DB_NAME` | Yes | MongoDB database name |
| `CORS_ORIGINS` | Yes | Allowed CORS origins (use `*` for dev) |
| `EMERGENT_LLM_KEY` | Yes | Emergent universal LLM key for Gemini access |

### Frontend (`/frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `REACT_APP_BACKEND_URL` | Yes | Backend API URL (e.g., `http://localhost:8001`) |

---

## Tech Stack

- **Frontend:** React 18, Tailwind CSS, Phosphor Icons, Shadcn UI
- **Backend:** FastAPI, Motor (async MongoDB), PyPDF2, python-docx
- **LLM:** Gemini 2.5 Flash via Emergent Integrations
- **Embeddings:** Pure Python TF-IDF (zero ML dependencies)
- **Database:** MongoDB
- **Design:** Swiss Brutalist / High-Contrast archetype (Outfit + IBM Plex fonts)
