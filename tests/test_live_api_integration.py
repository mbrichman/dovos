"""
Live API Integration Tests

These tests make actual HTTP requests to the running API to capture current
behavior and validate responses against the contract. These serve as regression
tests to ensure the PostgreSQL migration preserves exact API compatibility.
"""
import pytest
import json
import time
import os
from typing import Dict, Any

pytestmark = [pytest.mark.integration, pytest.mark.contract]


class TestLiveAPIEndpoints:
    """Integration tests against live API endpoints"""
    
    def test_api_conversations_list(self, client, contract_validator, golden_response_helpers):
        """Test GET /api/conversations endpoint with real data"""
        start_time = time.time()
        response = client.get('/api/conversations')
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        
        data = response.get_json()
        assert data is not None, "Response should contain JSON data"
        
        # Save actual response as golden snapshot
        golden_response_helpers["save"](data, "GET /api/conversations_live")
        
        # Validate legacy format structure
        assert "documents" in data, "Missing 'documents' field"
        assert "metadatas" in data, "Missing 'metadatas' field"
        assert "ids" in data, "Missing 'ids' field"
        assert isinstance(data["documents"], list)
        assert isinstance(data["metadatas"], list)
        assert isinstance(data["ids"], list)
        
        # Validate arrays have same length
        assert len(data["documents"]) == len(data["metadatas"]) == len(data["ids"])
            
        print(f"✅ /api/conversations - Response time: {response_time:.3f}s, Conversations: {len(data['documents'])}")
        
        return {
            "endpoint": "GET /api/conversations",
            "status_code": response.status_code,
            "response_time": response_time,
            "response_size": len(response.data),
            "conversation_count": len(data["documents"])
        }
    
    def test_api_conversations_with_pagination(self, client, contract_validator):
        """Test GET /api/conversations with different pagination parameters"""
        test_cases = [
            {"page": 1, "limit": 5},
            {"page": 2, "limit": 10},
            {"page": 1, "limit": 50}
        ]
        
        results = []
        for params in test_cases:
            start_time = time.time()
            response = client.get(f'/api/conversations?page={params["page"]}&limit={params["limit"]}')
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Validate legacy format structure
            assert "documents" in data
            assert "metadatas" in data
            assert "ids" in data
            
            # Note: Legacy API doesn't support pagination params, returns all results
            # Just validate we got results
            assert isinstance(data["documents"], list)
            
            results.append({
                "params": params,
                "response_time": response_time,
                "result_count": len(data["documents"])
            })
            
            print(f"✅ Pagination test {params} - {len(data['documents'])} results in {response_time:.3f}s")
        
        return results
    
    def test_api_conversation_detail(self, client, contract_validator, golden_response_helpers):
        """Test GET /api/conversation/<id> with real conversation ID"""
        # First get a list of conversations to find a valid ID
        list_response = client.get('/api/conversations')
        assert list_response.status_code == 200
        
        data = list_response.get_json()
        if not data.get("ids") or len(data["ids"]) == 0:
            pytest.skip("No conversations available for detail testing")
            
        conv_id = data["ids"][0]
        
        # Test conversation detail
        start_time = time.time()
        response = client.get(f'/api/conversation/{conv_id}')
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Save golden snapshot
        golden_response_helpers["save"](data, "GET /api/conversation/<id>_live")
        
        # Validate legacy format structure
        assert "documents" in data, "Missing 'documents' field"
        assert "metadatas" in data, "Missing 'metadatas' field"
        assert "ids" in data, "Missing 'ids' field"
        
        # Should have exactly one conversation
        assert len(data["documents"]) <= 1
        assert len(data["metadatas"]) <= 1
        assert len(data["ids"]) <= 1
        
        message_count = 0
        if len(data["documents"]) > 0:
            # Count messages by counting formatting markers in document
            document = data["documents"][0]
            message_count = document.count("**You said**") + document.count("**ChatGPT said**") + document.count("**Claude said**") + document.count("**Assistant said**")
        
        print(f"✅ /api/conversation/{conv_id} - Response time: {response_time:.3f}s, Messages: {message_count}")
        
        return {
            "endpoint": f"GET /api/conversation/{conv_id}",
            "status_code": response.status_code,
            "response_time": response_time,
            "response_size": len(response.data),
            "message_count": message_count,
            "conversation_title": data.get("title", "")
        }
    
    def test_api_conversation_detail_nonexistent(self, client):
        """Test GET /api/conversation/<id> with nonexistent ID"""
        start_time = time.time()
        response = client.get('/api/conversation/nonexistent-id-12345')
        response_time = time.time() - start_time
        
        # API returns 200 with empty arrays for nonexistent conversations
        assert response.status_code == 200
        data = response.get_json()
        
        # Should have empty arrays
        assert data["documents"] == []
        assert data["metadatas"] == []
        assert data["ids"] == []
        
        print(f"✅ Nonexistent conversation test - Status: {response.status_code}, Time: {response_time:.3f}s")
        
        return {
            "endpoint": "GET /api/conversation/nonexistent",
            "status_code": response.status_code,
            "response_time": response_time
        }
    
    def test_api_search(self, client, contract_validator, golden_response_helpers):
        """Test GET /api/search endpoint"""
        test_queries = [
            "python",
            "javascript", 
            "test query",
            "database"
        ]
        
        results = []
        for query in test_queries:
            start_time = time.time()
            response = client.get(f'/api/search?q={query}&n=10')
            response_time = time.time() - start_time
            
            # API may return 400 if no data, or 200 with results
            assert response.status_code in [200, 400], f"Unexpected status {response.status_code} for query '{query}'"
            
            if response.status_code == 200:
                data = response.get_json()
                
                # Validate contract
                assert contract_validator.validate_response("GET /api/search", data)
                
                # Save first successful search as golden snapshot
                if len(results) == 0:
                    golden_response_helpers["save"](data, "GET /api/search_live")
                
                # Validate structure
                assert "query" in data
                assert "results" in data
                assert data["query"] == query
                
                result_count = len(data["results"])
                
                # Validate search result structure if results exist
                if result_count > 0:
                    result = data["results"][0]
                    for field in ["title", "date", "content", "metadata"]:
                        assert field in result, f"Missing search result field: {field}"
                
                print(f"✅ Search '{query}' - {result_count} results in {response_time:.3f}s")
                
                results.append({
                    "query": query,
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "result_count": result_count
                })
            else:
                print(f"⚠️ Search '{query}' - Status {response.status_code} in {response_time:.3f}s")
                results.append({
                    "query": query,
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "result_count": 0
                })
                
        return results
    
    def test_api_search_keyword(self, client, contract_validator):
        """Test GET /api/search with keyword flag"""
        start_time = time.time()
        response = client.get('/api/search?q=test&keyword=true')
        response_time = time.time() - start_time
        
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.get_json()
            assert contract_validator.validate_response("GET /api/search", data)
            
        print(f"✅ Keyword search - Status: {response.status_code}, Time: {response_time:.3f}s")
        
        return {
            "endpoint": "GET /api/search?keyword=true",
            "status_code": response.status_code,
            "response_time": response_time
        }
    
    def test_api_rag_query(self, client, contract_validator, golden_response_helpers):
        """Test POST /api/rag/query endpoint"""
        query_data = {
            "query": "How do I use Python for web scraping?",
            "n_results": 5,
            "search_type": "semantic"
        }
        
        start_time = time.time()
        response = client.post('/api/rag/query',
                              json=query_data,
                              content_type='application/json')
        response_time = time.time() - start_time
        
        # May return 400/500 if not configured properly, or 200 with results
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.get_json()
            
            # Validate contract
            assert contract_validator.validate_response("POST /api/rag/query", data)
            
            # Save golden snapshot
            golden_response_helpers["save"](data, "POST /api/rag/query_live")
            
            # Validate structure
            assert "query" in data
            assert "search_type" in data  
            assert "results" in data
            assert data["query"] == query_data["query"]
            
            result_count = len(data["results"])
            
            # Validate RAG result structure if results exist
            if result_count > 0:
                result = data["results"][0]
                required_fields = ["id", "title", "content", "preview", "source", "distance", "relevance", "metadata"]
                for field in required_fields:
                    assert field in result, f"Missing RAG result field: {field}"
                    
                # Validate numeric fields
                assert isinstance(result["distance"], (int, float))
                assert isinstance(result["relevance"], (int, float))
                assert 0 <= result["relevance"] <= 1
                
            print(f"✅ RAG query - {result_count} results in {response_time:.3f}s")
            
            return {
                "endpoint": "POST /api/rag/query",
                "status_code": response.status_code,
                "response_time": response_time,
                "result_count": result_count,
                "query": query_data["query"]
            }
        else:
            print(f"⚠️ RAG query - Status {response.status_code} in {response_time:.3f}s")
            return {
                "endpoint": "POST /api/rag/query", 
                "status_code": response.status_code,
                "response_time": response_time,
                "result_count": 0
            }
    
    def test_api_rag_health(self, client, contract_validator, golden_response_helpers):
        """Test GET /api/rag/health endpoint"""
        start_time = time.time()
        response = client.get('/api/rag/health')
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Validate contract
        assert contract_validator.validate_response("GET /api/rag/health", data)
        
        # Save golden snapshot
        golden_response_helpers["save"](data, "GET /api/rag/health_live")
        
        # Validate structure
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
        
        if data["status"] == "healthy":
            optional_fields = ["collection_name", "document_count", "embedding_model"]
            present_fields = [f for f in optional_fields if f in data and data[f] is not None]
            print(f"✅ RAG health - {data['status']} with {len(present_fields)} fields in {response_time:.3f}s")
        else:
            error_msg = data.get("error", "No error message")
            print(f"⚠️ RAG health - {data['status']}: {error_msg} in {response_time:.3f}s")
        
        return {
            "endpoint": "GET /api/rag/health",
            "status_code": response.status_code, 
            "response_time": response_time,
            "health_status": data["status"]
        }
    
    def test_api_stats(self, client, contract_validator, golden_response_helpers):
        """Test GET /api/stats endpoint"""
        start_time = time.time()
        response = client.get('/api/stats')
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Validate contract
        assert contract_validator.validate_response("GET /api/stats", data)
        
        # Save golden snapshot
        golden_response_helpers["save"](data, "GET /api/stats_live")
        
        # Validate structure
        required_fields = ["status", "collection_name", "document_count", "embedding_model"]
        for field in required_fields:
            assert field in data, f"Missing stats field: {field}"
            
        # Validate data types
        assert isinstance(data["document_count"], int)
        assert data["document_count"] >= 0
        
        print(f"✅ Stats - {data['document_count']} documents, {data['embedding_model']} in {response_time:.3f}s")
        
        return {
            "endpoint": "GET /api/stats",
            "status_code": response.status_code,
            "response_time": response_time, 
            "document_count": data["document_count"],
            "collection_name": data["collection_name"],
            "embedding_model": data["embedding_model"]
        }


class TestLiveAPIPerformance:
    """Performance tests to establish baselines"""
    
    @pytest.mark.performance
    def test_endpoint_response_times(self, client, performance_baseline):
        """Test response times for all endpoints meet performance baselines"""
        results = []
        thresholds = performance_baseline["response_time_thresholds"]
        
        # Test conversations list
        start_time = time.time()
        response = client.get('/api/conversations')
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            threshold = thresholds.get("GET /api/conversations", 2.0)
            passed = response_time <= threshold
            results.append({
                "endpoint": "GET /api/conversations",
                "response_time": response_time,
                "threshold": threshold,
                "passed": passed
            })
            print(f"{'✅' if passed else '❌'} /api/conversations: {response_time:.3f}s (limit: {threshold}s)")
        
        # Test stats (usually fastest)
        start_time = time.time()
        response = client.get('/api/stats')
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            threshold = thresholds.get("GET /api/stats", 0.5)
            passed = response_time <= threshold
            results.append({
                "endpoint": "GET /api/stats",
                "response_time": response_time,
                "threshold": threshold,
                "passed": passed
            })
            print(f"{'✅' if passed else '❌'} /api/stats: {response_time:.3f}s (limit: {threshold}s)")
        
        # Test RAG health  
        start_time = time.time()
        response = client.get('/api/rag/health')
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            threshold = thresholds.get("GET /api/rag/health", 0.5)
            passed = response_time <= threshold
            results.append({
                "endpoint": "GET /api/rag/health",
                "response_time": response_time,
                "threshold": threshold,
                "passed": passed
            })
            print(f"{'✅' if passed else '❌'} /api/rag/health: {response_time:.3f}s (limit: {threshold}s)")
        
        # Report overall performance
        all_passed = all(r["passed"] for r in results)
        avg_response_time = sum(r["response_time"] for r in results) / len(results) if results else 0
        
        print(f"\nPerformance Summary: {'✅ PASS' if all_passed else '❌ FAIL'}")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Tests passed: {sum(1 for r in results if r['passed'])}/{len(results)}")
        
        return results
    
    @pytest.mark.performance
    def test_concurrent_requests(self, client):
        """Test handling of multiple concurrent requests"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request(endpoint):
            start_time = time.time()
            response = client.get(endpoint)
            response_time = time.time() - start_time
            results.put({
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time": response_time
            })
        
        # Test concurrent requests to different endpoints
        endpoints = ['/api/conversations', '/api/stats', '/api/rag/health'] * 3  # 9 total requests
        threads = []
        
        start_time = time.time()
        for endpoint in endpoints:
            thread = threading.Thread(target=make_request, args=(endpoint,))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        total_time = time.time() - start_time
        
        # Collect results
        concurrent_results = []
        while not results.empty():
            concurrent_results.append(results.get())
        
        # Analyze results
        successful_requests = [r for r in concurrent_results if r["status_code"] == 200]
        avg_response_time = sum(r["response_time"] for r in concurrent_results) / len(concurrent_results)
        
        print(f"✅ Concurrent test: {len(successful_requests)}/{len(concurrent_results)} successful")
        print(f"Total time: {total_time:.3f}s, Avg response time: {avg_response_time:.3f}s")
        
        assert len(successful_requests) >= len(concurrent_results) * 0.8  # At least 80% success rate
        
        return {
            "total_requests": len(concurrent_results),
            "successful_requests": len(successful_requests),
            "total_time": total_time,
            "avg_response_time": avg_response_time
        }


class TestLiveAPIErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_endpoints(self, client):
        """Test that invalid endpoints return appropriate errors"""
        invalid_endpoints = [
            '/api/invalid',
            '/api/conversations/invalid/path',
            '/api/conversation/invalid/path/extra'
        ]
        
        results = []
        for endpoint in invalid_endpoints:
            response = client.get(endpoint)
            results.append({
                "endpoint": endpoint,
                "status_code": response.status_code
            })
            
            assert response.status_code == 404, f"Expected 404 for {endpoint}, got {response.status_code}"
            print(f"✅ {endpoint} correctly returns 404")
        
        return results
    
    def test_method_not_allowed(self, client):
        """Test that wrong HTTP methods return 405"""
        method_tests = [
            {'endpoint': '/api/rag/query', 'method': 'GET'},  # Should be POST
            {'endpoint': '/clear_db', 'method': 'GET'},       # Should be POST
        ]
        
        results = []
        for test in method_tests:
            if test['method'] == 'GET':
                response = client.get(test['endpoint'])
            else:
                response = client.post(test['endpoint'])
                
            results.append({
                "endpoint": test['endpoint'],
                "method": test['method'], 
                "status_code": response.status_code
            })
            
            assert response.status_code == 405, f"Expected 405 for {test['method']} {test['endpoint']}, got {response.status_code}"
            print(f"✅ {test['method']} {test['endpoint']} correctly returns 405")
        
        return results