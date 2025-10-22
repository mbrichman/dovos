#!/usr/bin/env python3
"""
End-to-End Chat Import and Search Integration Test

This test demonstrates the complete pipeline:
1. Import chat conversations with multiple messages
2. Trigger embedding generation (via background workers)
3. Verify all search types work correctly (FTS, semantic, hybrid)
4. Test both direct service calls and API endpoints
5. Validate response formats match expected contracts
"""

import os
import sys
import json
import time
import asyncio
import threading
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

# Set feature flag to use PostgreSQL backend
os.environ['USE_POSTGRES'] = 'true'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database_setup import setup_database
from db.services.message_service import MessageService
from db.services.search_service import SearchService, SearchConfig
from db.workers.embedding_worker import EmbeddingWorker
from db.repositories.unit_of_work import get_unit_of_work
from db.adapters.legacy_api_adapter import get_legacy_adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EndToEndTester:
    """
    End-to-end integration test for chat import and search functionality.
    """
    
    def __init__(self):
        self.message_service = MessageService()
        self.search_service = SearchService()
        self.legacy_adapter = get_legacy_adapter()
        self.embedding_worker = None
        self.worker_thread = None
        self.test_conversations = []
        
    def setup_test_data(self) -> List[str]:
        """Import realistic test chat conversations."""
        logger.info("📥 Setting up test chat conversations...")
        
        # Realistic test conversations with diverse content
        test_chats = [
            {
                "title": "Python Web Scraping with Selenium",
                "messages": [
                    {
                        "role": "user",
                        "content": "I need to scrape a website that loads content dynamically with JavaScript. BeautifulSoup isn't working because it only gets the static HTML. What's the best approach?"
                    },
                    {
                        "role": "assistant", 
                        "content": "You're running into the classic problem of dynamic content loading. Here are the best solutions:\n\n1. **Selenium WebDriver** (most common):\n```python\nfrom selenium import webdriver\nfrom selenium.webdriver.common.by import By\nfrom selenium.webdriver.support.ui import WebDriverWait\nfrom selenium.webdriver.support import expected_conditions as EC\n\ndriver = webdriver.Chrome()\ndriver.get('your-website-url')\n\n# Wait for dynamic content to load\nwait = WebDriverWait(driver, 10)\nelement = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'dynamic-content')))\n\n# Now get the fully rendered HTML\nhtml = driver.page_source\nsoup = BeautifulSoup(html, 'html.parser')\n```\n\n2. **Playwright** (modern alternative):\n```python\nfrom playwright.sync_api import sync_playwright\n\nwith sync_playwright() as p:\n    browser = p.chromium.launch()\n    page = browser.new_page()\n    page.goto('your-website-url')\n    page.wait_for_selector('.dynamic-content')\n    content = page.content()\n```"
                    },
                    {
                        "role": "user",
                        "content": "Thanks! Which one is faster for large-scale scraping?"
                    },
                    {
                        "role": "assistant",
                        "content": "For large-scale scraping, here's the performance comparison:\n\n**Playwright is generally faster** because:\n- Better resource management\n- More efficient browser automation\n- Built-in async support\n- Lighter memory footprint\n\n**However**, consider these alternatives for scale:\n\n1. **Requests + Session reuse** if possible\n2. **httpx** with async for concurrent requests\n3. **Scrapy** with splash for JavaScript rendering\n\nFor 1000+ pages, I'd recommend:\n```python\n# Hybrid approach\nasync def scrape_with_playwright(urls):\n    async with async_playwright() as p:\n        browser = await p.chromium.launch()\n        tasks = [scrape_page(browser, url) for url in urls]\n        results = await asyncio.gather(*tasks)\n    return results\n```"
                    }
                ]
            },
            {
                "title": "PostgreSQL Performance Optimization",
                "messages": [
                    {
                        "role": "user",
                        "content": "My PostgreSQL queries are getting slow as my database grows. The main issue seems to be with my search functionality that needs to query across multiple tables. Any optimization tips?"
                    },
                    {
                        "role": "assistant",
                        "content": "PostgreSQL performance optimization is crucial for growing databases. Here are key strategies:\n\n## Indexing\n```sql\n-- B-tree indexes for exact matches and ranges\nCREATE INDEX idx_users_email ON users(email);\nCREATE INDEX idx_orders_created_at ON orders(created_at);\n\n-- Partial indexes for filtered queries\nCREATE INDEX idx_active_users ON users(id) WHERE status = 'active';\n\n-- Composite indexes for multi-column queries\nCREATE INDEX idx_orders_user_status ON orders(user_id, status);\n```\n\n## Query Optimization\n```sql\n-- Use EXPLAIN ANALYZE to understand query plans\nEXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 123;\n\n-- Avoid SELECT * - be specific\nSELECT id, total, status FROM orders WHERE user_id = 123;\n```\n\n## For search across multiple tables:\n```sql\n-- Use proper JOINs instead of subqueries when possible\nSELECT o.id, o.total, u.email \nFROM orders o\nJOIN users u ON o.user_id = u.id\nWHERE u.status = 'active';\n```\n\nWhat specific types of searches are you running?"
                    },
                    {
                        "role": "user",
                        "content": "I'm doing full-text search across user posts and comments, plus some semantic similarity matching. It's taking 5+ seconds for complex queries."
                    },
                    {
                        "role": "assistant",
                        "content": "5+ seconds is definitely too slow! Here's how to optimize full-text and semantic search:\n\n## PostgreSQL Full-Text Search\n```sql\n-- Create GIN index for full-text search\nCREATE INDEX idx_posts_fts ON posts USING GIN(to_tsvector('english', title || ' ' || content));\nCREATE INDEX idx_comments_fts ON comments USING GIN(to_tsvector('english', content));\n\n-- Optimized FTS query\nSELECT title, ts_rank(to_tsvector('english', title || ' ' || content), query) as rank\nFROM posts, plainto_tsquery('english', 'your search terms') query\nWHERE to_tsvector('english', title || ' ' || content) @@ query\nORDER BY rank DESC;\n```\n\n## Semantic Search with pgvector\n```sql\n-- Install and setup pgvector extension\nCREATE EXTENSION vector;\n\n-- Add vector column and index\nALTER TABLE posts ADD COLUMN embedding vector(384);\nCREATE INDEX ON posts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);\n\n-- Fast similarity search\nSELECT title, 1 - (embedding <=> query_vector) as similarity\nFROM posts\nWHERE 1 - (embedding <=> query_vector) > 0.8\nORDER BY embedding <=> query_vector\nLIMIT 10;\n```\n\n## Hybrid Approach\n```sql\n-- Combine FTS rank and vector similarity\nWITH fts_results AS (\n  SELECT id, ts_rank(fts_vector, query) * 0.4 as fts_score\n  FROM posts\n  WHERE fts_vector @@ query\n),\nvector_results AS (\n  SELECT id, (1 - (embedding <=> $1)) * 0.6 as vector_score\n  FROM posts\n  WHERE 1 - (embedding <=> $1) > 0.2\n)\nSELECT p.title, \n       COALESCE(f.fts_score, 0) + COALESCE(v.vector_score, 0) as combined_score\nFROM posts p\nLEFT JOIN fts_results f ON p.id = f.id\nLEFT JOIN vector_results v ON p.id = v.id\nORDER BY combined_score DESC;\n```\n\nThis should get you under 100ms for most queries!"
                    }
                ]
            },
            {
                "title": "Docker Container Networking",
                "messages": [
                    {
                        "role": "user",
                        "content": "I'm having trouble with Docker containers communicating with each other. My web app container can't connect to my database container. They're both running but the connection fails."
                    },
                    {
                        "role": "assistant",
                        "content": "Docker networking issues are common! Let me help you debug this step by step.\n\n## Check Current Network Setup\n```bash\n# List all networks\ndocker network ls\n\n# Inspect containers and their networks\ndocker inspect <container_name> | grep -i network\n\n# Check if containers are running\ndocker ps\n```\n\n## Solution 1: Docker Compose (Recommended)\n```yaml\n# docker-compose.yml\nversion: '3.8'\nservices:\n  web:\n    build: .\n    ports:\n      - \"3000:3000\"\n    environment:\n      - DATABASE_URL=postgresql://user:pass@db:5432/myapp\n    depends_on:\n      - db\n  \n  db:\n    image: postgres:13\n    environment:\n      - POSTGRES_DB=myapp\n      - POSTGRES_USER=user\n      - POSTGRES_PASSWORD=pass\n    volumes:\n      - postgres_data:/var/lib/postgresql/data\n\nvolumes:\n  postgres_data:\n```\n\n## Solution 2: Custom Network\n```bash\n# Create custom network\ndocker network create myapp-network\n\n# Run containers on the same network\ndocker run -d --name db --network myapp-network postgres:13\ndocker run -d --name web --network myapp-network -p 3000:3000 myapp\n```\n\n## Key Points:\n- Containers communicate using **service names** as hostnames\n- Use `db:5432` instead of `localhost:5432` in your connection string\n- Make sure both containers are on the same network\n\nWhat's your current setup? Are you using docker-compose or running containers individually?"
                    }
                ]
            },
            {
                "title": "Machine Learning Model Deployment",
                "messages": [
                    {
                        "role": "user",
                        "content": "I've trained a machine learning model for text classification and need to deploy it for production use. What's the best way to serve ML models at scale?"
                    },
                    {
                        "role": "assistant",
                        "content": "Great question! ML model deployment has several good options depending on your scale and requirements:\n\n## Option 1: FastAPI + Docker (Simple & Effective)\n```python\nfrom fastapi import FastAPI\nfrom pydantic import BaseModel\nimport joblib\nimport numpy as np\n\napp = FastAPI()\nmodel = joblib.load('model.pkl')\n\nclass PredictionRequest(BaseModel):\n    text: str\n\nclass PredictionResponse(BaseModel):\n    prediction: str\n    confidence: float\n\n@app.post('/predict', response_model=PredictionResponse)\nasync def predict(request: PredictionRequest):\n    # Preprocess text\n    features = preprocess_text(request.text)\n    \n    # Get prediction\n    prediction = model.predict([features])[0]\n    confidence = model.predict_proba([features]).max()\n    \n    return PredictionResponse(\n        prediction=prediction,\n        confidence=float(confidence)\n    )\n```\n\n## Option 2: TensorFlow Serving (For TF Models)\n```bash\n# Export your model\nmodel.save('my_model/1')\n\n# Run TF Serving\ndocker run -p 8501:8501 \\\n  --mount type=bind,source=/path/to/my_model,target=/models/my_model \\\n  -e MODEL_NAME=my_model -t tensorflow/serving\n```\n\n## Option 3: MLflow (Full MLOps)\n```python\nimport mlflow.sklearn\n\n# Log model\nwith mlflow.start_run():\n    mlflow.sklearn.log_model(model, \"text_classifier\")\n    \n# Serve model\n# mlflow models serve -m \"models:/text_classifier/1\" -p 5000\n```\n\n## Scaling Considerations:\n- **Load balancer** for multiple instances\n- **Redis/Memcached** for caching predictions\n- **Async processing** with Celery for batch jobs\n- **Model versioning** and A/B testing\n\nWhat's your expected traffic and model type (sklearn, TensorFlow, PyTorch)?"
                    }
                ]
            },
            {
                "title": "React State Management Best Practices",
                "messages": [
                    {
                        "role": "user",
                        "content": "I'm working on a React app that's getting complex with lots of components sharing state. Currently using useState but it's getting messy with prop drilling. Should I use Context, Redux, or something else?"
                    },
                    {
                        "role": "assistant",
                        "content": "State management complexity is a common React challenge! Here's a decision tree:\n\n## When to Use What:\n\n### **useState + Props** (Current)\n✅ Simple apps, 2-3 levels deep\n❌ Prop drilling, multiple components need same state\n\n### **React Context** (Good Middle Ground)\n```jsx\n// UserContext.js\nconst UserContext = createContext();\n\nexport const UserProvider = ({ children }) => {\n  const [user, setUser] = useState(null);\n  const [loading, setLoading] = useState(false);\n  \n  const login = async (credentials) => {\n    setLoading(true);\n    // login logic\n    setUser(userData);\n    setLoading(false);\n  };\n  \n  return (\n    <UserContext.Provider value={{ user, loading, login }}>\n      {children}\n    </UserContext.Provider>\n  );\n};\n\n// In components\nconst { user, login } = useContext(UserContext);\n```\n\n### **Zustand** (Modern, Simple)\n```jsx\nimport { create } from 'zustand'\n\nconst useStore = create((set) => ({\n  user: null,\n  loading: false,\n  login: async (credentials) => {\n    set({ loading: true });\n    const user = await api.login(credentials);\n    set({ user, loading: false });\n  },\n}))\n\n// In components\nconst { user, login } = useStore();\n```\n\n### **Redux Toolkit** (Complex Apps)\n```jsx\n// userSlice.js\nimport { createSlice, createAsyncThunk } from '@reduxjs/toolkit'\n\nexport const loginUser = createAsyncThunk(\n  'user/login',\n  async (credentials) => {\n    const response = await api.login(credentials)\n    return response.data\n  }\n)\n\nconst userSlice = createSlice({\n  name: 'user',\n  initialState: { user: null, loading: false },\n  reducers: {},\n  extraReducers: (builder) => {\n    builder\n      .addCase(loginUser.pending, (state) => {\n        state.loading = true\n      })\n      .addCase(loginUser.fulfilled, (state, action) => {\n        state.user = action.payload\n        state.loading = false\n      })\n  },\n})\n```\n\n## My Recommendation:\n1. **Start with Context** for auth, theme, user preferences\n2. **Add Zustand** if you need more complex state logic\n3. **Only use Redux** if you have complex async flows, time travel debugging needs, or team requirements\n\nHow many components are sharing state, and what type of data (user info, UI state, API data)?"
                    }
                ]
            }
        ]
        
        conversation_ids = []
        
        # Import each conversation
        with get_unit_of_work() as uow:
            for chat_data in test_chats:
                logger.info(f"📄 Creating conversation: {chat_data['title']}")
                
                # Create conversation
                conversation = uow.conversations.create(title=chat_data["title"])
                uow.session.flush()  # Get the ID immediately
                conversation_ids.append(str(conversation.id))
                
                # Add all messages
                for msg_data in chat_data["messages"]:
                    logger.info(f"💬 Adding {msg_data['role']} message ({len(msg_data['content'])} chars)")
                    self.message_service.create_message_with_embedding(
                        conversation_id=conversation.id,
                        role=msg_data["role"],
                        content=msg_data["content"]
                    )
                
                self.test_conversations.append({
                    "id": str(conversation.id),
                    "title": chat_data["title"],
                    "message_count": len(chat_data["messages"])
                })
        
        logger.info(f"✅ Created {len(conversation_ids)} conversations with realistic content")
        return conversation_ids
    
    def start_embedding_worker(self):
        """Start background embedding worker to process embedding jobs."""
        logger.info("🤖 Starting embedding worker...")
        
        def worker_loop():
            worker = EmbeddingWorker(
                max_workers=2,
                batch_size=5,
                poll_interval=1.0
            )
            worker.run()
        
        self.worker_thread = threading.Thread(target=worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("✅ Background embedding worker started")
    
    def wait_for_embeddings(self, timeout: int = 60):
        """Wait for all embeddings to be generated."""
        logger.info("⏳ Waiting for embeddings to be generated...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with get_unit_of_work() as uow:
                # Check pending jobs
                pending_count = uow.session.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
                ).scalar()
                
                # Check total embeddings
                embedding_count = uow.session.execute(
                    "SELECT COUNT(*) FROM message_embeddings"
                ).scalar()
                
                logger.info(f"📊 Status: {pending_count} pending jobs, {embedding_count} embeddings generated")
                
                if pending_count == 0:
                    logger.info("✅ All embeddings generated!")
                    return True
            
            time.sleep(2)
        
        logger.warning(f"⚠️  Timeout waiting for embeddings after {timeout}s")
        return False
    
    def test_direct_search_services(self) -> Dict[str, bool]:
        """Test search functionality directly through services."""
        logger.info("🔍 Testing direct search service functionality...")
        
        results = {}
        
        # Test queries for different content types
        test_queries = [
            ("Python scraping", "Should find web scraping conversation"),
            ("PostgreSQL optimization", "Should find database performance discussion"),
            ("Docker networking", "Should find container communication help"),
            ("machine learning deployment", "Should find ML serving discussion"),
            ("React state management", "Should find React state discussion"),
            ("semantic search vector", "Should find PostgreSQL + pgvector content"),
            ("FastAPI async", "Should find API deployment examples")
        ]
        
        for query, description in test_queries:
            logger.info(f"🔎 Testing query: '{query}' - {description}")
            
            # Test FTS search
            try:
                fts_results = self.search_service.search_fts_only(query, limit=5)
                fts_success = len(fts_results) > 0
                logger.info(f"  📝 FTS: {len(fts_results)} results")
                results[f"fts_{query.replace(' ', '_')}"] = fts_success
            except Exception as e:
                logger.error(f"  ❌ FTS failed: {e}")
                results[f"fts_{query.replace(' ', '_')}"] = False
            
            # Test vector search
            try:
                vector_results = self.search_service.search_vector_only(query, limit=5)
                vector_success = len(vector_results) > 0
                logger.info(f"  🎯 Vector: {len(vector_results)} results")
                results[f"vector_{query.replace(' ', '_')}"] = vector_success
            except Exception as e:
                logger.error(f"  ❌ Vector failed: {e}")
                results[f"vector_{query.replace(' ', '_')}"] = False
            
            # Test hybrid search
            try:
                hybrid_results = self.search_service.search(query, limit=5)
                hybrid_success = len(hybrid_results) > 0
                logger.info(f"  🔀 Hybrid: {len(hybrid_results)} results")
                results[f"hybrid_{query.replace(' ', '_')}"] = hybrid_success
                
                # Validate result quality
                if hybrid_results:
                    best_result = hybrid_results[0]
                    logger.info(f"  🏆 Best match: '{best_result.conversation_title}' (score: {best_result.combined_score:.3f})")
                
            except Exception as e:
                logger.error(f"  ❌ Hybrid failed: {e}")
                results[f"hybrid_{query.replace(' ', '_')}"] = False
            
            logger.info("")  # Empty line for readability
        
        return results
    
    def test_api_endpoints(self) -> Dict[str, bool]:
        """Test search functionality through API endpoints (legacy adapter)."""
        logger.info("🌐 Testing API endpoint functionality...")
        
        results = {}
        
        # Test /api/conversations
        try:
            conversations_data = self.legacy_adapter.get_all_conversations()
            conversations_success = (
                "documents" in conversations_data and 
                len(conversations_data["documents"]) > 0
            )
            logger.info(f"📋 /api/conversations: {len(conversations_data.get('documents', []))} conversations")
            results["api_conversations"] = conversations_success
        except Exception as e:
            logger.error(f"❌ /api/conversations failed: {e}")
            results["api_conversations"] = False
        
        # Test /api/search
        try:
            search_data = self.legacy_adapter.search(
                query_text="Python scraping",
                n_results=5,
                keyword_search=False
            )
            search_success = (
                "documents" in search_data and 
                len(search_data["documents"]) > 0 and
                len(search_data["documents"][0]) > 0
            )
            logger.info(f"🔍 /api/search: {len(search_data.get('documents', [[]])[0])} results")
            results["api_search"] = search_success
        except Exception as e:
            logger.error(f"❌ /api/search failed: {e}")
            results["api_search"] = False
        
        # Test RAG query
        try:
            rag_data = self.legacy_adapter.rag_query(
                query="How to optimize PostgreSQL for full-text search?",
                n_results=3,
                search_type="hybrid"
            )
            rag_success = (
                "results" in rag_data and 
                len(rag_data["results"]) > 0
            )
            logger.info(f"🤖 RAG query: {len(rag_data.get('results', []))} results")
            results["api_rag_query"] = rag_success
        except Exception as e:
            logger.error(f"❌ RAG query failed: {e}")
            results["api_rag_query"] = False
        
        # Test stats
        try:
            stats_data = self.legacy_adapter.get_stats()
            stats_success = (
                "status" in stats_data and 
                stats_data["status"] == "healthy" and
                stats_data.get("document_count", 0) > 0
            )
            logger.info(f"📊 Stats: {stats_data.get('document_count', 0)} documents, status: {stats_data.get('status')}")
            results["api_stats"] = stats_success
        except Exception as e:
            logger.error(f"❌ Stats failed: {e}")
            results["api_stats"] = False
        
        return results
    
    def test_search_relevance(self) -> Dict[str, bool]:
        """Test search relevance and ranking quality."""
        logger.info("🎯 Testing search relevance and ranking...")
        
        results = {}
        
        # Test specific queries that should return relevant results
        relevance_tests = [
            {
                "query": "web scraping JavaScript dynamic content",
                "expected_title_keywords": ["scraping", "selenium", "python"],
                "test_name": "web_scraping_relevance"
            },
            {
                "query": "PostgreSQL performance slow queries optimization",
                "expected_title_keywords": ["postgresql", "performance", "optimization"],
                "test_name": "postgres_optimization_relevance"
            },
            {
                "query": "Docker container networking communication",
                "expected_title_keywords": ["docker", "container", "networking"],
                "test_name": "docker_networking_relevance"
            }
        ]
        
        for test in relevance_tests:
            logger.info(f"🎯 Testing relevance for: '{test['query']}'")
            
            try:
                # Get hybrid search results
                hybrid_results = self.search_service.search(test["query"], limit=3)
                
                if not hybrid_results:
                    logger.error(f"  ❌ No results returned")
                    results[test["test_name"]] = False
                    continue
                
                # Check if top result is relevant
                top_result = hybrid_results[0]
                title_lower = top_result.conversation_title.lower()
                content_lower = top_result.content.lower()
                
                # Check if expected keywords appear in title or content
                relevance_score = 0
                for keyword in test["expected_title_keywords"]:
                    if keyword.lower() in title_lower or keyword.lower() in content_lower:
                        relevance_score += 1
                
                relevance_ratio = relevance_score / len(test["expected_title_keywords"])
                is_relevant = relevance_ratio >= 0.5  # At least 50% of keywords match
                
                logger.info(f"  🏆 Top result: '{top_result.conversation_title}'")
                logger.info(f"  📈 Combined score: {top_result.combined_score:.3f}")
                logger.info(f"  ✅ Relevance: {relevance_ratio:.1%} ({relevance_score}/{len(test['expected_title_keywords'])} keywords)")
                
                results[test["test_name"]] = is_relevant
                
            except Exception as e:
                logger.error(f"  ❌ Relevance test failed: {e}")
                results[test["test_name"]] = False
        
        return results
    
    def run_full_integration_test(self) -> bool:
        """Run complete end-to-end integration test."""
        logger.info("🚀 Starting End-to-End Integration Test")
        logger.info("=" * 70)
        
        try:
            # Step 1: Setup database
            logger.info("📋 Step 1: Setting up database...")
            setup_database()
            
            # Step 2: Import test conversations
            logger.info("📋 Step 2: Importing test chat conversations...")
            conversation_ids = self.setup_test_data()
            
            # Step 3: Start embedding worker
            logger.info("📋 Step 3: Starting background embedding generation...")
            self.start_embedding_worker()
            
            # Step 4: Wait for embeddings
            logger.info("📋 Step 4: Waiting for embeddings to be generated...")
            embeddings_ready = self.wait_for_embeddings(timeout=90)
            
            if not embeddings_ready:
                logger.error("❌ Embeddings not ready in time - some tests may fail")
            
            # Step 5: Test direct search services
            logger.info("📋 Step 5: Testing search services...")
            service_results = self.test_direct_search_services()
            
            # Step 6: Test API endpoints
            logger.info("📋 Step 6: Testing API endpoints...")
            api_results = self.test_api_endpoints()
            
            # Step 7: Test search relevance
            logger.info("📋 Step 7: Testing search relevance...")
            relevance_results = self.test_search_relevance()
            
            # Combine all results
            all_results = {**service_results, **api_results, **relevance_results}
            
            # Generate report
            logger.info("\n" + "=" * 70)
            logger.info("📊 INTEGRATION TEST RESULTS")
            logger.info("=" * 70)
            
            passed = sum(1 for result in all_results.values() if result)
            total = len(all_results)
            
            logger.info(f"📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
            logger.info("")
            
            # Detailed results
            categories = {
                "Search Services": [k for k in all_results.keys() if k.startswith(('fts_', 'vector_', 'hybrid_'))],
                "API Endpoints": [k for k in all_results.keys() if k.startswith('api_')],
                "Search Relevance": [k for k in all_results.keys() if k.endswith('_relevance')]
            }
            
            for category, tests in categories.items():
                if tests:
                    category_passed = sum(1 for test in tests if all_results[test])
                    category_total = len(tests)
                    logger.info(f"📋 {category}: {category_passed}/{category_total} passed")
                    
                    for test in tests:
                        status = "✅ PASS" if all_results[test] else "❌ FAIL"
                        logger.info(f"  {status}: {test}")
            
            # Summary
            logger.info("")
            logger.info("📝 Test Summary:")
            logger.info(f"   📚 Conversations imported: {len(self.test_conversations)}")
            for conv in self.test_conversations:
                logger.info(f"      • {conv['title']} ({conv['message_count']} messages)")
            
            logger.info(f"   🎯 Search functionality: {'✅ Working' if any(k.startswith('hybrid_') and v for k, v in all_results.items()) else '❌ Failed'}")
            logger.info(f"   🌐 API compatibility: {'✅ Working' if all_results.get('api_search', False) else '❌ Failed'}")
            logger.info(f"   🔍 Search relevance: {'✅ Good' if any(k.endswith('_relevance') and v for k, v in all_results.items()) else '❌ Poor'}")
            
            success = passed >= total * 0.8  # 80% pass rate
            
            if success:
                logger.info("🎉 END-TO-END INTEGRATION TEST PASSED!")
                logger.info("   The chat import and search pipeline is working correctly.")
            else:
                logger.error("❌ INTEGRATION TEST FAILED!")
                logger.error("   Some components are not working as expected.")
            
            return success
            
        except Exception as e:
            logger.error(f"💥 Integration test failed with exception: {e}")
            return False


def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='End-to-end integration test for chat import and search'
    )
    parser.add_argument('--timeout', type=int, default=90,
                       help='Timeout for embedding generation (seconds)')
    
    args = parser.parse_args()
    
    tester = EndToEndTester()
    success = tester.run_full_integration_test()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()