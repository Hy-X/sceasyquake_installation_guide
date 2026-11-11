# SeisComP & easyQuake Real-Time Deployment Guides

> [!IMPORTANT]
> ### 🔗 Upstream Repository
> This repository contains documentation, installation manuals, operational workflows, and presentation materials for integrating **easyQuake** with **SeisComP**.
> 
> For the core source code, native SeisComP wrappers, and official releases, please visit the main upstream repository:  
> **👉 [https://github.com/jakewalter/easyQuake_seiscomp](https://github.com/jakewalter/easyQuake_seiscomp)**

---

## Overview

**`easyQuake_seiscomp` (`sceasyquake`)** bridges modern deep-learning seismic phase pickers (PhaseNet, EQTransformer, GPD via the [SeisBench](https://github.com/seisbench/seisbench) framework) directly into [SeisComP](https://www.seiscomp.de/)'s real-time acquisition and automatic event processing pipeline.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    SeedLink     │ ────► │   sceasyquake   │ ────► │    scautoloc    │ ────► │  scevent / DB   │
│ Waveform Stream │       │ (PhaseNet / AI) │       │ (Associator)    │       │ (Origins / GUI) │
└─────────────────┘       └─────────────────┘       └─────────────────┘       └─────────────────┘
```

* **Continuous 3-Component Processing**: Evaluates incoming waveforms in sliding buffers (e.g. 60s window every 5s).
* **Simultaneous P & S Wave Picking**: Detects and labels both phase arrivals in real time.
* **Native Message Bus Integration**: Publishes SeisComP data model `Pick` and synthetic `Amplitude` (SNR) objects straight to `scmaster`.
* **Zero Disruption to Duty Seismologists**: Downstream origin declaration (`scautoloc`), magnitude calculation (`scmag`), and graphical review (`scolv`) remain completely native.

---

## Documentation Index

This repository provides comprehensive documentation for deploying, configuring, and operating the system:

| Document | Description |
| :--- | :--- |
| 📖 **[Installation Guide](SEISCOMP_EASYQUAKE_INSTALLATION_GUIDE.md)** | Step-by-step instructions for installing SeisComP, MariaDB, Python ML dependencies (PyTorch, SeisBench, ObsPy), `sceasyquake`, and verifying the deployment. |
| ⚙️ **[Autopick & Real-Time Workflow](SEISCOMP_AUTOPICK_WORKFLOW.md)** | Detailed architecture of real-time SeedLink streaming, configuration hierarchy, association tuning, troubleshooting, and validation drills. |
| 📝 **[Learning Notes & Diagnostic Cheat Sheet](learning_note.md)** | Architectural background, binding hierarchy, headless remote operations, and quick CLI query references. |

---

## Upstream References & Credits

* **Core Repository**: [jakewalter/easyQuake_seiscomp](https://github.com/jakewalter/easyQuake_seiscomp)
* **easyQuake Framework**: [jakewalter/easyQuake](https://github.com/jakewalter/easyQuake)
* **SeisBench Machine Learning Hub**: [seisbench/seisbench](https://github.com/seisbench/seisbench)
* **SeisComP Official Software**: [seiscomp.de](https://www.seiscomp.de/)

