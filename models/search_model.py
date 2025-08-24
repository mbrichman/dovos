from models import BaseModel
from models.conversation_model import ConversationModel
from models.search_utils import expand_query_with_stems


class SearchModel(BaseModel):
    """Model for handling search operations"""
    
    def __init__(self):
        self.conversation_model = ConversationModel()
        self.initialize()
    
    def initialize(self):
        """Initialize the search model"""
        pass
    
    def search_conversations(self, query_text, n_results=5, date_range=None, keyword_search=False):
        """Search conversations using the conversation model"""
        return self.conversation_model.search(
            query_text=query_text,
            n_results=n_results,
            date_range=date_range,
            keyword_search=keyword_search
        )
    
    def get_all_conversations(self, include=None, limit=None):
        """Get all conversations"""
        return self.conversation_model.get_documents(include=include, limit=limit)
    
    def get_conversation_by_id(self, doc_id):
        """Get a specific conversation by ID"""
        # Try to find the document by its actual ChromaDB ID
        try:
            # Get all documents with their IDs
            all_docs = self.conversation_model.collection.get(include=["documents", "metadatas"])
            
            if all_docs.get("ids") and doc_id in all_docs["ids"]:
                # Found the document by ID
                idx = all_docs["ids"].index(doc_id)
                return {
                    "documents": [all_docs["documents"][idx]],
                    "metadatas": [all_docs["metadatas"][idx]],
                    "ids": [doc_id]
                }
            else:
                # Try other methods
                pass
        except Exception as e:
            print(f"Error finding document {doc_id}: {e}")
        
        # Try to get the document with the ID in the metadata 'id' field  
        doc_result = self.conversation_model.get_documents(
            where={"id": doc_id}, include=["documents", "metadatas"]
        )
        
        if doc_result and doc_result.get("documents") and doc_result["documents"]:
            return doc_result
            
        # Try other possible ID fields
        where_conditions = [{"conversation_id": doc_id}, {"original_index": doc_id}]
        for condition in where_conditions:
            doc_result = self.conversation_model.get_documents(
                where=condition, include=["documents", "metadatas"]
            )
            if doc_result and doc_result.get("documents") and doc_result["documents"]:
                return doc_result
                
        return None
    
    def get_statistics(self):
        """Get statistics about the conversations"""
        # Get basic stats
        doc_count = self.conversation_model.get_count()

        # Get all metadata to analyze
        all_meta = self.conversation_model.get_documents(include=["metadatas"], limit=9999)["metadatas"]

        # Count by source
        sources = {}
        for meta in all_meta:
            source = meta.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

        # Get date range
        dates = [meta.get("earliest_ts") for meta in all_meta if meta.get("earliest_ts")]
        date_range = None
        if dates:
            dates.sort()
            date_range = {"earliest": dates[0], "latest": dates[-1]}

        # Count by chunks
        chunked = sum(1 for meta in all_meta if meta.get("is_chunk", False))

        stats_data = {
            "total": doc_count,
            "sources": sources,
            "date_range": date_range,
            "chunked": chunked,
            "full": doc_count - chunked,
        }
        
        return stats_data
