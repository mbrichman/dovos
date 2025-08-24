# Dovos Application - MVC Refactored Structure

## Overview
This document outlines the refactored structure of the Dovos application following MVC (Model-View-Controller) principles. The refactoring separates concerns by moving business logic to models, keeping controllers thin, and maintaining the existing views.

## Directory Structure
```
dovos/
├── app.py                 # Application entry point
├── routes.py              # Route definitions
├── config.py              # Configuration settings
├── forms.py               # Form definitions
├── utils.py               # Utility functions
├── templates/             # HTML templates (views)
│   ├── conversations.html
│   ├── index.html
│   ├── stats.html
│   ├── upload.html
│   └── view.html
├── models/                # Business logic layer
│   ├── __init__.py        # BaseModel class
│   ├── conversation_model.py     # Main data model for conversations
│   ├── search_model.py           # Search-related business logic
│   ├── conversation_view_model.py # Presentation logic for conversations
│   └── search_utils.py           # Search utility functions
└── controllers/           # Thin controllers
    ├── __init__.py
    └── conversation_controller.py # Route handlers
```

## Models

### BaseModel (/models/__init__.py)
- Abstract base class for all models
- Defines the `initialize()` abstract method

### ConversationModel (/models/conversation_model.py)
- Manages conversation data storage and retrieval
- Handles indexing of JSON and DOCX files
- Implements search functionality (both semantic and keyword)
- Manages ChromaDB collection operations
- Handles document processing and cleaning

### SearchModel (/models/search_model.py)
- Coordinates search operations across conversations
- Provides statistics functionality
- Handles document retrieval by ID
- Acts as a facade for ConversationModel's search capabilities

### ConversationViewModel (/models/conversation_view_model.py)
- Formats data for presentation in views
- Handles conversation list formatting
- Processes search results for display
- Manages conversation detail view formatting
- Contains filter and sorting logic

### SearchUtils (/models/search_utils.py)
- Contains utility functions for search operations
- Implements query stemming and expansion
- Handles NLTK-based text processing

## Controllers

### ConversationController (/controllers/conversation_controller.py)
- Thin controller implementing route handlers
- Coordinates between models and views
- Handles HTTP request/response logic
- Manages form processing
- Implements error handling for routes

### UploadController (/controllers/conversation_controller.py)
- Handles file upload functionality
- Processes JSON and DOCX file uploads
- Implements API search endpoint

## Key Improvements

1. **Separation of Concerns**: Business logic is now encapsulated in models, making the codebase more maintainable.

2. **Thin Controllers**: Route handlers in controllers are minimal and delegate to models for business logic.

3. **Reusability**: Models can be used independently of the web interface.

4. **Testability**: Business logic in models can be unit tested without web framework dependencies.

5. **Scalability**: New features can be added by extending models without modifying controller logic.

## Data Flow

1. **Request Handling**: Controller receives HTTP request
2. **Business Logic**: Controller delegates to appropriate Model
3. **Data Processing**: Model processes data and returns results
4. **Presentation**: Controller formats data using ViewModel
5. **Response**: Controller renders appropriate View template

## Testing
Models can be tested independently:
```python
# Example model usage
from models.conversation_model import ConversationModel
from models.search_model import SearchModel

# Create model instances
conversation_model = ConversationModel()
search_model = SearchModel()

# Use models directly
results = search_model.search_conversations("query")
```

## Conclusion
The refactored application follows MVC principles with clear separation between:
- **Models**: Handle data and business logic
- **Views**: Manage presentation (HTML templates)
- **Controllers**: Coordinate between models and views

This structure improves maintainability, testability, and scalability of the application.
