import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from typing import Dict, List, Any
from emergentintegrations.llm.chat import LlmChat, UserMessage
from document_processor import DocumentProcessor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

class QAService:
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.warning("EMERGENT_LLM_KEY not found in environment")
    
    def _calculate_confidence(self, retrieved_chunks: List[Dict], answer: str) -> float:
        if not retrieved_chunks:
            return 0.0
        
        # For TF-IDF, similarity scores are typically lower than dense embeddings
        # Scale up the top similarity to get meaningful confidence
        top_similarity = max(chunk["similarity"] for chunk in retrieved_chunks)
        avg_similarity = sum(chunk["similarity"] for chunk in retrieved_chunks) / len(retrieved_chunks)
        
        # Weighted blend: emphasize top match
        base_confidence = (top_similarity * 0.7 + avg_similarity * 0.3)
        # Scale TF-IDF scores (typically 0-0.5) into more useful range
        scaled = min(1.0, base_confidence * 2.5)
        
        uncertainty_phrases = ["not found", "unclear", "cannot determine", "not mentioned", "not specified", "no information"]
        has_uncertainty = any(phrase in answer.lower() for phrase in uncertainty_phrases)
        
        if has_uncertainty:
            confidence = scaled * 0.4
        elif len(answer) < 20:
            confidence = scaled * 0.6
        else:
            confidence = scaled
        
        return min(1.0, max(0.0, confidence))
    
    def _apply_guardrails(self, confidence: float, answer: str, threshold: float = 0.15) -> str:
        if confidence < threshold:
            return "I cannot confidently answer this question based on the provided document. The information may not be present or is unclear."
        return answer
    
    async def answer_question(self, document_id: str, question: str) -> Dict[str, Any]:
        try:
            retrieved_chunks = self.document_processor.retrieve_relevant_chunks(
                document_id=document_id,
                query=question,
                k=3
            )
            
            if not retrieved_chunks:
                return {
                    "answer": "No relevant information found in the document.",
                    "confidence_score": 0.0,
                    "source_chunks": [],
                    "metadata": {"retrieval_count": 0}
                }
            
            context = "\n\n".join([
                f"[Source {i+1}]: {chunk['chunk']}" 
                for i, chunk in enumerate(retrieved_chunks)
            ])
            
            prompt = f"""You are an AI assistant analyzing logistics documents. Answer the question based ONLY on the provided context.

Context from document:
{context}

Question: {question}

Instructions:
- Answer ONLY using information from the context above
- If the answer is not in the context, say "Not found in document"
- Be concise and factual
- Do not add information not present in the context

Answer:"""
            
            import uuid
            chat = LlmChat(
                api_key=self.api_key,
                session_id=str(uuid.uuid4()),
                system_message="You are a logistics document analysis assistant. Provide accurate, grounded answers."
            ).with_model("gemini", "gemini-2.5-flash")
            
            user_message = UserMessage(text=prompt)
            answer = await chat.send_message(user_message)
            
            confidence = self._calculate_confidence(retrieved_chunks, answer)
            final_answer = self._apply_guardrails(confidence, answer)
            
            return {
                "answer": final_answer,
                "confidence_score": round(confidence, 2),
                "source_chunks": [chunk["chunk"] for chunk in retrieved_chunks],
                "metadata": {
                    "retrieval_count": len(retrieved_chunks),
                    "top_similarity": round(retrieved_chunks[0]["similarity"], 2) if retrieved_chunks else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error in QA service: {str(e)}")
            raise
