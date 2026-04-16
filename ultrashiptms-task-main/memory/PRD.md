# Logistics Document AI - PRD

## Problem Statement
Build a POC AI system that allows users to upload logistics documents (PDF, DOCX, TXT) and interact with them using natural language questions. The system retrieves relevant content via RAG, answers grounded questions, applies guardrails, returns confidence scores, and extracts structured shipment data.

## Architecture
- **Frontend**: React + Tailwind CSS (Swiss brutalist 3-panel dashboard)
- **Backend**: FastAPI + MongoDB
- **LLM**: Gemini 2.5 Flash via Emergent LLM key (emergentintegrations)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2) - open source, no API key
- **Vector DB**: FAISS (in-memory + disk persistence)

## Chunking Strategy
Sentence-level chunking with 500-char chunk size and overlap. Text split by sentence boundaries then grouped.

## Retrieval Method
FAISS L2 similarity search. Top-3 chunks retrieved. Exponential decay distance-to-similarity conversion.

## Guardrails
- Confidence threshold (0.2) - refuses to answer below threshold
- Uncertainty phrase detection in LLM output
- "Not found in document" forced when context is missing

## Confidence Scoring
Based on: avg retrieval similarity, uncertainty phrase penalty, answer length heuristic.

## What's Been Implemented (Feb 2026)
- [x] Document upload & processing (PDF/DOCX/TXT)
- [x] Text extraction, chunking, embedding, FAISS indexing
- [x] RAG-based Q&A with confidence scores
- [x] Hallucination guardrails
- [x] Structured extraction (11 shipment fields as JSON)
- [x] 3-panel UI (Upload/Extract, Chat, Source Viewer)
- [x] API endpoints: /api/upload, /api/ask, /api/extract

## Backlog
- P1: Improve confidence scoring (currently returns lower scores for correct answers)
- P1: Add PDF upload testing via UI (tested with TXT)
- P2: Multi-document support
- P2: Chat history persistence in MongoDB
- P3: Document preview in source viewer panel

## Next Tasks
- Improve chunking strategy with semantic boundaries
- Add retry logic for transient LLM budget errors
- Enhance source text highlighting in right panel
