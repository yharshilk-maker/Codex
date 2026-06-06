"""Tests for the pipeline orchestrator."""

import logging
import os
import tempfile
import shutil

import pytest
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure we're in project root so relative paths in config resolve
os.chdir(PROJECT_ROOT)


def make_test_config(tmp_dir):
    return {
        "pipeline": {
            "database_path": os.path.join(tmp_dir, "test.db"),
            "csv_output_dir": os.path.join(tmp_dir, "csv"),
            "reports_dir": os.path.join(tmp_dir, "reports"),
            "log_dir": os.path.join(tmp_dir, "logs"),
        },
        "schedule": {
            "analytics_cron": "0 0 * * *",
            "timezone": "America/New_York",
        },
        "data_generation": {
            "num_engines": 10,
            "num_parts": 20,
            "history_years": 1,
        },
    }


def make_logger(tmp_dir):
    log_dir = os.path.join(tmp_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(f"test_pipeline_{id(tmp_dir)}")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(log_dir, "pipeline.log"))
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


@pytest.fixture
def pipeline_env():
    tmp_dir = tempfile.mkdtemp(prefix="pipeline_test_")
    config = make_test_config(tmp_dir)
    logger = make_logger(tmp_dir)
    yield config, logger, tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_run_once_produces_output(pipeline_env):
    """--run-once should execute all stages and produce expected output files."""
    from scheduler.pipeline import run_pipeline_once

    config, logger, tmp_dir = pipeline_env

    # Use absolute paths for pipeline internals
    config["pipeline"]["database_path"] = os.path.join(tmp_dir, "test.db")

    success = run_pipeline_once(config, logger)
    assert success

    assert os.path.exists(os.path.join(tmp_dir, "test.db"))

    csv_dir = os.path.join(tmp_dir, "csv")
    assert os.path.exists(os.path.join(csv_dir, "engines.csv"))
    assert os.path.exists(os.path.join(csv_dir, "work_orders.csv"))

    reports_data = os.path.join(tmp_dir, "reports", "data")
    assert os.path.isdir(reports_data)
    csvs = [f for f in os.listdir(reports_data) if f.endswith(".csv")]
    assert len(csvs) == 5

    reports_parquet = os.path.join(tmp_dir, "reports", "parquet")
    assert os.path.isdir(reports_parquet)


def test_validation_failure_blocks_analytics(pipeline_env):
    """A failed validation should prevent analytics from running."""
    from scheduler.pipeline import job_generate, job_validate, load_config
    from unittest.mock import patch

    config, logger, tmp_dir = pipeline_env
    config["pipeline"]["database_path"] = os.path.join(tmp_dir, "test.db")

    job_generate(config, logger)

    with patch("data_generator.validate.validate", return_value=False):
        from scheduler.pipeline import run_pipeline_once

        # Patch job_generate to skip (already done) and job_validate to fail
        with patch("scheduler.pipeline.job_generate", return_value=True):
            with patch("scheduler.pipeline.job_validate", return_value=False):
                success = run_pipeline_once(config, logger)
                assert not success


def test_config_loads_correctly():
    from scheduler.pipeline import load_config
    config = load_config()
    assert "pipeline" in config
    assert "schedule" in config
    assert "data_generation" in config
    assert config["data_generation"]["num_engines"] == 50


def test_pipeline_logs_created(pipeline_env):
    from scheduler.pipeline import run_pipeline_once

    config, logger, tmp_dir = pipeline_env
    config["pipeline"]["database_path"] = os.path.join(tmp_dir, "test.db")

    run_pipeline_once(config, logger)

    log_path = os.path.join(tmp_dir, "logs", "pipeline.log")
    assert os.path.exists(log_path)
    with open(log_path) as f:
        log_content = f.read()
    assert "Pipeline run started" in log_content
    assert "Pipeline run completed" in log_content
