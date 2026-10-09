import argparse
import logging
import os
import socket
import time

from influxdb_client_3 import InfluxDBClient3, Point, PointSettings

from device_monitor import collector
from device_monitor.logsetup import configure_logging

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 10

# No secrets here: host/db have local defaults, token comes from env/args only.
ENDPOINT = os.getenv("INFLUXDB_HOST", "http://127.0.0.1:8181")
DATABASE = os.getenv("INFLUXDB_DATABASE", "edge_dev_db")


def collect_metrics():
    points = []

    cpu = collector.collect_cpu_metrics()
    points.append(
        Point("cpu")
        .field("total", cpu["total"])
        .field("user", cpu["user_percent"])
        .field("system", cpu["system_percent"])
        .field("iowait", cpu["iowait_percent"])
    )

    try:
        gpus_metric = collector.collect_gpu_metrics()
    except Exception as e:
        logger.warning("GPU collection failed, continuing without GPU metrics: %s", e)
        gpus_metric = {}
    for i, m in gpus_metric.items():
        points.append(
            Point("gpu")
            .tag("gpu_id", str(i))
            .tag("gpu_name", str(m.get("name", "unknown")))
            .field("gpu_percent", m["gpu_percent"])
            .field("memory_percent", m["memory_percent"])
            .field("vram_memory_usage", m["vram_memory_usage"])
            .field("vram_memory_total", m["vram_memory_total"])
            .field("temperature", m["temperature"])
        )

    memory_metric = collector.collect_mem_metrics()
    points.append(
        Point("memory")
        .field("percent", memory_metric["percent"])
        .field("used_mb", memory_metric["used_mb"])
        .field("total_mb", memory_metric["total_mb"])
    )

    disk_metric = collector.collect_disk_metrics()
    for path, metric in disk_metric.items():
        points.append(
            Point("disk")
            .tag("path", path)
            .field("percent", metric["percent"])
            .field("used_gb", metric["used_gb"])
            .field("total_gb", metric["total_gb"])
        )

    # A point with no fields (all values None) serializes to "" and
    # InfluxDB rejects it, so drop such points.
    return [p for p in points if p.to_line_protocol()]


def build_parser():
    parser = argparse.ArgumentParser(
        prog="Device metric collector",
        description="Collects hardware devices' metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--log-file", default="collector.log", help="Set log file name")
    parser.add_argument("--log-dir", default="./log", help="Set log directory")

    parser.add_argument(
        "--interval",
        type=int,
        default=INTERVAL_SECONDS,
        help="Collecting Interval in second",
    )

    hostname = socket.gethostname()
    parser.add_argument("--name", default=hostname, help="Device name")
    parser.add_argument("--city", default="Dublin", help="City the device is located")
    parser.add_argument(
        "--region", default="Leinster", help="Region the device is located"
    )
    parser.add_argument("--country", default="IE", help="Country the device is located")

    parser.add_argument("--influxdb-host", default=ENDPOINT, help="InfluxDB URL")
    parser.add_argument(
        "--influxdb-token",
        default=os.getenv("INFLUXDB_TOKEN"),
        help="InfluxDB access TOKEN (or INFLUXDB_TOKEN env)",
    )
    parser.add_argument("--influxdb-db", default=DATABASE, help="InfluxDB Database")
    parser.add_argument(
        "-v", "--verbose", action="count", default=1, help="Verbose level"
    )

    return parser


def main():

    parser = build_parser()
    args = parser.parse_args()

    configure_logging(
        log_file=args.log_file, log_dir=args.log_dir, verbosity=args.verbose
    )

    logger.info("Starting collector process...")

    use_influx = bool(args.influxdb_host and args.influxdb_token and args.influxdb_db)
    client = None
    if use_influx:
        client = InfluxDBClient3(
            host=args.influxdb_host,
            token=args.influxdb_token,
            database=args.influxdb_db,
            point_settings=PointSettings(
                device=args.name,
                city=args.city,
                region=args.region,
                country=args.country,
            ),
        )
    else:
        logger.error("No InfluxDB config given, exit the program.")
        return

    try:
        while True:
            try:
                points = collect_metrics()

                if args.verbose == 2:
                    for point in points:
                        logging.debug(point.to_line_protocol())

                if client is not None:
                    if points:
                        client.write(points)

            except Exception as e:
                logger.error("Error in metrics daemon: %s", e, exc_info=True)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Collector stopped.")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
