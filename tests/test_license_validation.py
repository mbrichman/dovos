"""
Test script to demonstrate license validation functionality.

Run this to verify that license checking is working correctly.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_license_validation():
    """Test license validation with different scenarios."""
    from utils.license import get_license_validator, check_feature_license
    from importlib import reload
    import utils.license

    print("=" * 60)
    print("License Validation Test")
    print("=" * 60)

    # Scenario 1: No license key
    print("\n1. Testing WITHOUT license key...")
    os.environ.pop('DOVOS_LICENSE_KEY', None)
    reload(utils.license)

    validator = utils.license.get_license_validator()
    status = validator.get_status()
    print(f"   Tier: {status['tier']}")
    print(f"   Has Pro: {status['has_pro']}")
    print(f"   Is Licensed: {status['is_licensed']}")

    has_access, error = utils.license.check_feature_license('ChatGPT', requires_license=True)
    print(f"   ChatGPT Access: {has_access}")
    if error:
        print(f"   Error: {error}")

    # Scenario 2: With Pro license
    print("\n2. Testing WITH Pro license...")
    os.environ['DOVOS_LICENSE_KEY'] = 'DOVOS-PRO-test123'
    reload(utils.license)

    validator = utils.license.get_license_validator()
    status = validator.get_status()
    print(f"   Tier: {status['tier']}")
    print(f"   Has Pro: {status['has_pro']}")
    print(f"   Is Licensed: {status['is_licensed']}")

    has_access, error = utils.license.check_feature_license('ChatGPT', requires_license=True)
    print(f"   ChatGPT Access: {has_access}")

    # Scenario 3: With Enterprise license
    print("\n3. Testing WITH Enterprise license...")
    os.environ['DOVOS_LICENSE_KEY'] = 'DOVOS-ENT-enterprise123'
    reload(utils.license)

    validator = utils.license.get_license_validator()
    status = validator.get_status()
    print(f"   Tier: {status['tier']}")
    print(f"   Has Enterprise: {status['has_enterprise']}")
    print(f"   Is Licensed: {status['is_licensed']}")

    has_access, error = utils.license.check_feature_license('DOCX', requires_license=True)
    print(f"   DOCX Access: {has_access}")

    # Scenario 4: Invalid license key
    print("\n4. Testing WITH invalid license key...")
    os.environ['DOVOS_LICENSE_KEY'] = 'INVALID-KEY-123'
    reload(utils.license)

    validator = utils.license.get_license_validator()
    status = validator.get_status()
    print(f"   Tier: {status['tier']}")
    print(f"   Has Pro: {status['has_pro']}")

    # Scenario 5: Free features (always accessible)
    print("\n5. Testing free features...")
    os.environ.pop('DOVOS_LICENSE_KEY', None)
    reload(utils.license)

    has_access, error = utils.license.check_feature_license('Claude', requires_license=False)
    print(f"   Claude Access (free feature): {has_access}")

    has_access, error = utils.license.check_feature_license('OpenWebUI', requires_license=False)
    print(f"   OpenWebUI Access (free feature): {has_access}")

    print("\n" + "=" * 60)
    print("✅ All license validation tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    test_license_validation()
