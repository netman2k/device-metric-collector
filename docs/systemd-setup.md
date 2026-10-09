# Run MetricCollector with systemd

Runs `src/main.py` as a system service under dedicated user `collector`.

## 1. Install code

```bash
sudo mkdir -p /usr/local/share/MetricCollector
sudo cp -r src Pipfile /usr/local/share/MetricCollector/
sudo chown -R root:collector /usr/local/share/MetricCollector
sudo chmod -R 750 /usr/local/share/MetricCollector
```

Project layout expected:

```text
/usr/local/share/MetricCollector/src/main.py
/usr/local/share/MetricCollector/src/device_monitor/
```

## 2. Create service user

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin collector
# Only if AMD GPU collection needs it:
sudo usermod -aG video,render collector
```

Do not reuse a venv from `/home/...` — `collector` cannot read it.

## 3. Create venv

```bash
sudo python3 -m venv /usr/local/share/MetricCollector/.venv
sudo /usr/local/share/MetricCollector/.venv/bin/pip install --upgrade pip
sudo /usr/local/share/MetricCollector/.venv/bin/pip install psutil influxdb3-python amdsmi nvidia-ml-py
sudo chown -R root:collector /usr/local/share/MetricCollector/.venv
sudo chmod -R 750 /usr/local/share/MetricCollector/.venv
```

## 4. Configure InfluxDB credentials

Create `/usr/local/share/MetricCollector/src/collector.env` with `600` permissions:

```bash
INFLUXDB_HOST=http://127.0.0.1:8181
INFLUXDB_DATABASE=edge_dev_db
INFLUXDB_TOKEN=apiv3_YOUR_TOKEN_HERE
```

```bash
sudo chown root:collector /usr/local/share/MetricCollector/src/collector.env
sudo chmod 640 /usr/local/share/MetricCollector/src/collector.env
```

## 5. Install unit file

`/etc/systemd/system/metric-collector.service`:

```ini
[Unit]
Description=Hardware Device Metric Collector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=collector
Group=collector
WorkingDirectory=/usr/local/share/MetricCollector/src
EnvironmentFile=/usr/local/share/MetricCollector/src/collector.env
ExecStart=/usr/local/share/MetricCollector/.venv/bin/python /usr/local/share/MetricCollector/src/main.py --log-dir /var/log/metric-collector --interval 10
LogsDirectory=metric-collector
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

`LogsDirectory=` creates `/var/log/metric-collector` owned by `collector`. `main.py` creates the log file on startup via `os.makedirs(..., exist_ok=True)`.

For AMD GPU add under `[Service]`:

```ini
Environment=LD_LIBRARY_PATH=/opt/rocm/lib
```

## 6. Enable and verify

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now metric-collector.service
systemctl status metric-collector.service
journalctl -u metric-collector.service -f
ls -l /var/log/metric-collector
```

## Troubleshooting

```bash
# Config / permission errors
sudo systemd-analyze verify metric-collector.service
sudo -u collector /usr/local/share/MetricCollector/.venv/bin/python /usr/local/share/MetricCollector/src/main.py --help

# Token not picked up: EnvironmentFile path wrong or missing INFLUXDB_TOKEN
sudo systemctl show metric-collector.service -p EnvironmentFiles,Environment
```
