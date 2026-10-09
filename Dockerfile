FROM python:3.12-slim

# Mirror systemd layout: code in /usr/local/share/MetricCollector/src,
# logs in /var/log/metric-collector, runtime user `collector`.
ENV INFLUXDB_HOST=http://influxdb3-core:8181 \
    INFLUXDB_DATABASE=edge_dev_db \
    PYTHONUNBUFFERED=1

WORKDIR /usr/local/share/MetricCollector/src

# psutil wheels are prebuilt, but gcc is needed as fallback on some archs.
# For AMI GPU:
#   wget/gnupg fetch the ROCm repo key; amd-smi-lib provides libamd_smi.so
#   required by the amdsmi Python package at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc wget gnupg ca-certificates \
    && mkdir -p --mode=0755 /etc/apt/keyrings \
    && wget https://repo.radeon.com/rocm/rocm.gpg.key -O - \
        | gpg --dearmor -o /etc/apt/keyrings/rocm.gpg \
    && echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/7.2.4 jammy main' \
        > /etc/apt/sources.list.d/rocm.list \
    && printf 'Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600\n' \
        > /etc/apt/preferences.d/rocm-pin-600 \
    && apt-get update \
    && apt-get install -y --no-install-recommends amd-smi-lib libdrm-amdgpu1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pipenv

COPY Pipfile Pipfile.lock /usr/local/share/MetricCollector/

RUN cd /usr/local/share/MetricCollector && pipenv install --deploy --system && rm -rf /root/.cache

COPY src/main.py ./
COPY src/device_monitor/ ./device_monitor/

RUN useradd --system --no-create-home --shell /usr/sbin/nologin collector \
    && mkdir -p /var/log/metric-collector \
    && chown -R collector:collector /usr/local/share/MetricCollector/src /var/log/metric-collector

USER collector

# INFLUXDB_TOKEN must be supplied at runtime: -e INFLUXDB_TOKEN=... / --influxdb-token
CMD ["python", "main.py", "--log-dir", "/var/log/metric-collector", "--interval", "10"]


# [TODO]
# - [ ] [FIX] Still I am not able to get cpu_percent when I run it in a container
#       2026-10-09 12:38:54,728 WARNING device_monitor.collector: GPU util unavailable for device 0: Error code: 43 | AMDSMI_STATUS_UNEXPECTED_DATA - The data read or provided was unexpected
