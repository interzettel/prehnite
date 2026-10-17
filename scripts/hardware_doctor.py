"""Read-only JSON hardware report. Run after installing Prehnite locally."""
from __future__ import annotations

import json
from prehnite.hardware import hardware_report

if __name__ == "__main__":
    print(json.dumps(hardware_report(), indent=2, sort_keys=True))
