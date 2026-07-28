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
    parser.add_argument('--batch-size', type=int, default=None)
    args = parser.parse_args()

    config = ConfigLoader()
    db = Database()
    scheduler = Scheduler(db.db_path, config.get_scheduling_config())

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    if args.mode == 'bulk':
        if args.batch_size is None:
            bulk_cfg = config.get_scheduling_config().get('bulk', {})
            try:
                batch_size = int(bulk_cfg.get('batch_size', 20))
            except (ValueError, TypeError):
                batch_size = 20
        else:
            batch_size = args.batch_size
        if batch_size <= 0:
            print("ERROR: batch-size must be a positive integer")
            sys.exit(1)
        count = scheduler.generate_bulk_tasks(today, batch_size)
    else:
        scheduling_cfg = config.get_scheduling_config()
        incremental_cfg = scheduling_cfg.get('incremental', {})
        try:
            max_tasks = int(incremental_cfg.get('max_per_day', 15))
        except (ValueError, TypeError):
            print("ERROR: incremental max_per_day must be a positive integer")
            sys.exit(1)
        if max_tasks <= 0:
            print("ERROR: incremental max_per_day must be a positive integer")
            sys.exit(1)
        count = scheduler.generate_incremental_tasks(today, max_tasks)

    print(f"Generated {count} tasks for {today}")


if __name__ == '__main__':
    main()
