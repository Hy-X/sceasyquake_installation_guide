# SeisComP & easyQuake: Comprehensive Learning Notes

This document organizes the core concepts, architecture, workflows, and operational insights for **SeisComP** and its integration with deep-learning machine learning pickers (**easyQuake / SeisBench**).

> [!TIP]
> **Looking for foundational concepts?** If you are transitioning from undergraduate Earth Science coursework to operational seismology, check out the **[Comprehensive Terminology Guide](SEISCOMP_TERMINOLOGY_GUIDE.md)** for detailed explanations of SEED channel codes, miniSEED, StationXML, STA/LTA vs. Deep Learning (PhaseNet), and the SeisComP data model.

---

## Table of Contents
1. [Big Picture: The Earthquake Monitoring Pipeline](#1-big-picture-the-earthquake-monitoring-pipeline)
2. [Key Components & Terminology](#2-key-components--terminology)
3. [The easyQuake_seiscomp Repository](#3-the-easyquake_seiscomp-repository)
4. [Human Review & Operator Workflows (`scolv`)](#4-human-review--operator-workflows-scolv)
5. [System Architecture: Why 3 Nodes in Production?](#5-system-architecture-why-3-nodes-in-production)
6. [Learning & Deploying on a Single Machine](#6-learning--deploying-on-a-single-machine)
7. [Resource Profile & Low-End Machine Viability](#7-resource-profile--low-end-machine-viability)
8. [The Role of MariaDB (Your Personal Database)](#8-the-role-of-mariadb-your-personal-database)
9. [Remote Management over SSH & Headless Operation](#9-remote-management-over-ssh--headless-operation)
10. [Quick Diagnostic & Query Cheat Sheet](#10-quick-diagnostic--query-cheat-sheet)

---

## 1. Big Picture: The Earthquake Monitoring Pipeline

Seismic data flows from physical vibrations in the ground to an authoritative earthquake catalog and public alerts in seconds:

```mermaid
flowchart TD
    subgraph Field ["1. Upstream & Field Telemetry"]
        S[Field Seismometers & Digitizers\nCentaur, Güralp, Quanterra] --> AS[Apollo Server\nNanometrics Acquisition & Telemetry]
        S --> RS[Ringserver\nSeedLink / DataLink Ring Buffer]
        AS --> RS
    end

    subgraph Acquisition ["2. SeisComP Acquisition"]
        RS -->|SeedLink Protocol\nport 18000| SL[SeisComP SeedLink Daemon]
        SL -->|Saves miniSEED files| SDS[(SDS Archive\nvar/lib/archive)]
    end

    subgraph Messaging ["3. The Backbone: Message Bus & DB"]
        SL -->|Waveform Streams| BUS((scmaster\nMessaging Broker))
        BUS <---> SCDB[(MySQL / MariaDB\nSeisComP DB)]
    end

    subgraph Processing ["4. Processing (Automated Detection)"]
        BUS -->|Waveforms| PICKER[Picker: scautopick OR sceasyquake ML]
        PICKER -->|PICK Group| BUS
        BUS -->|Picks| AMP[scamp\nAmplitude Calculation]
        BUS -->|Picks| ASSOC[Associator / Locator\nscautoloc / scpyocto]
        ASSOC -->|LOCATION Group: Origins| BUS
        BUS -->|Origins + Amplitudes| MAG[scmag\nMagnitude Calculation]
        MAG -->|MAGNITUDE Group| BUS
        BUS -->|Origins + Mags| EVENT[scevent\nDeclares Earthquake Events]
        EVENT -->|EVENT Group| BUS
    end

    subgraph Production ["5. Production, Dissemination & GUIs"]
        BUS --> GUIS[Operator GUIs\nscolv, scmv, scrttv]
        BUS --> WEB[FDSN Web Services / QuakeML]
        BUS --> ALERTS[Alerting: Email, SMS, Webhooks]
    end
```

---

## 2. Key Components & Terminology

| Component | What it is | Role in the Ecosystem |
|---|---|---|
| **Apollo Server** | Nanometrics central telemetry server | Aggregates field digitizers (Centaur/Trillium), monitors SOH (state of health), and feeds SeedLink. |
| **Ringserver** | C-based packet ring-buffer (EarthScope/IRIS) | Buffers continuous miniSEED streams and routes real-time data to clients without dropping packets. |
| **SeedLink** | Standard streaming protocol & daemon | Ingests waveforms into SeisComP on port `18000`. |
| **SDS Archive** | SeisComP Data Structure filesystem | Raw file archive layout: `ARCHIVE/YEAR/NET/STA/CHAN.D/NET.STA.LOC.CHAN.D.YEAR.JULDAY`. |
| **`scmaster`** | Central publish–subscribe message bus | Decouples all modules. Routes messages across groups (`PICK`, `LOCATION`, `MAGNITUDE`, `EVENT`). |
| **`scdb`** | Database synchronization daemon | Subscribes to all messaging groups and persists objects to relational database tables. |
| **`scolv`** | Origin Locator View GUI | Interactive waveform review workbench for duty seismologists. |
| **`scmv`** | Map View GUI | Real-time map displaying station status, ground motion alarms, and live events. |
| **`scrttv`** | Real-Time Trace View GUI | Streaming multi-station helicorder/waveform display. |

---

## 2.1 SeisComP Directory Structure ($SEISCOMP_ROOT)

```
<PARENT_DIR>/ (e.g. ~/Projects/SeiscomP or $HOME)
│
├── stationxml/                   # Staging directory for raw FDSN StationXML downloads
│   ├── OK_stations.xml
│   └── TX_stations.xml
│
└── seiscomp/                     # ($SEISCOMP_ROOT) Core SeisComP Installation
    ├── bin/                      # All executable programs and GUIs
    │   ├── seiscomp              # Master controller script (start, stop, status, exec)
    │   ├── scmaster              # Messaging broker daemon
    │   ├── seedlink              # Acquisition daemon
    │   ├── scautopick            # Traditional STA/LTA picker daemon
    │   ├── scautoloc             # Hypocenter locator daemon
    │   ├── scdb                  # Database synchronization daemon
    │   ├── scolv                 # Graphical Origin Locator View
    │   ├── scmv                  # Graphical Map View
    │   ├── scrttv                # Graphical Real-Time Waveform Trace View
    │   └── scinv / fdsnxml2inv   # Inventory import & sync tools
    │
    ├── etc/                      # All system configurations & bindings
    │   ├── global.cfg            # Global config (database login, log level)
    │   ├── scmaster.cfg          # Messaging broker parameters
    │   ├── seedlink.cfg          # Acquisition parameters
    │   ├── scautopick.cfg        # Picker filters and detection thresholds
    │   ├── sceasyquake.cfg       # ML Picker configuration (PhaseNet / GPU)
    │   │
    │   ├── inventory/            # StationXML / SeisComP inventory XMLs
    │   │   └── inventory_OK.xml  # Station coordinates & instrument responses
    │   │
    │   └── key/                  # Station BINDINGS (Which module listens to which station)
    │       ├── global/           # Channel sample rates & gains (e.g. station_OK_ALVA)
    │       ├── seedlink/         # Upstream server profiles (e.g. profile_iris)
    │       └── scautopick/       # Filter/detector profiles for each station
    │
    ├── var/                      # Dynamic runtime data (logs, PIDs, raw waveforms)
    │   ├── run/                  # Process ID files (seiscomp.pid, scmaster.pid)
    │   ├── log/                  # Module logs (scmaster.log, scautopick.log)
    │   │
    │   └── lib/
    │       ├── archive/          # SDS Raw Waveform Archive (miniSEED files)
    │       │   └── 2026/OK/ALVA/HHZ.D/OK.ALVA..HHZ.D.2026.296
    │       └── seedlink/         # SeedLink circular in-memory buffer ring
    │
    ├── lib/                      # Libraries and Python bindings
    │   ├── libseiscomp_core.so   # C++ runtime engine
    │   ├── libseiscomp_qt.so     # C++ Qt GUI library
    │   │
    │   └── python/               # Python bindings (import seiscomp.client, etc.)
    │       └── seiscomp/         # Native Python library
    │
    └── share/                    # Static schemas, travel-time tables, and map tiles
        ├── db/
        │   └── mysql.sql         # SQL schema tables loaded into MariaDB
        ├── locsat/               # 1D Earth velocity travel-time tables
        │   └── tables/iasp91.*   # Theoretical P and S arrival curves (IASP91)
        └── maps/                 # Geographic vector basemaps & topography (from seiscomp-maps.tar.gz)
            └── ...               # Coastlines, borders, and tiles for scolv & scmv GUIs
```

> [!NOTE]
> The base binary release (`seiscomp-*-*.tar.gz`) excludes map layers to keep the core download small. To enable geographic basemaps and coastlines in `scolv` and `scmv`, download `seiscomp-maps.tar.gz` from [seiscomp.de/downloader](https://www.seiscomp.de/downloader/) into the parent directory and unpack with `tar -xvf seiscomp-maps.tar.gz`.

---

## 2.2 The Configuration & Binding Architecture

In SeisComP, an inventory database might contain thousands of station definitions imported from global networks. Modules do **not** automatically process everything in the database. Instead, SeisComP uses a 3-tier **Binding System**:

### 1. The 3 Tiers
```
1. Profile Template    (etc/key/<module>/profile_<name>)
      │  Defines reusable parameter sets (e.g. EarthScope server, 100 Hz HH channels, STA/LTA filter).
      ▼
2. Station Binding     (etc/key/<module>/station_<NET>_<STA>)
      │  A simple text file pointing a specific station to a Profile (e.g. OK.ALVA -> iris).
      ▼
3. Compiled Runtime    (var/run/<module>/*)
         Generated automatically when running "seiscomp update-config".
         C++ daemons read these consolidated files at startup.
```

### 2. The 3 Core Bindings Required by Every Station
* **`global`**: Declares universal stream parameters (e.g. `detecStream = HH` to monitor 100 Hz broadband, `detecLocid = ""` for empty location ID).
* **`seedlink`**: Declares how raw waveforms are acquired (e.g. `sources = chain`, `address = rtserve.earthscope.org`, `port = 18000`).
* **`scautopick`**: Declares the detection filter and STA/LTA parameters (e.g. `filter = "RMHP(10)>>ITL(0.2)>>BW(4,1.0,20.0)"`).

### 3. Why `seiscomp update-config` is Mandatory
Daemons **never parse `etc/key/` files directly** during execution. Reading hundreds of station files repeatedly would cause severe I/O bottlenecks. 
Instead, **`seiscomp update-config` compiles** `etc/inventory/` + `etc/key/` + `etc/*.cfg` into optimized runtime files in `var/run/`. If you modify bindings or profiles, you must always run `seiscomp update-config` to compile the changes!

---

## 3. The `easyQuake_seiscomp` Repository

This repository integrates modern **machine learning phase picking** and **advanced associators** directly into SeisComP 5+:

### Key Modules:
1. **`sceasyquake`** (Real-time ML Picker Daemon):
   - Replaces/complements traditional STA/LTA (`scautopick`).
   - Connects to SeedLink, batches waveforms across stations, and runs high-throughput inference (`predict_multi()`).
   - Supports **PhaseNet**, **EQTransformer**, and **GPD** (via SeisBench or easyQuake).
   - Generates paired `Amplitude(type='snr')` objects required by `scautoloc`.
   - Includes `scSassoc.py` to match incoming S picks to P-located origins using 1D travel-time tables (`iasp91`).
   - **SeedLink Integration & Auto-Discovery**:
     - Connects via ObsPy's `EasySeedLinkClient` to `localhost:18000`.
     - SeedLink v3 servers reject wildcards (`*` or `????`) in the `STATION` handshake command. `sceasyquake` uses `_get_seedlink_stations()` to query SeedLink via `INFO STATIONS` and automatically expands patterns like `OK.*..HH?` to explicit station subscriptions across the entire active network.
     - Resolves the Python 3 ObsPy timeout bug by explicitly setting `self.conn.timeout = 10.0` in `_Client.__init__`.
2. **`scpyocto`** (PyOcto Associator Daemon):
   - Wraps the high-throughput **PyOcto** associator as a native SeisComP client.
   - Ideal for dense microseismic networks and handling high pick volumes.
3. **`scphasepapy`** (PhasePaPy Associator Daemon):
   - 1D PhasePaPy associator using SQLite/SQLAlchemy backend for candidate clustering.
4. **`gap_recovery`**:
   - Automated pipeline that scans the SDS archive for dropouts, back-fills missing data from SeedLink ring-buffers (`scart`) or EarthScope FDSN, re-picks with ML, and pushes picks with a rate throttle (`--pick-rate 20`) to prevent bus saturation.
5. **Operational Tooling**:
   - `examples/bbox_station_service.py`: Web UI to draw a bounding box and auto-provision station XML and SeedLink bindings.
   - `examples/status_check.py`: System health audit, config snapshots, diffing, and deployment templates.
   - `associator_status.sh`: Terminal health dashboard across `scautoloc`, `scphasepapy`, and `scpyocto`.
   - `archive_cleanup.sh`: Retention cleaner for the SDS archive using Julian days.

---

## 4. Human Review & Operator Workflows (`scolv`)

Because SeisComP has a decoupled client–server architecture, human analysts do not need to sit at the production server:

```
[ Production Server: scmaster & DB ]
                 │
                 │ Remote IP / VPN / LAN
                 ▼
       [ Analyst Client ]
       ├── Option A: Native scolv on analyst's laptop
       ├── Option B: Remote desktop / VNC / FastX / NoMachine
       └── Option C: SSH with X11 forwarding (ssh -Y)
```

### What Happens During Human Review?
1. The automated pipeline (`sceasyquake` + `scautoloc` + `scmag` + `scevent`) detects and locates an earthquake automatically within 30–60 seconds.
2. The duty seismologist opens **`scolv`** to inspect the automatic solution.
3. The analyst re-picks phase arrivals, discards bad traces, recalculates the location, and clicks **Commit**.
4. `scolv` creates a new `Origin` tagged with `evaluationMode: manual` and the analyst's author name.
5. `scevent` prioritizes human review over machine solutions and promotes it to **Preferred Origin**.
6. The public catalog and external notifications are immediately broadcast with verified status.

![Origin Locator View (scolv)](assets/scolv.png)
*Figure 4.1: The Origin Locator View (`scolv`) showing 3-component waveforms, theoretical travel-time alignment curves, and manual pick adjustments.*

---

## 5. System Architecture: Why 3 Nodes in Production?

In major national observatories (USGS, GEOFON, EMSC), the system is divided across 3 specialized machines:

| Node | Primary Job | Dominant Workload | Protection / Blast Radius |
|---|---|---|---|
| **1. Acquisition (`aqui`)** | Ingest telemetry (`seedlink`) & write raw files (`slarchive`). | High TCP connection churn, constant disk writes. | **"Never drop a packet."** Network flapping or telemetry disconnects will not disrupt detection. |
| **2. Processing (`processing`)** | Run ML inference (`sceasyquake`), association (`scautoloc`/`scpyocto`), and magnitude calculation (`scmag`). | 100% CPU/GPU spikes, matrix operations, ray-tracing. | Severe aftershock swarms can saturate compute without locking disk writes or web traffic. |
| **3. Production (`production`)** | Host database (`scdb`), analyst review (`scolv`), and public APIs (`fdsnws`). | Database transactions (NVMe SSD), high outbound web bandwidth. | Survives the **"Hug of Death"**—millions of citizens hitting the website won't crash real-time earthquake detection. |

---

## 6. Learning & Deploying on a Single Machine

While national centers split into 3 nodes for redundancy, **you can run the entire stack on a single machine**.

```
[ Your Single Machine (e.g. Ubuntu 26.04 LTS) ]
 ├── Acquisition : seedlink (localhost:18000)
 ├── Message Bus : scmaster (localhost:18001)
 ├── Processing  : sceasyquake + scautoloc daemons
 ├── Database    : MariaDB (localhost:3306)
 └── Review/GUI  : scolv / scmv / scconfig
```

### Free Ways to Feed Data for Learning:
1. **Live Internet Streams**: Configure local `seedlink` to connect to public servers (e.g., EarthScope `rtserve.earthscope.org:18000` or GEOFON `geofon.gfz-potsdam.de:18000`).
2. **Replay Past Earthquakes**: Use `scart` or `msrtsimul` to inject historical miniSEED earthquake waveforms into your SeedLink buffer to trigger the pipeline on demand.

---

## 7. Resource Profile & Low-End Machine Viability

A low-end or modest machine (e.g., dual/quad-core CPU, 4–8 GB RAM, no GPU) **is fully capable of running 5 to 20 stations**:

* **PhaseNet CPU Throughput**: Benchmarked at **~4.7 ms per station** per pass.
  * For 10 stations, inference takes **~0.05 seconds** out of every 5-second interval (**~1% CPU load**).
* **RAM Usage**:
  * PhaseNet + SeisBench: ~360 MB
  * MariaDB: ~150–250 MB
  * SeisComP core daemons: < 500 MB
  * **Total Stack Footprint**: Under 2–3 GB RAM.
* **Network Bandwidth**: ~2–5 KB/s per 3-component station (negligible).

### Recommended Low-End Settings (`sceasyquake.cfg`):
```ini
picker.backend            = phasenet   # Fast 1D U-Net (40x faster on CPU than GPD)
picker.device             = cpu
picker.step_seconds       = 5          # or 10 for very low-power CPUs
picker.buffer_seconds     = 60
picker.max_batch_stations = 64         # Cap per step to prevent CPU falling behind real-time
streams.codes             = NET.STA1..HH?, NET.STA2..HH?   # Select specific stations
```

---

## 8. The Role of MariaDB (Your Personal Database)

When you install MariaDB on your machine, it acts as your **private, local database of record**:

* **Scope**: Completely private; listens only on `localhost:3306`.
* **What it stores**:
  * Station metadata (lat, lon, elevation, gain).
  * Every P and S pick made by ML (timestamp, phase, probability, SNR).
  * Hypocenter solutions (Origins) and magnitudes.
  * Official event history.
* **Database Schema Structure**:
  * In SeisComP's relational schema, universal identifiers (`publicID`) are kept in the `PublicObject` table and link to specific entity tables (`Pick`, `Origin`, `Event`) via `_oid`.
  * Running `SELECT publicID FROM Pick;` causes `ERROR 1054: Unknown column 'publicID'`. Always join `PublicObject po ON po._oid = p._oid`.
* **What it does NOT store**:
  * Raw continuous waveform data (the squiggly lines) are stored as `.mseed` files on the filesystem (`~/seiscomp/var/lib/archive/`), keeping the database fast and lightweight.
* **SQL Query Examples**:
  ```bash
  # 1. Query real-time AI phase picks (PhaseNet P & S):
  mysql -u sysop -psysop seiscomp -e "
    SELECT 
        po.publicID AS pick_id,
        p.time_value,
        p.waveformID_networkCode AS net,
        p.waveformID_stationCode AS sta,
        p.waveformID_channelCode AS cha,
        p.phaseHint_code AS phase,
        p.methodID,
        p.creationInfo_author AS author,
        p.creationInfo_creationTime AS created
    FROM Pick p
    JOIN PublicObject po ON po._oid = p._oid
    ORDER BY p.creationInfo_creationTime DESC LIMIT 15;
  "

  # 2. Query declared hypocenters / origins:
  mysql -u sysop -psysop seiscomp -e "
    SELECT 
        po.publicID AS origin_id,
        o.time_value,
        ROUND(o.latitude_value, 4) AS lat, 
        ROUND(o.longitude_value, 4) AS lon,
        ROUND(o.depth_value, 1) AS depth_km,
        o.quality_usedPhaseCount AS phases,
        o.creationInfo_creationTime AS created
    FROM Origin o
    JOIN PublicObject po ON po._oid = o._oid
    ORDER BY o.creationInfo_creationTime DESC LIMIT 5;
  "
  ```

---

## 9. Remote Management over SSH & Headless Operation

> [!TIP]
> For a full step-by-step tutorial on generating SSH keys, passwordless login, `~/.ssh/config` host aliases, multi-port service tunneling, X11 forwarding for macOS/Windows, and `tmux` session persistence, refer to the **[Remote Server Access & SSH Operations Guide](SSH_REMOTE_OPERATIONS_GUIDE.md)**.

SeisComP can be operated completely headless from another machine (e.g., Mac to Ubuntu):

### 1. Browser Configuration (`scconfig --web`)
```bash
# On Mac:
ssh -L 8080:localhost:8080 user@ubuntu-ip

# In SSH session:
seiscomp exec scconfig --web 8080

# In Mac browser:
# Navigate to http://localhost:8080
```

### 2. X11 Window Forwarding (XQuartz for Mac)
```bash
# 1. Install XQuartz on Mac: brew install --cask xquartz (log out & back in)
# 2. SSH with trusted X11 forwarding:
ssh -Y user@ubuntu-ip

# 3. Launch any GUI directly on Mac desktop:
scolv   # Origin Locator View
scmv    # Map View
```

> [!TIP]
> **Missing Basemaps in `scolv` or `scmv`?** If the map canvas renders a blank or black background, the map tiles package was not installed. Unpack `seiscomp-maps.tar.gz` into the parent directory of `$SEISCOMP_ROOT` (`cd $SEISCOMP_ROOT/.. && tar -xvf seiscomp-maps.tar.gz`) so `$SEISCOMP_ROOT/share/maps/` is populated.

---

## 10. Quick Diagnostic & Query Cheat Sheet

> [!TIP]
> For an extended, standalone command reference covering SeedLink packet inspection, PhaseNet pick filtering, MariaDB SQL queries, and database cleanup scripts, see the **[Daily CLI Operations Cheat Sheet](SEISCOMP_CLI_CHEAT_SHEET.md)**.

```bash
# Manage pipeline lifecycle:
seiscomp start                 # Start all enabled modules
seiscomp stop                  # Gracefully shut down all running modules
seiscomp restart               # Restart all enabled modules
seiscomp stop scautopick       # Stop an individual module
seiscomp check                 # Verify process table and clear stale PID locks

# Check running status of all SeisComP daemons
seiscomp status

# Verify live SeedLink packet streams from EarthScope
seiscomp exec slinktool -Q localhost:18000

# Inspect scautopick startup log (stops at 'Connection established' under default level 2 logging):
tail -n 20 ~/.seiscomp/log/scautopick.log

# Optional: Run scautopick interactively to see live STA/LTA math on screen without modifying config:
seiscomp exec scautopick --console 1 --debug

# Follow live ML picks and inference status generated by sceasyquake
tail -f ~/.seiscomp/log/sceasyquake.log

# Check recent real-time AI phase picks (PhaseNet P & S) recorded in MariaDB
mysql -u sysop -psysop seiscomp -e "
  SELECT 
      po.publicID AS pick_id,
      p.time_value,
      p.waveformID_stationCode AS sta,
      p.phaseHint_code AS phase,
      p.creationInfo_author AS author,
      p.creationInfo_creationTime AS created
  FROM Pick p
  JOIN PublicObject po ON po._oid = p._oid
  ORDER BY p.creationInfo_creationTime DESC LIMIT 10;
"

# Check associator status and pick error rates
./associator_status.sh

# Query MySQL directly for the last 10 detected origins
mysql -u sysop -psysop seiscomp -e "
  SELECT po.publicID, o.time_value, o.latitude_value, o.longitude_value, o.quality_usedPhaseCount
  FROM Origin o
  JOIN PublicObject po ON po._oid = o._oid
  ORDER BY o.time_value DESC LIMIT 10;
"

# Format complete seismological bulletin via CLI (events, hypocenters, P/S phases, residuals):
seiscomp exec scevtls -d mysql://sysop:sysop@localhost/seiscomp -l 10
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -E <event-id>
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -l 1   # Most recent event

# Run picker capacity benchmark on CPU
python sceasyquake/tests/bench_picker_capacity.py --cpu-only --channels 10 --step-seconds 5
```
