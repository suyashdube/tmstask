import requests
import sys
import json
import time
from pathlib import Path

class LogisticsAITester:
    def __init__(self, base_url="https://cargo-insight-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.document_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        if not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files)
                else:
                    response = requests.post(url, json=data, headers=headers)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_document_upload(self):
        """Test document upload with sample BOL"""
        print("\n📄 Testing Document Upload...")
        
        # Read sample document
        sample_file = Path("/tmp/sample_bol.txt")
        if not sample_file.exists():
            print("❌ Sample document not found at /tmp/sample_bol.txt")
            return False
        
        with open(sample_file, 'rb') as f:
            files = {'file': ('sample_bol.txt', f, 'text/plain')}
            success, response = self.run_test(
                "Upload Sample BOL Document",
                "POST",
                "upload",
                200,
                files=files
            )
        
        if success and 'document_id' in response:
            self.document_id = response['document_id']
            print(f"   Document ID: {self.document_id}")
            print(f"   Chunks: {response.get('chunk_count', 'N/A')}")
            return True
        return False

    def test_invalid_file_upload(self):
        """Test upload with invalid file type"""
        print("\n📄 Testing Invalid File Upload...")
        
        # Create a fake .exe file
        fake_content = b"This is not a valid document"
        files = {'file': ('malware.exe', fake_content, 'application/octet-stream')}
        
        success, response = self.run_test(
            "Upload Invalid File Type",
            "POST",
            "upload",
            400,
            files=files
        )
        return success

    def test_qa_functionality(self):
        """Test Q&A functionality with various questions"""
        if not self.document_id:
            print("❌ No document uploaded, skipping Q&A tests")
            return False
        
        print("\n💬 Testing Q&A Functionality...")
        
        # Test questions with different expected confidence levels
        test_questions = [
            {
                "question": "What is the shipment ID?",
                "description": "High confidence question - direct fact",
                "expected_confidence": "high"
            },
            {
                "question": "Who is the shipper?",
                "description": "High confidence question - clear info",
                "expected_confidence": "high"
            },
            {
                "question": "What is the pickup date and time?",
                "description": "Medium confidence question - specific detail",
                "expected_confidence": "medium"
            },
            {
                "question": "What is the weather forecast for delivery?",
                "description": "Low confidence question - not in document",
                "expected_confidence": "low"
            },
            {
                "question": "How many nuclear reactors are being shipped?",
                "description": "Guardrail test - completely unrelated",
                "expected_confidence": "low"
            }
        ]
        
        qa_results = []
        for test_q in test_questions:
            print(f"\n   Question: {test_q['question']}")
            success, response = self.run_test(
                f"Q&A: {test_q['description']}",
                "POST",
                "ask",
                200,
                data={
                    "question": test_q["question"],
                    "document_id": self.document_id
                }
            )
            
            if success:
                confidence = response.get('confidence_score', 0)
                answer = response.get('answer', '')
                sources = response.get('source_chunks', [])
                
                print(f"   Answer: {answer[:100]}...")
                print(f"   Confidence: {confidence}")
                print(f"   Sources: {len(sources)} chunks")
                
                qa_results.append({
                    "question": test_q["question"],
                    "confidence": confidence,
                    "answer": answer,
                    "sources_count": len(sources)
                })
                
                # Check guardrails for low confidence
                if confidence < 0.3 and "cannot confidently answer" not in answer.lower():
                    print(f"⚠️  Warning: Low confidence ({confidence}) but no guardrail triggered")
            else:
                qa_results.append({"question": test_q["question"], "error": True})
        
        return len(qa_results) > 0

    def test_invalid_qa(self):
        """Test Q&A with invalid document ID"""
        print("\n💬 Testing Q&A with Invalid Document ID...")
        
        success, response = self.run_test(
            "Q&A with Invalid Document ID",
            "POST",
            "ask",
            404,
            data={
                "question": "What is the shipment ID?",
                "document_id": "invalid-doc-id"
            }
        )
        return success

    def test_structured_extraction(self):
        """Test structured data extraction"""
        if not self.document_id:
            print("❌ No document uploaded, skipping extraction test")
            return False
        
        print("\n🔧 Testing Structured Data Extraction...")
        
        success, response = self.run_test(
            "Extract Structured Shipment Data",
            "POST",
            "extract",
            200,
            data={"document_id": self.document_id}
        )
        
        if success:
            extracted_data = response.get('extracted_data', {})
            confidence = response.get('confidence_score', 0)
            
            print(f"   Extraction Confidence: {confidence}")
            print(f"   Extracted Fields: {len(extracted_data)}")
            
            # Check for expected fields
            expected_fields = [
                'shipment_id', 'shipper', 'consignee', 'pickup_datetime',
                'delivery_datetime', 'equipment_type', 'mode', 'rate',
                'currency', 'weight', 'carrier_name'
            ]
            
            found_fields = 0
            for field in expected_fields:
                if field in extracted_data and extracted_data[field] is not None:
                    found_fields += 1
                    print(f"   ✓ {field}: {extracted_data[field]}")
                else:
                    print(f"   ✗ {field}: Not found")
            
            print(f"   Fields Found: {found_fields}/{len(expected_fields)}")
            return True
        
        return False

    def test_invalid_extraction(self):
        """Test extraction with invalid document ID"""
        print("\n🔧 Testing Extraction with Invalid Document ID...")
        
        success, response = self.run_test(
            "Extract with Invalid Document ID",
            "POST",
            "extract",
            404,
            data={"document_id": "invalid-doc-id"}
        )
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Logistics AI Backend Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test sequence
        tests = [
            ("Root Endpoint", self.test_root_endpoint),
            ("Document Upload", self.test_document_upload),
            ("Invalid File Upload", self.test_invalid_file_upload),
            ("Q&A Functionality", self.test_qa_functionality),
            ("Invalid Q&A", self.test_invalid_qa),
            ("Structured Extraction", self.test_structured_extraction),
            ("Invalid Extraction", self.test_invalid_extraction),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    print(f"⚠️  {test_name} had issues")
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = LogisticsAITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())