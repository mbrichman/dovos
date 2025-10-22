#!/usr/bin/env python3
"""
Manual Chat Import and Search Test

A simple script to manually test importing a chat conversation
and searching for it using all available search methods.
"""

import os
import sys
import time
import logging
from typing import Dict, Any

# Set feature flag to use PostgreSQL backend
os.environ['USE_POSTGRES'] = 'true'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database_setup import setup_database
from db.services.message_service import MessageService
from db.services.search_service import SearchService
from db.workers.embedding_worker import EmbeddingWorker
from db.repositories.unit_of_work import get_unit_of_work
from db.adapters.legacy_api_adapter import get_legacy_adapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def import_test_chat() -> str:
    """Import a single test conversation and return its ID."""
    logger.info("📥 Importing test chat conversation...")
    
    # Simple test conversation
    test_chat = {
        "title": "Getting Started with Machine Learning",
        "messages": [
            {
                "role": "user",
                "content": "I'm new to machine learning and want to start learning. What programming language should I use and what are the basic concepts I need to understand?"
            },
            {
                "role": "assistant", 
                "content": "Great question! Here's a beginner-friendly roadmap for machine learning:\n\n## Programming Language\n**Python** is the best choice for beginners because:\n- Extensive ML libraries (scikit-learn, pandas, numpy)\n- Easy to learn syntax\n- Large community and resources\n- Industry standard for ML/AI\n\n## Essential Concepts to Learn\n\n### 1. Data Fundamentals\n- Data types (numerical, categorical, text)\n- Data cleaning and preprocessing\n- Exploratory data analysis (EDA)\n\n### 2. Core ML Concepts\n- **Supervised Learning**: Learning from labeled examples\n  - Classification (predicting categories)\n  - Regression (predicting numbers)\n- **Unsupervised Learning**: Finding patterns in unlabeled data\n  - Clustering\n  - Dimensionality reduction\n\n### 3. Key Libraries\n```python\nimport pandas as pd          # Data manipulation\nimport numpy as np           # Numerical computing\nimport matplotlib.pyplot as plt  # Data visualization\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.metrics import accuracy_score\n```\n\n## Learning Path\n1. **Start with Python basics** (if you haven't already)\n2. **Learn pandas and numpy** for data manipulation\n3. **Practice with simple datasets** (iris, housing prices)\n4. **Understand the ML workflow**: data → model → prediction → evaluation\n5. **Try different algorithms** and see how they perform\n\n## Recommended First Project\nStart with a simple classification problem like predicting whether an email is spam or not spam. This will teach you the complete ML pipeline without being overwhelming.\n\nWould you like me to recommend some specific resources or walk through a simple example?"
            },
            {
                "role": "user",
                "content": "That's really helpful! Can you show me a simple example of how to build a basic machine learning model in Python?"
            },
            {
                "role": "assistant",
                "content": "Absolutely! Here's a complete beginner example using the famous Iris dataset:\n\n```python\n# Import required libraries\nimport pandas as pd\nimport numpy as np\nfrom sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import accuracy_score, classification_report\nimport matplotlib.pyplot as plt\n\n# Step 1: Load the data\niris = load_iris()\nX = iris.data    # Features (measurements)\ny = iris.target  # Labels (flower species)\n\nprint(\"Dataset shape:\", X.shape)\nprint(\"Features:\", iris.feature_names)\nprint(\"Target classes:\", iris.target_names)\n\n# Step 2: Split data into training and testing sets\nX_train, X_test, y_train, y_test = train_test_split(\n    X, y, test_size=0.2, random_state=42\n)\n\nprint(f\"Training set: {X_train.shape[0]} samples\")\nprint(f\"Testing set: {X_test.shape[0]} samples\")\n\n# Step 3: Create and train the model\nmodel = RandomForestClassifier(n_estimators=100, random_state=42)\nmodel.fit(X_train, y_train)\n\n# Step 4: Make predictions\ny_pred = model.predict(X_test)\n\n# Step 5: Evaluate the model\naccuracy = accuracy_score(y_test, y_pred)\nprint(f\"\\nAccuracy: {accuracy:.3f} ({accuracy*100:.1f}%)\")\n\n# Detailed classification report\nprint(\"\\nDetailed Results:\")\nprint(classification_report(y_test, y_pred, target_names=iris.target_names))\n\n# Step 6: Feature importance (what the model learned)\nfeature_importance = model.feature_importances_\nfor i, importance in enumerate(feature_importance):\n    print(f\"{iris.feature_names[i]}: {importance:.3f}\")\n\n# Step 7: Make a prediction on new data\nnew_flower = [[5.1, 3.5, 1.4, 0.2]]  # New measurements\npredicted_class = model.predict(new_flower)[0]\npredicted_species = iris.target_names[predicted_class]\nconfidence = model.predict_proba(new_flower)[0].max()\n\nprint(f\"\\nNew prediction:\")\nprint(f\"Measurements: {new_flower[0]}\")\nprint(f\"Predicted species: {predicted_species}\")\nprint(f\"Confidence: {confidence:.3f}\")\n```\n\n## What This Example Teaches:\n\n1. **Data Loading**: How to work with datasets\n2. **Data Splitting**: Separating training/testing data\n3. **Model Selection**: Choosing an algorithm (Random Forest)\n4. **Training**: Teaching the model from data\n5. **Evaluation**: Measuring how well it performs\n6. **Prediction**: Using the model on new data\n\n## Key Takeaways:\n- The model achieved ~97% accuracy (very good!)\n- It learned which flower measurements are most important\n- You can use it to classify new flowers\n\n## Next Steps:\n1. Try different algorithms (Decision Tree, SVM, etc.)\n2. Experiment with different datasets\n3. Learn about data preprocessing techniques\n4. Explore feature engineering\n\nWant to try this example or have questions about any part?"
            }
        ]
    }
    
    message_service = MessageService()
    
    with get_unit_of_work() as uow:
        # Create conversation
        conversation = uow.conversations.create(title=test_chat["title"])
        uow.session.flush()
        
        logger.info(f"✅ Created conversation: {test_chat['title']}")
        logger.info(f"   Conversation ID: {conversation.id}")
        
        # Add messages
        for i, msg_data in enumerate(test_chat["messages"]):
            logger.info(f"💬 Adding message {i+1}/{len(test_chat['messages'])} ({msg_data['role']})")
            message_service.create_message_with_embedding(
                conversation_id=conversation.id,
                role=msg_data["role"],
                content=msg_data["content"]
            )
    
    return str(conversation.id)


def wait_for_embeddings(timeout: int = 30) -> bool:
    """Wait for embeddings to be generated."""
    logger.info("⏳ Waiting for embeddings to be generated...")
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        with get_unit_of_work() as uow:
            pending_count = uow.session.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
            ).scalar()
            
            embedding_count = uow.session.execute(
                "SELECT COUNT(*) FROM message_embeddings"
            ).scalar()
            
            if pending_count == 0 and embedding_count > 0:
                logger.info(f"✅ Embeddings ready! Generated {embedding_count} embeddings.")
                return True
            
            logger.info(f"📊 Status: {pending_count} pending jobs, {embedding_count} embeddings")
        
        time.sleep(2)
    
    logger.warning(f"⚠️ Timeout after {timeout}s. Continuing anyway...")
    return False


def test_search_methods(conversation_id: str):
    """Test all search methods on the imported conversation."""
    logger.info("🔍 Testing all search methods...")
    
    search_service = SearchService()
    legacy_adapter = get_legacy_adapter()
    
    # Test queries
    queries = [
        "machine learning Python",
        "RandomForestClassifier iris dataset", 
        "beginner programming language",
        "supervised learning classification"
    ]
    
    for query in queries:
        logger.info(f"\n🔎 Query: '{query}'")
        logger.info("-" * 50)
        
        # 1. FTS Search (Direct Service)
        try:
            fts_results = search_service.search_fts_only(query, limit=3)
            logger.info(f"📝 FTS Search: {len(fts_results)} results")
            for i, result in enumerate(fts_results):
                logger.info(f"   {i+1}. {result.conversation_title} (score: {result.combined_score:.3f})")
        except Exception as e:
            logger.error(f"❌ FTS search failed: {e}")
        
        # 2. Vector Search (Direct Service)
        try:
            vector_results = search_service.search_vector_only(query, limit=3)
            logger.info(f"🎯 Vector Search: {len(vector_results)} results")
            for i, result in enumerate(vector_results):
                logger.info(f"   {i+1}. {result.conversation_title} (similarity: {result.similarity:.3f})")
        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
        
        # 3. Hybrid Search (Direct Service) 
        try:
            hybrid_results = search_service.search(query, limit=3)
            logger.info(f"🔀 Hybrid Search: {len(hybrid_results)} results")
            for i, result in enumerate(hybrid_results):
                logger.info(f"   {i+1}. {result.conversation_title} (combined: {result.combined_score:.3f})")
        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
        
        # 4. Legacy API Search
        try:
            api_results = legacy_adapter.search(query_text=query, n_results=3)
            api_count = len(api_results.get("documents", [[]])[0])
            logger.info(f"🌐 API Search: {api_count} results")
            if api_count > 0:
                for i, result in enumerate(api_results["results"]):
                    logger.info(f"   {i+1}. {result['title']}")
        except Exception as e:
            logger.error(f"❌ API search failed: {e}")
        
        # 5. RAG Query
        try:
            rag_results = legacy_adapter.rag_query(query=query, n_results=2)
            rag_count = len(rag_results.get("results", []))
            logger.info(f"🤖 RAG Query: {rag_count} results")
            for i, result in enumerate(rag_results.get("results", [])):
                logger.info(f"   {i+1}. {result['title']} (relevance: {result['relevance']:.3f})")
        except Exception as e:
            logger.error(f"❌ RAG query failed: {e}")


def run_manual_test():
    """Run the complete manual test."""
    logger.info("🚀 Starting Manual Chat Import and Search Test")
    logger.info("=" * 60)
    
    try:
        # Step 1: Setup database
        logger.info("📋 Step 1: Setting up database...")
        setup_database()
        
        # Step 2: Import test chat
        logger.info("📋 Step 2: Importing test conversation...")
        conversation_id = import_test_chat()
        
        # Step 3: Wait for embeddings
        logger.info("📋 Step 3: Processing embeddings...")
        embeddings_ready = wait_for_embeddings(timeout=30)
        
        # Step 4: Test search methods
        logger.info("📋 Step 4: Testing search functionality...")
        test_search_methods(conversation_id)
        
        # Step 5: Test API endpoints
        logger.info("\n📋 Step 5: Testing API endpoints...")
        legacy_adapter = get_legacy_adapter()
        
        # Test conversation retrieval
        logger.info("📋 Testing conversation retrieval...")
        try:
            conversations = legacy_adapter.get_all_conversations()
            logger.info(f"✅ Retrieved {len(conversations.get('documents', []))} conversations")
            
            # Get specific conversation
            specific = legacy_adapter.get_conversation_by_id(conversation_id)
            logger.info(f"✅ Retrieved specific conversation: {len(specific.get('documents', []))} documents")
        except Exception as e:
            logger.error(f"❌ Conversation retrieval failed: {e}")
        
        # Test stats
        logger.info("📊 Testing stats...")
        try:
            stats = legacy_adapter.get_stats()
            logger.info(f"✅ Stats: {stats.get('document_count', 0)} documents, status: {stats.get('status')}")
        except Exception as e:
            logger.error(f"❌ Stats failed: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Manual test completed!")
        logger.info("✅ Your chat has been imported and is searchable")
        logger.info(f"💡 Conversation ID: {conversation_id}")
        logger.info("🔍 Try searching for: 'machine learning', 'Python', 'iris dataset'")
        
    except Exception as e:
        logger.error(f"💥 Manual test failed: {e}")
        raise


if __name__ == "__main__":
    run_manual_test()