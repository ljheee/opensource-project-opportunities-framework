#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


def main():
    db = Database()
    db.init_tables()
    db.repair_analyzing_status()
    db.repair_orphan_records()
    print("Database initialized successfully.")


if __name__ == '__main__':
    main()
