import io
import os
import math
import PyPDF2
from docx import Document
import logging
from typing import List, Dict
from collections import Counter
import pickle
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Common English stop words
STOP_WORDS = set([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "up", "it",
    "its", "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them", "their",
    "what", "which", "who", "whom"
])


def tokenize(text: str) -> List[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stop words"""
    words = re.findall(r'[a-z0-9]+', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def cosine_sim(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors (dicts)"""
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class DocumentProcessor:
    def __init__(self):
        logger.info("Initializing document processor...")
        self.document_stores = {}
        self.storage_path = Path(os.environ.get('STORAGE_PATH', '/app/backend/document_storage'))
        self.storage_path.mkdir(exist_ok=True)

    def _extract_text(self, content: bytes, file_type: str) -> str:
        try:
            if file_type == ".pdf":
                pdf_file = io.BytesIO(content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
            elif file_type == ".docx":
                docx_file = io.BytesIO(content)
                doc = Document(docx_file)
                text = "\n".join([p.text for p in doc.paragraphs])
                return text.strip()
            elif file_type == ".txt":
                return content.decode('utf-8').strip()
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            raise

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        if current_chunk:
            chunks.append(current_chunk.strip())
        if not chunks:
            chunks = [text]
        return chunks

    def _build_tfidf(self, chunks: List[str]):
        """Build TF-IDF vectors using pure Python"""
        # Tokenize all chunks
        chunk_tokens = [tokenize(c) for c in chunks]

        # Document frequency
        df = Counter()
        for tokens in chunk_tokens:
            unique = set(tokens)
            for t in unique:
                df[t] += 1

        n_docs = len(chunks)
        idf = {}
        for term, freq in df.items():
            idf[term] = math.log((n_docs + 1) / (freq + 1)) + 1

        # TF-IDF vectors per chunk
        vectors = []
        for tokens in chunk_tokens:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec = {}
            for term, count in tf.items():
                vec[term] = (count / total) * idf.get(term, 0)
            vectors.append(vec)

        return vectors, idf

    async def process_document(self, document_id: str, filename: str,
                               content: bytes, file_type: str) -> int:
        try:
            logger.info(f"Processing document {document_id}...")
            text = self._extract_text(content, file_type)
            if not text:
                raise ValueError("No text extracted from document")

            chunks = self._chunk_text(text)
            logger.info(f"Created {len(chunks)} chunks")

            vectors, idf = self._build_tfidf(chunks)

            self.document_stores[document_id] = {
                "chunks": chunks,
                "vectors": vectors,
                "idf": idf,
                "full_text": text,
                "filename": filename
            }
            self._save_to_disk(document_id)
            return len(chunks)
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise

    def _save_to_disk(self, document_id: str):
        try:
            doc_path = self.storage_path / f"{document_id}.pkl"
            with open(doc_path, 'wb') as f:
                pickle.dump(self.document_stores[document_id], f)
        except Exception as e:
            logger.error(f"Error saving to disk: {str(e)}")

    def _load_from_disk(self, document_id: str):
        try:
            doc_path = self.storage_path / f"{document_id}.pkl"
            if doc_path.exists():
                with open(doc_path, 'rb') as f:
                    self.document_stores[document_id] = pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading from disk: {str(e)}")

    def retrieve_relevant_chunks(self, document_id: str, query: str, k: int = 3) -> List[Dict]:
        try:
            if document_id not in self.document_stores:
                self._load_from_disk(document_id)
            if document_id not in self.document_stores:
                raise ValueError(f"Document {document_id} not found")

            store = self.document_stores[document_id]

            # Build query vector using same IDF
            query_tokens = tokenize(query)
            tf = Counter(query_tokens)
            total = len(query_tokens) if query_tokens else 1
            query_vec = {}
            for term, count in tf.items():
                query_vec[term] = (count / total) * store["idf"].get(term, 0)

            # Compute similarities
            scored = []
            for i, chunk_vec in enumerate(store["vectors"]):
                sim = cosine_sim(query_vec, chunk_vec)
                scored.append((i, sim))

            scored.sort(key=lambda x: x[1], reverse=True)
            top_k = scored[:k]

            results = []
            for rank, (idx, sim) in enumerate(top_k):
                results.append({
                    "chunk": store["chunks"][idx],
                    "similarity": sim,
                    "rank": rank + 1
                })
            return results
        except Exception as e:
            logger.error(f"Error retrieving chunks: {str(e)}")
            raise

    def get_full_text(self, document_id: str) -> str:
        if document_id not in self.document_stores:
            self._load_from_disk(document_id)
        if document_id not in self.document_stores:
            raise ValueError(f"Document {document_id} not found")
        return self.document_stores[document_id]["full_text"]
