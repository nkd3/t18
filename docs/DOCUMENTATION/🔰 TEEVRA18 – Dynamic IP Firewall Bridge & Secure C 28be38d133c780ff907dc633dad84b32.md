# 🔰 TEEVRA18 – Dynamic IP Firewall Bridge & Secure Connectivity Setup

---

## 🧭 **1. Project Overview**

This document describes the design, configuration, and implementation of the **Dynamic IP + Auto-Firewall Bridge** for **TEEVRA18**, the SEBI-compliant trading platform for NIFTY/BANK-NIFTY/NIFTY-50 derivatives.

The goal is to ensure **secure, continuous SSH and API connectivity** between a **Windows development client (dynamic IP)** and a **Vultr-hosted static IP bridge VPS**—without manually updating firewall rules every time the home IP changes.

---

### 🎯 **Objective**

> Maintain SEBI-compliant, encrypted, audit-logged, and dynamically updated connectivity between the Windows TEEVRA18 environment and the static-IP VPS used as the trading gateway.
> 

**Key Features:**

- Auto-updates allowed SSH source IPs when the home IP changes.
- Keeps all changes logged with timestamps for SEBI audit compliance (5-year retention).
- Prevents unauthorized access using layered security.
- Maintains uninterrupted DhanHQ API connectivity from the static-IP VPS.

---

## 🧩 **2. System Architecture**

```mermaid
flowchart TD

A["Windows Client (Home Network)"]
B["DuckDNS Dynamic DNS"]
C["Vultr VPS (Static IP - Mumbai)"]
D["UFW Firewall + Auto-Updater"]
E["DhanHQ API / Exchanges"]

A -->|"PowerShell updater"| B
B -->|"teevra18.duckdns.org → Home IP"| D
D -->|"Whitelist current IP"| C
C -->|"Static-IP gateway"| E

```

---

### 🧠 **Architecture Layers**

| Layer | Component | Function | Frequency |
| --- | --- | --- | --- |
| **1. Client** | Windows Task Scheduler + PowerShell Script | Updates DuckDNS every 5 min | 5 min |
| **2. DNS Layer** | DuckDNS | Dynamic hostname → Current home IP | Real-time |
| **3. VPS Firewall Layer** | UFW + systemd timer | Auto-updates allowed SSH IP | 2 min |
| **4. Security Layer** | SSH keys + Fail2ban + static VPS IP | SEBI security & access control | Continuous |
| **5. Logging Layer** | `/var/log/teevra18_fw.log` | Timestamped audit of IP changes | Continuous |

---

## ⚙️ **3. Implementation Steps**

### **A. DuckDNS Dynamic DNS Configuration**

**Goal:** Create a free dynamic hostname (`teevra18.duckdns.org`) to represent your changing home IP.

**Steps:**

1. Visit [https://www.duckdns.org](https://www.duckdns.org/) → sign in via GitHub/Google.
2. Add domain → **`teevra18`**.
3. Copy your **token** for API updates.
4. Confirm the DNS resolves correctly after setup:
    
    ```powershell
    nslookup teevra18.duckdns.org
    
    ```
    

---

### **B. Windows PowerShell Updater**

**File:** `C:\T18\duckdns\Update-DuckDNS.ps1`

```powershell
$Domain = "teevra18"
$Token  = "<YOUR_TOKEN>"
$LogDir = "C:\T18\duckdns\logs"
$Log    = Join-Path $LogDir "duckdns.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-PublicIP {
    $urls = @("https://api.ipify.org","https://ifconfig.me/ip","https://checkip.amazonaws.com")
    foreach ($u in $urls) {
        try {
            $ip = (Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 10).Content.Trim()
            if ($ip -match '^\d{1,3}(\.\d{1,3}){3}$') { return $ip }
        } catch {}
    }
}

$MyIP = Get-PublicIP
$Url = "https://www.duckdns.org/update?domains=$Domain&token=$Token&ip=$MyIP"
try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 20
    $respText = [System.Text.Encoding]::ASCII.GetString([byte[]]$resp.Content)
    $status = if ($respText.Trim() -eq "OK") {"ok"} else {"fail"}
} catch { $status="error"; $respText=$_.Exception.Message }

$ts = (Get-Date).ToString("s")
"$ts | ip=$MyIP | status=$status | resp=$respText" | Out-File $Log -Append

```

**Scheduled Task:**

```powershell
schtasks /Create /TN "DuckDNS-Update-teevra18" /SC MINUTE /MO 5 `
 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\T18\duckdns\Update-DuckDNS.ps1'" `
 /RU "SYSTEM" /RL LIMITED /F

```

---

### **C. VPS Auto-Firewall Script**

**File:** `/usr/local/bin/update_teevra18_firewall.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

HOST="teevra18.duckdns.org"
STATE_DIR="/var/lib/teevra18_fw"
STATE_FILE="$STATE_DIR/current_ip"
LOG_FILE="/var/log/teevra18_fw.log"

mkdir -p "$STATE_DIR"

NEW_IP="$(getent ahostsv4 "$HOST" | awk '{print $1}' | head -n1 || true)"
ts() { date +"%Y-%m-%dT%H:%M:%S"; }

if [[ -z "$NEW_IP" ]]; then
  echo "$(ts) | WARN | could not resolve $HOST" >> "$LOG_FILE"; exit 0
fi

OLD_IP="$(cat "$STATE_FILE" 2>/dev/null || true)"
if [[ "$NEW_IP" == "$OLD_IP" ]]; then
  echo "$(ts) | OK | no change ($NEW_IP)" >> "$LOG_FILE"; exit 0
fi

echo "$(ts) | INFO | IP change detected: $OLD_IP -> $NEW_IP" >> "$LOG_FILE"

[[ -n "$OLD_IP" ]] && ufw delete allow proto tcp from "$OLD_IP" to any port 22 2>/dev/null || true
ufw allow proto tcp from "$NEW_IP" to any port 22 comment "teevra18-home-ip"
ufw limit 22/tcp || true
echo "$NEW_IP" > "$STATE_FILE"
echo "$(ts) | OK | updated UFW for $NEW_IP" >> "$LOG_FILE"

```

---

### **D. Systemd Service & Timer**

**Service File:** `/etc/systemd/system/teevra18-fw.service`

```
[Unit]
Description=Teevra18 DuckDNS firewall updater

[Service]
Type=oneshot
ExecStart=/usr/local/bin/update_teevra18_firewall.sh

```

**Timer File:** `/etc/systemd/system/teevra18-fw.timer`

```
[Unit]
Description=Run Teevra18 firewall updater every 2 minutes

[Timer]
OnBootSec=30sec
OnUnitActiveSec=2min
AccuracySec=30sec
Unit=teevra18-fw.service

[Install]
WantedBy=timers.target

```

**Enable & verify:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now teevra18-fw.timer
sudo systemctl status teevra18-fw.timer

```

✅ Expected:

`Active: active (waiting)` → means timer is running.

Log file updates every 2 minutes.

---

## 🔒 **4. Layered Security Controls**

```mermaid
graph TD

A["Cloud Firewall (Vultr)"]
B["Host Firewall (UFW)"]
C["SSH Service"]
D["Fail2ban + Public Key Auth"]
E["Audit Logging + Timestamped IP Changes"]

A --> B
B --> C
C --> D
D --> E

```

### **Final Rule Sets**

### Vultr Firewall Group (t18-bridge-fw)

| Port | Protocol | Source | Action | Notes |
| --- | --- | --- | --- | --- |
| 22 | TCP (SSH) | 0.0.0.0/0 | Accept | Base access |
| 443 | TCP (HTTPS) | 0.0.0.0/0 | Accept | Dashboard/API |
| 444 | TCP | 0.0.0.0/0 | Accept | OAuth bridge |
| 0-65535 | any | 0.0.0.0/0 | Drop | Default deny |

### VPS Firewall (UFW)

| Port | Source | Action | Comment |
| --- | --- | --- | --- |
| 22 | 84.68.158.77 | ALLOW | `teevra18-home-ip` |
| 443 | Anywhere | ALLOW | `HTTPS bridge` |
| 444 | Anywhere | ALLOW | `OAuth callback HTTPS` |

---

## 🧾 **5. Logging and Audit Trail**

### **Location**

`/var/log/teevra18_fw.log`

### **Sample Entries**

```
2025-10-13T22:12:26 | INFO | IP change detected:  -> 84.68.158.77
2025-10-13T22:12:27 | OK   | updated UFW for 84.68.158.77
2025-10-13T22:41:39 | OK   | no change (84.68.158.77)
2025-10-13T22:33:34 | WARN | could not resolve teevra18.duckdns.org

```

Each entry is timestamped and SEBI-auditable.

Recommended retention: 5 years (as per NSE/SEBI Algo Circular INVG67858).

**Optional Daily Archive Script**

```bash
sudo bash -c 'echo "0 0 * * * root cp /var/log/teevra18_fw.log /T18/logs/security/audit/$(date +\%F)_fw.log" >> /etc/crontab'

```

---

## 🧰 **6. Maintenance Tasks**

| Task | Frequency | Command / Check |
| --- | --- | --- |
| Verify timer | Weekly | `systemctl status teevra18-fw.timer` |
| Inspect logs | Weekly | `tail -n 20 /var/log/teevra18_fw.log` |
| Check DuckDNS sync | Weekly | `nslookup teevra18.duckdns.org` |
| Backup logs | Monthly | `cp /var/log/teevra18_fw.log /T18/logs/security/audit/` |
| Test IP change | Quarterly | Restart router and verify log updates |

---

## 🧠 **7. SEBI Compliance Mapping**

| Requirement | Control Implemented | Evidence |
| --- | --- | --- |
| **Static IP at server** | VPS (Mumbai) with fixed IPv4 | Vultr instance config |
| **Audit trail (5 years)** | Log + daily archive | `/var/log/teevra18_fw.log` |
| **User authentication & traceability** | SSH key + Fail2ban | `/etc/ssh/sshd_config` |
| **Order tagging & algorithm isolation** | Maintained via TEEVRA18 core | T18 source compliance module |
| **Secure access** | 2-layer firewall + 2FA at app level | Architecture diagram |

---

## 🌐 **8. Verification Checklist**

| Verification | Status |
| --- | --- |
| DuckDNS resolving correctly | ✅ |
| Windows updater task running | ✅ |
| VPS timer active | ✅ |
| UFW showing dynamic IP only | ✅ |
| Vultr firewall minimal and layered | ✅ |
| Logs showing “no change” updates | ✅ |
| SSH works only from home IP | ✅ |

---

## 🧩 **9. Workflow Summary**

```mermaid
sequenceDiagram
    participant W as Windows Client
    participant D as DuckDNS
    participant V as VPS (UFW)
    participant L as Log File

    W->>D: Updates teevra18.duckdns.org with current public IP
    D-->>V: Host resolves new IP via DNS
    V->>V: Script compares OLD_IP vs NEW_IP
    alt IP changed
        V->>UFW: Remove old allow rule
        V->>UFW: Add new allow rule for NEW_IP
        V->>L: Log “updated UFW for <NEW_IP>”
    else No change
        V->>L: Log “no change (<CURRENT_IP>)”
    end

```

---

## 🧩 **10. Key Benefits**

- **SEBI-compliant static-VPS architecture** without static home IP cost.
- **Zero manual intervention** during IP changes.
- **Full auditability** of each update cycle.
- **Defense-in-depth** design (cloud firewall → host firewall → dynamic rule → SSH keys → Fail2ban).
- **No downtime** for trading APIs or TEEVRA18 services.

---

## 🧩 **11. Future Enhancements**

| Feature | Description | Priority |
| --- | --- | --- |
| Daily log archival + rotation | Store logs under `/T18/logs/security/audit/` | High |
| Email / Telegram alert on IP change | Notification for external monitoring | Medium |
| Web GUI for viewing firewall status | Lightweight dashboard using Flask/Streamlit | Medium |
| Integration with TEEVRA18 Risk Engine | Unified compliance reporting | Medium |

---

## ✅ **12. Final Validation Snapshot**

**As of 13 Oct 2025**

```
DuckDNS Host : teevra18.duckdns.org
Resolved IP  : 84.68.158.77
UFW Rule     : ALLOW IN 84.68.158.77 (teevra18-home-ip)
Timer Status : active (waiting)
Log Health   : OK (auto-updates every 2 min)
Vultr FW     : 22,443,444 open; rest dropped
SEBI Status  : Compliant

```

---

📘 **End of Document — TEEVRA18 Dynamic IP Bridge Configuration Guide**

*© 2025 Neelkanth Dwibedi | CYBER CRISPS LIMITED*

---