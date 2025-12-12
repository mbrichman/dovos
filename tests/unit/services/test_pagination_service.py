"""
Unit tests for PaginationService.

Tests pagination logic independently of HTTP/Flask context.
"""

import pytest
from db.services.pagination_service import PaginationService


@pytest.fixture
def pagination_service():
    """Provide a PaginationService instance."""
    return PaginationService()


class TestCalculatePagination:
    """Test pagination calculation logic."""
    
    def test_calculate_pagination_empty_list(self, pagination_service):
        """Test pagination with empty item list."""
        result = pagination_service.calculate_pagination([], page=1, per_page=20)
        
        assert result["total_items"] == 0
        assert result["page_count"] == 0
        assert result["current_page"] == 1
        assert result["per_page"] == 20
    
    def test_calculate_pagination_single_page(self, pagination_service):
        """Test pagination with items that fit on one page."""
        items = list(range(10))  # 10 items
        result = pagination_service.calculate_pagination(items, page=1, per_page=20)
        
        assert result["total_items"] == 10
        assert result["page_count"] == 1
        assert result["current_page"] == 1
    
    def test_calculate_pagination_multiple_pages(self, pagination_service):
        """Test pagination with multiple pages needed."""
        items = list(range(100))  # 100 items
        result = pagination_service.calculate_pagination(items, page=1, per_page=20)
        
        assert result["total_items"] == 100
        assert result["page_count"] == 5
        assert result["current_page"] == 1
    
    def test_calculate_pagination_exact_multiple(self, pagination_service):
        """Test pagination when items divide evenly by per_page."""
        items = list(range(60))  # Exactly 3 pages of 20
        result = pagination_service.calculate_pagination(items, page=1, per_page=20)
        
        assert result["total_items"] == 60
        assert result["page_count"] == 3
    
    def test_calculate_pagination_returns_dict(self, pagination_service):
        """Test that calculate_pagination returns proper structure."""
        items = list(range(50))
        result = pagination_service.calculate_pagination(items, page=1, per_page=20)
        
        assert isinstance(result, dict)
        assert "total_items" in result
        assert "page_count" in result
        assert "current_page" in result
        assert "per_page" in result


class TestValidatePage:
    """Test page validation logic."""
    
    def test_validate_page_within_range(self, pagination_service):
        """Test page validation for valid page number."""
        valid_page = pagination_service.validate_page(2, page_count=5)
        assert valid_page == 2
    
    def test_validate_page_first_page(self, pagination_service):
        """Test validation for first page."""
        valid_page = pagination_service.validate_page(1, page_count=5)
        assert valid_page == 1
    
    def test_validate_page_last_page(self, pagination_service):
        """Test validation for last page."""
        valid_page = pagination_service.validate_page(5, page_count=5)
        assert valid_page == 5
    
    def test_validate_page_too_high(self, pagination_service):
        """Test that page number is clamped to page_count."""
        valid_page = pagination_service.validate_page(10, page_count=5)
        assert valid_page == 5
    
    def test_validate_page_zero(self, pagination_service):
        """Test that page 0 is clamped to 1."""
        valid_page = pagination_service.validate_page(0, page_count=5)
        assert valid_page == 1
    
    def test_validate_page_negative(self, pagination_service):
        """Test that negative page is clamped to 1."""
        valid_page = pagination_service.validate_page(-5, page_count=5)
        assert valid_page == 1
    
    def test_validate_page_zero_pages(self, pagination_service):
        """Test validation when there are no pages."""
        valid_page = pagination_service.validate_page(1, page_count=0)
        assert valid_page == 1


class TestGetPageItems:
    """Test page item slicing logic."""
    
    def test_get_page_items_first_page(self, pagination_service):
        """Test getting items from first page."""
        items = list(range(100))
        page_items = pagination_service.get_page_items(items, page=1, per_page=20)
        
        assert len(page_items) == 20
        assert page_items[0] == 0
        assert page_items[-1] == 19
    
    def test_get_page_items_second_page(self, pagination_service):
        """Test getting items from second page."""
        items = list(range(100))
        page_items = pagination_service.get_page_items(items, page=2, per_page=20)
        
        assert len(page_items) == 20
        assert page_items[0] == 20
        assert page_items[-1] == 39
    
    def test_get_page_items_last_page_partial(self, pagination_service):
        """Test getting items from last page with fewer items."""
        items = list(range(55))
        page_items = pagination_service.get_page_items(items, page=3, per_page=20)
        
        assert len(page_items) == 15  # Last page has only 15 items
        assert page_items[0] == 40
        assert page_items[-1] == 54
    
    def test_get_page_items_single_page(self, pagination_service):
        """Test getting items when everything fits on one page."""
        items = list(range(10))
        page_items = pagination_service.get_page_items(items, page=1, per_page=20)
        
        assert len(page_items) == 10
        assert page_items == items
    
    def test_get_page_items_empty_list(self, pagination_service):
        """Test getting items from empty list."""
        page_items = pagination_service.get_page_items([], page=1, per_page=20)
        
        assert len(page_items) == 0
        assert page_items == []


class TestPaginationIntegration:
    """Integration tests combining multiple pagination operations."""
    
    def test_full_pagination_flow(self, pagination_service):
        """Test full pagination flow: calculate, validate, get items."""
        items = list(range(75))
        
        # Calculate pagination
        pagination = pagination_service.calculate_pagination(items, page=2, per_page=20)
        assert pagination["page_count"] == 4
        
        # Validate page
        valid_page = pagination_service.validate_page(pagination["current_page"], 
                                                       page_count=pagination["page_count"])
        assert valid_page == 2
        
        # Get items for page
        page_items = pagination_service.get_page_items(items, page=valid_page, per_page=20)
        assert len(page_items) == 20
        assert page_items[0] == 20
    
    def test_pagination_with_invalid_page_number(self, pagination_service):
        """Test pagination when given invalid page number."""
        items = list(range(75))
        
        # Try to get page 10 (out of range)
        pagination = pagination_service.calculate_pagination(items, page=10, per_page=20)
        valid_page = pagination_service.validate_page(10, page_count=pagination["page_count"])
        
        # Should clamp to last page
        assert valid_page == 4
        
        # Get items for clamped page
        page_items = pagination_service.get_page_items(items, page=valid_page, per_page=20)
        assert len(page_items) == 15  # Last page has 15 items
