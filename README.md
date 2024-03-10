# licenseMonitor V1.3.1

## Update history
***
| Version | Date      | Update content                                                   |
|:--------|:----------|:-----------------------------------------------------------------|
| V1.0    | (2023.01) | Release original version.                                        |
| V1.1    | (2023.07) | Add tool bin/license_sample.                                     |
|         |           | Add UTILIZATION/COST tab.                                        |
| V1.2    | (2023.11) | Add log search function on FEATURE/USAGE tabs.                   |
|         |           | Add feature/product filter function on UTILIZATION/COST tabs.    |
|         |           | Add tool tools/gen_LM_LICENSE_FILE.py.                           |
| V1.3    | (2023.12) | Add CURVE tab.                                                   |
|         |           | Add logo and menu icons.                                         |
|         |           | Add tools tools/update_*.py.                                     |
| V1.3.1  | (2024.03) | Add license file search function on EXPIRES tab.                 |
|         |           | Add license log search function on UTILIZATION/COST tabs.        |
|         |           | Add product fast fuzzy search function on UTILIZATION/COST tabs. |
|         |           | Add tools tools/*.                                               |


## Introduction
***

### 0. What is licenseMonitor?
licenseMonitor is an open source software for EDA license information data-collection,
data-analysis and data-display.

### 1. Python dependency
Need python3.8.8, Anaconda3-2021.05-Linux-x86_64.sh is better.
Install python library dependency with command

    pip install -r requirements.txt

### 2. Install
Copy install package into install directory.
Execute below command under install directory.

    python3 install.py

### 3. Config
  - $MONITOR_VIEWER_INSTALL_PATH/config/config.py : top configuration file for licenseMonitor.
  - $MONITOR_VIEWER_INSTALL_PATH/config/LM_LICENSE_FILE : LM_LICENSE_FILE list.
  - $MONITOR_VIEWER_INSTALL_PATH/config/cost : cost related settings.
  - $MONITOR_VIEWER_INSTALL_PATH/config/others : license log and product_feature related settings.
  - $MONITOR_VIEWER_INSTALL_PATH/config/project : project related settigns.
  - $MONITOR_VIEWER_INSTALL_PATH/config/utilization : utilization related settings.

### 4. Sample
  - Sample EDA license information with tool bin/license_sample.


More details please see ["docs/licenseMonitor_user_manual.pdf"](./docs/licenseMonitor_user_manual.pdf)
