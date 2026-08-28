from pathlib import Path
import subprocess
import sys

PLANTS = "plants_basic.csv"
FUEL = "fuel.csv"
DEMAND = "demand.csv"
PROFILES = "profiles_renewables.csv"
USE_BATTERY = False
BATTERY = "battery.csv"
OUTPUT_NAME = "output_profiles"

ROOT = Path(__file__).resolve().parent

args = [sys.executable, str(ROOT / "model" / "MFDM.py"),
        "--plants", PLANTS, "--fuel", FUEL,
        "--demand", DEMAND, "--profiles", PROFILES,
        "--label", OUTPUT_NAME]
if USE_BATTERY:
    args += ["--battery", BATTERY]
else:
    args += ["--no-battery"]

model = subprocess.call(args)
if model == 0:
    subprocess.call([sys.executable, str(ROOT / "dashboard" / "dashboard.py")])

# quickstart, just run dashboard.py, there are some examples ready to go
