import json
import logging
import os
from contextlib import contextmanager

import amdsmi
import psutil
import pynvml

logger = logging.getLogger(__name__)

GPU_TYPE_NVIDIA = "NVIDIA"
GPU_TYPE_AMD = "AMD"
GPU_TYPE_INTEL = "INTEL"


def detect_gpu_via_sysfs():
    drm_path = "/sys/class/drm"
    if not os.path.exists(drm_path):
        return "Unknown (No DRM sub-system)"

    gpu_type = None
    for folder in os.listdir(drm_path):
        if folder.startswith("card") and "-" not in folder:
            vendor_file = os.path.join(drm_path, folder, "device/vendor")

            if os.path.exists(vendor_file):
                with open(vendor_file, "r") as f:
                    vendor_id = f.read().strip().lower()

                # Matching PCI Vendor ID
                if "0x1002" in vendor_id:
                    gpu_type = GPU_TYPE_AMD
                elif "0x10de" in vendor_id:
                    gpu_type = GPU_TYPE_NVIDIA
                elif "0x8086" in vendor_id:
                    gpu_type = GPU_TYPE_INTEL
                else:
                    pass

    return gpu_type


@contextmanager
def gpu_session():
    """Own the GPU driver lifecycle. Replaces initialize_gpu()/shutdown_gpu().

    Usage:
        with gpu_session() as gpu_type:
            if gpu_type == GPU_TYPE_NVIDIA:
                collect_nvidia_gpu_metrics()
            elif gpu_type == GPU_TYPE_AMD:
                collect_amd_gpu_metrics()
    """
    gpu_type = detect_gpu_via_sysfs()
    initialized = False

    if gpu_type == GPU_TYPE_NVIDIA:
        # https://codesamplez.com/programming/nvml-python-api-tutorial
        try:
            pynvml.nvmlInit()
            initialized = True
            logger.info("NVML initialized successfully")
        except pynvml.NVMLError as e:
            logger.warning("Unable to initialize NVML: %s", e)
            raise
    elif gpu_type == GPU_TYPE_AMD:
        try:
            amdsmi.amdsmi_init()
            initialized = True
            logger.debug("AMD SMI initialized successfully")
        except amdsmi.AmdSmiException as e:
            logger.warning("Unable to initialize AMD SMI: %s", e)
            raise
    else:
        logger.info("No supported GPU to initialize (detected: %s)", gpu_type)

    try:
        yield gpu_type
    finally:
        if not initialized:
            return
        if gpu_type == GPU_TYPE_NVIDIA:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError as e:
                logger.warning("Failed to shut down NVML: %s", e)
        elif gpu_type == GPU_TYPE_AMD:
            try:
                amdsmi.amdsmi_shut_down()
            except amdsmi.AmdSmiException as e:
                logger.warning("Failed to shut down AMD SMI: %s", e)


def collect_nvidia_gpu_metrics():
    """Requires an active `gpu_session()`. Returns {index: metrics}."""
    metrics = {}
    device_count = pynvml.nvmlDeviceGetCount()
    for i in range(device_count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")

        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except pynvml.NVMLError as e:
            logger.warning("Unable to get temperature of %s GPU: %s", i, e)
            temp = None

        metrics[i] = {
            "name": name,
            "gpu_percent": util.gpu,
            "memory_percent": util.memory,
            "vram_memory_usage": mem_info.used,
            "vram_memory_total": mem_info.total,
            "temperature": temp,
        }

    return metrics


def collect_amd_gpu_metrics():
    """Requires an active `gpu_session()`. Returns {index: metrics}."""
    metrics = {}

    handles = amdsmi.amdsmi_get_processor_handles()

    if len(handles) == 0:
        return metrics

    for i, device in enumerate(handles):
        metrics[i] = {}

        name = amdsmi.amdsmi_get_gpu_asic_info(device)["market_name"]

        vram_memory_usage = amdsmi.amdsmi_get_gpu_memory_usage(
            device, amdsmi.AmdSmiMemoryType.VRAM
        )
        vram_memory_total = amdsmi.amdsmi_get_gpu_memory_total(
            device, amdsmi.AmdSmiMemoryType.VRAM
        )

        temp = amdsmi.amdsmi_get_temp_metric(
            device,
            amdsmi.AmdSmiTemperatureType.EDGE,
            amdsmi.AmdSmiTemperatureMetric.CURRENT,
        )

        try:
            if hasattr(amdsmi, "amdsmi_get_gpu_busy_percent"):
                gpu_util = amdsmi.amdsmi_get_gpu_busy_percent(device)
            else:
                # amdsmi 7.0.2 (PyPI) has no busy_percent; gfx_activity is equivalent.
                activity = amdsmi.amdsmi_get_gpu_activity(device)
                gpu_util = activity.get("gfx_activity")
        except Exception as e:
            # I do not want to have mutiple lines of error message
            logger.warning(
                "GPU util unavailable for device %s: %s", i, " ".join(str(e).split())
            )
            gpu_util = None
        if gpu_util == "N/A":
            gpu_util = None

        metrics[i] = {
            "name": name,
            "gpu_percent": gpu_util,
            "memory_percent": round(vram_memory_usage / vram_memory_total * 100, 2),
            "vram_memory_usage": vram_memory_usage,
            "vram_memory_total": vram_memory_total,
            "temperature": temp,
        }

    return metrics


def collect_gpu_metrics():
    """Dispatch to the matching collect_* based on detected GPU."""
    with gpu_session() as gpu_type:
        if gpu_type == GPU_TYPE_NVIDIA:
            return collect_nvidia_gpu_metrics()
        elif gpu_type == GPU_TYPE_AMD:
            return collect_amd_gpu_metrics()
        else:
            logger.warning("Unsupported GPU type: %s, no metrics collected", gpu_type)
            return {}


def collect_cpu_metrics():
    cpu_times = psutil.cpu_times_percent(interval=None)
    metrics = {
        "total": psutil.cpu_percent(interval=None),
        "user_percent": cpu_times.user,
        "system_percent": cpu_times.system,
        "iowait_percent": getattr(cpu_times, "iowait", 0.0),
    }
    return metrics


def collect_disk_metrics(path="/"):
    disk_usage = psutil.disk_usage(path)

    metrics = {
        path: {
            "percent": disk_usage.percent,
            "used_gb": round(disk_usage.used / (1024**3), 2),
            "total_gb": round(disk_usage.total / (1024**3), 2),
        }
    }

    return metrics


def collect_mem_metrics():

    mem = psutil.virtual_memory()

    metrics = {
        "percent": mem.percent,
        "used_mb": round(mem.used / (1024**2), 1),
        "total_mb": round(mem.total / (1024**2), 1),
    }

    return metrics


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    gpu_metrics = collect_gpu_metrics()
    logging.debug("Collected GPU metrics: %s", json.dumps(gpu_metrics))

    cpu_metrics = collect_cpu_metrics()
    logging.debug("Collected CPU metrics: %s", json.dumps(cpu_metrics))

    mem_metrics = collect_mem_metrics()
    logging.debug("Collected memory metrics: %s", json.dumps(mem_metrics))

    disk_metrics = collect_disk_metrics()
    logging.debug("Collected disk metric: %s", json.dumps(disk_metrics))

    metrics = {
        "gpu": gpu_metrics,
        "cpu": cpu_metrics,
        "memory": mem_metrics,
        "disk": disk_metrics,
    }

    logging.info("Collected metrics: %s", json.dumps(metrics))

    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
