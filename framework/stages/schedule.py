#!/usr/bin/env python3
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scheduler import Scheduler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['bulk', 'incremental'], default='incremental')
    parser.add_argument('--batch-size', type=int, default=20)
    args = parser.parse_args()

    config = ConfigLoader()
    db = Database()
    scheduler = Scheduler(db.db_path, config.get_scheduling_config())

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    if args.mode == 'bulk':
        count = scheduler.generate_bulk_tasks(today, args.batch_size)
    else:
        max_tasks = config.get_scheduling_config()['incremental']['max_per_day']
        count = scheduler.generate_incremental_tasks(today, max_tasks)

    print(f"Generated {count} tasks for {today}")


if __name__ == '__main__':
    main()
