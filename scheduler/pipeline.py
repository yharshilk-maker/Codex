"""APScheduler-based pipeline orchestrator for sustainment analytics."""

import argparse
import logging
import os
import sys
import time

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_config(config_path=None):
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "scheduler", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def setup_logging(log_dir):
    log_dir = os.path.join(PROJECT_ROOT, log_dir)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "pipeline.log")

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(log_path)
        fh.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


def job_generate(config, logger):
    logger.info("Job 1: Data Generation — starting")
    start = time.time()

    from data_generator.generate import run as generate_data

    gen_cfg = config["data_generation"]
    pipe_cfg = config["pipeline"]
    db_path = os.path.join(PROJECT_ROOT, pipe_cfg["database_path"])
    csv_dir = os.path.join(PROJECT_ROOT, pipe_cfg["csv_output_dir"])

    generate_data(
        db_path=db_path,
        csv_dir=csv_dir,
        num_engines=gen_cfg["num_engines"],
        history_years=gen_cfg["history_years"],
    )
    elapsed = time.time() - start
    logger.info(f"Job 1: Data Generation — completed in {elapsed:.1f}s")
    return True


def job_validate(config, logger):
    logger.info("Job 2: Data Validation — starting")
    start = time.time()

    from data_generator.validate import validate

    pipe_cfg = config["pipeline"]
    db_path = os.path.join(PROJECT_ROOT, pipe_cfg["database_path"])
    success = validate(db_path)

    elapsed = time.time() - start
    if success:
        logger.info(f"Job 2: Data Validation — passed in {elapsed:.1f}s")
    else:
        logger.error(f"Job 2: Data Validation — FAILED in {elapsed:.1f}s")
    return success


def job_analytics(config, logger):
    logger.info("Job 3: PySpark Analytics — starting")
    start = time.time()

    from analytics.run_all import run as run_analytics

    pipe_cfg = config["pipeline"]
    csv_dir = os.path.join(PROJECT_ROOT, pipe_cfg["csv_output_dir"])
    reports_dir = os.path.join(PROJECT_ROOT, pipe_cfg["reports_dir"])

    run_analytics(csv_dir=csv_dir, reports_dir=reports_dir)

    elapsed = time.time() - start
    logger.info(f"Job 3: PySpark Analytics — completed in {elapsed:.1f}s")
    return True


def job_report(config, logger):
    logger.info("Job 4: Report Generation — starting")
    start = time.time()

    pipe_cfg = config["pipeline"]
    reports_dir = os.path.join(PROJECT_ROOT, pipe_cfg["reports_dir"])

    try:
        from reports.generate_report import generate_all
        generate_all(reports_dir=reports_dir)
    except ImportError:
        logger.info("Job 4: Report module not yet implemented — skipping visualization")

    elapsed = time.time() - start
    logger.info(f"Job 4: Report Generation — completed in {elapsed:.1f}s")
    return True


def run_pipeline_once(config, logger):
    """Execute the full pipeline sequentially with job chaining."""
    logger.info("=== Pipeline run started ===")
    overall_start = time.time()

    steps = [
        ("generate", job_generate),
        ("validate", job_validate),
        ("analytics", job_analytics),
        ("report", job_report),
    ]

    for name, fn in steps:
        try:
            success = fn(config, logger)
            if not success:
                logger.error(f"Pipeline halted: {name} failed — skipping downstream jobs")
                return False
        except Exception as e:
            logger.error(f"Pipeline halted: {name} raised {type(e).__name__}: {e}")
            return False

    elapsed = time.time() - overall_start
    logger.info(f"=== Pipeline run completed in {elapsed:.1f}s ===")
    return True


def run_scheduled(config, logger):
    """Start the APScheduler daemon with cron-triggered analytics."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched_cfg = config["schedule"]
    cron_expr = sched_cfg["analytics_cron"]
    tz = sched_cfg["timezone"]

    # Parse cron: "minute hour day month day_of_week"
    parts = cron_expr.split()
    trigger = CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4], timezone=tz,
    )

    scheduler = BackgroundScheduler(timezone=tz)

    def scheduled_run():
        try:
            run_pipeline_once(config, logger)
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}")

    scheduler.add_job(scheduled_run, trigger, id="pipeline_cron", name="Sustainment Pipeline")
    scheduler.start()

    logger.info(f"Scheduler started — cron: '{cron_expr}' ({tz})")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def main():
    os.chdir(PROJECT_ROOT)

    parser = argparse.ArgumentParser(description="Sustainment Analytics Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-once", action="store_true", help="Run the full pipeline once and exit")
    group.add_argument("--schedule", action="store_true", help="Start the scheduler daemon")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config["pipeline"]["log_dir"])

    if args.run_once:
        success = run_pipeline_once(config, logger)
        sys.exit(0 if success else 1)
    elif args.schedule:
        run_scheduled(config, logger)


if __name__ == "__main__":
    main()
