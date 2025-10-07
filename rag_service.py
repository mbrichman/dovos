"""
RAG API Service for OpenWebUI Integration
"""
import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from sentence_transformers import SentenceTransformer
from config import COLLECTION_NAME, PERSIST_DIR, DEFAULT_EMBEDDING_MODEL

app = Flask(__name__)
CORS(app)

class RAGService:
    def __init__(self):
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=PERSIST_DIR)
        
        # Get the collection
        try:
            self.collection = self.chroma_client.get_collection(COLLECTION_NAME)
        except Exception as e:
            print(f"Error getting collection: {e}")
            self.collection = None
            
        # Initialize embedding model
        print("Loading embedding model...")
        self.embedder = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
        
    def query_documents(self, query_text, n_results=5, search_type="semantic"):
        """Query documents using semantic or keyword search"""
        if not self.collection:
            return {"error": "Collection not initialized"}
            
        try:
            if search_type == "keyword":
                return self._keyword_search(query_text, n_results)
            else:
                return self._semantic_search(query_text, n_results)
        except Exception as e:
            return {"error": str(e)}
    
    def _semantic_search(self, query_text, n_results=5):
        """Perform semantic search using embeddings"""
        # Generate embedding for the query
        query_embedding = self.embedder.encode([query_text])[0]
        
        # Perform search
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        return results
    
    def _keyword_search(self, query_text, n_results=5):
        """Perform keyword search using regex matching"""
        # Get more documents to filter through
        all_docs = self.collection.get(
            include=["documents", "metadatas"],
            limit=1000
        )
        
        if not all_docs or not all_docs.get("documents"):
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        # Score documents based on keyword matches
        matches = []
        query_terms = query_text.lower().split()
        
        for i, doc in enumerate(all_docs["documents"]):
            doc_lower = doc.lower()
            score = 0
            
            # Count matches for each query term
            for term in query_terms:
                # Exact match
                exact_matches = doc_lower.count(term)
                score += exact_matches * 2
                
                # Partial matches (for broader matching)
                partial_matches = len(re.findall(r'\b' + re.escape(term) + r'\w*', doc_lower))
                score += partial_matches
            
            if score > 0:
                matches.append({
                    "document": doc,
                    "metadata": all_docs["metadatas"][i] if i < len(all_docs.get("metadatas", [])) else {},
                    "score": score
                })
        
        # Sort by score and take top results
        matches.sort(key=lambda x: x["score"], reverse=True)
        top_matches = matches[:n_results]
        
        if not top_matches:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        # Format results similar to ChromaDB query results
        documents = [m["document"] for m in top_matches]
        metadatas = [m["metadata"] for m in top_matches]
        # Convert scores to distance-like values (lower is better)
        max_score = max(m["score"] for m in top_matches)
        distances = [1.0 - (m["score"] / max_score) if max_score > 0 else 0.0 for m in top_matches]
        
        return {"documents": [documents], "metadatas": [metadatas], "distances": [distances]}

# Initialize the RAG service
rag_service = RAGService()

@app.route('/rag/query', methods=['POST'])
def rag_query():
    """RAG query endpoint for OpenWebUI integration"""
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        n_results = data.get('n_results', 5)
        search_type = data.get('search_type', 'semantic')  # 'semantic' or 'keyword'
        
        if not query_text:
            return jsonify({"error": "Query text is required"}), 400
            
        # Query the documents
        results = rag_service.query_documents(query_text, n_results, search_type)
        
        if "error" in results:
            return jsonify(results), 500
            
        # Format results for OpenWebUI
        formatted_results = []
        if results.get("documents") and results["documents"][0]:
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0], 
                results["metadatas"][0], 
                results["distances"][0]
            )):
                # Extract a preview of the content
                preview = doc[:500] + "..." if len(doc) > 500 else doc
                
                formatted_results.append({
                    "id": meta.get("id", f"result-{i}"),
                    "title": meta.get("title", "Untitled"),
                    "content": doc,
                    "preview": preview,
                    "source": meta.get("source", "unknown"),
                    "distance": dist,
                    "relevance": 1.0 - dist,  # Convert distance to relevance score
                    "metadata": meta
                })
        
        return jsonify({
            "query": query_text,
            "search_type": search_type,
            "results": formatted_results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rag/search', methods=['POST'])
def hybrid_search():
    """Hybrid search combining semantic and keyword search"""
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        n_results = data.get('n_results', 5)
        semantic_weight = data.get('semantic_weight', 0.7)  # Weight for semantic search (0.0 to 1.0)
        
        if not query_text:
            return jsonify({"error": "Query text is required"}), 400
            
        # Get results from both search methods
        semantic_results = rag_service.query_documents(query_text, n_results * 2, "semantic")
        keyword_results = rag_service.query_documents(query_text, n_results * 2, "keyword")
        
        # Combine and rank results
        combined_scores = {}
        
        # Process semantic results
        if not "error" in semantic_results and semantic_results.get("documents") and semantic_results["documents"][0]:
            for i, (doc, meta, dist) in enumerate(zip(
                semantic_results["documents"][0], 
                semantic_results["metadatas"][0], 
                semantic_results["distances"][0]
            )):
                doc_id = meta.get("id", f"semantic-{i}")
                semantic_score = 1.0 - dist  # Convert distance to relevance
                combined_scores[doc_id] = {
                    "document": doc,
                    "metadata": meta,
                    "semantic_score": semantic_score,
                    "keyword_score": 0.0
                }
        
        # Process keyword results
        if not "error" in keyword_results and keyword_results.get("documents") and keyword_results["documents"][0]:
            for i, (doc, meta, dist) in enumerate(zip(
                keyword_results["documents"][0], 
                keyword_results["metadatas"][0], 
                keyword_results["distances"][0]
            )):
                doc_id = meta.get("id", f"keyword-{i}")
                keyword_score = 1.0 - dist  # Convert distance to relevance
                
                if doc_id in combined_scores:
                    combined_scores[doc_id]["keyword_score"] = keyword_score
                else:
                    combined_scores[doc_id] = {
                        "document": doc,
                        "metadata": meta,
                        "semantic_score": 0.0,
                        "keyword_score": keyword_score
                    }
        
        # Calculate combined scores
        final_results = []
        for doc_id, data in combined_scores.items():
            combined_score = (
                data["semantic_score"] * semantic_weight + 
                data["keyword_score"] * (1 - semantic_weight)
            )
            
            final_results.append({
                "id": doc_id,
                "document": data["document"],
                "metadata": data["metadata"],
                "semantic_score": data["semantic_score"],
                "keyword_score": data["keyword_score"],
                "combined_score": combined_score
            })
        
        # Sort by combined score and take top results
        final_results.sort(key=lambda x: x["combined_score"], reverse=True)
        top_results = final_results[:n_results]
        
        # Format for response
        formatted_results = []
        for i, result in enumerate(top_results):
            doc = result["document"]
            meta = result["metadata"]
            
            # Extract a preview of the content
            preview = doc[:500] + "..." if len(doc) > 500 else doc
            
            formatted_results.append({
                "id": result["id"],
                "title": meta.get("title", "Untitled"),
                "content": doc,
                "preview": preview,
                "source": meta.get("source", "unknown"),
                "semantic_score": result["semantic_score"],
                "keyword_score": result["keyword_score"],
                "combined_score": result["combined_score"],
                "metadata": meta
            })
        
        return jsonify({
            "query": query_text,
            "results": formatted_results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/rag/search_by_title', methods=['POST'])
def search_by_title():
    """Search specifically in conversation titles"""
    try:
        data = request.get_json()
        query_text = data.get('query', '').lower()
        n_results = data.get('n_results', 5)
        
        if not query_text:
            return jsonify({"error": "Query text is required"}), 400
        
        all_docs = rag_service.collection.get(
            include=["documents", "metadatas"]
        )
        
        matches = []
        for i, (doc, meta) in enumerate(zip(all_docs["documents"], all_docs["metadatas"])):
            title = meta.get("title", "").lower()
            
            # Score based on title matching
            score = 0
            for term in query_text.split():
                if term in title:
                    score += 10  # Exact substring match
                if title == term:
                    score += 50  # Exact title match
            
            if score > 0:
                matches.append({
                    "document": doc,
                    "metadata": meta,
                    "score": score
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        top_matches = matches[:n_results]
        
        formatted_results = []
        for m in top_matches:
            formatted_results.append({
                "title": m["metadata"].get("title", "Untitled"),
                "content": m["document"],
                "metadata": m["metadata"],
                "score": m["score"]
            })
        
        return jsonify({
            "query": query_text,
            "results": formatted_results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rag/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    collection_count = 0
    if rag_service.collection:
        try:
            collection_count = rag_service.collection.count()
        except:
            pass
            
    return jsonify({
        "status": "healthy",
        "collection_count": collection_count
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=True)
