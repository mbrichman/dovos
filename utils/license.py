"""
License validation utilities for DovOS premium features.

Validates license keys and checks feature access permissions.
"""

import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class LicenseValidator:
    """Validates DovOS license keys and feature access."""

    # License tiers
    TIER_FREE = "free"
    TIER_PRO = "pro"
    TIER_ENTERPRISE = "enterprise"

    # Valid license key prefixes
    VALID_PREFIXES = {
        "DOVOS-PRO-": TIER_PRO,
        "DOVOS-ENT-": TIER_ENTERPRISE,
    }

    def __init__(self):
        """Initialize the license validator."""
        self._license_key = os.environ.get('DOVOS_LICENSE_KEY', '').strip()
        self._tier = self._detect_tier()

    def _detect_tier(self) -> str:
        """
        Detect the license tier from the environment variable.

        Returns:
            License tier string ('free', 'pro', or 'enterprise')
        """
        if not self._license_key:
            return self.TIER_FREE

        for prefix, tier in self.VALID_PREFIXES.items():
            if self._license_key.startswith(prefix):
                # Basic validation: ensure there's something after the prefix
                if len(self._license_key) > len(prefix):
                    logger.info(f"Valid {tier} license detected")
                    return tier

        # Invalid format
        logger.warning(f"Invalid license key format: {self._license_key[:15]}...")
        return self.TIER_FREE

    def get_tier(self) -> str:
        """
        Get the current license tier.

        Returns:
            License tier string ('free', 'pro', or 'enterprise')
        """
        return self._tier

    def has_pro_license(self) -> bool:
        """
        Check if user has Pro or Enterprise license.

        Returns:
            True if Pro or Enterprise license is active
        """
        return self._tier in (self.TIER_PRO, self.TIER_ENTERPRISE)

    def has_enterprise_license(self) -> bool:
        """
        Check if user has Enterprise license.

        Returns:
            True if Enterprise license is active
        """
        return self._tier == self.TIER_ENTERPRISE

    def check_feature_access(self, feature_name: str, requires_license: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check if user has access to a feature.

        Args:
            feature_name: Name of the feature (e.g., 'ChatGPT', 'DOCX')
            requires_license: Whether the feature requires a Pro/Enterprise license

        Returns:
            Tuple of (has_access: bool, error_message: Optional[str])
            If has_access is True, error_message is None.
            If has_access is False, error_message contains user-friendly explanation.
        """
        # Features that don't require a license are always accessible
        if not requires_license:
            return True, None

        # Check if user has Pro or Enterprise license
        if self.has_pro_license():
            return True, None

        # User needs a license but doesn't have one
        error_msg = (
            f"{feature_name} is a premium feature that requires a DovOS Pro or Enterprise license. "
            f"Visit https://github.com/mbrichman/dovos for licensing information."
        )
        return False, error_msg

    def get_status(self) -> dict:
        """
        Get license status information.

        Returns:
            Dict with license status details
        """
        return {
            'tier': self._tier,
            'has_pro': self.has_pro_license(),
            'has_enterprise': self.has_enterprise_license(),
            'is_licensed': self._tier != self.TIER_FREE,
            'license_key_present': bool(self._license_key)
        }


# Global license validator instance
_validator: Optional[LicenseValidator] = None


def get_license_validator() -> LicenseValidator:
    """
    Get the global license validator instance.

    Returns:
        LicenseValidator instance
    """
    global _validator
    if _validator is None:
        _validator = LicenseValidator()
    return _validator


def check_feature_license(feature_name: str, requires_license: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to check feature access.

    Args:
        feature_name: Name of the feature
        requires_license: Whether the feature requires a license

    Returns:
        Tuple of (has_access: bool, error_message: Optional[str])
    """
    validator = get_license_validator()
    return validator.check_feature_access(feature_name, requires_license)
