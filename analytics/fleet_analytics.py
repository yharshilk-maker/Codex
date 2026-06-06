"""Five PySpark analytics jobs for fleet sustainment analysis."""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def failure_rate_heatmap(spark: SparkSession, tables: dict) -> DataFrame:
    """
    Group unscheduled work orders by (engine_model, part_category, quarter)
    to produce a pivot-ready DataFrame showing where failures cluster.
    """
    work_orders = tables["work_orders"]
    engines = tables["engines"]
    part_replacements = tables["part_replacements"]
    parts = tables["parts"]

    unscheduled = work_orders.filter(F.col("event_type") == "Unscheduled")

    joined = (
        unscheduled
        .join(engines, "engine_id")
        .join(part_replacements, "work_order_id")
        .join(parts, "part_id")
    )

    result = (
        joined
        .withColumn("quarter", F.concat(
            F.year("open_date").cast("string"),
            F.lit("-Q"),
            F.quarter("open_date").cast("string")
        ))
        .groupBy("engine_model", "part_category", "quarter")
        .agg(
            F.count("*").alias("failure_count"),
            F.sum("quantity").alias("parts_replaced"),
        )
        .orderBy("engine_model", "part_category", "quarter")
    )
    return result


def part_lifecycle_curve(spark: SparkSession, tables: dict) -> DataFrame:
    """
    For each part, calculate Kaplan-Meier-style survival percentages
    at flight-hour intervals.
    """
    part_replacements = tables["part_replacements"]
    parts = tables["parts"]

    replacement_hours = (
        part_replacements
        .join(parts, "part_id")
        .select("part_id", "part_name", "mean_time_between_failure_hours", "flight_hours_at_replacement")
    )

    # Bucket into 2500-hour intervals
    bucketed = replacement_hours.withColumn(
        "hour_bucket", (F.floor(F.col("flight_hours_at_replacement") / 2500) * 2500).cast("int")
    )

    total_per_part = bucketed.groupBy("part_id", "part_name").agg(
        F.count("*").alias("total_replacements")
    )

    failures_by_bucket = bucketed.groupBy("part_id", "hour_bucket").agg(
        F.count("*").alias("failures_in_bucket")
    )

    # Cumulative failures via window
    w = Window.partitionBy("part_id").orderBy("hour_bucket").rowsBetween(Window.unboundedPreceding, Window.currentRow)

    result = (
        failures_by_bucket
        .withColumn("cumulative_failures", F.sum("failures_in_bucket").over(w))
        .join(total_per_part, "part_id")
        .withColumn(
            "survival_pct",
            F.round((1.0 - F.col("cumulative_failures") / F.col("total_replacements")) * 100, 1)
        )
        .select("part_id", "part_name", "hour_bucket", "failures_in_bucket",
                "cumulative_failures", "total_replacements", "survival_pct")
        .orderBy("part_id", "hour_bucket")
    )
    return result


def maintenance_cost_forecast(spark: SparkSession, tables: dict) -> DataFrame:
    """
    Rolling 6-month average cost per engine model, projected forward 3 months
    using linear trend via PySpark window functions.
    """
    work_orders = tables["work_orders"]
    engines = tables["engines"]
    part_replacements = tables["part_replacements"]
    parts = tables["parts"]

    monthly_cost = (
        work_orders
        .join(engines, "engine_id")
        .join(part_replacements, "work_order_id")
        .join(parts, "part_id")
        .withColumn("month", F.date_trunc("month", F.col("open_date")))
        .groupBy("engine_model", "month")
        .agg(F.round(F.sum(F.col("quantity") * F.col("unit_cost_usd")), 2).alias("monthly_cost"))
    )

    w6 = Window.partitionBy("engine_model").orderBy("month").rowsBetween(-5, 0)

    with_rolling = monthly_cost.withColumn(
        "rolling_6m_avg", F.round(F.avg("monthly_cost").over(w6), 2)
    )

    # Linear trend: slope = (last - first) / 5 over the 6-month window
    w_first = Window.partitionBy("engine_model").orderBy("month").rowsBetween(-5, -5)
    w_last = Window.partitionBy("engine_model").orderBy("month").rowsBetween(0, 0)

    with_trend = (
        with_rolling
        .withColumn("first_val", F.avg("monthly_cost").over(w_first))
        .withColumn("last_val", F.avg("monthly_cost").over(w_last))
        .withColumn("monthly_slope", F.round((F.col("last_val") - F.col("first_val")) / 5, 2))
    )

    # Get the latest month per model to project from
    latest = with_trend.groupBy("engine_model").agg(F.max("month").alias("month"))
    latest_data = with_trend.join(latest, ["engine_model", "month"])

    # Project 1, 2, 3 months ahead
    projections = []
    for i in range(1, 4):
        proj = (
            latest_data
            .withColumn("month", F.add_months(F.col("month"), i))
            .withColumn("monthly_cost", F.lit(None).cast("double"))
            .withColumn(
                "rolling_6m_avg",
                F.round(F.col("rolling_6m_avg") + F.col("monthly_slope") * i, 2)
            )
        )
        projections.append(proj)

    from functools import reduce
    all_months = reduce(
        lambda a, b: a.unionByName(b, allowMissingColumns=True),
        [with_trend] + projections
    )

    result = (
        all_months
        .select("engine_model", "month", "monthly_cost", "rolling_6m_avg", "monthly_slope")
        .orderBy("engine_model", "month")
    )
    return result


def fleet_availability_score(spark: SparkSession, tables: dict) -> DataFrame:
    """
    For each month, calculate % of engines Active vs In MRO, by fleet type.
    Uses work order open/close dates to infer MRO periods.
    """
    engines = tables["engines"]
    work_orders = tables["work_orders"]

    # Get the overall date range
    date_range = work_orders.agg(
        F.min("open_date").alias("min_date"),
        F.max("open_date").alias("max_date"),
    ).collect()[0]

    min_date = date_range["min_date"]
    max_date = date_range["max_date"]

    # Generate month spine
    months_df = spark.sql(
        f"SELECT explode(sequence(to_date('{min_date}'), to_date('{max_date}'), interval 1 month)) as month"
    )

    # Cross join engines with months
    engine_months = engines.select("engine_id", "fleet").crossJoin(months_df)

    # An engine is "In MRO" for a month if it has an open work order (Overhaul or Unscheduled)
    # that overlaps that month
    mro_events = work_orders.filter(
        F.col("event_type").isin("Overhaul", "Unscheduled")
    ).select("engine_id", "open_date", "close_date")

    in_mro = (
        engine_months.alias("em")
        .join(
            mro_events.alias("mro"),
            (F.col("em.engine_id") == F.col("mro.engine_id"))
            & (F.col("mro.open_date") <= F.last_day(F.col("em.month")))
            & (F.col("mro.close_date") >= F.col("em.month")),
            "left"
        )
        .withColumn("is_in_mro", F.when(F.col("mro.open_date").isNotNull(), 1).otherwise(0))
        .groupBy(F.col("em.engine_id"), F.col("em.fleet"), F.col("em.month"))
        .agg(F.max("is_in_mro").alias("in_mro_flag"))
    )

    result = (
        in_mro
        .groupBy("month", "fleet")
        .agg(
            F.count("*").alias("total_engines"),
            F.sum("in_mro_flag").alias("in_mro_count"),
            F.round(
                (1.0 - F.sum("in_mro_flag") / F.count("*")) * 100, 1
            ).alias("availability_pct"),
        )
        .orderBy("month", "fleet")
    )
    return result


def anomaly_detection_flags(spark: SparkSession, tables: dict) -> DataFrame:
    """
    Flag part replacements where flight_hours_at_replacement < 50% of MTBF
    (premature failure), returning engine_id, part_id, and severity score.
    """
    part_replacements = tables["part_replacements"]
    parts = tables["parts"]
    work_orders = tables["work_orders"]

    joined = (
        part_replacements
        .join(parts, "part_id")
        .join(work_orders.select("work_order_id", "engine_id"), "work_order_id")
    )

    flagged = joined.filter(
        F.col("flight_hours_at_replacement") < 0.5 * F.col("mean_time_between_failure_hours")
    )

    # Severity: how far below 50% MTBF — lower ratio = higher severity (1-10 scale)
    result = (
        flagged
        .withColumn(
            "ratio_to_mtbf",
            F.round(F.col("flight_hours_at_replacement") / F.col("mean_time_between_failure_hours"), 3)
        )
        .withColumn(
            "severity_score",
            F.round(F.lit(10) * (1.0 - F.col("ratio_to_mtbf") / 0.5), 1)
        )
        .select(
            "engine_id", "part_id", "part_name", "part_category",
            "work_order_id", "flight_hours_at_replacement",
            "mean_time_between_failure_hours", "ratio_to_mtbf", "severity_score"
        )
        .orderBy(F.desc("severity_score"))
    )
    return result
