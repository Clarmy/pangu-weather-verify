from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

from pwv.main import main

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    job = scheduler.add_job(main, "interval", hours=1)
    for job in scheduler.get_jobs():
        job.modify(next_run_time=datetime.now())
    scheduler.start()
