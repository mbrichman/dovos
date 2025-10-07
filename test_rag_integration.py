#!/usr/bin/env python3
"""
Test script for RAG service integration
"""

import requests
import json

def test_rag_service():
    """Test the RAG service endpoints"""
    base_url = "http://localhost:8000"
    
    # Test health endpoint
    print("Testing RAG service health...")
    try:
        response = requests.get(f"{base_url}/rag/health")
        print(f"Health check: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Health check failed: {e}")
        return
    
    # Test query endpoint
    print("\nTesting RAG query endpoint...")
    query_data = {
        "query": "machine learning",
        "n_results": 3,
        "search_type": "semantic"
    }
    
    try:
        response = requests.post(f"{base_url}/rag/query", json=query_data)
        print(f"Query response: {response.status_code}")
        if response.status_code == 200:
            results = response.json()
            print(f"Found {len(results.get('results', []))} results")
            for i, result in enumerate(results.get('results', [])[:2]):
                print(f"  {i+1}. {result.get('title', 'Untitled')} (Relevance: {result.get('relevance', 0):.2f})")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Query test failed: {e}")
    
    # Test hybrid search
    print("\nTesting hybrid search...")
    hybrid_data = {
        "query": "artificial intelligence",
        "n_results": 3,
        "semantic_weight": 0.7
    }
    
    try:
        response = requests.post(f"{base_url}/rag/search", json=hybrid_data)
        print(f"Hybrid search response: {response.status_code}")
        if response.status_code == 200:
            results = response.json()
            print(f"Found {len(results.get('results', []))} results")
            for i, result in enumerate(results.get('results', [])[:2]):
                print(f"  {i+1}. {result.get('title', 'Untitled')} (Combined Score: {result.get('combined_score', 0):.2f})")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Hybrid search test failed: {e}")

def test_main_app_rag():
    """Test the RAG endpoint in the main app"""
    base_url = "http://localhost:5001"
    
    print("\nTesting main app RAG endpoint...")
    query_data = {
        "query": "chatbot development",
        "n_results": 2,
        "search_type": "semantic"
    }
    
    try:
        response = requests.post(f"{base_url}/api/rag/query", json=query_data)
        print(f"Main app RAG response: {response.status_code}")
        if response.status_code == 200:
            results = response.json()
            print(f"Found {len(results.get('results', []))} results")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Main app RAG test failed: {e}")

if __name__ == "__main__":
    test_rag_service()
    test_main_app_rag()
