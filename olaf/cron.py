from olaf.db import Connection
from olaf.tools.safe_eval import safe_eval
from multiprocessing import Pool, TimeoutError
from datetime import datetime, timedelta
import threading
import logging
import time
import os

logger = logging.getLogger(__name__)


class SchedulerMeta(type):
    """ This class ensures there's always a single
    instance of the Scheduler class along the entire
    application. 
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SchedulerMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Scheduler(metaclass=SchedulerMeta):
    """ A scheduler for running planned tasks
    """

    def __init__(self, timeout=60, heartbeat=-1):
        self.timeout = timeout
        self.jobs = None
        self.heartbeat = heartbeat
        self.start()

    def start(self):
        # Prevent reinitializing scheduler with this method
        if self.jobs is not None:
            return

        conn = Connection()

        # Get all active jobs
        jobs = conn.db["base.cron"].find({"active": True})

        # Update all nextcalls older than current time
        for job in jobs:
            now = datetime.now()
            if now > job["nextcall"]:
                new_nextcall = now + timedelta(seconds=job["interval"])
                conn.db["base.cron"].update_one(
                    {"_id": job["_id"]},
                    {"$set": {"nextcall": new_nextcall }})
                
        # Iterate again to get updated values    
        # and load them into memory
        jobs.rewind()
        self.jobs = dict()
        for job in jobs:
            self.jobs[job["_id"]] = job

        self.running = True
        self.process = threading.Thread(
            name="SchedulerLoop", target=self.loop)
        self.process.start()

    def stop(self):
        self.running = False
        self.jobs = None
        while self.process.is_alive():
            time.sleep(1)

    def reset(self):
        self.stop()
        self.start()

    def loop(self):
        conn = Connection()
        logger.debug("Starting Scheduler Loop")
        # Initialize Heartbeat
        if self.heartbeat > 0:
            next_hb = datetime.now() + timedelta(seconds=self.heartbeat)
        while self.running:
            for job_id, job in self.jobs.items():
                # Nextcall overpassed, execute job
                if datetime.now() > job["nextcall"]:
                    self.run(job)
                    new_nextcall = datetime.now() + timedelta(seconds=job["interval"])
                    # Update Internal Value
                    self.jobs[job_id]["nextcall"] = new_nextcall
                    # Update Database Entry
                    conn.db["base.cron"].update_one(
                        {"_id": job_id},
                        {"$set": {"nextcall": new_nextcall}})
            # Handle Heartbeat
            if self.heartbeat > 0:
                if datetime.now() > next_hb:
                    logger.info("Scheduler Heartbeat")
                    next_hb = datetime.now() + timedelta(seconds=self.heartbeat)
            time.sleep(1)
        logger.debug("Scheduler Loop has been terminated")

    def run(self, job):
        logger.info("Running job {} ({})...".format(job["_id"], job["name"]))
        safe_eval(job["code"], {"datetime": datetime, "timedelta": timedelta, "logger": logger})
        
