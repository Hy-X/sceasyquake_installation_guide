# SeisComP & easyQuake: Daily CLI Operations Cheat Sheet

[ English ](README.md) | [ 简体中文 ](README_zh.md)

A rapid copy-paste command reference for day-to-day operations, log monitoring, database inspection, and pipeline diagnostics on **SeisComP 7.4** with **easyQuake (`sceasyquake`)**.

---

## Table of Contents
1. [Pipeline Lifecycle & Process Management](#1-pipeline-lifecycle--process-management)
2. [SeedLink Real-Time Waveform Streaming](#2-seedlink-real-time-waveform-streaming)
3. [AI & Traditional Phase Picker Monitoring](#3-ai--traditional-phase-picker-monitoring)
4. [Event & Origin CLI Inspection (`scevtls`, `scbulletin`, `scxmldump`)](#4-event--origin-cli-inspection)
5. [Direct MariaDB SQL Queries](#5-direct-mariadb-sql-queries)
6. [Station Bindings & Inventory Management](#6-station-bindings--inventory-management)
7. [GUI & Headless Web Launchers](#7-gui--headless-web-launchers)
8. [Database Reset & Clean Slate (Testing Drills)](#8-database-reset--clean-slate-testing-drills)
9. [Log File Locations & Troubleshooting Commands](#9-log-file-locations--troubleshooting-commands)

---

## 1. Pipeline Lifecycle & Process Management

```bash
# Check status of all configured modules
seiscomp status

# Start or stop the complete pipeline
seiscomp start
seiscomp stop

# Restart a specific module (e.g. after editing its configuration)
seiscomp restart sceasyquake
seiscomp restart scautoloc
seiscomp restart seedlink

# Compile all station bindings & config templates (MANDATORY after any edit)
seiscomp update-config

# Check raw operating system processes
ps aux | grep -E "scmaster|seedlink|sceasyquake|scautoloc"

# Force-kill orphaned Python or SeisComP processes if a restart hangs
pkill -9 -f sceasyquake-stream
pkill -9 -f seedlink
```

---

## 2. SeedLink Real-Time Waveform Streaming

```bash
# Check incoming packet flow from local SeedLink daemon (shows station packet counts)
seiscomp exec slinktool -Q localhost:18000

# List all active stations, channels, and sampling rates currently in the ring buffer
seiscomp exec slinktool -p localhost:18000

# Inspect waveform delivery latency (station latency in seconds)
seiscomp exec slinktool -L localhost:18000

# Stream raw miniSEED packet headers live in terminal (test data flow on OK.ALVA)
seiscomp exec slinktool -v -s "OK_ALVA:HHZ" localhost:18000

# Test connection to public upstream server (e.g. EarthScope / IRIS)
seiscomp exec slinktool -Q rtserve.earthscope.org:18000
```

---

## 3. AI & Traditional Phase Picker Monitoring

### Follow Live AI Phase Picks (`sceasyquake`)
```bash
# Follow full sceasyquake daemon log in real time
tail -f ~/.seiscomp/log/sceasyquake.log

```

### Follow Traditional STA/LTA Picker (`scautopick`)
```bash
# Follow scautopick log
tail -f ~/.seiscomp/log/scautopick.log
```

### Check GPU & Machine Learning Environment
```bash
# Check real-time NVIDIA GPU utilization and VRAM consumption (refreshes every 1s)
nvidia-smi -l 1

# Verify SeisComP's embedded Python can load PyTorch, SeisBench, and CUDA
$(seiscomp exec which python3) -c '
import torch, seisbench, obspy
print("PyTorch Version:", torch.__version__)
print("CUDA Available :", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU Device Name:", torch.cuda.get_device_name(0))
'
```

---

## 4. Event & Origin CLI Inspection

Inspect declared earthquakes from the command line without opening a GUI:

```bash
# List the 10 most recent earthquake events declared by the system
seiscomp exec scevtls -d mysql://sysop:sysop@localhost/seiscomp -l 10

# Print complete technical bulletin for the MOST RECENT earthquake
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -l 1

# Print technical bulletin for a specific Event ID
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -E <event-id>

# Print technical bulletin for a specific Origin ID (shows all P & S phase arrivals and residuals)
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -O <origin-id>

# Export an earthquake event and all associated picks to standard QuakeML XML
seiscomp exec scxmldump -d mysql://sysop:sysop@localhost/seiscomp -E <event-id> -o event.xml
```

---

## 5. Direct MariaDB SQL Queries

Run these queries directly in the terminal using the `mysql` CLI:

### 1. View the 10 Most Recent Phase Picks (P and S)
```bash
mysql -u sysop -psysop seiscomp -e "
SELECT 
    po.publicID AS pick_id,
    p.waveformID_networkCode AS net,
    p.waveformID_stationCode AS sta,
    p.waveformID_channelCode AS cha,
    p.phaseHint_code AS phase,
    p.time_value AS arrival_time,
    p.creationInfo_author AS author
FROM Pick p
JOIN PublicObject po ON po._oid = p._oid
ORDER BY p.time_value DESC LIMIT 10;
"
```

### 2. View the 5 Most Recent Earthquake Origins (Hypocenters)
```bash
mysql -u sysop -psysop seiscomp -e "
SELECT 
    po.publicID AS origin_id,
    ROUND(o.latitude_value, 4) AS lat,
    ROUND(o.longitude_value, 4) AS lon,
    ROUND(o.depth_value, 1) AS depth_km,
    o.quality_usedPhaseCount AS phases,
    ROUND(o.quality_standardError, 2) AS residual_sec,
    o.time_value AS origin_time
FROM Origin o
JOIN PublicObject po ON po._oid = o._oid
ORDER BY o.time_value DESC LIMIT 5;
"
```

### 3. View Declared Events with Magnitudes & Epicenters
```bash
mysql -u sysop -psysop seiscomp -e "
SELECT 
    e.publicID AS event_id,
    ROUND(o.latitude_value, 3) AS lat,
    ROUND(o.longitude_value, 3) AS lon,
    ROUND(o.depth_value, 1) AS depth_km,
    ROUND(m.magnitude_value, 2) AS mag,
    m.type AS mag_type,
    e.creationInfo_creationTime AS declared_at
FROM Event e
JOIN Origin o ON o.publicID = e.preferredOriginID
LEFT JOIN Magnitude m ON m.publicID = e.preferredMagnitudeID
ORDER BY e.creationInfo_creationTime DESC LIMIT 5;
"
```

### 4. Summary Count of All Picks by Phase Type
```bash
mysql -u sysop -psysop seiscomp -e "
SELECT phaseHint_code AS phase, COUNT(*) AS total_picks 
FROM Pick 
GROUP BY phaseHint_code;
"
```

---

## 6. Station Bindings & Inventory Management

```bash
# List all active station bindings in your system
ls -l $SEISCOMP_ROOT/etc/key/station_*

# Count the total number of bound stations
ls $SEISCOMP_ROOT/etc/key/station_* | wc -l

# Inspect the active profile configuration of a specific station (e.g. OK.ALVA)
cat $SEISCOMP_ROOT/etc/key/station_OK_ALVA

# Convert newly downloaded StationXML file into SeisComP inventory XML
bin/seiscomp exec fdsnxml2inv ../stationxml/new_stations.xml etc/inventory/inventory_new.xml

# Synchronize inventory directory with the MariaDB database
bin/seiscomp exec scinv sync

# Enter SeisComP CLI shell to add or update station profiles
bin/seiscomp shell
# Inside shell:
# set profile global default OK.*
# set profile seedlink iris OK.*
# set profile sceasyquake default OK.*
# exit

# Recompile runtime configuration (ALWAYS required after shell edits)
bin/seiscomp update-config
```

---

## 7. GUI & Headless Web Launchers

### Headless Web Configuration Interface (`scconfig`)
```bash
# 1. Start web server in offscreen mode on remote server:
QT_QPA_PLATFORM=offscreen seiscomp exec scconfig --web 8080

# 2. Access from local browser (via SSH tunnel ssh -L 8080:localhost:8080 user@server):
# Open: http://localhost:8080
```

### Native Desktop GUIs (Over SSH X11 Forwarding: `ssh -Y user@server`)
```bash
# Origin Locator View (waveform picker & duty review)
scolv

# Map View (station ground motion & live epicenter display)
scmv

# Real-Time Trace View (streaming multi-channel helicorder)
scrttv
```

---

## 8. Database Reset & Clean Slate (Testing Drills)

When developing or running simulation drills, you may want to purge test picks and events without wiping your station inventory or configuration:

```bash
# 1. Stop processing daemons
seiscomp stop

# 2. Truncate detection and event tables (preserves schemas and inventory)
mariadb -u sysop -psysop seiscomp << 'EOF'
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE Event;
TRUNCATE TABLE EventDescription;
TRUNCATE TABLE Origin;
TRUNCATE TABLE Arrival;
TRUNCATE TABLE Pick;
TRUNCATE TABLE Amplitude;
TRUNCATE TABLE StationMagnitude;
TRUNCATE TABLE Magnitude;
TRUNCATE TABLE PublicObject;
SET FOREIGN_KEY_CHECKS = 1;
EOF

# 3. Restart the pipeline
seiscomp start
```

---

## 9. Log File Locations & Troubleshooting Commands

| Module | Log File Path | Primary Diagnostic Purpose |
| :--- | :--- | :--- |
| **`sceasyquake`** | `~/.seiscomp/log/sceasyquake.log` | Deep-learning model inference times, batch size warnings, published P/S picks. |
| **`seedlink`** | `$SEISCOMP_ROOT/var/log/seedlink.log` | Upstream TCP connection state, dropped packets, buffer overflow. |
| **`scmaster`** | `$SEISCOMP_ROOT/var/log/scmaster.log` | Message bus health, client disconnects, database sync status. |
| **`scautoloc`** | `~/.seiscomp/log/scautoloc.log` | Phase association trials, rejected origins, travel-time residual errors. |
| **`scdb`** | `~/.seiscomp/log/scdb.log` | Database insertion failures, SQL deadlocks. |

### Quick Diagnostic One-Liners
```bash
# Find any recent errors across ALL SeisComP logs simultaneously
grep -i "error" ~/.seiscomp/log/*.log $SEISCOMP_ROOT/var/log/*.log | tail -n 25

# Check if SeedLink port 18000 is open and listening
ss -tuln | grep 18000

# Check disk space in SDS miniSEED waveform archive
du -sh $SEISCOMP_ROOT/var/lib/archive/*
```
