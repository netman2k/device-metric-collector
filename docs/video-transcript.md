# Video Transcript — Hardware Device Monitoring Solution

> Narration script for a walkthrough of this repository. Target length: ~6–8 minutes.
> Bracketed lines are on-screen cues for the person recording.

---

## 0. Intro (0:00 – 0:30)

[Show the repository title and the architecture diagram at `assets/architecture.png`]

Hi, in this video I'll walk through a small monitoring solution I built. The goal is straightforward: collect utilisation metrics from the hardware on a machine — CPU, memory, disk, and GPU — and push those metrics into a time-series database on a regular interval, so they can be queried and visualised on a dashboard.

I want to be upfront about something first. There are plenty of mature, well-made open-source and commercial tools that do exactly this, and in a real deployment you should absolutely reach for those before writing your own. So the point of this project isn't to reinvent monitoring. It's to show, in a hands-on way, how you can collect metrics from multiple devices with a small Python collector and a handful of other solutions.

---

## 1. Architecture overview (0:30 – 3:00)

[Display `assets/architecture.png`]

Let me start with the production architecture and then explain why I made each choice, because the reasoning matters more than the boxes.

[Point to the database layer]

First, the database. I chose **Amazon Timestream for InfluxDB** which is a high-performance, purpose-built time-series database,  optimised for large volumes of time-stamped data. So it's naturally fit for device monitoring, DevOps metrics, and real-time analytics. Unlike a regular relational database, a time-series database handles fast queries, data clean-up, and data summaries much better.

[Point to the arrow from devices to the ingestion endpoint]

Out of all my decisions, I'm most confident about this next one: choosing a **push model over a pull model**. Let me explain why.

With a push model, devices send out their data on their own. This means you don't have to open up holes in their firewalls, which makes them much more secure. It is also fit for devices spread across different locations because you don't have to manage messy firewall rules for each site. Instead, every device just connects outward to one central spot or service endpoint. Finally, the central collector doesn't need a list of devices to connect for metrics.

Now, to be fair: pull model would actually be the better fit, when the inventory is fixed and lives in a trusted network, where collectors can reach every device directly. But that's not the situation for devices spread across locations, so push is the right call here.

[Point to the collector box]

For the collector, the obvious production-grade choice would be **Telegraf**. Of course there are plenty of other solutions out there.

It's an open-source plugin-driven agent with built-in data buffering and importantly it's light and it can collect almost every metric on the device.

For this project, though, I wrote a small **Python** script instead, because the goal is a custom collector that pulls CPU, memory, disk, and GPU metrics for the purpose. The collector stays light because it never accepts requests from the outside. The trade-off is that configuration — like the database endpoint and the token — has to be maintained on every device.

[Point to the dashboard layer]

For the dashboard, I used **Grafana** which is an **open-source data visualization and monitoring web application** used to track the health and performance of large-scale infrastructure and applications..

It queries InfluxDB and lets us visualise the metrics we collect with the datasource and a dashboard I created to show how metrics look like.

[Point to the alarming layer]

For production monitoring, **Amazon CloudWatch** is the target platform, enabling automated responses via AWS Lambda and Amazon Simple Notification Service when specific alarm criteria are met. Of course, SNS

Grafana can also send alerts—like texting your Slack if a computer gets too hot—which is great for a free, local setup. But we choose CloudWatch for the live system because it connects perfectly with all other Amazon services.

That said, this specific project does not include alerting. It focuses strictly on local development, showing you how to collect, store, and visualize data using open-source tools.

---

## 2. Development environment (3:00 – 4:15)

[Display `assets/architecture_dev.png`]

Since there's no AWS account for development and testing, I replaced the production CloudWatch path locally with open-source tooling. The Python collector pushes metrics to a local **InfluxDB 3** instance, which I visualise with Grafana. All the backend services run as containers via `podman-compose`, defined in `containers/compose.yml`.

[Walk through the dev diagram top to bottom]

On the right is the **metric collector**. It runs either on the host as a systemd service — there's a guide in `docs/systemd-setup.md` — or as a container on the same network as InfluxDB. Either way it pushes CPU, memory, disk, and GPU metrics every ten seconds which can be adjusted as it runs.

Next is **InfluxDB 3 Core** on port 8181, the time-series store for the `edge_dev_db` database.

Then **Grafana** on port 3000. The datasource and a sample dashboard are auto-provisioned but it's minimal at this stage, just enough to show the functionality and data we collect.

lastly **InfluxDB 3 Explorer** on port 8080 although it's not in this diagram, but it is a nice ad-hoc query UI for InfluxDB. You can test out the InfluxDB queries within this solution.

One quick GPU note: my dev machine has an AMD integrated GPU, so I collect AMD metrics through `amdsmi`. I also wrote NVIDIA collection code using `pynvml`, but I couldn't verify it — there was no NVIDIA hardware available to test against.

---

## 3. Live demo (4:15 – 6:00)

[Switch to the running environment — no setup typing; the stack is already up]

Rather than walk through the setup commands, I'll demonstrate how the solution actually works. If you do want to reproduce this yourself, the full step-by-step instructions are in the "How to test" section of the README.

So, everything is already running. Let me show you the pieces in action.

[Show the containers]

As you can see, the output shows that I have 3 containers running in my dev machine which are influxdb3-core, influx3db-explorer and grafana.

[Show the InfluxDB container logs, then the collector output]

An this is the Python collector which is pushing metrics every ten seconds — CPU, memory, disk, and GPU. If I turn up the verbosity, each line shows the actual points in line protocol, which is the format InfluxDB ingests.

[Switch to Grafana on port 3000]

Now let's see where that data lands. Here's Grafana. The datasource is provisioned automatically on startup, so the collected data is queryable straight away.

[Show the dashboard — a simple chart is enough]

I'll be upfront: the dashboard isn't finished yet. It's an early starting point, there just to show that the metrics we collect can actually be visualised — not a polished set of panels. But that's the point I wanted to demonstrate: the data we're collecting shows up here and can be charted. So the whole pipeline works end to end — collect, push, store, and visualise.

[If available, use the `device` variable dropdown]

There's also a `device` variable wired to the dashboard, so it can be scoped to a specific host — and since every point is tagged with city, region, and country, location-based filtering is possible too. Building that out into a full dashboard is the next step, not something that's done here.

[Open InfluxDB 3 Explorer on port 8080]

Let me also jump over to the InfluxDB 3 Explorer, which is handy for ad-hoc queries. I'll run a quick one:

```
SELECT * FROM cpu ORDER BY time DESC LIMIT 10
```

And there's the raw data — the same points the dashboard is built on, straight from the time-series store. This is the flow end to end: collect, push, store, query, and visualise.

---

## 4. Future considerations (6:00 – 7:00)

[Back to slides or the README]

A couple of things I'd improve before this ever touched production.

**Automatic location tagging.** Every point is already tagged with device, city, region, and country, but right now those values come from static flags that default to Dublin, Leinster, and IE. For a fleet spread across areas, populating those automatically — for example from an IP geolocation database at startup — would let operators filter by location and correlate events across nearby devices on the dashboard.

**Secure communication.** The local setup uses plain HTTP with no TLS, and the ingestion endpoint has to be reachable from every device, so access control on that port is critical. In production I'd carry the traffic over a private path — either a site-to-site VPN or Direct Connect — with TLS, and I'd rotate the InfluxDB tokens that the collectors hold. Ideally those tokens live in a secrets manager rather than in on-device env files.

---

## 5. Wrap-up (7:00 – 7:30)

[Show the repository one more time]

So that's the solution. To recap: devices push metrics so we avoid inbound ports and per-device firewall rules; a small Python collector gathers CPU, memory, disk, and GPU metrics every ten seconds; InfluxDB 3 stores them; and Grafana makes them queryable and visualisable — the dashboard here is minimal, just to prove it works. Grafana alerting is available locally (including Slack notifications on threshold breaches), while CloudWatch is the target in production for deeper AWS integration. It's a deliberately simple design, and the trade-offs were conscious ones. Thanks for watching.
