#!/usr/bin/env python3
"""
PostgreSQL Feature Flag Management

This script helps you enable or disable the PostgreSQL backend feature flag
and check the current status.
"""

import os
import sys
import subprocess
from pathlib import Path

def get_current_flag_status():
    """Get the current status of the USE_POSTGRES flag."""
    flag_value = os.getenv('USE_POSTGRES', '').lower()
    if flag_value == 'true':
        return True, "PostgreSQL backend ENABLED"
    elif flag_value == 'false':
        return False, "PostgreSQL backend DISABLED (explicitly)"
    else:
        return False, "PostgreSQL backend DISABLED (default - not set)"

def set_flag_in_shell_profile(enable: bool):
    """Add/update the flag in shell profile files."""
    home = Path.home()
    profiles = ['.zshrc', '.bashrc', '.bash_profile', '.profile']
    
    flag_line = f'export USE_POSTGRES={"true" if enable else "false"}'
    action = "ENABLED" if enable else "DISABLED"
    
    updated_files = []
    
    for profile_name in profiles:
        profile_path = home / profile_name
        
        if profile_path.exists():
            # Read current content
            with open(profile_path, 'r') as f:
                lines = f.readlines()
            
            # Remove existing USE_POSTGRES lines
            new_lines = [line for line in lines if not line.strip().startswith('export USE_POSTGRES')]
            
            # Add new flag line
            new_lines.append(f'\n# PostgreSQL backend feature flag\n{flag_line}\n')
            
            # Write back
            with open(profile_path, 'w') as f:
                f.writelines(new_lines)
            
            updated_files.append(profile_name)
    
    return updated_files, flag_line

def main():
    """Main function to manage the PostgreSQL feature flag."""
    if len(sys.argv) < 2:
        print("PostgreSQL Feature Flag Management")
        print("=" * 40)
        print()
        
        # Show current status
        is_enabled, status_msg = get_current_flag_status()
        print(f"🔍 Current Status: {status_msg}")
        print()
        
        print("Usage:")
        print(f"  {sys.argv[0]} enable   - Enable PostgreSQL backend")
        print(f"  {sys.argv[0]} disable  - Disable PostgreSQL backend") 
        print(f"  {sys.argv[0]} status   - Show current status")
        print(f"  {sys.argv[0]} test     - Run integration test")
        print()
        print("Environment Variable Control:")
        print("  export USE_POSTGRES=true   # Enable")
        print("  export USE_POSTGRES=false  # Disable")
        print("  unset USE_POSTGRES         # Use default (disabled)")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        is_enabled, status_msg = get_current_flag_status()
        print(f"🔍 {status_msg}")
        
        if is_enabled:
            print("✅ Your application will use the PostgreSQL backend")
            print("📊 Features available:")
            print("   • Hybrid semantic + full-text search")
            print("   • Background embedding generation")  
            print("   • PostgreSQL vector similarity")
            print("   • Enterprise-grade database features")
        else:
            print("⚠️  Your application will use the legacy ChromaDB/SQLite backend")
            print("💡 To enable PostgreSQL: python manage_postgres_flag.py enable")
    
    elif command == "enable":
        # Set in shell profiles
        updated_files, flag_line = set_flag_in_shell_profile(True)
        
        # Set in current environment
        os.environ['USE_POSTGRES'] = 'true'
        
        print("🚀 PostgreSQL backend ENABLED!")
        print(f"📝 Added '{flag_line}' to:")
        for file in updated_files:
            print(f"   • {file}")
        
        print()
        print("⚡ To apply immediately:")
        print("   source ~/.zshrc  # or source ~/.bashrc")
        print()
        print("🔄 Or restart your terminal/application")
        print()
        print("🧪 Test the setup:")
        print(f"   {sys.argv[0]} test")
    
    elif command == "disable":
        # Set in shell profiles
        updated_files, flag_line = set_flag_in_shell_profile(False)
        
        # Set in current environment
        os.environ['USE_POSTGRES'] = 'false'
        
        print("🛑 PostgreSQL backend DISABLED!")
        print(f"📝 Added '{flag_line}' to:")
        for file in updated_files:
            print(f"   • {file}")
        
        print()
        print("⚡ To apply immediately:")
        print("   source ~/.zshrc  # or source ~/.bashrc")
        print()
        print("🔄 Or restart your terminal/application")
        print("📚 Application will use legacy ChromaDB/SQLite backend")
    
    elif command == "test":
        print("🧪 Running PostgreSQL integration test...")
        
        # Set flag for this test
        os.environ['USE_POSTGRES'] = 'true'
        
        try:
            # Run the manual test
            result = subprocess.run([
                sys.executable, 'test_manual_chat_import.py'
            ], cwd=os.path.dirname(__file__), capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ PostgreSQL integration test PASSED!")
                print("🎉 Your PostgreSQL backend is working correctly")
            else:
                print("❌ PostgreSQL integration test FAILED!")
                print("Error output:")
                print(result.stderr)
                
        except FileNotFoundError:
            print("❌ test_manual_chat_import.py not found")
            print("💡 Make sure you're running this from the project root directory")
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("💡 Use: enable, disable, status, or test")

if __name__ == "__main__":
    main()