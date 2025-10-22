"""Repository for managing application settings."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import func

from db.models.models import Setting


class SettingRepository:
    """Repository for CRUD operations on settings."""
    
    def __init__(self, session):
        self.session = session
    
    def get(self, setting_id: str) -> Optional[Setting]:
        """Get a setting by ID."""
        return self.session.query(Setting).filter(Setting.id == setting_id).first()
    
    def get_value(self, setting_id: str, default: Any = None) -> Any:
        """Get a setting value, returning default if not found."""
        setting = self.get(setting_id)
        return setting.value if setting else default
    
    def get_all(self, category: Optional[str] = None) -> list[Setting]:
        """Get all settings, optionally filtered by category."""
        query = self.session.query(Setting)
        if category:
            query = query.filter(Setting.category == category)
        return query.all()
    
    def get_all_as_dict(self, category: Optional[str] = None) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        settings = self.get_all(category)
        return {setting.id: setting.value for setting in settings}
    
    def create_or_update(self, setting_id: str, value: str, 
                        description: Optional[str] = None, 
                        category: str = 'general') -> Setting:
        """Create or update a setting."""
        setting = self.get(setting_id)
        
        if setting:
            # Update existing
            setting.value = value
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
        else:
            # Create new
            setting = Setting(
                id=setting_id,
                value=value,
                description=description,
                category=category
            )
            self.session.add(setting)
        
        return setting
    
    def delete(self, setting_id: str) -> bool:
        """Delete a setting."""
        result = self.session.query(Setting).filter(Setting.id == setting_id).delete()
        return result > 0
    
    def count(self, category: Optional[str] = None) -> int:
        """Count settings, optionally by category."""
        query = self.session.query(func.count(Setting.id))
        if category:
            query = query.filter(Setting.category == category)
        return query.scalar() or 0
