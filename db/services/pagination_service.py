"""
Service for handling pagination logic.

Provides pure, testable pagination functions independent of HTTP/Flask context.
Follows Single Responsibility Principle - only handles pagination math.
"""

from typing import List, Dict, Any, TypeVar

T = TypeVar('T')


class PaginationService:
    """Service for pagination calculations and item slicing."""
    
    def calculate_pagination(
        self,
        items: List[T],
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, int]:
        """
        Calculate pagination information for a list of items.
        
        Args:
            items: List of items to paginate
            page: Current page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Dict with total_items, page_count, current_page, per_page
        """
        total_items = len(items)
        
        # Calculate page count using ceiling division
        page_count = 0 if total_items == 0 else (total_items + per_page - 1) // per_page
        
        return {
            "total_items": total_items,
            "page_count": page_count,
            "current_page": page,
            "per_page": per_page
        }
    
    def validate_page(self, page: int, page_count: int) -> int:
        """
        Validate and clamp page number to valid range.
        
        Args:
            page: Requested page number
            page_count: Total number of pages
            
        Returns:
            Valid page number (1 to page_count, or 1 if no pages)
        """
        if page_count == 0:
            return 1
        
        return max(1, min(page, page_count))
    
    def get_page_items(
        self,
        items: List[T],
        page: int = 1,
        per_page: int = 20
    ) -> List[T]:
        """
        Get items for a specific page.
        
        Args:
            items: List of all items
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Slice of items for the requested page
        """
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        return items[start_idx:end_idx]
