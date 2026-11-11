# Implementing easyQuake in Real Time in SeisComP
## Integrating Modern Deep Learning Phase Pickers into Production Networks
**Target Audience**: SeisComP Practitioners, Network Operators, Observational Seismologists  
**Presentation Duration**: 30 Minutes (20 min talk, 5 min demo, 5 min Q&A)  
**Total Slides**: 17 Slides (~1.2–1.5 minutes per slide)

---

## Slide 1: Title & Overview [1 min]
### Implementing easyQuake in Real Time in SeisComP
*Sub-title*: Bridging Modern Machine Learning (PhaseNet / EQTransformer / SeisBench) with Mission-Critical SeisComP Infrastructure

* **Speaker**: [Your Name / Agency]
* **Target Network**: Oklahoma Seismic Network (`OK.*` — 118 real-time stations)
* **Core Technology Stack**: SeisComP 5/6/7, `easyQuake_seiscomp`, SeisBench, ObsPy, PyTorch, MariaDB
* **Key Takeaway**: High-throughput, 3-component real-time AI phase picking (P & S) running stably on commodity hardware (< 3 GB RAM) with flexible multi-model backend support.

> **Speaker Notes**:  
> "Good morning/afternoon everyone. Today I'm excited to present our implementation of easyQuake in real time inside SeisComP.  
> 
> As SeisComP practitioners, we all value the reliability, speed, and standard compliance of the platform. The goal of this work is to supercharge SeisComP's front-end: feeding high-accuracy 3-component P and S phase picks from modern neural networks directly into standard downstream associators and locators in real time, while retaining complete analyst oversight in `scolv`."

---

## Slide 2: The Motivation — Moving Beyond STA/LTA [1.5 min]
### Why Integrate Deep Learning into Real-Time SeisComP?

| Feature | Legacy `scautopick` (STA/LTA) | Deep Learning (`sceasyquake` / PhaseNet) |
|---|---|---|
| **Components** | Single-component vertical (`Z` only) | 3-Component (`Z`, `N`, `E`) simultaneous |
| **Phase Types** | P-wave onsets only | **Both P and S arrivals** detected & labeled |
| **Microseismicity** | Misses events near or below noise floor | High sensitivity in low Signal-to-Noise conditions |
| **False Positives** | High trigger rate on cultural/spurious noise | Trained on millions of earthquake waveforms |
| **Amplitude Output** | Requires companion `scamp` calculation | Direct physical **SNR amplitude** attached to pick |

> **Speaker Notes**:  
> "We've all tuned `scautopick` filters. STA/LTA has served our community for decades, but it has inherent limitations: it's inherently a 1D vertical energy detector. It cannot reliably pick S-waves because horizontal shear energy overlaps with the P-coda.  
> 
> By running deep learning in real time, we get two transformative advantages: first, simultaneous P and S picks from the very first detection, which dramatically tightens hypocenter location constraints; and second, automatic SNR estimation bundled right into the pick object."

---

## Slide 3: End-to-End System Architecture [1.5 min]
### Seamless Integration via the `scmaster` Messaging Bus

```mermaid
flowchart TD
    subgraph Ingestion ["1. Acquisition & Telemetry"]
        RS["Upstream Telemetry\n(EarthScope / Field Ringserver)"] -->|SeedLink:18000| SL["SeisComP SeedLink Daemon"]
        SL -->|Raw miniSEED| SDS[("SDS Archive\nvar/lib/archive")]
    end

    subgraph Messaging ["2. The Backbone"]
        SL -->|Waveform Streams| BUS(("scmaster\nMessage Broker"))
        BUS <---> DB[("MariaDB Database\n(SeisComP DB)")]
    end

    subgraph ML_Pipeline ["3. AI Detection & Association"]
        BUS -->|Waveforms| EQ["sceasyquake\n(PhaseNet 60s Sliding Buffer)"]
        EQ -->|P & S Picks + SNR Amplitudes| BUS
        BUS -->|Picks| ASSOC["scautoloc / scpyocto\n(Origin Hypocenter Locator)"]
        ASSOC -->|Origins| BUS
        BUS -->|Origins| MAG["scmag & scevent\n(Magnitudes & Event Declaration)"]
    end

    subgraph Review ["4. Production & Analyst Review"]
        BUS --> SCOLV["scolv / scmv\n(Human Analyst Workbench)"]
    end
```

> **Speaker Notes**:  
> "Here is the architectural beauty of SeisComP: it is completely modular. `sceasyquake` connects to `scmaster` just like any standard SeisComP client.  
> 
> It reads streaming miniSEED from SeedLink, batches waveforms into sliding windows, runs inference, and broadcasts standard `DataModel::Pick` and `DataModel::Amplitude` objects to the `PICK` messaging group. Downstream modules like `scautoloc`, `scmag`, and `scevent` don't care that the pick came from a neural network—it looks, smells, and behaves like an authoritative SeisComP pick."

---

## Slide 4: Multi-Model Architecture & Configuration Page [2 min]
### SeisBench Backend: Universal Plug-and-Play Machine Learning

Operators configure `sceasyquake` graphically in **`scconfig`** (Desktop Qt or Web UI at `http://localhost:8080`) or via `etc/sceasyquake.cfg`:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  scconfig ──► Modules ──► Processing ──► sceasyquake                           │
├────────────────────────────────────────────────────────────────────────────────┤
│  picker.backend     │ [ seisbench   ▼ ]  (seisbench | easyquake | stub)        │
│  picker.model       │ [ phasenet    ▼ ]  (phasenet | eqtransformer | gpd)      │
│  picker.pretrained  │ [ stead       ▼ ]  (stead, diting, ethz, scedc, geofon) │
│  picker.model_path  │ /home/sysop/models/oklahoma_finetuned_phasenet.pt        │
│  picker.threshold   │ 0.50                                                     │
│  picker.device      │ [ cuda        ▼ ]  (cuda | cpu)                          │
│  picker.norm        │ [ peak        ▼ ]  (peak | std)                          │
│  picker.label_order │ [ PSN         ▼ ]  (PSN | NPS)                           │
└────────────────────────────────────────────────────────────────────────────────┘
```

* **1. Supported Model Architectures (`picker.model`)**:
  * **PhaseNet** (Zhu & Beroza, 2019): Ultra-fast 1D U-Net. High-throughput continuous streaming.
  * **EQTransformer** (Mousavi et al., 2020): Attention-based. Simultaneous event detection & P/S picking.
  * **GPD** (Ross et al., 2018): Generalized Phase Detection CNN.
* **2. Pretrained Model Hub Weights (`picker.pretrained`)**:
  * `stead` (Global Stanford dataset), `diting` (China), `ethz` (Europe), `scedc` (California), `geofon` (Global GFZ), `instance` (Italy), `neic` (USGS).
* **3. Custom Fine-Tuned Weights (`picker.model_path`)**:
  * Point directly to a custom `.pt` state-dict or SeisBench model directory.
  * Configure `norm` (`std` vs `peak`) and `label_order` (`PSN` vs `NPS`) to match your training recipe without changing a single line of C++ or Python code.

> **Speaker Notes**:  
> "One of the most powerful features of modern `easyQuake` in SeisComP is the SeisBench integration. It turns SeisComP into a universal deep-learning testing ground.  
> 
> As you can see on the configuration screen in `scconfig`, you are not locked into one model. With a simple dropdown, you can switch between PhaseNet, EQTransformer, and GPD. You can select pretrained weights trained on STEAD, Southern California, or Europe.  
> 
> Even better: if your research team trains custom weights on your local regional network, you just drop the `.pt` file into `picker.model_path`. SeisComP loads your fine-tuned weights at startup, handles normalization, and runs them in real time."

---

## Slide 5: Inside `sceasyquake`: Sliding Buffers & Inference [1.5 min]
### How Waveform Streaming Translates to Neural Network Predictions

* **Continuous Circular Ring Buffer**:
  * Stations are buffered locally in memory: `buffer_seconds = 60`.
  * Every `step_seconds = 5`, the buffer slides forward.
* **Batching Across Stations**:
  * Gathers all stations with new data into a single tensor batch: `(B, 3, 6000)`.
  * Runs single-pass 1D U-Net forward pass.
* **Peak Picking & Thresholding**:
  * Probability threshold: `picker.threshold = 0.5`.
  * Extracts P and S arrival times with millisecond precision.
  * Calculates physical peak amplitude and noise floor to compute `snr`.
* **Publication**:
  * Emits `Pick` with `phaseHint = P` or `S`, `methodID = PhaseNet`, `evaluationMode = automatic`.
  * Emits paired `Amplitude` with `type = snr`.

> **Speaker Notes**:  
> "How does `sceasyquake` work under the hood? It maintains per-station trace queues. Every 5 seconds, it gathers a 60-second window across all eligible stations, stacks them into a batch tensor, and passes them to PyTorch.  
> 
> PhaseNet outputs probability curves for P, S, and noise. Onsets above the 0.5 threshold are converted to picks with travel-time uncertainties and immediate SNR estimates, then dispatched over `scmaster`."

---

## Slide 6: Real-World Testbed: Oklahoma Network (`OK.*`) [1.5 min]
### Ingesting 118 Active Stations in Real Time

* **Network Scope**: Oklahoma Geological Survey / USGS (`OK` network).
* **Channels**: Mixed broadband (`HHZ, HHN, HHE` @ 100 Hz) and mid-period (`BHZ, BHN, BHE` @ 20–40 Hz).
* **Live Ingestion**: **118 actively streaming stations** distributed across the region.
* **Inference Sliding Window**:
  * Ring buffer length: `buffer_seconds = 60`.
  * Forward step: `step_seconds = 5`.
* **Hardware Target**: Single commodity Linux workstation / VM (Ubuntu 24.04/26.04 x86_64).

> **Speaker Notes**:  
> "To test this in a production-realistic setting, we configured the entire Oklahoma seismic network—118 stations actively streaming live from EarthScope.  
> 
> Oklahoma is seismically active with dense station spacing, making it the ideal proving ground for pick rates, associator clustering, and latency under continuous streaming."

---

## Slide 7: Real Example 1 — End-to-End Local Earthquake Detection [2 min]
### Second-by-Second Lifecycle of Event `xiao2026vyeo` in Oklahoma

```mermaid
sequenceDiagram
    autonumber
    participant Field as Ground Motion
    participant SL as SeedLink (18000)
    participant EQ as sceasyquake (PhaseNet)
    participant LOC as scautoloc (Locator)
    participant MAG as scmag / scevent
    participant SCOLV as scolv (Analyst GUI)

    Field->>SL: T=00.0s: P-wave reaches BLOK, DOVR, X34A
    Field->>SL: T+03.5s: S-wave arrives at RICK, MRSH
    SL->>EQ: T+05.0s: 60s waveform buffer forwarded
    Note over EQ: PhaseNet 1D U-Net Inference (0.3s)
    EQ->>LOC: T+05.5s: 10 picks published (6 P-picks, 4 S-picks) + SNR amplitudes
    Note over LOC: scautoloc associates phases via IASP91 tables
    LOC->>MAG: T+06.8s: Hypocenter declared (36.12°N, -97.45°W, depth: 5.8 km)
    MAG->>SCOLV: T+08.0s: ML 2.4 computed; Event xiao2026vyeo posted to scolv
```

* **Timeline**: Total latency from ground rupture to declared event in `scolv` was **8.0 seconds**.
* **Key Contribution of AI**: The S-picks arrived simultaneously with the P-picks in step 5, pinning the depth down to $5.8 \text{ km}$ on the very first origin solution.

> **Speaker Notes**:  
> "Let's walk through a real local earthquake recorded in our system: event `xiao2026vyeo`.  
> 
> At T=0, the earthquake ruptures. Five seconds later, our 5-second sliding buffer fires. Within 300 milliseconds, PhaseNet evaluates the 118 stations, detecting 6 P-waves and 4 S-waves. It publishes them with SNR amplitudes.  
> 
> By T+6.8 seconds, `scautoloc` has associated the picks and calculated a tight hypocenter at 5.8 km depth. By T+8.0 seconds, `scmag` calculates an ML 2.4 and `scevent` publishes the event to `scolv`. The entire automated detection-to-screen cycle took 8 seconds."

---

## Slide 8: Real Example 2 — Side-by-Side: STA/LTA vs. PhaseNet [2 min]
### Head-to-Head Comparison on the Exact Same Earthquake

```
                      OK.RICK: 3-Component Waveform (Z, N, E)
Z: ───/\──/\_/\/\──────/\/\/\/\/\/\/\/\/\/\/\/\────────────────────────────
N: ───────────/\/\/\/\──────────────/\/\/\/\/\/\/\/\/\/\/\/\/\─────────────
E: ──────────────/\/\/\/\───────────/\/\/\/\/\/\/\/\/\/\/\/\/\─────────────
                 ▲                  ▲
             P Arrival          S Arrival (Horizontals dominant)
```

| Metric | Legacy STA/LTA (`scautopick`) | Deep Learning (`sceasyquake` / PhaseNet) |
|---|---|---|
| **Detected Phases** | 5 P-picks (0 S-picks) | **11 P-picks, 8 S-picks** |
| **Noisy Station `OK.RICK`** | Missed (SNR below STA/LTA threshold) | **Picked both P and S** (SNR: P=4.2, S=8.7) |
| **Azimuthal Gap** | $192^\circ$ (one-sided station trigger) | **$74^\circ$** (dense multi-quadrant coverage) |
| **Depth Error ($\Delta z$)** | $\pm 14.8\text{ km}$ (floating depth) | **$\pm 1.9\text{ km}$** (pinned by 8 S–P differential times) |
| **Origin RMS Residual** | $0.42\text{ s}$ | **$0.16\text{ s}$** |

> **Speaker Notes**:  
> "This slide shows why this work matters. Here is a head-to-head comparison on the exact same event.  
> 
> With STA/LTA, noisy stations like RICK failed to trigger. Because STA/LTA only looks at the vertical channel, it produced zero S-picks. With only 5 P-picks in a single quadrant, the depth uncertainty was $\pm 14.8$ kilometers.  
> 
> PhaseNet picked both the vertical P-wave and the large horizontal S-wave on RICK. Across the network, it produced 11 P-picks and 8 S-picks. The S minus P travel-time differentials pinned the focal depth to within 1.9 kilometers, and reduced the origin residual from 0.42 to 0.16 seconds."

---

## Slide 9: Real-Time Proof: MariaDB Pick Table [1.5 min]
### Live Database Inspection During Peak Activity

```bash
mysql -u sysop -psysop seiscomp -e "
  SELECT po.publicID, p.time_value, p.waveformID_stationCode AS sta, 
         p.phaseHint_code AS phase, p.methodID, p.creationInfo_author
  FROM Pick p JOIN PublicObject po ON po._oid = p._oid 
  ORDER BY p.creationInfo_creationTime DESC LIMIT 6;
"
```

**Output from Production Terminal**:
```text
+-----------------------+---------------------+------+-------+----------+----------------------+
| publicID              | time_value (UTC)    | sta  | phase | methodID | author               |
+-----------------------+---------------------+------+-------+----------+----------------------+
| Pick/20261106.201434  | 2026-11-06 20:14:34 | RICK | S     | PhaseNet | sceasyquake/PhaseNet |
| Pick/20261106.201431  | 2026-11-06 20:14:31 | RICK | P     | PhaseNet | sceasyquake/PhaseNet |
| Pick/20261106.201346  | 2026-11-06 20:13:46 | MRSH | S     | PhaseNet | sceasyquake/PhaseNet |
| Pick/20261106.201342  | 2026-11-06 20:13:42 | MRSH | P     | PhaseNet | sceasyquake/PhaseNet |
| Pick/20261106.193236  | 2026-11-06 19:32:36 | BLOK | P     | PhaseNet | sceasyquake/PhaseNet |
| Pick/20261106.193226  | 2026-11-06 19:32:26 | DOVR | P     | PhaseNet | sceasyquake/PhaseNet |
+-----------------------+---------------------+------+-------+----------+----------------------+
```

* **Verification**: P and S pairs generated by `PhaseNet` are stamped with real-time UTC timestamps and authored as `sceasyquake/PhaseNet`.

> **Speaker Notes**:  
> "Here is the raw database output taken directly from our MariaDB instance while running live. Notice the timestamps: arrivals are recorded within seconds of real time.  
> 
> Notice stations RICK and MRSH: PhaseNet picked both the P-wave and the S-wave. In traditional setups, S-picks are either nonexistent or added manually minutes later by duty seismologists. Here, they feed downstream associators immediately."

---

## Slide 10: Real Example 3 — The Teleseismic 750 km Depth Trap [2 min]
### Real Incident: Event `xiao2026vyfx` in the Texas Panhandle

```
[ Teleseismic Planar Wavefront: Deep Mantle Arrival (~28 km/s apparent velocity) ]
   Station 1          Station 2          Station 3             Station 81
       │                  │                  │                      │
   0.0s ───────────►   +1.2s ─────────►   +2.4s ──────────────►   +14.7s
─────────────────────────────────────────────────────────────────────────────
UNCONSTRAINED LOCSAT: "Planar near-vertical arrival across 81 stations!"
Inversion Result    : FORCED TO MAXIMUM GRID DEPTH: 750 km depth in Texas Panhandle!
```

* **The Incident (`xiao2026vyfx`)**:
  * A distant teleseismic earthquake hit Oklahoma. 81 stations picked it within 14.7 seconds.
  * LOCSAT inverted this near-vertical arrival into a **750 km deep local earthquake**.
* **The Root Cause**:
  * Regional stations recorded a planar wave with ~28 km/s apparent velocity. LOCSAT's 1D crustal model could only fit that apparent speed by pushing the source down to its mathematical maximum depth (750 km).
* **The Regional Defense** in `etc/scautoloc.cfg`:
  ```ini
  autoloc.maxDepth = 40.0         # Hard ceiling for crustal earthquakes
  autoloc.maxAzimuthalGap = 300   # Discards non-enclosed planar wavefronts
  ```

> **Speaker Notes**:  
> "Now let's examine a fascinating real failure mode: event `xiao2026vyfx`.  
> 
> During testing, our system suddenly declared an earthquake in the Texas Panhandle at exactly 750 kilometers depth. Oklahoma crust is 40 km thick—there are no earthquakes at 750 km.  
> 
> What happened? A deep teleseismic event from the Pacific arrived across Oklahoma. Because the wavefront traveled through the deep mantle, it emerged almost vertically, crossing 81 stations in just 14 seconds. LOCSAT's regional velocity model couldn't explain an apparent 28 km/s speed from a shallow source, so the least-squares inversion plunged the hypocenter down to its 750 km boundary.  
> 
> By setting `autoloc.maxDepth = 40.0` and `autoloc.maxAzimuthalGap = 300`, we instruct the associator to reject planar wavefronts that lack regional curvature."

---

## Slide 11: Operational Pitfall #1 — The Amplitude Deadlock [2 min]
### Why `scautoloc` Produces Zero Earthquakes from AI Picks

```mermaid
flowchart LR
    A["sceasyquake Pick"] -->|Publishes| B["Amplitude (type='snr')"]
    B -.->|DEFAULT scautoloc waits for 'mb'| C["Stalled Pick\n(waiting for amplitude)"]
    C -->|Result| D["ZERO Origins Created!\n(Silent Pipeline Failure)"]
    
    B ==>|autoloc.amplTypeAbs = snr| E["Pick Amplitude Validated!"]
    E ==>|Result| F["Origin Successfully Formed!"]
```

* **The Trap**:
  * `scautoloc` checks `hasAmplitude()` by verifying `pick->amp > 0`.
  * By default, `scautoloc` expects `mb` amplitudes generated by `scamp`.
  * `sceasyquake` publishes `type="snr"`.
  * **Result**: Every pick stalls forever in memory waiting for an amplitude that will never arrive.
* **The Fix** in `etc/scautoloc.cfg`:
  ```ini
  autoloc.amplTypeAbs = snr
  autoloc.amplTypeSNR = snr
  autoloc.minPickSNR  = 0
  ```

> 🛠️ **Hands-On Live Drill**:  
> "Comment out `autoloc.amplTypeAbs = snr` in `etc/scautoloc.cfg` and run `seiscomp reload scautoloc`. Watch the origins stop completely despite thousands of incoming picks! Restore the line and reload—origins instantly resume."

> **Speaker Notes**:  
> "This next issue is the single most frustrating trap for anyone setting up ML in SeisComP. I call it the Amplitude Deadlock.  
> 
> You start `sceasyquake`. The logs look beautiful: thousands of picks are streaming over the bus! But you look at `scolv` or your database, and there are ZERO earthquakes.  
> 
> Why? Because inside `scautoloc`'s C++ source code, a pick cannot be used to locate an event until it has an absolute amplitude. It defaults to waiting for `mb` from `scamp`. Because ML pickers emit `snr` amplitudes, the picks stall forever. Setting `autoloc.amplTypeAbs = snr` tells `scautoloc` to accept the AI picker's SNR as a qualifying amplitude, immediately unlocking origin creation."

---

## Slide 12: Operational Pitfall #2 — SeedLink Handshake & Auto-Discovery [1.5 min]
### Overcoming SeedLink v3 Wildcard Rejection

* **The Protocol Restriction**:
  * In SeedLink v3 (SeisComP's standard C daemon):
    * `SELECT HH?` (channel wildcards) $\rightarrow$ **Supported**.
    * `STATION * OK` or `STATION ???? OK` (station wildcards) $\rightarrow$ **Rejected with `'no stations accepted'`**.
  * The `STATION` handshake command requires literal station names (`STATION ALVA OK`).
* **The User Problem**:
  * Must the operator manually type 118 station codes into `sceasyquake.cfg`?
* **The Solution: Dynamic Station Auto-Discovery**:
  * Patched `seiscomp_stream.py` to query `INFO STATIONS` XML during startup.
  * Dynamically discovers all 140 configured stations.
  * Automatically expands `streams.codes = OK.*..HH?` to 140 explicit station subscriptions.

```text
[info] SeedLink: expanded pattern OK.* (selector='HH?') -> 140 stations
[info] SeedLink: expanded pattern OK.* (selector='BH?') -> 140 stations
[info] SeedLink: total streams subscribed: 280
[info] SeisCompStream connected to localhost:18000
```

> 🛠️ **Hands-On Live Drill**:  
> Test what stations your SeedLink daemon serves right now in 1 second:  
> `bin/seiscomp exec slinktool -L localhost:18000 | grep OK | head -n 10`

> **Speaker Notes**:  
> "The next pitfall is in the SeedLink protocol itself. Standard SeedLink servers reject wildcard characters in station handshake commands. If you specify `OK.*`, SeedLink literally looks for a station with the name asterisk.  
> 
> Rather than forcing network operators to manually maintain configuration files with hundreds of individual station names, we enhanced `seiscomp_stream.py` with automatic discovery. When it sees an asterisk or question mark, it queries SeedLink's `INFO STATIONS` endpoint, extracts the active station list, and subscribes to each station explicitly. The user writes `OK.*`, and the code handles the rest."

---

## Slide 13: Operational Pitfall #3 — Low-Level Runtime Quirks [1.5 min]
### Python 3 Timeout Bug, Schema Joins, & Missing Basemaps

1. **ObsPy SeedLink `timeout=None` Bug**:
   * In Python 3.12+, ObsPy's `EasySeedLinkClient` left `conn.timeout = None`.
   * Connection checks executed `(time.time() - start) < None`, raising `TypeError: '<' not supported between float and NoneType`.
   * **Fix**: Explicitly set `self.conn.timeout = 10.0` in `_Client.__init__`.
2. **SeisComP Relational Schema (`PublicObject` Joins)**:
   * Running `SELECT publicID FROM Pick;` fails with `Unknown column 'publicID'`.
   * SeisComP stores public identifiers in `PublicObject` and joins entities via `_oid`.
   * **Fix**: Always query with `JOIN PublicObject po ON po._oid = p._oid`.
3. **Missing Basemaps in `scolv` & `scmv`**:
   * Modern base binary tarballs exclude GIS layers to minimize download size.
   * GUI map canvases render blank/black backgrounds.
   * **Fix**: Download `seiscomp-maps.tar.gz` and extract into `seiscomp/share/maps/`.

> **Speaker Notes**:  
> "Here are three quick runtime traps:  
> First, modern Python strictly disallows comparing floats to `None`. ObsPy had an uninitialized timeout that crashed connection checks; we patched that by setting an explicit 10-second timeout.  
> Second, SeisComP's MariaDB schema doesn't put `publicID` inside the `Pick` or `Origin` tables—it's normalized in `PublicObject` and linked by `_oid`.  
> And third, if your `scolv` maps are black, it's not a GPU driver bug; the base SeisComP tarball omits map tiles, which must be extracted from `seiscomp-maps.tar.gz`."

---

## Slide 14: Real Example 4 — Historical Replay Drills (`msrtsimul`) [1.5 min]
### Validating AI Pickers on Historical Events Before Going Live

```bash
# 1. Download historical waveforms (e.g. 2016 M5.8 Pawnee earthquake)
# 2. Replay into SeisComP SeedLink in real time:
msrtsimul -v pawnee_event_waveforms.mseed

# 3. Watch real-time processing unfold across the pipeline:
#    - sceasyquake picks P & S
#    - scautoloc locates hypocenter
#    - scmag computes magnitude
#    - scevent posts to scolv
```

* **Why this is critical for operators**:
  * You don't have to wait for an earthquake to occur to validate your pipeline.
  * Allows tuning `picker.threshold` and `picker.min_distance` on known historical ground truth.
  * Verifies that travel times and focal mechanisms align with authoritative network catalogs.

> **Speaker Notes**:  
> "How can an observatory team validate this before switching their live feeds? You don't need to wait for an earthquake.  
> 
> Using SeisComP's built-in `msrtsimul` tool, you can take a past earthquake—like the 2016 M5.8 Pawnee event—and inject it into SeedLink at real-time playback speed. The entire pipeline reacts as if the earthquake is happening right now: `sceasyquake` picks the arrivals, `scautoloc` locates the epicenter, and `scmag` calculates the magnitude. This provides a repeatable, offline benchmark for quality assurance."

---

## Slide 15: Performance & Compute Footprint [1.5 min]
### Feasibility on Commodity Hardware

* **RAM Footprint**: **< 3.0 GB Total**
  * MariaDB: ~200 MB
  * Core SeisComP Daemons (`scmaster`, `seedlink`, `scdb`, `scautoloc`, `scmag`): ~500 MB
  * `sceasyquake` (PyTorch + 118 station buffers): ~1.2 GB
* **CPU vs. GPU Throughput**:
  * **On 8-core CPU**: PhaseNet evaluates 64 three-component stations in ~5 seconds.
  * **On Consumer GPU (`cuda`)**: Evaluates 150+ stations in **< 0.25 seconds**.
* **Safety Valve (`picker.max_batch_stations`)**:
  * Built-in batch cap (default 64) prevents slower CPUs from accumulating processing lag.
  * Overdue stations are prioritized first, maintaining full continuous monitoring.

> **Speaker Notes**:  
> "A frequent question from observatory managers is: 'Do we need a massive high-performance cluster to run AI?'  
> 
> The answer is no. The entire stack—database, message broker, SeedLink server, and PhaseNet—runs stably within 3 GB of RAM on a standard Linux workstation. On CPU, PhaseNet processes 64 stations in 5 seconds. If you add an entry-level GPU, processing 150 stations drops to under a quarter of a second, leaving virtually the entire machine free for downstream tasks."

---

## Slide 16: Human-in-the-Loop & Remote Operations [1.5 min]
### AI Accelerates; Seismologists Authorize

```
[ Real-Time Ingestion & ML Picking ]
                 │
                 ▼
[ scautoloc Declares Origin (automatic) ]
                 │
                 ▼
[ scolv GUI: Analyst Reviews Waveforms & Adjusts Picks ]
                 │
                 ▼ (Click "Commit")
[ New Origin Created (evaluationMode: manual) ]
                 │
                 ▼
[ scevent Promotes Manual Solution to PREFERRED ORIGIN ]
                 │
                 ▼
[ Public Dissemination: Web, Email, FDSN Event WebService ]
```

* **Zero Paradigm Shift for Analysts**:
  * Seismologists connect via SSH X11 (`ssh -Y`) or Web Config (`scconfig --web 8080`).
  * `scolv` displays PhaseNet P and S picks directly on the interactive trace display.
  * When an analyst re-picks or commits, SeisComP's event associator (`scevent`) automatically prioritizes the human review over machine detections.

> **Speaker Notes**:  
> "It is vital to emphasize that AI phase picking does not replace the duty seismologist. It empowers them.  
> 
> Rather than spending the first two minutes manually picking basic arrivals, the analyst opens `scolv` to find clean, pre-populated P and S picks. The analyst checks the residuals, adjusts phases if necessary, and commits. SeisComP's standard rules immediately promote the manual solution to preferred status."

---

## Slide 17: Conclusion & Live Demonstration [1 min + 5 min Q&A]
### Summary & Next Steps

* **Key Achievements**:
  * Successfully deployed real-time easyQuake & SeisBench picking into native SeisComP.
  * Multi-model backend supports PhaseNet, EQTransformer, GPD, and custom weights.
  * Ingesting **118 active stations** with continuous 5-second inference batches.
  * Solved amplitude deadlocks, teleseismic depth mislocations, and protocol handshake limits.
  * Verified end-to-end event location with simultaneous P & S arrivals.
  * Maintained single-machine footprint under 3 GB RAM.
* **Resources & Code**:
  * Repository: `easyQuake_seiscomp` (`sceasyquake`)
  * Full Documentation: `SEISCOMP_EASYQUAKE_INSTALLATION_GUIDE.md` & `learning_note.md`

### Open for Questions & Live Terminal Demo
*(Switch to live terminal to inspect real-time pick streams and `scolv`)*

> **Speaker Notes**:  
> "To conclude: deep learning is no longer an offline post-processing tool. It is ready for real-time mission-critical observatory operations inside standard SeisComP architectures with full support for modern model hubs and fine-tuned weights.  
> 
> Thank you for your time. I'd be happy to answer any questions, and we can switch to the live terminal to inspect the real-time pick stream."

---

## Appendix: 5-Minute Live Terminal Hands-On Demonstration Script
### A Step-by-Step Instructor Guide for the Live Demo Block

Use this script during the 5-minute live demo portion. Keep two terminal windows open side-by-side (or split panes in tmux/iterm2).

```
┌──────────────────────────────────────────┬──────────────────────────────────────────┐
│ Left Terminal: Live ML Engine Logs       │ Right Terminal: Interactive SQL & Audits │
│ tail -f ~/.seiscomp/log/sceasyquake.log  │ mysql -u sysop -psysop seiscomp          │
└──────────────────────────────────────────┴──────────────────────────────────────────┘
```

#### Step 1: Prove System Health (30 Seconds)
In the right terminal, run the automated 12-point health audit:
```bash
bin/seiscomp exec python3 examples/status_check.py check
```
* **What to tell the audience**:  
  "Notice that with one command, we verify that all 7 core daemons are running, the SeedLink ring-buffer is less than 10 minutes old, `autoloc.amplTypeAbs = snr` is confirmed, and the database has greater than 90% pick-to-amplitude pairing."

#### Step 2: Show the Real-Time Inference Loop (60 Seconds)
In the left terminal, start following the live `sceasyquake` log:
```bash
tail -f ~/.seiscomp/log/sceasyquake.log
```
* **What to tell the audience**:  
  "Look at the timestamps on the left. Every 5 to 6 seconds, the sliding 60-second buffer evaluates incoming waveforms from our 118 Oklahoma stations. Notice the inference batch latency: it completes in a fraction of a second, well before the next 5-second step."

#### Step 3: Query Real-Time P & S Arrivals from MariaDB (60 Seconds)
In the right terminal, execute the live database query:
```bash
mysql -u sysop -psysop seiscomp -e "
SELECT 
    po.publicID AS pick_id,
    p.time_value,
    p.waveformID_stationCode AS sta,
    p.waveformID_channelCode AS cha,
    p.phaseHint_code AS phase,
    p.creationInfo_author AS author,
    p.creationInfo_creationTime AS created
FROM Pick p
JOIN PublicObject po ON po._oid = p._oid
ORDER BY p.creationInfo_creationTime DESC
LIMIT 8;
"
```
* **What to tell the audience**:  
  "Notice the `phase` column: we are seeing simultaneous P and S phase picks arriving right now with current UTC timestamps, authored by `sceasyquake/PhaseNet`. Legacy STA/LTA cannot produce S-picks on 3-component data like this."

#### Step 4: Show the Declared Earthquake Origins & Print Bulletin (60 Seconds)
In the right terminal, inspect the resulting earthquake origins:
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
LIMIT 4;
"
```

Next, list events and generate the official seismological bulletin directly on the command line:
```bash
# List the latest declared event IDs:
seiscomp exec scevtls -d mysql://sysop:sysop@localhost/seiscomp

# Print full bulletin for the most recent declared earthquake:
seiscomp exec scbulletin -d mysql://sysop:sysop@localhost/seiscomp -l 1
```

* **What to tell the audience**:  
  "Here is the official SeisComP earthquake bulletin generated straight from `scbulletin`. Notice the arrival table: it lists our PhaseNet P and S arrivals, their travel-time residuals, epicentral distances, and azimuths, demonstrating full system integration from ML inference to official event publication without touching the GUI."

#### Step 5: Live Hardware Capacity Benchmark (30 Seconds)
Run the built-in picker benchmark right in front of the audience:
```bash
python sceasyquake/tests/bench_picker_capacity.py --cpu-only --channels 20 --step-seconds 5
```
* **What to tell the audience**:  
  "This tool simulates 20 continuous 3-component channels and benchmarks the exact compute margin on your host CPU. It confirms how much headroom you have before reaching real-time saturation."
