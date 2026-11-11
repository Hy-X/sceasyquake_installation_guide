# Native SeisComP Workflow Guide: Learning with scautopick

This guide walks you through the **native, standard SeisComP workflow** using the built-in traditional picker (**`scautopick`**). 

By mastering this baseline setup first, you will understand how stations are added, how waveforms flow through SeedLink, how STA/LTA triggers work, and how events appear in **`scolv`**—before substituting in machine learning (`sceasyquake`).

---

## Table of Contents
1. [Workflow Architecture](#1-workflow-architecture)
2. [Step 1: Ingest Live Waveforms (Public SeedLink Chaining)](#step-1-ingest-live-waveforms-public-seedlink-chaining)
3. [Step 2: Understand & Configure SeisComP "Bindings"](#step-2-understand--configure-seiscomp-bindings)
4. [Step 3: Managing the Pipeline (Enable, Start, Stop, Status)](#step-3-managing-the-pipeline-enable-start-stop-status)
5. [Step 4: Real-Time Monitoring & Verification](#step-4-real-time-monitoring--verification)
6. [Step 5: Visualizing Traces & Origins (`scrttv`, `scmv`, `scolv`)](#step-5-visualizing-traces--origins-scrttv-scmv-scolv)
7. [Step 6: The Bridge — Upgrading to sceasyquake (ML)](#step-6-the-bridge--upgrading-to-sceasyquake-ml)
8. [Step 7: Scaling Up — Adding More Stations & Networks](#step-7-scaling-up--adding-more-stations--networks)
9. [Step 8: Troubleshooting & Real-World Gotchas](#step-8-troubleshooting--real-world-gotchas)

---

## 1. Workflow Architecture

In native SeisComP, the processing pipeline uses **`scautopick`** (the STA/LTA algorithm):

```
[ Public Live SeedLink (e.g. EarthScope / IRIS) ]
                    │
                    ▼ SeedLink Chain
          [ Local seedlink ]  (localhost:18000)
                    │
                    ▼ Waveforms
             [ scmaster bus ]
             │              │
             │ Waveforms    │ Raw files
             ▼              ▼
       [ scautopick ]  [ slarchive ] ──► [ SDS Archive (miniSEED) ]
       (STA/LTA algorithm)
             │
             ▼ P-picks
       [ scautoloc ] ──► Triangulates Hypocenter (Origins)
             │
             ▼
         [ scamp ]   ──► Measures Peak Amplitudes
             │
             ▼
         [ scmag ]   ──► Calculates Magnitudes (ML, mb, etc.)
             │
             ▼
        [ scevent ]  ──► Groups Origins & Declares Events
             │
             ├──► [ MariaDB Database ]
             └──► [ Operator GUIs: scrttv, scmv, scolv ]
```

---

## Step 1: Ingest Live Waveforms (Public SeedLink Chaining)

You don't need local hardware or physical sensors. SeisComP can pull real-time data from free national servers (like **EarthScope / IRIS**):

### Example Target: 5 Stations from Oklahoma Geological Survey (`OK`)
- `OK.ALVA` (Alva, OK)
- `OK.AMES` (Ames, OK)
- `OK.ARC2` (Arcadia, OK)
- `OK.BAUM` (Baum, OK)
- `OK.BCOK` (Blaine County, OK)

### Method A: Configure via Web `scconfig` (Recommended)
1. Start the headless web configuration interface:
   ```bash
   QT_QPA_PLATFORM=offscreen ./bin/seiscomp exec scconfig --web 8080
   ```
2. In your Mac's browser, open **`http://localhost:8080`**.
3. Navigate to: **Inventory** $\to$ **Import** $\to$ **FDSN Web Services**.
4. Set URL to `http://service.iris.edu` and query stations:
   - Network: `OK`
   - Station: `ALVA,AMES,ARC2,BAUM,BCOK`
   - Channel: `HHZ,HHN,HHE`
5. Click **Import**, then click the **Save** icon (top left).

### Method B: Configure via CLI (Pure Terminal)

Make sure you are in your actual SeisComP directory:
```bash
export SEISCOMP_ROOT=/home/hongyuxiao/Projects/SeiscomP/seiscomp
cd $SEISCOMP_ROOT
```

Download station metadata directly into SeisComP inventory using `curl` and SeisComP's inventory synchronizer:

```bash
# 1. Download official StationXML from IRIS FDSN for the 5 OK stations (HH and BH channels)
mkdir -p /home/hongyuxiao/Projects/SeiscomP/stationxml
curl -sL "https://service.iris.edu/fdsnws/station/1/query?net=OK&sta=ALVA,AMES,ARC2,BAUM,BCOK&cha=HH?,BH?&level=response&format=xml" \
  -o /home/hongyuxiao/Projects/SeiscomP/stationxml/OK_stations.xml

# 2. Import into SeisComP's inventory directory
mkdir -p etc/inventory
bin/seiscomp exec fdsnxml2inv /home/hongyuxiao/Projects/SeiscomP/stationxml/OK_stations.xml etc/inventory/inventory_OK.xml

# 3. Synchronize inventory with the database
bin/seiscomp exec scinv sync
```

---

## Step 2: Understand & Configure SeisComP "Bindings"

### 1. The Mental Model: Why Doesn't SeisComP Pick Every Station Automatically?
When you import an inventory (like from EarthScope or GEOFON), your database might contain metadata for **hundreds or thousands of stations** worldwide. 

If SeisComP automatically connected to and processed every station, your server would instantly crash from network overload and memory starvation.

Therefore, SeisComP uses **Bindings**:
> **A Binding is an explicit contract** that tells SeisComP: *"Activate station X for module Y, and apply configuration profile Z."*

If a station is in your inventory database but has **no bindings**, SeisComP treats it as dormant and completely ignores it.

---

### 2. The 3-Tier Configuration Architecture

SeisComP organizes station settings into three distinct layers:

```
[ Tier 1: Profiles ]  (Reusable Templates)
   etc/key/global/profile_default        ──► "Detect on HH channels (100 Hz)"
   etc/key/seedlink/profile_iris         ──► "Pull streams from rtserve.earthscope.org:18000"
   etc/key/scautopick/profile_default    ──► "Use STA/LTA filter: RMHP(10)>>ITL(0.2)>>BW(4,1,20)"
                    │
                    ▼ Assigned via "seiscomp shell"
[ Tier 2: Station Bindings ]  (Master file in etc/key/ linking a Station to Profiles)
   etc/key/station_OK_ALVA               ──► contains:
                                               global:default
                                               seedlink:iris
                                               scautopick:default
                    │
                    ▼ Compiled by "seiscomp update-config"
[ Tier 3: Runtime Daemon Files ]  (What C++ Daemons Actually Read)
   var/run/seedlink/seedlink.ini         ──► SeedLink connects to EarthScope for OK.ALVA
   var/run/scautopick.cfg                ──► scautopick listens for OK.ALVA HHZ
```

> [!NOTE]
> **Understanding Master Station Keys vs. Module Subfolders (Backward Compatibility)**  
> You may encounter two different layout styles for station bindings in SeisComP:
> 1. **Modern Consolidated Master Key (`etc/key/station_<NET>_<STA>`)**: When you run `seiscomp shell` or `scconfig`, SeisComP creates a **single consolidated file** per station directly inside `etc/key/`. That file lists all module bindings in one place (`global:default`, `seedlink:iris`, `scautopick:default`). This prevents filesystem bloat (in a 2,000-station network, it avoids creating 16,000 separate files across 8 subdirectories).
> 2. **Legacy Per-Module Subfolders (`etc/key/<module>/station_<NET>_<STA>`)**: Older versions or manual tutorials split each module's binding into its own subfolder (e.g. `etc/key/seedlink/station_OK_ALVA` containing just `iris`).
> 3. **Backward Compatibility**: `seiscomp update-config` supports both formats simultaneously! If an older station has files in `etc/key/<module>/` while newly added stations only exist as `etc/key/station_*`, SeisComP automatically merges them. The canonical list of active stations on your system is always `ls etc/key/station_*`.

---

### 3. The Three Essential Modules Every Station Needs

To process a seismic station from acquisition to pick detection, you must configure **three distinct modules**:

| Module Binding | Directory | What It Controls | Real-World Example |
|---|---|---|---|
| **`global`** | `etc/key/global/` | General station properties shared by all modules. | Defines `detecStream = HH` (100 Hz broadband) and `detecLocid = ""` (empty location code). Tells picker/locator which stream to evaluate. |
| **`seedlink`** | `etc/key/seedlink/` | Real-time waveform acquisition. | Defines `sources = chain` and `sources.chain.address = rtserve.earthscope.org`. Tells SeedLink where to fetch raw data over TCP. |
| **`scautopick`** | `etc/key/scautopick/` | Detection algorithm parameters. | Defines the bandpass filter, STA/LTA time windows, and threshold ratio. |

---

### 4. Why Do We Use Profiles Instead of Hardcoding Each Station?
Imagine you are operating 50 broadband stations on bedrock and 20 geophones on soft sediment:
* Instead of configuring all 70 stations individually, you create two profiles:
  * `profile_rock` (high-frequency filter: 2–15 Hz)
  * `profile_sediment` (low-frequency filter: 0.5–5 Hz)
* You then simply bind stations to their matching profile. If you ever want to adjust a filter, you edit **one** profile file, and all 50 stations update simultaneously!

---

### 5. Why `seiscomp update-config` is Mandatory

> [!IMPORTANT]
> **C++ daemons (like `scautopick` and `seedlink`) DO NOT read `etc/key/` directly!**
> 
> Reading hundreds of individual station text files repeatedly during runtime would cause severe disk bottlenecks. 
> 
> Instead, **`seiscomp update-config` acts as a compiler**:
> 1. It scans your inventory XML files (`etc/inventory/`).
> 2. It inspects all station binding files (`etc/key/*`).
> 3. It combines them with system defaults (`etc/*.cfg`).
> 4. It compiles everything into optimized, consolidated runtime configuration files under **`var/run/`**.
>
> If you create bindings but forget to run `seiscomp update-config`, the daemons will read empty configurations and immediately terminate with:
> `[error/Autopick] No stations added (empty module configuration?) and thus nothing to do`

---

### 6. Step-by-Step Configuration Commands

Run this complete block to create the profiles, bind all 5 Oklahoma stations, and compile the configuration:

```bash
# 1. Ensure you are in your SeisComP directory
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 2. Define the SeedLink chain profile for EarthScope (pulling HH and BH channels)
mkdir -p etc/key/seedlink
cat << 'EOF' > etc/key/seedlink/profile_iris
sources = chain
sources.chain.address = rtserve.earthscope.org
sources.chain.port = 18000
sources.chain.selectors = HH? BH?
EOF

# 3. Define the global profile (detect on HH and BH channels, location code "")
mkdir -p etc/key/global
cat << 'EOF' > etc/key/global/profile_default
detecStream = "HH,BH"
detecLocid = ""
EOF

# 4. Define the scautopick STA/LTA detector profile
mkdir -p etc/key/scautopick
cat << 'EOF' > etc/key/scautopick/profile_default
filter = "RMHP(10)>>ITL(0.2)>>BW(4,1.0,20.0)"
timeCorr = 0.0
ringBufferSize = 100
EOF

# 5. Bind all Oklahoma stations to their profiles using SeisComP's CLI shell
bin/seiscomp shell << 'EOF'
set profile global default OK.*
set profile seedlink iris OK.*
set profile scautopick default OK.*
exit
EOF

# 6. Compile all bindings into active runtime files (MANDATORY)
bin/seiscomp update-config
```

---

### 7. Regional Associator Constraints (`etc/scautoloc.cfg`)

By default, SeisComP's associator (`scautoloc`) operates without depth caps or azimuthal gap limits. For a regional network (such as Oklahoma or Texas), steep incoming teleseismic wavefronts from distant global earthquakes can be mistakenly fit as "750 km deep" local events or one-sided array solutions. 

Apply crustal constraints by creating a user override configuration in `etc/scautoloc.cfg`:

```bash
# Make sure you are in /home/hongyuxiao/Projects/SeiscomP/seiscomp
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# Create user override file
cat << 'EOF' >> etc/scautoloc.cfg
# Maximum hypocenter depth in km (discards deep teleseismic mislocations)
autoloc.maxDepth = 40.0

# Prevent one-sided array solutions (rejects solutions with >300 deg gap)
autoloc.maxAzimuthalGap = 300
EOF

bin/seiscomp update-config scautoloc
bin/seiscomp restart scautoloc
```

#### How to Verify the Bindings Were Created:
You can inspect the generated station binding files directly in your filesystem. In SeisComP, master station bindings live directly in `etc/key/station_<NET>_<STA>`:

```bash
# Check that master station key files exist for your stations:
ls -l etc/key/station_OK_*

# Count the total number of bound stations:
ls -l etc/key/station_OK_* | wc -l

# Inspect any station's active module profiles:
cat etc/key/station_OK_ALVA
```
*Expected Output:*
```text
global:default
seedlink:iris
scautopick:default
```

> [!NOTE]
> **Why `ls etc/key/seedlink/station_OK_*` might only show 5 stations:**  
> Subdirectories like `etc/key/seedlink/`, `etc/key/global/`, and `etc/key/scautopick/` store **reusable profile templates** (e.g. `profile_iris`, `profile_default`). While earlier manual tutorials or older SeisComP versions created per-station text files in those subfolders, modern `seiscomp shell` consolidates all station bindings directly into master files under `etc/key/station_<NET>_<STA>`. Due to SeisComP's built-in **backward compatibility**, `seiscomp update-config` reads both. As long as `etc/key/station_OK_*` exists, the station is fully active.

---

## Step 3: Enable & Start the Native Pipeline

Enable the core native modules and start the system:

```bash
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# Enable acquisition, database, picker, locator, amplitude, magnitude, event, and waveform archive
./bin/seiscomp enable seedlink scdb scautopick scautoloc scamp scmag scevent slarchive

# Update config & restart
./bin/seiscomp update-config
./bin/seiscomp restart
```

> [!TIP]
> **What Gets Saved: Metadata (`scdb`) vs Raw Waveforms (`slarchive`)**
> - **`scdb` (Database)**: Writes all detection objects (picks, amplitudes, triangulated hypocenters, magnitudes, events) permanently to **MariaDB**.
> - **`slarchive` (SDS Waveform Archive)**: Permanently writes raw continuous miniSEED waveform files to disk under `$SEISCOMP_ROOT/var/lib/archive/` in standard **SDS structure** (`YEAR/NET/STA/CHAN.D/NET.STA.LOC.CHAN.D.YEAR.JULIANDAY`).
> - *Without `slarchive`, waveforms only reside in SeedLink's temporary memory ring buffer (~1–2 hours) and are overwritten once the buffer fills up.*
> - For 5 stations (15 channels at 100 Hz), continuous archiving requires only **~20 MB per day (~600 MB per month)** of disk space.

Verify that all modules report **running**:
```bash
./bin/seiscomp status
```
*Expected Output:*
```
scmaster             is running
scdb                 is running
seedlink             is running
slarchive            is running
scautopick           is running
scautoloc            is running
scamp                is running
scmag                is running
scevent              is running
```

> [!IMPORTANT]
> **Verify `scautopick` Did Not Immediately Shut Down:**
> If station bindings were missing or `seiscomp update-config` was not run, `scautopick` will exit within 1 second of starting.
> Check the log:
> ```bash
> tail -n 20 ~/.seiscomp/log/scautopick.log
> ```
> A **healthy** running log must look like:
> ```text
> 2026/10/23 14:42:18 [notice/Application] Starting scautopick 
> 2026/10/23 14:42:18 [notice/Application]   Framework   : 7.4.0 Release
> 2026/10/23 14:42:18 [notice/Application]   API Version : 17.4.0
> 2026/10/23 14:42:18 [notice/Application] Connection to localhost/production established
> ```
> If you see `[error/Autopick] No stations added (empty module configuration?) and thus nothing to do` followed by `Shutdown`, see [Step 7: Troubleshooting](#step-7-troubleshooting--real-world-gotchas).

---

### How to Stop, Pause, or Restart SeisComP

#### 1. Stop the Entire System (All Modules)
To gracefully shut down all running background daemons:
```bash
seiscomp stop
```
*Expected Output:*
```text
shutting down scevent
shutting down scmag
shutting down scamp
shutting down scautoloc
shutting down scautopick
shutting down slarchive
shutting down seedlink
shutting down scdb
shutting down scmaster
Summary: 9 modules stopped
```

#### 2. Stop an Individual Module
You do not need to take down the entire system when tweaking or debugging a single component:
```bash
# Stop just the picker:
seiscomp stop scautopick

# Stop just SeedLink acquisition:
seiscomp stop seedlink
```

#### 3. Start or Restart Modules
```bash
# Start all enabled modules:
seiscomp start

# Start or restart a single module:
seiscomp start scautopick
seiscomp restart scautopick

# Restart the entire pipeline:
seiscomp restart
```

#### 4. Disable a Module (Prevent Auto-Start)
If you want to deactivate a module so it does not launch when running `seiscomp start` (such as when replacing `scautopick` with `sceasyquake`):
```bash
seiscomp disable scautopick
```
*(To re-enable it later: `seiscomp enable scautopick`).*

#### 5. Emergency Stop / Killing Stuck Daemons
If a daemon hangs or an ungraceful shutdown leaves stale PID lock files in `var/run/`:
```bash
# 1. Clean up stale PID locks and verify process states:
seiscomp check

# 2. Force-kill all SeisComP background processes if they refuse to exit:
pkill -9 -f scmaster
pkill -9 -f seedlink
pkill -9 -f scautopick
```

---

## Step 4: Real-Time Monitoring & Verification

### 1. Verify Live Waveforms are Streaming (SeedLink)
Check that your local SeedLink is actively receiving data packets from EarthScope (IRIS):
```bash
seiscomp exec slinktool -Q localhost:18000
```
*Expected Output: You will see your 5 Oklahoma stations (`ALVA`, `AMES`, `ARC2`, `BAUM`, `BCOK`) streaming 100 Hz `HH` channels with up-to-the-second timestamps:*
```text
OK ALVA     HHE D 2026/10/23 19:54:37.9300  -  2026/10/23 19:55:07.2100
OK ALVA     HHN D 2026/10/23 19:54:35.2900  -  2026/10/23 19:55:08.0500
OK ALVA     HHZ D 2026/10/23 19:54:37.8300  -  2026/10/23 19:55:08.4300
OK AMES     HHZ D 2026/10/23 19:54:37.8000  -  2026/10/23 19:55:06.5000
OK ARC2     HHZ D 2026/10/23 19:54:34.5500  -  2026/10/23 19:55:07.5100
OK BAUM     HHZ D 2026/10/23 19:54:36.9200  -  2026/10/23 19:55:05.7600
OK BCOK     HHZ D 2026/10/23 19:54:35.1000  -  2026/10/23 19:55:07.1200
```

To check packet throughput and data rates:
```bash
seiscomp exec slinktool -p localhost:18000
```

### 2. Understanding Daemon Logs vs Real-Time Detections
You will notice that `tail -f ~/.seiscomp/log/scautopick.log` stops printing after:
```text
2026/10/23 15:07:28 [notice/Application] Connection to localhost/production established
```
**This is completely normal and expected production design:**
- SeisComP sets all background daemons to **`logging.level = 2` (Notice)** by default to preserve disk health and avoid massive log files when monitoring tens or hundreds of channels.
- Individual arrival picks are classified as **Level 3 (Info)** and are **not written to the `.log` text file** under default production settings.
- Instead, `scautopick` publishes pick objects in-memory directly to the `scmaster` messaging bus. From there:
  1. **`scdb`** captures them and records them permanently in the **MariaDB `Pick` table**.
  2. **`scrttv`** captures them and draws vertical pick markers (`P`) directly on the live continuous waveforms.
  3. **`scautoloc`** captures them and begins triangulating hypocenters.

> [!NOTE]
> **Optional Console Debugging (Without Modifying Config):**
> If you ever want to temporarily observe `scautopick`'s raw internal STA/LTA evaluations and trigger calculations live on your screen, you can run:
> ```bash
> seiscomp exec scautopick --console 1 --debug
> ```
> Press `Ctrl+C` to exit. For routine monitoring, keep the default configuration and check arrivals via MariaDB or `scrttv`.

### 3. Check Recent Picks in MariaDB
The `scdb` daemon automatically writes all detections to your local MariaDB database. Query the `Pick` table directly:
```bash
mysql -u sysop -psysop seiscomp -e "
  SELECT time_value, waveformID_networkCode, waveformID_stationCode, 
         waveformID_channelCode, phaseHint_code, creationInfo_agencyID 
  FROM Pick 
  ORDER BY time_value DESC LIMIT 10;
"
```
*Expected Output:*
```text
+---------------------+------------------------+----------------+
| time_value          | waveformID_stationCode | phaseHint_code |
+---------------------+------------------------+----------------+
| 2026-10-23 20:08:16 | BAUM                   | P              |
| 2026-10-23 20:07:44 | ARC2                   | P              |
+---------------------+------------------------+----------------+
```

### 4. Check for Triangulated Earthquakes (Origins)
When multiple stations pick arrivals close in time, `scautoloc` triangulates an **Origin**:
```bash
mysql -u sysop -psysop seiscomp -e "
  SELECT po.publicID, o.time_value, o.latitude_value AS lat, 
         o.longitude_value AS lon, o.depth_value AS depth_km, 
         o.quality_usedPhaseCount AS phases
  FROM Origin o
  JOIN PublicObject po ON po._oid = o._oid
  ORDER BY o.time_value DESC LIMIT 5;
"
```

You can also use SeisComP's built-in CLI tools to inspect declared events and print formatted seismological bulletins:
```bash
# List recent event IDs from the database:
seiscomp exec scevtls -d mysql://sysop:sysop@localhost/seiscomp

# Print the complete formatted bulletin for an event (hypocenter, magnitudes, phase arrivals, and residuals):
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -E <event-id>

# Or print the bulletin for the most recent event:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -l 1

# Or inspect a specific Origin directly:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -O <origin-id>
```

### 5. Inspect the Archived Raw Waveforms (SDS Archive)
If `slarchive` is running, continuous raw waveforms are written in real time to the **SDS directory tree**:
```bash
# Check the directory tree of archived Oklahoma stations:
ls -lh var/lib/archive/$(date +%Y)/OK/*/*
```
*You will see day-volume miniSEED files (e.g. `OK.ALVA..HHZ.D.2026.296`) growing in size as new seconds of data arrive.*

### 6. Do I Have to Wait for a Real Earthquake to Happen?
**No, you do NOT have to wait for an earthquake.** In professional seismology, systems are tested and validated using several approaches:

#### Approach A: Observe Natural Ambient Noise & Micro-Tremors (Passive)
Seismic sensors are sensitive enough to detect wind gusts, passing freight trains, quarry blasting, and micro-tremors ($M < 1.5$). Standard STA/LTA triggers will pick up cultural transients within a few hours. Check `tail -f ~/.seiscomp/log/scautopick.log` or your MariaDB `Pick` table to see these incoming picks.

#### Approach B: Temporarily Lower Trigger Threshold (Instant Pipeline Test)
To verify the entire pipeline (SeedLink $\to$ `scautopick` $\to$ `scmaster` $\to$ `scdb` $\to$ MariaDB) right now without waiting:
1. Temporarily drop the trigger threshold to `2.0` in `etc/key/scautopick/profile_default`:
   ```ini
   trigger = 2.0
   ```
2. Run `seiscomp update-config && seiscomp restart scautopick`.
3. Within 1–2 minutes, ambient noise will trigger multiple picks and insert them into MariaDB, verifying full end-to-end communication!
4. Reset `trigger` back to `3.0` (or `4.0`) afterwards to avoid high false-positive rates.

#### Approach C: Replay Historical Earthquakes (`msrtsimul` / `scart`)
SeisComP includes playback tools like **`msrtsimul`** (miniSEED Real-Time Simulator) and **`scart`**:
- You can download historical miniSEED waveforms of a past Oklahoma event (e.g. 2016 $M5.8$ Pawnee or $M5.0$ Cushing) from EarthScope.
- Run `msrtsimul -v event_waveforms.mseed` to inject the records into SeedLink in real time.
- SeisComP will process the waveforms as if the earthquake is occurring live: `scautopick` triggers, `scautoloc` triangulates the epicenter, `scmag` calculates the magnitude, and an official event is declared!

#### Approach D: Ingest Hyperactive Regional Networks
Oklahoma has relatively calm seismicity compared to active plate boundaries. You can add 3–5 stations from Southern California (`CI`), Northern California (`NC`), or Puerto Rico (`PR`) from EarthScope SeedLink, where micro-earthquakes ($M 1.5 - 2.5$) occur multiple times every day.

---

## Step 5: Visualizing Traces & Origins (`scrttv`, `scmv`, `scolv`)

If you have X11 forwarding enabled (`ssh -Y user@ubuntu-ip`), you can launch the native SeisComP visualization GUIs directly on your Mac desktop:

### 1. `scrttv` (Real-Time Trace View)
```bash
scrttv
```
- Displays live, streaming continuous waveforms for your active stations.
- You will see vertical dashed lines appear in real time whenever `scautopick` declares a detection!

### 2. `scmv` (Map View)
```bash
scmv
```
- Displays an interactive world map.
- Stations flash **yellow/red** when a pick is triggered.
- When `scautoloc` triangulates an epicenter, an earthquake circle pops up with depth and magnitude.

### 3. `scolv` (Origin Locator View)
```bash
scolv
```
- The seismologist review workbench.
- Select any detected event to inspect the waveform arrival alignment across all stations.
- You can manually drag pick markers, reject bad stations, and click **Locate** to see hypocenter residuals.

---

## Step 6: The Bridge — Upgrading to sceasyquake (ML)

Once you are comfortable with this workflow, upgrading to machine learning is effortless:

| Feature | Built-in `scautopick` | `sceasyquake` (Machine Learning) |
|---|---|---|
| **Algorithm** | Traditional STA/LTA ratio | Deep Learning U-Net (PhaseNet / EQTransformer) |
| **P-Wave Picking** | Yes | Yes (Higher accuracy, lower false alarms) |
| **S-Wave Picking** | Limited / Poor | **Yes** (Accurate $S$-wave picks with probabilities) |
| **Sensitivity** | Misses weak signals in noise | Detects events buried in cultural / seismic noise |
| **Configuration** | Needs fine-tuning filter bands | Universal pre-trained weights (`stead`, etc.) |

### To switch from `scautopick` to `sceasyquake`:
You only need to swap one command:
```bash
# 1. Disable traditional picker
seiscomp disable scautopick

# 2. Enable deep-learning picker
seiscomp enable sceasyquake

# 3. Reload configuration and restart
seiscomp update-config
seiscomp restart
```

Because both modules speak the exact same SeisComP messaging format (`DataModel.Pick` on the `PICK` group), **`scautoloc`, `scmag`, `scevent`, `scolv`, and the database will continue working without changing a single downstream setting!**

---

## Step 7: Scaling Up — Adding More Stations & Networks

No matter whether you are adding 5 more stations, a whole new network (e.g. Texas `TX` or California `CI`), or hundreds of stations across a regional bounding box, the process in SeisComP **always follows the exact same 3-step cycle**:

```
[ 1. Ingest Inventory ]          [ 2. Bind Profiles ]                [ 3. Compile & Reload ]
  curl StationXML                 seiscomp shell                      seiscomp update-config
        │                               │                                    │
        ▼                               ▼                                    ▼
  fdsnxml2inv & scinv sync   set profile global/seedlink/scautopick   restart seedlink & picker
```

---

### Scenario A: Adding More Stations to the SAME Network (Oklahoma `OK`)

If you want to expand your current Oklahoma network from 5 stations to 15 stations (or all available OK stations):

```bash
# 0. Navigate to SeisComP root directory
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 1. Download full OK network metadata from IRIS (supporting both 100 Hz HH and 20-40 Hz BH channels)
mkdir -p ../stationxml
curl -sL "https://service.iris.edu/fdsnws/station/1/query?net=OK&sta=*&cha=HH?,BH?&level=response&format=xml" \
  -o ../stationxml/OK_all_stations.xml

# 2. Convert to SeisComP inventory & sync database
bin/seiscomp exec fdsnxml2inv ../stationxml/OK_all_stations.xml etc/inventory/inventory_OK.xml
bin/seiscomp exec scinv sync

# 3. Create bindings for all OK stations using the wildcard OK.*
bin/seiscomp shell << 'EOF'
set profile global default OK.*
set profile seedlink iris OK.*
set profile scautopick default OK.*
exit
EOF

# 4. Compile configuration and restart acquisition & picker
bin/seiscomp update-config
bin/seiscomp restart seedlink
bin/seiscomp restart scautopick

# 5. Verify the new stations appear in SeedLink
bin/seiscomp exec slinktool -Q localhost:18000
```

---

### Scenario B: Adding a NEW Network (e.g. TexNet by Bureau of Economic Geology at UT Austin `TX`)

Suppose you want to monitor the neighboring state of Texas (`TX`) alongside Oklahoma (`OK`):

```bash
# 0. Navigate to SeisComP root directory
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 1. Download official StationXML for network TX (HH and BH channels)
mkdir -p ../stationxml
curl -sL "https://service.iris.edu/fdsnws/station/1/query?net=TX&sta=*&cha=HH?,BH?&level=response&format=xml" \
  -o ../stationxml/TX_stations.xml

# 2. Convert and synchronize into inventory
bin/seiscomp exec fdsnxml2inv ../stationxml/TX_stations.xml etc/inventory/inventory_TX.xml
bin/seiscomp exec scinv sync

# 3. Bind the new TX stations (reusing EarthScope profile_iris and scautopick default)
bin/seiscomp shell << 'EOF'
set profile global default TX.*
set profile seedlink iris TX.*
set profile scautopick default TX.*
exit
EOF

# 4. Compile configuration and reload
bin/seiscomp update-config
bin/seiscomp restart seedlink
bin/seiscomp restart scautopick
```

> [!TIP]
> **What if the new network uses `BH` (40 Hz) instead of `HH` (100 Hz)?**  
> If you already configured `detecStream = "HH,BH"` in `profile_default`, TX stations will be picked automatically! If you want a dedicated profile for specific filter settings on 40 Hz broadband, create `etc/key/global/profile_broadband` with `detecStream = BH` and bind via `set profile global broadband TX.*`.

---

### Scenario C: Adding Stations from a DIFFERENT Upstream Server (e.g. GEOFON Germany)

You are not limited to EarthScope. You can pull stations from different international data centers simultaneously by creating multiple SeedLink profiles:

```bash
# 0. Navigate to SeisComP root directory
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 1. Create a second SeedLink profile pointing to GEOFON (Potsdam, Germany)
cat << 'EOF' > etc/key/seedlink/profile_geofon
sources = chain
sources.chain.address = geofon.gfz-potsdam.de
sources.chain.port = 18000
sources.chain.selectors = BH?
EOF

# 2. Download metadata for desired GEOFON station (e.g. GE.MORC in Czech Republic)
mkdir -p ../stationxml
curl -sL "https://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=MORC&cha=BH?&level=response&format=xml" \
  -o ../stationxml/GE_MORC.xml
bin/seiscomp exec fdsnxml2inv ../stationxml/GE_MORC.xml etc/inventory/inventory_GE.xml
bin/seiscomp exec scinv sync

# 3. Bind the station to the GEOFON SeedLink profile
bin/seiscomp shell << 'EOF'
set profile global default GE.MORC
set profile seedlink geofon GE.MORC
set profile scautopick default GE.MORC
exit
EOF

# 4. Compile and restart
bin/seiscomp update-config
bin/seiscomp restart seedlink
bin/seiscomp restart scautopick
```
*Your local SeedLink daemon will now simultaneously stream Oklahoma stations from EarthScope and European stations from GEOFON!*

---

### Scenario D: Adding All Stations in a Geographic Bounding Box

If you want to monitor a regional tectonic zone regardless of network operator, query FDSN using geographic coordinates (`minlat, maxlat, minlon, maxlon`):

```bash
# 0. Navigate to SeisComP root directory
cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

# 1. Query all broadband stations inside the Oklahoma/Texas border region:
mkdir -p ../stationxml
curl -sL "https://service.iris.edu/fdsnws/station/1/query?minlat=33.5&maxlat=37.5&minlon=-100.5&maxlon=-95.0&cha=HH?,BH?&level=response&format=xml" \
  -o ../stationxml/regional_box.xml

# 2. Convert and synchronize
bin/seiscomp exec fdsnxml2inv ../stationxml/regional_box.xml etc/inventory/inventory_regional.xml
bin/seiscomp exec scinv sync

# 3. Bind all imported stations across all networks with wildcard *.*:
bin/seiscomp shell << 'EOF'
set profile global default *.*
set profile seedlink iris *.*
set profile scautopick default *.*
exit
EOF

# 4. Compile and restart
bin/seiscomp update-config
bin/seiscomp restart seedlink
bin/seiscomp restart scautopick
```

---

### Scenario E: If You Are Using `sceasyquake` (Machine Learning)
When using the ML picker (`sceasyquake`), remember that stream selection is also filtered in `etc/sceasyquake.cfg`. 
If you add new networks, update `streams.codes`:

```ini
# In etc/sceasyquake.cfg:
# Allow both OK and TX networks:
streams.codes = OK.????.*.HHZ, OK.????.*.HHN, OK.????.*.HHE, TX.????.*.HHZ, TX.????.*.HHN, TX.????.*.HHE

# Or use wildcards for all bound 3-component streams:
streams.codes = *.????.*.HHZ, *.????.*.HHN, *.????.*.HHE, *.????.*.BHZ, *.????.*.BHN, *.????.*.BHE
```
And restart: `seiscomp restart sceasyquake`.

---

## Step 8: Troubleshooting & Real-World Gotchas

### Gotcha 1: `scautopick` Exits with "No stations added (empty module configuration?)"
- **Symptom:** In `~/.seiscomp/log/scautopick.log`:
  ```text
  [error/Autopick] No stations added (empty module configuration?) and thus nothing to do
  [notice/Application] Shutdown
  ```
  And `seiscomp status` shows `scautopick is not running [WARNING]`.
- **Causes & Fixes:**
  1. **Did you run `seiscomp update-config`?**
     `seiscomp shell` writes key binding files in `etc/key/`, but SeisComP daemons read from generated configuration files in `var/run/`. You **must** run `seiscomp update-config` after any binding change!
  2. **Channel mismatch (`HH` vs `BH`):**
     SeisComP defaults to searching for `BH` (20–40 Hz) streams. Oklahoma Geological Survey (`OK`) stations stream at 100 Hz on `HH` (`HHZ, HHN, HHE`). Ensure `etc/key/global/profile_default` contains:
     ```ini
     detecStream = HH
     detecLocid = ""
     ```
     *(Notice the spelling is `detecStream`, not `detectStream`).*
  3. **Station bindings not set:**
     Run the bindings in `seiscomp shell`:
     ```bash
     seiscomp shell << 'EOF'
     set profile global default OK.*
     set profile seedlink iris OK.*
     set profile scautopick default OK.*
     exit
     EOF
     seiscomp update-config
     seiscomp restart scautopick
     ```

### Gotcha 2: `seiscomp exec scdumppicks: not found`
- **Cause:** `scdumppicks` is a legacy utility that does not exist in modern SeisComP releases (Framework 7.x / SeisComP 5+).
- **Fix:** Do not search for `scdumppicks`. Instead, use:
  - `seiscomp exec slinktool -Q localhost:18000` (SeedLink packet streams)
  - `tail -f ~/.seiscomp/log/scautopick.log` (picker triggers)
  - `mysql -u sysop -psysop seiscomp -e "SELECT * FROM Pick ORDER BY time_value DESC LIMIT 10;"` (database records)

### Gotcha 3: `seiscomp status` Returns Blank or Exit Code 245
- **Cause:** `$SEISCOMP_ROOT` is pointing to the outer folder (`/home/hongyuxiao/Projects/SeiscomP`) instead of the true installation root (`/home/hongyuxiao/Projects/SeiscomP/seiscomp`), which lacks `etc/descriptions`.
- **Fix:** Ensure `~/.bashrc` has:
  ```bash
  export SEISCOMP_ROOT=/home/hongyuxiao/Projects/SeiscomP/seiscomp
  ```
  And reload with `source ~/.bashrc`.

### Gotcha 4: Where Are the Log Files Located?
- In modern SeisComP on Ubuntu, daemon logs are placed in:
  - `~/.seiscomp/log/<module>.log` (primary user log directory for scautopick, GUI tools)
  - `$SEISCOMP_ROOT/var/log/<module>.log` (for daemons like `seedlink.log` and `scmaster.log`)
- If `var/log/scautopick.log` looks empty or untouched, check `~/.seiscomp/log/scautopick.log`.

### Gotcha 5: `chain0: error: cannot resolve hostname rtserve.iris.washington.edu`
- **Cause:** IRIS merged with UNAVCO into EarthScope, and the legacy University of Washington endpoint (`rtserve.iris.washington.edu`) was retired and shut down.
- **Fix:** Update `etc/key/seedlink/profile_iris` (or your SeedLink profile) to use the new cloud endpoint:
  ```ini
  sources = chain
  sources.chain.address = rtserve.earthscope.org
  sources.chain.port = 18000
  sources.chain.selectors = HH?
  ```
  Then reload:
  ```bash
  seiscomp update-config seedlink
  seiscomp restart seedlink
  ```

### Gotcha 6: `scautopick.log` Stays Quiet and Doesn't Print Incoming Picks
- **Symptom:** `tail -f ~/.seiscomp/log/scautopick.log` stops at `Connection to localhost/production established` even though `mysql` shows picks were inserted.
- **Cause:** By default, SeisComP runs at `logging.level = 2` (Notice). Picks are classified as `INFO` (Level 3). To avoid filling the disk when processing dozens or hundreds of channels, SeisComP routes picks across memory rather than logging each arrival to disk.
- **Resolution:** No action needed; this is expected production behavior. Check picks in `scrttv` (graphical trace markers) or query MariaDB (`SELECT * FROM Pick ORDER BY time_value DESC LIMIT 10;`).

### Gotcha 7: False "750 km Deep" Earthquakes or Out-of-Region Plane-Wave Mislocations
- **Symptom:** `scbulletin` reports an event at maximum LOCSAT depth (`depth = 750 km`) in Texas/Oklahoma or far out of network (e.g. Indiana) with a massive azimuthal gap ($>300^\circ$), where dozens of regional stations triggered within a tight 15-second window.
- **Cause:** A distant, strong teleseismic earthquake ($M \ge 5.5$) arrived nearly vertically. Because the steep wavefront struck the entire regional network almost simultaneously (apparent velocity $\sim 28\text{ km/s}$), LOCSAT mathematically fit the near-zero relative travel times by pushing the hypocenter straight down to its 750 km depth ceiling.
- **Fix:** Restrict `scautoloc` to regional crustal limits and reject one-sided array geometries in `etc/scautoloc.cfg`:
  ```bash
  # Make sure you are in /home/hongyuxiao/Projects/SeiscomP/seiscomp
  cd /home/hongyuxiao/Projects/SeiscomP/seiscomp

  # Create user override file
  cat << 'EOF' >> etc/scautoloc.cfg
  # Maximum hypocenter depth in km (discards deep teleseismic mislocations)
  autoloc.maxDepth = 40.0

  # Prevent one-sided array solutions (rejects solutions with >300 deg gap)
  autoloc.maxAzimuthalGap = 300
  EOF

  bin/seiscomp update-config scautoloc
  bin/seiscomp restart scautoloc
  ```
