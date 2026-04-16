"""
Logistics AI Document Q&A System - Backend API Tests
Tests: Document upload, Q&A with RAG, Structured extraction, Guardrails
"""
import pytest
import requests
import os
import time
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndRoot:
    """Basic health and root endpoint tests"""
    
    def test_root_endpoint(self):
        """Test root API endpoint returns correct message"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Logistics Document AI System"


class TestDocumentUpload:
    """Document upload functionality tests"""
    
    def test_upload_txt_document(self):
        """Test uploading a TXT document"""
        sample_file = Path("/tmp/sample_bol.txt")
        if not sample_file.exists():
            pytest.skip("Sample document not found at /tmp/sample_bol.txt")
        
        with open(sample_file, 'rb') as f:
            files = {'file': ('sample_bol.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "document_id" in data
        assert "filename" in data
        assert "status" in data
        assert "chunk_count" in data
        assert "message" in data
        
        # Validate values
        assert data["filename"] == "sample_bol.txt"
        assert data["status"] == "ready"
        assert data["chunk_count"] >= 1
        assert isinstance(data["document_id"], str)
        assert len(data["document_id"]) > 0
    
    def test_upload_invalid_file_type(self):
        """Test upload with invalid file type returns error"""
        fake_content = b"This is not a valid document"
        files = {'file': ('malware.exe', fake_content, 'application/octet-stream')}
        
        response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
        # Should return 400 or 500 with error message about unsupported file type
        assert response.status_code in [400, 500]
        data = response.json()
        assert "detail" in data
        assert "Unsupported file type" in data["detail"]


class TestQAFunctionality:
    """Q&A functionality tests with RAG"""
    
    @pytest.fixture(scope="class")
    def uploaded_document(self):
        """Upload document and return document_id for Q&A tests"""
        sample_file = Path("/tmp/sample_bol.txt")
        if not sample_file.exists():
            pytest.skip("Sample document not found")
        
        with open(sample_file, 'rb') as f:
            files = {'file': ('sample_bol.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
        if response.status_code != 200:
            pytest.skip("Document upload failed")
        
        return response.json()["document_id"]
    
    def test_qa_shipment_id(self, uploaded_document):
        """Test Q&A for shipment ID - high confidence expected"""
        response = requests.post(f"{BASE_URL}/api/ask", json={
            "question": "What is the shipment ID?",
            "document_id": uploaded_document
        })
        
        # Handle transient budget errors with retry
        if response.status_code == 500 and "Budget has been exceeded" in response.text:
            time.sleep(2)
            response = requests.post(f"{BASE_URL}/api/ask", json={
                "question": "What is the shipment ID?",
                "document_id": uploaded_document
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "answer" in data
        assert "confidence_score" in data
        assert "source_chunks" in data
        assert "metadata" in data
        
        # Validate answer contains expected value
        assert "BOL-2024-5678" in data["answer"]
        assert isinstance(data["confidence_score"], float)
        assert 0 <= data["confidence_score"] <= 1
        assert len(data["source_chunks"]) > 0
    
    def test_qa_shipper_info(self, uploaded_document):
        """Test Q&A for shipper information"""
        response = requests.post(f"{BASE_URL}/api/ask", json={
            "question": "Who is the shipper?",
            "document_id": uploaded_document
        })
        
        # Handle transient budget errors with retry
        if response.status_code == 500 and "Budget has been exceeded" in response.text:
            time.sleep(2)
            response = requests.post(f"{BASE_URL}/api/ask", json={
                "question": "Who is the shipper?",
                "document_id": uploaded_document
            })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "ABC Manufacturing" in data["answer"]
        assert len(data["source_chunks"]) > 0
    
    def test_qa_invalid_document_id(self):
        """Test Q&A with invalid document ID returns 404"""
        response = requests.post(f"{BASE_URL}/api/ask", json={
            "question": "What is the shipment ID?",
            "document_id": "invalid-doc-id-12345"
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


class TestGuardrails:
    """Guardrail tests - refuse low-confidence answers"""
    
    @pytest.fixture(scope="class")
    def uploaded_document(self):
        """Upload document for guardrail tests"""
        sample_file = Path("/tmp/sample_bol.txt")
        if not sample_file.exists():
            pytest.skip("Sample document not found")
        
        with open(sample_file, 'rb') as f:
            files = {'file': ('sample_bol.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
        if response.status_code != 200:
            pytest.skip("Document upload failed")
        
        return response.json()["document_id"]
    
    def test_guardrail_unrelated_question(self, uploaded_document):
        """Test guardrail triggers for unrelated questions"""
        response = requests.post(f"{BASE_URL}/api/ask", json={
            "question": "What is the weather forecast for delivery?",
            "document_id": uploaded_document
        })
        
        # Handle transient budget errors with retry
        if response.status_code == 500 and "Budget has been exceeded" in response.text:
            time.sleep(2)
            response = requests.post(f"{BASE_URL}/api/ask", json={
                "question": "What is the weather forecast for delivery?",
                "document_id": uploaded_document
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Low confidence expected
        assert data["confidence_score"] < 0.3
        # Guardrail message expected
        assert "cannot confidently answer" in data["answer"].lower()
    
    def test_guardrail_completely_unrelated(self, uploaded_document):
        """Test guardrail for completely unrelated questions"""
        response = requests.post(f"{BASE_URL}/api/ask", json={
            "question": "How many nuclear reactors are being shipped?",
            "document_id": uploaded_document
        })
        
        # Handle transient budget errors with retry
        if response.status_code == 500 and "Budget has been exceeded" in response.text:
            time.sleep(2)
            response = requests.post(f"{BASE_URL}/api/ask", json={
                "question": "How many nuclear reactors are being shipped?",
                "document_id": uploaded_document
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Very low confidence expected
        assert data["confidence_score"] < 0.3
        # Guardrail should trigger
        assert "cannot confidently answer" in data["answer"].lower()


class TestStructuredExtraction:
    """Structured data extraction tests"""
    
    @pytest.fixture(scope="class")
    def uploaded_document(self):
        """Upload document for extraction tests"""
        sample_file = Path("/tmp/sample_bol.txt")
        if not sample_file.exists():
            pytest.skip("Sample document not found")
        
        with open(sample_file, 'rb') as f:
            files = {'file': ('sample_bol.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
        if response.status_code != 200:
            pytest.skip("Document upload failed")
        
        return response.json()["document_id"]
    
    def test_extract_shipment_data(self, uploaded_document):
        """Test structured extraction returns all expected fields"""
        response = requests.post(f"{BASE_URL}/api/extract", json={
            "document_id": uploaded_document
        })
        
        # Handle transient budget errors with retry
        if response.status_code == 500 and "Budget has been exceeded" in response.text:
            time.sleep(2)
            response = requests.post(f"{BASE_URL}/api/extract", json={
                "document_id": uploaded_document
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "document_id" in data
        assert "extracted_data" in data
        assert "confidence_score" in data
        
        extracted = data["extracted_data"]
        
        # Validate expected fields exist
        expected_fields = [
            'shipment_id', 'shipper', 'consignee', 'pickup_datetime',
            'delivery_datetime', 'equipment_type', 'mode', 'rate',
            'currency', 'weight', 'carrier_name'
        ]
        
        for field in expected_fields:
            assert field in extracted, f"Missing field: {field}"
        
        # Validate specific values
        assert extracted["shipment_id"] == "BOL-2024-5678"
        assert "ABC Manufacturing" in extracted["shipper"]
        assert "XYZ Distribution" in extracted["consignee"]
        assert extracted["currency"] == "USD"
        assert "National Freight" in extracted["carrier_name"]
        
        # Rate should be numeric
        assert extracted["rate"] is not None
        if isinstance(extracted["rate"], (int, float)):
            assert extracted["rate"] == 2450 or extracted["rate"] == 2450.0
    
    def test_extract_invalid_document_id(self):
        """Test extraction with invalid document ID returns 404"""
        response = requests.post(f"{BASE_URL}/api/extract", json={
            "document_id": "invalid-doc-id-12345"
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
