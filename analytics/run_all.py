"""Entry point that runs all 5 analytics jobs and saves results."""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(csv_dir=None, reports_dir=None):
    from analytics.spark_session import create_spark_session, load_tables
    from analytics.fleet_analytics import (
        failure_rate_heatmap,
        part_lifecycle_curve,
        maintenance_cost_forecast,
        fleet_availability_score,
        anomaly_detection_flags,
    )

    if reports_dir is None:
        reports_dir = os.path.join(PROJECT_ROOT, "reports")

    csv_out = os.path.join(reports_dir, "data")
    parquet_out = os.path.join(reports_dir, "parquet")
    os.makedirs(csv_out, exist_ok=True)
    os.makedirs(parquet_out, exist_ok=True)

    spark = create_spark_session()
    tables = load_tables(spark, csv_dir)

    jobs = [
        ("failure_rate_heatmap", failure_rate_heatmap),
        ("part_lifecycle_curve", part_lifecycle_curve),
        ("maintenance_cost_forecast", maintenance_cost_forecast),
        ("fleet_availability_score", fleet_availability_score),
        ("anomaly_detection_flags", anomaly_detection_flags),
    ]

    results = {}
    failed = False

    for name, fn in jobs:
        print(f"Running {name}...")
        start = time.time()
        try:
            df = fn(spark, tables)
            elapsed = time.time() - start
            row_count = df.count()
            print(f"  {name}: {row_count} rows in {elapsed:.1f}s")

            pdf = df.toPandas()
            pdf.to_csv(os.path.join(csv_out, f"{name}.csv"), index=False)
            df.write.mode("overwrite").parquet(os.path.join(parquet_out, name))

            results[name] = df
        except Exception as e:
            elapsed = time.time() - start
            print(f"  FAILED {name} after {elapsed:.1f}s: {e}")
            failed = True

    spark.stop()

    if failed:
        print("\nSome jobs failed.")
        sys.exit(1)
    else:
        print(f"\nAll {len(jobs)} jobs completed. Output in {reports_dir}")
        return results


if __name__ == "__main__":
    run()
