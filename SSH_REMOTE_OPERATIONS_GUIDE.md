# Remote Server Access & SSH Operations Guide for SeisComP

[ English ](README.md) | [ 简体中文 ](README_zh.md)

In production earthquake observatories and research institutions, **SeisComP** and its deep-learning pickers (**easyQuake**) almost always run on dedicated headless Linux servers (in a data center, server rack, or cloud VM). Analysts, seismologists, and students manage these systems remotely from their personal laptops (macOS, Linux, or Windows).

This guide walks you through setting up secure **SSH key-based authentication**, streamlining connections with **SSH config aliases**, tunneling ports for **web interfaces and databases**, running graphical review tools (**`scolv`**, **`scmv`**) over **X11 forwarding**, and preserving long-running workflows with **`tmux`**.

---

## Table of Contents
1. [SSH Key Concepts (Public vs. Private)](#1-ssh-key-concepts-public-vs-private)
2. [Step 1: Generate an SSH Key Pair (On Your Laptop)](#step-1-generate-an-ssh-key-pair-on-your-laptop)
3. [Step 2: Copy the Public Key to the Remote Server](#step-2-copy-the-public-key-to-the-remote-server)
4. [Step 3: Configure `~/.ssh/config` for One-Command Logins](#step-3-configure-sshconfig-for-one-command-logins)
5. [Step 4: Running SeisComP Graphical Tools Remotely (X11 & Web)](#step-4-running-seiscomp-graphical-tools-remotely-x11--web)
6. [Step 5: SSH Port Forwarding & Service Tunnels](#step-5-ssh-port-forwarding--service-tunnels)
7. [Step 6: Keeping Long-Running Tasks Alive with `tmux`](#step-6-keeping-long-running-tasks-alive-with-tmux)
8. [Step 7: Transferring Files (`rsync` and `scp`)](#step-7-transferring-files-rsync-and-scp)
9. [Step 8: Server Security Hardening (Best Practices)](#step-8-server-security-hardening-best-practices)
10. [Troubleshooting & Gotchas](#troubleshooting--gotchas)

---

## 1. SSH Key Concepts (Public vs. Private)

SSH keys use asymmetric cryptography to authenticate your connection without typing passwords over the network:

```
┌──────────────────────────────────────┐             ┌──────────────────────────────────────┐
│       YOUR LOCAL LAPTOP (Client)     │             │       SEISCOMP SERVER (Remote)       │
│                                      │             │                                      │
│  Private Key: id_ed25519 (NEVER SHARE)│ ──Handshake►│  Public Key: authorized_keys         │
│  Public Key:  id_ed25519.pub         │             │  (Locks access to matching private)  │
└──────────────────────────────────────┘             └──────────────────────────────────────┘
```

* **Private Key (`id_ed25519`)**: Stored exclusively on your local machine under `~/.ssh/`. **Never share, upload, or email this file.**
* **Public Key (`id_ed25519.pub`)**: Uploaded to the remote server and saved in `~/.ssh/authorized_keys`. Anyone can see this key; it acts as a digital lock that only your private key can open.

---

## Step 1: Generate an SSH Key Pair (On Your Laptop)

Open a terminal on your local machine (macOS Terminal, Linux Shell, or Windows PowerShell / Git Bash):

```bash
# Generate a modern, highly secure Ed25519 keypair:
ssh-keygen -t ed25519 -C "your_email@institution.edu"
```

*(If your environment requires legacy RSA keys, run `ssh-keygen -t rsa -b 4096 -C "your_email@institution.edu"` instead).*

1. **Enter file in which to save the key**: Press **Enter** to accept the default (`~/.ssh/id_ed25519`).
2. **Enter passphrase**: Enter a secure passphrase (recommended for laptops) or press **Enter** twice for no passphrase.

Check that the keys were created:
```bash
ls -l ~/.ssh/id_ed25519*
```
*You should see two files:*
* `id_ed25519` (Private key — permissions must be `600`)
* `id_ed25519.pub` (Public key — permissions `644`)

---

## Step 2: Copy the Public Key to the Remote Server

### Method A: Using `ssh-copy-id` (Recommended — macOS & Linux)

`ssh-copy-id` automatically connects, creates `~/.ssh` on the remote server with the correct permissions, and appends your public key:

```bash
# Syntax: ssh-copy-id -i ~/.ssh/id_ed25519.pub <user>@<server-ip-or-domain>
ssh-copy-id -i ~/.ssh/id_ed25519.pub sysop@192.168.1.100
```
Enter the remote user's password one last time. From this point forward, authentication will be passwordless.

---

### Method B: Manual Setup (Windows PowerShell or when `ssh-copy-id` is unavailable)

If `ssh-copy-id` is not installed on your system:

1. Display your local public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   # On Windows PowerShell: Get-Content ~\.ssh\id_ed25519.pub
   ```
   Copy the entire line starting with `ssh-ed25519 AAAA...`.

2. Log into the remote server using password authentication:
   ```bash
   ssh sysop@192.168.1.100
   ```

3. On the remote server, append the key and ensure strict file permissions:
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   echo "PASTE_YOUR_PUBLIC_KEY_STRING_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

---

## Step 3: Configure `~/.ssh/config` for One-Command Logins

Instead of remembering IP addresses, custom ports, and username flags:
```bash
# The painful way:
ssh -i ~/.ssh/id_ed25519 -X sysop@192.168.1.100 -p 22
```

You can define an alias on your **local machine** in `~/.ssh/config`:

```bash
# Create or open your local SSH config:
nano ~/.ssh/config
```

Add a block for your SeisComP server:

```ssh-config
Host seiscomp
    HostName 192.168.1.100
    User sysop
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ForwardX11 yes
    ForwardX11Trusted yes
    ServerAliveInterval 60
    ServerAliveCountMax 5
```

### Now connect with a single word:
```bash
ssh seiscomp
```

> [!TIP]
> **Why `ServerAliveInterval 60` is essential**: Remote institutional firewalls often drop silent SSH connections after 5–10 minutes of inactivity. `ServerAliveInterval 60` sends an invisible keep-alive ping every 60 seconds, preventing broken pipes while you read documentation.

---

## Step 4: Running SeisComP Graphical Tools Remotely (X11 & Web)

SeisComP features rich Qt-based GUI tools:
* **`scolv`**: Origin Locator View (waveform picking and manual origin review)
* **`scmv`**: Map View (real-time station status and event epicenter alerts)
* **`scrttv`**: Real-Time Trace View (streaming helicorder)

Because the server is headless, you have two primary methods to access these interfaces:

### Option A: X11 Forwarding (Display GUIs on Your Local Desktop)

#### 1. Setup on Your Local Laptop:
* **macOS**: Install **[XQuartz](https://www.xquartz.org/)**. Open XQuartz $\to$ Preferences $\to$ Security $\to$ check *"Allow connections from network clients"*. Log out and log back in (or restart your Mac).
* **Linux**: Native X11 works out of the box.
* **Windows**: Install **[MobaXterm](https://mobaxterm.mobatek.net/)** (has a built-in X11 server) or install **VcXsrv** for WSL2.

#### 2. Connect with Trusted X11 Forwarding (`-Y`):
```bash
ssh -Y seiscomp
```

#### 3. Launch any GUI from the remote shell:
```bash
# Test that X11 display forwarding is active:
echo $DISPLAY
# (Should print something like: localhost:10.0)

# Launch SeisComP tools:
scolv
scmv
```
The application window will render directly on your local computer's desktop!

---

### Option B: Web-Based Configuration (`scconfig --web`)

If you only need to configure stations, bindings, or database settings and don't want to use X11, SeisComP provides a lightweight built-in HTTP server:

1. Connect to the server with local port forwarding:
   ```bash
   ssh -L 8080:localhost:8080 seiscomp
   ```

2. On the remote server, start the headless web interface:
   ```bash
   QT_QPA_PLATFORM=offscreen seiscomp exec scconfig --web 8080
   ```

3. On your local laptop, open your web browser and navigate to:
   ```
   http://localhost:8080
   ```
   You can view and modify the entire inventory, edit module parameters, and click **Save** directly through the browser.

---

## Step 5: SSH Port Forwarding & Service Tunnels

SSH port forwarding allows your local computer to communicate securely with internal services running on the remote server as if they were running locally.

### Useful SeisComP Port Tunnels

```bash
# Forward SeedLink (18000), scconfig (8080), and MariaDB (3306) in one command:
ssh -L 18000:localhost:18000 \
    -L 8080:localhost:8080 \
    -L 3306:localhost:3306 \
    seiscomp
```

| Service | Remote Port | Local Access Endpoint | Purpose |
| :--- | :---: | :--- | :--- |
| **SeedLink** | `18000` | `localhost:18000` | Connect local Python/ObsPy scripts or `slinktool` directly to the server's live waveform stream. |
| **Web `scconfig`** | `8080` | `http://localhost:8080` | Access SeisComP's web configuration interface in your local browser. |
| **MariaDB / MySQL** | `3306` | `localhost:3306` | Connect local desktop database tools (DBeaver, DataGrip, VS Code SQL) to inspect the `seiscomp` database schema. |

---

## Step 6: Keeping Long-Running Tasks Alive with `tmux`

When you disconnect from an SSH session or close your laptop lid, standard terminal processes receive a `SIGHUP` signal and are **immediately terminated**. 

To run long-running inventory imports, waveform back-fills, or ML testing without interruption, use **`tmux`** (terminal multiplexer):

```bash
# 1. On the remote server, install tmux if not present:
sudo apt install -y tmux

# 2. Start a named tmux session:
tmux new -s seiscomp

# 3. Inside tmux, run your long-running task:
seiscomp start
python3 test_model_inference.py

# 4. Detach safely (leaves everything running in the background):
# Press: Ctrl + b, then press d

# You can now safely close your SSH connection or shut down your laptop!
```

### Reattaching to Your Session Later:
```bash
# Reconnect to the server:
ssh seiscomp

# Reattach to the running session:
tmux attach -t seiscomp
```

### Essential `tmux` Shortcuts:
* `Ctrl+b` then `d`: Detach from session (keeps processes running).
* `Ctrl+b` then `c`: Create a new window inside the session.
* `Ctrl+b` then `n`: Switch to next window.
* `Ctrl+b` then `[`: Enter scrollback mode (use arrow keys or PgUp/PgDn to scroll; press `q` to exit).

---

## Step 7: Transferring Files (`rsync` and `scp`)

### Push Files (Local $\to$ Remote)
Upload custom StationXML files or inventory updates from your local machine to the server:

```bash
# Using rsync (shows progress and resumes interrupted transfers):
rsync -avzP ~/Downloads/station_metadata.xml seiscomp:~/seiscomp/stationxml/

# Using scp:
scp ~/Downloads/station_metadata.xml seiscomp:~/seiscomp/stationxml/
```

### Pull Files (Remote $\to$ Local)
Download event bulletins, figures, or SDS miniSEED waveform files to your local laptop:

```bash
# Download an SDS archive directory for analysis:
rsync -avzP seiscomp:~/seiscomp/var/lib/archive/2026/OK/ ~/SeismicData/2026/OK/
```

---

## Step 8: Server Security Hardening (Best Practices)

Once your SSH key authentication is confirmed working, secure your server by disabling password logins:

1. Edit the SSH daemon configuration on the **server**:
   ```bash
   sudo nano /etc/ssh/sshd_config
   ```

2. Set the following directives:
   ```ini
   # Disable password authentication (requires SSH key):
   PasswordAuthentication no

   # Prevent root login with password:
   PermitRootLogin prohibit-password

   # Ensure public key authentication is active:
   PubkeyAuthentication yes
   ```

3. Restart the SSH service:
   ```bash
   sudo systemctl restart ssh
   ```

4. Configure the Ubuntu firewall (`ufw`):
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow 22/tcp       # SSH
   sudo ufw allow 18000/tcp    # SeedLink (if accepting outside station streams)
   sudo ufw enable
   ```

---

## Troubleshooting & Gotchas

| Symptom | Cause | Resolution |
| :--- | :--- | :--- |
| `Permission denied (publickey)` | Wrong file permissions on `~/.ssh` or `authorized_keys` | Run on server: `chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && chown -R $USER:$USER ~/.ssh`. |
| `X11 forwarding request failed on channel 0` | `xauth` package is missing on server, or `X11Forwarding` is disabled in `sshd_config` | Run on server: `sudo apt install -y xauth` and verify `X11Forwarding yes` in `/etc/ssh/sshd_config`. |
| `Could not connect to any X display` on macOS | XQuartz is not running or network connections are blocked | Launch XQuartz manually before SSH. In XQuartz Preferences $\to$ Security, check *"Allow connections from network clients"*, then run `ssh -Y seiscomp`. |
| GUI opens but renders extremely slowly | Network latency over remote WAN | Use Web `scconfig` (`--web 8080`) for configuration, or use local port forwarding rather than raw X11 over high-latency connections. |
| Broken pipe / SSH disconnects after inactivity | Institutional router drops idle connections | Add `ServerAliveInterval 60` and `ServerAliveCountMax 5` to your local `~/.ssh/config`. |
| Port already in use (`bind: Address already in use`) | A previous tunnel or local process is bound to the port | Find and kill the stale tunnel process locally: `lsof -i :8080` then `kill <PID>`. |
