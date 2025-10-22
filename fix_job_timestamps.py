#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.repositories.unit_of_work import get_unit_of_work
from sqlalchemy import text

def fix_timestamps():
    with get_unit_of_work() as uow:
        # Update all pending jobs to be ready now
        result = uow.session.execute(text("""
            UPDATE jobs 
            SET not_before = NOW() - INTERVAL '1 minute'
            WHERE status = 'pending'
        """))
        
        print(f"Updated {result.rowcount} pending jobs to be ready for processing")

if __name__ == "__main__":
    fix_timestamps()