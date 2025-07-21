# deploy-tool

## Architecture

### High-Level Overview

The `deploy-tool` consists of two interconnected systems:

1. **Deployment Pipeline**  
   A client-side automation system responsible for building and deploying web applications to an S3 bucket.
```
   code structure:
    cli-tool/
    ├── .deploy-config.json # generated on `deploy-tool init`
    ├── .gitignore
    ├── README.md
    ├── requirements.txt
    ├── deploy_tool/
    │  ├── init.py
    │  ├── cli.py
    │  ├── commands/
    │  │ ├── init.py
    │  │ ├── config.py
    │  │ ├── deploy.py
    │  │ ├── init.py
    │  │ ├── monitoring.py
    │  │ ├── rollback.py
    │  │ ├── status.py
    │  │ └── versions.py
    │  └── core/
    │    ├── init.py
    │    ├── aws_manager.py
    │    ├── build_manager.py
    │    ├── config_manager.py
    │    ├── git_manager.py
    │    └── utils.py
    ├── terraform/
    ├── monitoring/
    │  ├── terraform/
```            


2. **Monitoring Stack**  
   A server-side infrastructure responsible for observing the health and performance of the deployed applications.

   *the below given code structure is inside the monitoring server instance.*
``` 
   code structure:
   monitoring-server/                  
    ├── docker-compose.yml          
    │
    ├── prometheus/
    │   ├── prometheus.yml          
    │   └── targets/
    │       └── auto_discovered_websites.json  
    │
    ├── grafana/
    │   ├── dashboards/             
    │   │   └── application_dashboard.json 
    │   │
    │   └── provisioning/           
    │       ├── datasources/
    │       │   └── prometheus.yml  
    │       └── dashboards/
    │           └── dashboard.yml   
    │
    ├── alertmanager/
    │   └── alertmanager.yml        
    │
    ├── blackbox/
    │   └── blackbox.yml            
    │
    ├── discovery-service/          
    │   ├── discovery.py            
    │   └── requirements.txt  
```

---

## I. CLI Tool (`deploy-tool`)

This is the primary interface for users. Built using Python and the **Click** framework, it translates user commands like `init`, `deploy`, `rollback`, or `monitoring start` into orchestrated actions handled by internal managers.

> ![Basic Workflow](<basic workflow.drawio.png>)

---

## II. Core Managers

These are the internal engines responsible for executing the deployment pipeline:

### 1. ConfigManager
- **Purpose:** Manages project configuration.
- **Responsibilities:**
  - Reads/writes to `.deploy-config.json`
  - Provides unified access to GitHub URL, AWS profile, and build commands.

### 2. GitManager
- **Purpose:** Handles source control.
- **Responsibilities:**
  - Clones GitHub repositories into isolated temporary directories.
  - Cleans up after deployment.

### 3. BuildManager
- **Purpose:** Automates building of modern web applications.
- **Responsibilities:**
  - **Framework Detection** via `package.json` (e.g., Vite, React)
  - **Dependency Installation** using `npm install` / `npm ci`
  - **Build Execution** with fallbacks (e.g., `npx vite build`)
  - **S3 Optimization** by converting absolute paths in `index.html` to relative paths.

### 4. AWSManager
- **Purpose:** Handles all AWS interactions.
- **Responsibilities:**
  - AWS authentication
  - S3 uploads with checksum checks
  - S3 versioning and deployment activation
  - EC2 management for monitoring stack

---

## III. Deployment Infrastructure (AWS S3 Versioning)

The S3 structure supports **atomic deployments** and **instant rollbacks**:

```
s3://minfy-uzaif-capstone-deployments/
└── my-project-name/
    ├── versions/
    │   ├── v20250721-100000/
    │   └── v20250721-100500/
    └── current/
        ├── index.html
        └── assets/
```

### Deployment Process
- New builds are uploaded to timestamped folders in `versions/`
- The `current/` folder is replaced with the new version contents.

### Rollback Process
- Rollback is achieved by copying contents of a previous `versions/` folder into `current/`.

---

## IV. Monitoring Infrastructure (EC2 & Docker)

Designed for cost-efficiency, this monitoring stack runs on a separate EC2 instance and can be toggled on/off.

### Components:

- **Docker & Docker Compose**  
  Entire monitoring stack is containerized and managed via `docker-compose`.

- **Prometheus**  
  Pulls and stores metrics from various services.

- **Grafana**  
  Provides visual dashboards based on Prometheus data.

- **Exporters**  
  - **Node Exporter:** Monitors host metrics (CPU, memory, disk).
  - **Blackbox Exporter:** Probes live URLs for uptime/latency.

- **Custom Discovery Service**  
  - Scans deployed apps in S3
  - Generates `targets.json` for Prometheus
  - Ensures **auto-monitoring** of newly deployed apps

---

## Features

- **One-Command Deployment:** `deploy-tool deploy` handles cloning, building, and uploading.
- **GitHub Integration:** Ensures deployments use latest code.
- **Automatic Framework Detection:** Supports React, Vite, Next.js, Angular, Vue.
- **Integrated Monitoring:** Control EC2-based monitoring services from the CLI.

---

## CLI Tool Command Reference

### Core Deployment Commands

#### - deploy-tool init
Initializes a new deployment project.

```
deploy-tool init --github-url <repository-url>
```

**Options:**
- `--github-url TEXT`: Required GitHub repo URL
- `--project-name TEXT`: Optional custom name
- `--framework [react|vite|next|auto]`: Framework selection (default: auto)
- `--environment [development|staging|production]`: Deployment environment (default: production)

**Example:**
```
deploy-tool init --github-url https://github.com/Uzaif-Minfy/capstonte-testing-2
```

---

- ####  deploy-tool deploy
Builds and deploys the application to AWS S3.

```
deploy-tool deploy
```

**Options:**
- `--env [production|staging|dev]`: Target environment (default: production)
- `--version TEXT`: Custom version tag
- `--build-only`: Only build without deployment


**Examples:**
```
deploy-tool deploy --version 1.0.0.1
deploy-tool deploy --env staging
```

---

- ####  deploy-tool status
Displays the current deployed version and last deployment time.

```
deploy-tool status
```

---

- ####  deploy-tool rollback
Reverts deployment to a previous version.

```
deploy-tool rollback
deploy-tool rollback --version <version-tag>
```

---

- ####  deploy-tool versions
Lists the last 10 deployed versions.

```
deploy-tool versions
```

Clean up old versions
```
deploy-tool versions --list Example: deploy-tool versions --cleanup --keep 5
```
---





- #### deploy-tool config 

**Options:**
-  `get`        Get a configuration value
-  `reset`      Reset all configuration
-  `set`        Set a configuration value
-  `show`       Display current configuration





**Examples:**
```
deploy-tool config show
deploy-tool config set project.name my-awesome-app
```




---

## Monitoring Management (`monitoring`)

**Options:**
- `dashboard`   Open Grafana dashboard in browser
-  `discovered`  List auto-discovered applications
-  `logs`    View monitoring service logs
-  `start`     Start monitoring server and containers
- `status`      Check monitoring server status
-  `stop`      Stop monitoring containers and server
-  `urls`      Get monitoring service URLs

**Examples:**
```
deploy-tool monitoring start
deploy-tool monitoring dashboard
deploy-tool monitoring stop
```
