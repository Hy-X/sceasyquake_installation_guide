# SeisComP + easyQuake ML Picker: Complete Installation & Setup Guide

This guide walks you through setting up a complete, single-machine real-time earthquake monitoring system on **Ubuntu 26.04.1 LTS (Resolute Raccoon x86_64)** using **SeisComP** and **easyQuake** (deep-learning phase picking with PhaseNet, EQTransformer, and GPD).

---

## Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [Prerequisites](#prerequisites)
3. [Step 1: System Packages & MariaDB Database](#step-1-system-packages--mariadb-database)
4. [Step 2: Download & Install SeisComP](#step-2-download--install-seiscomp)
5. [Step 3: Install Python Machine Learning Dependencies](#step-3-install-python-machine-learning-dependencies)
6. [Step 4: Install sceasyquake (easyQuake_seiscomp)](#step-4-install-sceasyquake-easyquake_seiscomp)
7. [Step 5: Configure the Pipeline](#step-5-configure-the-pipeline)
8. [Step 6: Remote Access & GUI Operation via SSH](#step-6-remote-access--gui-operation-via-ssh)
9. [Step 7: Verification & Diagnostics](#step-7-verification--diagnostics)
10. [Troubleshooting](#troubleshooting)

---

## Overview & Architecture

On a single Ubuntu machine, the entire end-to-end pipeline runs locally:

```
[ Field or Public Internet Streams (e.g. EarthScope / GEOFON) ]
                           │ SeedLink
                           ▼
                 [ SeisComP SeedLink ]  (localhost:18000)
                           │
                           ▼
                  [ scmaster bus ]
                  │              │
                  │ Waveforms    │ Waveforms
                  ▼              ▼
           [ sceasyquake ]   [ slarchive ] ──► [ SDS Archive ]
           (PhaseNet ML)
                  │
                  ▼ P & S Picks + SNR Amplitudes
           [ scautoloc / scpyocto ] ──► Hypocenter Origins
                  │
                  ▼
              [ scmag ] ──► Earthquake Magnitudes
                  │
                  ▼
             [ scevent ] ──► Declares Official Events
                  │
                  ├──► [ MariaDB Database ]
                  └──► [ scolv / scmv GUIs & Alerts ]
```

---

## Prerequisites

- **OS**: Ubuntu 26.04.1 LTS (Resolute Raccoon) x86_64
- **CPU**: 4+ cores recommended
- **RAM**: Minimum 8 GB (16 GB+ recommended for large station counts)
- **Disk**: 50 GB+ free disk space
- **GPU (Optional)**: NVIDIA GPU with driver ≥ 525 (CPU-only works fine for 20–50 stations)

---

## Step 1: System Packages & MariaDB Database

Update system packages and install git, curl, and the MariaDB SQL server:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y mariadb-server git curl python3-pip libmariadb-dev
```

Secure the database installation (optional in modern Ubuntu, press Enter or set root password):
```bash
sudo mariadb-secure-installation
```

Create the `seiscomp` database, user accounts, and grant privileges:
```bash
sudo mariadb << 'EOF'
CREATE DATABASE IF NOT EXISTS seiscomp CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER IF NOT EXISTS 'sysop'@'localhost' IDENTIFIED BY 'sysop';
CREATE USER IF NOT EXISTS 'sysop'@'%' IDENTIFIED BY 'sysop';
ALTER USER 'sysop'@'localhost' IDENTIFIED BY 'sysop';
ALTER USER 'sysop'@'%' IDENTIFIED BY 'sysop';
GRANT ALL PRIVILEGES ON seiscomp.* TO 'sysop'@'localhost';
GRANT ALL PRIVILEGES ON seiscomp.* TO 'sysop'@'%';
FLUSH PRIVILEGES;
EOF
```

---

## Step 2: Download & Install SeisComP

1. Register and download the official SeisComP release tarball for Ubuntu (e.g. `seiscomp-*-ubuntu26.04-x86_64.tar.gz` or the latest compatible Ubuntu/Debian x86_64 release) from [seiscomp.de/downloader](https://www.seiscomp.de/downloader/).
2. Extract into your directory:
   ```bash
   tar -xzf seiscomp-*.tar.gz
   ```

3. **Install the Map Package (Required for Basemaps in `scolv` & `scmv`)**:
   > [!IMPORTANT]
   > The base binary package (`seiscomp-*-ubuntu26.04-x86_64.tar.gz`) is deliberately lightweight and **does not include map tiles or vector geographic layers**. Without maps, GUI applications (`scolv`, `scmv`) render blank or black map backgrounds.
   
   Download and unpack `seiscomp-maps.tar.gz` into `/home/hongyuxiao/Projects/SeiscomP`:
   ```bash
   cd /home/hongyuxiao/Projects/SeiscomP
   wget https://www.seiscomp.de/downloader/seiscomp-maps.tar.gz
   tar -xvf seiscomp-maps.tar.gz
   cd seiscomp
   ```
   *(This extracts basemaps, coastlines, and topography directly into `seiscomp/share/maps/`).*

4. **Install all Ubuntu system libraries (Qt, XML, SSL, ncurses)** automatically:
   ```bash
   sudo ./bin/seiscomp install-deps base gui mariadb-server

   # Reclaim directory ownership (prevents permission denied errors):
   sudo chown -R $USER:$USER .
   ```

5. **Initialize the Database Schema directly** (bypasses python setup script bugs on modern MariaDB 11.x):
   ```bash
   mariadb -u sysop -psysop seiscomp < share/db/mysql.sql
   ```

6. Initialize the configuration:
   ```bash
   ./bin/seiscomp setup
   ```
   *Follow the interactive prompts exactly as shown below:*
   - `Enable database storage [yes]:` Press **Enter** *(yes)*
   - `Database backend [0]:` Press **Enter** *(0: mysql/mariadb)*
   - `Create the SeisComP database [yes]:` Type **`no`** *(already created)*
   - `Database name [seiscomp]:` Press **Enter**
   - `Database hostname [localhost]:` Press **Enter**
   - `Database read-write user [sysop]:` Press **Enter**
   - `Database read-write password [sysop]:` Press **Enter** *(or type `sysop`)*
   - `Database public hostname [localhost]:` Press **Enter**
   - `Database read-only user [sysop]:` Press **Enter**
   - `Database read-only password [sysop]:` Press **Enter** *(or type `sysop`)*
   - `Command? [P]:` Press **Enter** *(Proceed to apply configuration)*

7. **Add SeisComP to your environment (`~/.bashrc`)**:
   ```bash
   cat << 'EOF' >> ~/.bashrc

   # SeisComP Environment
   export SEISCOMP_ROOT=/home/hongyuxiao/Projects/SeiscomP/seiscomp
   export PATH=$SEISCOMP_ROOT/bin:$PATH
   export LD_LIBRARY_PATH=$SEISCOMP_ROOT/lib:$LD_LIBRARY_PATH
   export PYTHONPATH=$SEISCOMP_ROOT/lib/python:$PYTHONPATH
   EOF

   source ~/.bashrc
   ```

---

## Step 3: Install Python Machine Learning Dependencies

SeisComP runs its own embedded Python bindings. You must install PyTorch, SeisBench, and ObsPy into **SeisComP's Python interpreter**.

> [!NOTE]
> Modern Ubuntu (24.04 / 26.04 LTS) enforces **PEP 668** (`externally-managed-environment`). If you are using system Python bindings outside a dedicated conda/virtual environment, append `--break-system-packages` to the `pip` commands below.

```bash
# 1. Navigate to your SeisComP root directory and identify SeisComP's Python binary
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp
export SC_PYTHON=$(bin/seiscomp exec which python3)
echo "SeisComP Python: $SC_PYTHON"

# 2. Upgrade pip and install core scientific libraries
$SC_PYTHON -m pip install --upgrade pip --break-system-packages
$SC_PYTHON -m pip install obspy scipy numpy PyYAML watchdog psutil seisbench --break-system-packages

# 3. Install PyTorch:
# OPTION A: CPU-only (recommended for learning / standard machines)
$SC_PYTHON -m pip install torch --index-url https://download.pytorch.org/whl/cpu --break-system-packages

# OPTION B: NVIDIA GPU / CUDA 12.x (if you have an NVIDIA GPU)
# $SC_PYTHON -m pip install torch --index-url https://download.pytorch.org/whl/cu121 --break-system-packages
```

### 4. Verify the Python Environment & Dependencies

Run this verification one-liner to confirm all libraries load into SeisComP's Python environment:

```bash
$SC_PYTHON -c 'import torch, seisbench, obspy; print("Dependencies successfully loaded. CUDA Available:", torch.cuda.is_available())'
```
*Expected Output:*
```text
Dependencies successfully loaded. CUDA Available: True  (or False if CPU-only)
```

---

## Step 4: Install sceasyquake (easyQuake_seiscomp)

Clone this repository and run the automated installer, passing your SeisComP root path:

```bash
# 1. Clone into your Projects directory alongside SeiscomP
cd /home/hongyuxiao/Projects
git clone https://github.com/jakewalter/easyQuake_seiscomp.git
cd easyQuake_seiscomp/sceasyquake

# 2. Run the installer, explicitly passing your SeisComP installation directory:
bash install.sh /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 3. On modern Ubuntu (PEP 668), register the editable package with pip:
$SC_PYTHON -m pip install -e /home/hongyuxiao/Projects/easyQuake_seiscomp/sceasyquake --break-system-packages

# 4. Verify that sceasyquake imports cleanly:
$SC_PYTHON -c 'import sceasyquake; print("sceasyquake loaded successfully")'
```

*(Optional)* If you also wish to use **PyOcto** for high-throughput phase association:
```bash
$SC_PYTHON -m pip install pyocto pandas --break-system-packages
cd /home/hongyuxiao/Projects/easyQuake_seiscomp/scpyocto
bash install.sh /home/hongyuxiao/Projects/SeiscomP/seiscomp
```

---

## Step 5: Configure the Pipeline

### Architecture Overview: Who Does What?

Before enabling modules, understand how tasks are divided in this AI-enhanced pipeline:

```
[ SeedLink ] ──► [ sceasyquake ] ──► P & S Picks ──► [ Associator ] ──► [ scevent ] ──► [ Database / scolv ]
                  (AI Picker)                        - scautoloc          (Event          (Relocation &
                                                     - scpyocto           Declaring)       Human Review)
                                                     - scphasepapy
```

* **Phase Picking (`sceasyquake`)**: Replaces the legacy STA/LTA picker (`scautopick`). It continuously evaluates 3-component waveforms using deep neural networks (PhaseNet / EQTransformer) and publishes high-precision P-wave and S-wave picks with SNR amplitudes onto the message bus. `sceasyquake` does **not** associate picks or calculate hypocenters.
* **Phase Association Options**:
  1. **`scautoloc` (Default)**: Native SeisComP associator using classic grid search and the `LOCSAT` locator. Works out of the box.
  2. **`scpyocto` (PyOcto)**: Modern AI-era associator using 3D KD-tree octree search. Ideal for dense microseismic networks and high pick rates.
  3. **`scphasepapy` (PhasePaPy)**: 1D regional velocity associator (developed at the Oklahoma Geological Survey). Excellent for local regional models where P and S phase pairs need strict 1D velocity constraints.
* **Locating & Relocation Engines**:
  1. **`LOCSAT`**: Fast 1D linear matrix inversion (built into SeisComP; used by `scautoloc`, `screloc`, and `scolv`).
  2. **`NonLinLoc` (NLL)**: Anthony Lomax's non-linear, probabilistic 3D/1D global-search grid locator. Standard in the standalone `easyQuake` python package, and available in SeisComP via the `nll` locator plugin for high-precision hypocenter uncertainty scatter clouds.
* **Human Review & Relocation (`scolv` / `screloc`)**: Analysts review waveforms in **`scolv`** (GUI) or run **`screloc`** (CLI) to fix depth, prune bad phases, switch locators (LOCSAT $\leftrightarrow$ NonLinLoc), and commit manual verified origins.

---

### 1. Disable the traditional STA/LTA picker and enable sceasyquake
```bash
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

bin/seiscomp disable scautopick
bin/seiscomp enable sceasyquake
bin/seiscomp update-config
```

### 2. Configure `sceasyquake.cfg`
Edit `$SEISCOMP_ROOT/etc/sceasyquake.cfg` (or `/home/hongyuxiao/Projects/SeiscomP/seiscomp/etc/sceasyquake.cfg`):

```ini
# SeedLink source (local acquisition)
seedlink.host = localhost
seedlink.port = 18000

# Stream selectors (e.g. all 3-component HH and BH channels for network 'OK')
streams.codes = OK.????..HH?, OK.????..BH?

# ML Picker Model & Backend
picker.backend        = seisbench  # options: seisbench | easyquake
picker.model          = phasenet   # options: phasenet | eqtransformer | gpd
picker.pretrained     = stead      # weights: stead, diting, ethz, scedc
picker.device         = cpu        # change to 'cuda' if using GPU
picker.threshold      = 0.5

# Sliding Buffer Parameters
picker.buffer_seconds     = 60
picker.step_seconds       = 5
picker.max_batch_stations = 150    # default is 64; raise to 150-200 to process all stations simultaneously
```

### 3. Ensure `scautoloc` is configured to associate AI picks
Because `sceasyquake` attaches **SNR** amplitude estimates to its picks, `scautoloc` must be configured to recognize `snr` amplitudes so it associates them immediately without waiting for legacy amplitude modules. 

Ensure `$SEISCOMP_ROOT/etc/scautoloc.cfg` contains:
```ini
# Accept sceasyquake SNR amplitudes immediately:
autoloc.amplTypeAbs = snr
autoloc.amplTypeSNR = snr
autoloc.minPickSNR  = 0

# Regional depth & gap constraints (prevents 750 km teleseismic mislocations):
autoloc.maxDepth = 40.0
autoloc.maxAzimuthalGap = 300
```

### 4. Start, Stop, or Restart SeisComP
```bash
# Start all enabled modules:
seiscomp start
seiscomp status

# Gracefully shut down all modules:
seiscomp stop

# Restart the pipeline:
seiscomp restart
```

---

## Step 6: Remote Access & GUI Operation via SSH

If the Ubuntu server is headless or remote, you can interact with it from your local machine (e.g., Mac or laptop):

### Option 1: Web-Based Configuration (`scconfig`)
1. Connect via SSH with port forwarding:
   ```bash
   ssh -L 8080:localhost:8080 user@your-ubuntu-ip
   ```
2. Start the web configuration server in headless/offscreen mode:
   ```bash
   QT_QPA_PLATFORM=offscreen ./bin/seiscomp exec scconfig --web 8080
   ```
   *(Note: If Qt complains about missing cursor libraries on headless Ubuntu, run `sudo apt install -y libxcb-cursor0`).*
3. Open `http://localhost:8080` in Chrome/Safari on your local machine.

### Option 2: X11 GUI Forwarding (for `scolv` and `scmv`)
1. On your Mac, install [XQuartz](https://www.xquartz.org/) (`brew install --cask xquartz`).
2. Log out and back into your Mac once.
3. SSH into the Ubuntu machine with `-Y`:
   ```bash
   ssh -Y user@your-ubuntu-ip
   ```
4. Launch the GUI:
   ```bash
   scolv   # Origin Locator View
   # or
   scmv    # Map View
   ```
   The GUI window will render directly on your local screen.

---

## Step 7: Verification & Diagnostics

Run these commands inside your SSH terminal to ensure everything is operating smoothly:

### 1. Check all modules are running
```bash
seiscomp status
```

### 2. Follow live ML phase picks in real time
```bash
# Follow sceasyquake daemon log:
tail -f ~/.seiscomp/log/sceasyquake.log

# Or filter directly for published AI picks:
tail -f ~/.seiscomp/log/sceasyquake.log | grep -E "Published Pick|Inference:"
```

### 3. Check Live AI Phase Picks in MariaDB
In SeisComP's database schema, `publicID` is stored in the `PublicObject` table (linked via `_oid`). Run this query to inspect incoming AI picks, phase types (`P` vs `S`), and author tags:

```bash
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
ORDER BY p.creationInfo_creationTime DESC
LIMIT 15;
"
```
*(Notice both `P` and `S` phases appear, confirming 3-component PhaseNet deep-learning classification).*

### 4. Check for Recent Earthquakes / Origins in MariaDB
To verify that `scautoloc` is actively associating the AI picks into hypocenter solutions (earthquakes):

```bash
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
ORDER BY o.creationInfo_creationTime DESC
LIMIT 10;
"
```

### 5. Inspect Event & Origin Bulletins via CLI (`scbulletin` & `scevtls`)
SeisComP includes built-in CLI utilities to query declared events and format full seismological bulletins (including phase arrival lists, travel-time residuals, and station weights) directly from MariaDB:

```bash
# List recent events:
seiscomp exec scevtls -d mysql://sysop:sysop@localhost/seiscomp -l 10

# Print complete bulletin for a specific event ID:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -E <event-id>

# Or print bulletin for the most recent declared event:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -l 1

# Or inspect an Origin directly by its publicID:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -O <origin-id>
```

### 6. Run Associator Health Diagnostic
```bash
cd ~/easyQuake_seiscomp
./associator_status.sh
```

### 7. Run the Capacity Benchmark
Test how many channels your CPU/GPU can process per 5-second interval:
```bash
cd ~/easyQuake_seiscomp/sceasyquake
python tests/bench_picker_capacity.py --cpu-only --channels 20 --step-seconds 5
```

---

## Key Bug Fixes & Architecture Adaptations for sceasyquake

During deployment with modern Python (3.12+) and SeisComP, several critical low-level protocol and schema issues were identified and resolved in `sceasyquake/lib/sceasyquake/stream/seiscomp_stream.py`:

### 1. ObsPy SeedLink Connection Timeout Bug (`TypeError`)
* **Problem**: In ObsPy's `EasySeedLinkClient`, `self.conn.timeout` is initialized to `None` by default. Inside `is_connected_impl`, it checks:
  ```python
  (time.time() - start_time) < timeout
  ```
  In Python 3, comparing a `float` with `NoneType` raises `TypeError: '<' not supported between instances of 'float' and 'NoneType'`. This caught `sceasyquake` in an infinite reconnect loop:
  `SeisCompStream.connect() attempt X failed ("cannot connect to SeedLink server: '<' not supported between instances of 'float' and 'NoneType'")`.
* **Fix**: In `seiscomp_stream.py`, subclass `EasySeedLinkClient` and explicitly initialize:
  ```python
  class _Client(EasySeedLinkClient):
      def __init__(self, *args, **kwargs):
          super().__init__(*args, **kwargs)
          if hasattr(self, 'conn') and self.conn is not None:
              self.conn.timeout = 10.0
  ```

### 2. SeedLink Protocol Wildcard Limitation (`'no stations accepted'`)
* **Problem**: In the SeedLink v3 protocol used by SeisComP's C daemon, channel selectors support wildcards (`SELECT HH?`), but the `STATION` handshake command requires **literal station names** (`STATION ALVA OK`). When `sceasyquake` attempted to send wildcard patterns like `OK.*..HH?` or `OK.????..HH?`, SeedLink rejected the handshake with:
  `obspy.clients.seedlink [localhost:18000]: response: station not accepted, skipping`
  `obspy.clients.seedlink [localhost:18000]: negotiation with remote SeedLink failed: 'no stations accepted'`.
* **Fix**: Implemented **Station Auto-Discovery** (`_get_seedlink_stations`) in `seiscomp_stream.py`. When a stream pattern contains wildcards (`*` or `?`), `sceasyquake` queries SeedLink via `INFO STATIONS`, extracts all active stations matching the network pattern (e.g. all 140 Oklahoma stations), and subscribes to each station explicitly via `client.select_stream(net, sta, selector)`.

### 3. Batch Cap Throttle Tuning (`picker.max_batch_stations`)
* **Context**: `worker.py` contains a batch cap (default 64 stations per step) to prevent weak CPUs from accumulating lag. When monitoring a large network (e.g., 118 live stations in Oklahoma), the log reports:
  `Batch cap hit: 118 eligible stations, processing 64 this step (consider raising picker.max_batch_stations)`.
* **Tuning**:
  * On **CPU**: 64 stations every 5–6 seconds provides a stable throughput without falling behind real time. Overdue stations are prioritized first.
  * On **GPU (`picker.device = cuda`)**: PhaseNet runs in ~0.2s for 150+ stations. You can safely raise `picker.max_batch_stations = 150` or `200` in `etc/sceasyquake.cfg` to evaluate all stations simultaneously on every step.

### 4. Database Schema Structure (`PublicObject` Joins)
* **Context**: SeisComP uses an object-relational mapping where global unique IDs (`publicID`) are kept in the `PublicObject` table. Running `SELECT publicID FROM Pick;` causes `ERROR 1054: Unknown column 'publicID'`. Always join `PublicObject po ON po._oid = p._oid` and use `p.creationInfo_author` for author metadata.

---

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `seisbench not available` or `No module named torch` | Installed in system Python rather than SeisComP's Python | Ensure you ran `$SC_PYTHON -m pip install ...` where `$SC_PYTHON` is `$(seiscomp exec which python3)`. |
| `Cannot connect to database` | MariaDB service is stopped or bad credentials | Check `sudo systemctl status mariadb` and verify user `sysop` password in `$HOME/seiscomp/etc/global.cfg`. |
| `Client name not unique` | An old `sceasyquake` process is still running | Run `pkill -f sceasyquake-stream` then restart via `seiscomp restart sceasyquake`. |
| `Zero origins created` | `scautoloc` waiting for SNR amplitudes | Ensure `autoloc.amplTypeAbs = snr` is added to `$HOME/seiscomp/etc/scautoloc.cfg`. |
| GPU stays at 0% utilization | Configured for CPU device | Set `picker.device = cuda` in `sceasyquake.cfg` and verify `torch.cuda.is_available()`. |
| `No stations added (empty module configuration?)` | Station bindings missing, `detecStream` channel mismatch, or forgot `seiscomp update-config` | Ensure `detecStream = HH` in `etc/key/global/profile_default`, bind via `seiscomp shell`, and run `seiscomp update-config`. |
| `seiscomp status` exits blank or code 245 | `$SEISCOMP_ROOT` points to outer directory without `etc/descriptions` | Ensure `SEISCOMP_ROOT=/home/hongyuxiao/Projects/SeiscomP/seiscomp` in `~/.bashrc` and `source ~/.bashrc`. |
| `scdumppicks: not found` | Obsolete command removed in modern SeisComP 5/6/7 | Use `tail -f ~/.seiscomp/log/scautopick.log` or direct MariaDB SQL queries on the `Pick` table. |
| `cannot connect to SeedLink server: '<' not supported between instances of 'float' and 'NoneType'` | In Python 3, ObsPy's `EasySeedLinkClient` leaves `self.conn.timeout = None` by default, causing `is_connected_impl` to compare `float < None` | Set `self.conn.timeout = 10.0` inside `_Client.__init__` in `sceasyquake/lib/sceasyquake/stream/seiscomp_stream.py`. |
| `negotiation with remote SeedLink failed: 'no stations accepted'` | SeedLink v3 protocol rejects station wildcards (`*` or `????`) during the `STATION` handshake command | Use `_get_seedlink_stations()` auto-discovery in `seiscomp_stream.py` to query active stations via `INFO STATIONS` and subscribe explicitly. |
| `Batch cap hit: N eligible stations, processing 64 this step` | Default safety throttle (`picker.max_batch_stations = 64`) to protect single-threaded CPUs from lag | Overdue stations are prioritized first; on GPU or multi-core CPU, raise `picker.max_batch_stations = 150` in `etc/sceasyquake.cfg`. |
| `ERROR 1054: Unknown column 'publicID'` in MariaDB | In SeisComP's relational schema, universal IDs are stored in the `PublicObject` table | Join `PublicObject po ON po._oid = Pick._oid` to access `publicID`. |
| `scolv` or `scmv` shows blank / black map background | The base SeisComP release tarball does not contain map tiles/layers | Download `https://www.seiscomp.de/downloader/seiscomp-maps.tar.gz` to `/home/hongyuxiao/Projects/SeiscomP` and run `tar -xvf seiscomp-maps.tar.gz`. |
