from abc import ABC, abstractmethod

class BaseModel(ABC):
    """Base model class for all models in the application"""
    
    @abstractmethod
    def initialize(self):
        """Initialize the model"""
        pass
