from pathlib import Path
import subprocess
import sys

PLANTS = "plants_ramping.csv"
FUEL = "fuel.csv"
DEMAND = "demand.csv"
PROFILES = "profiles_renewables.csv"
OUTPUT_NAME = "output_ramping"

ROOT = Path(__file__).resolve().parent

model = subprocess.call([sys.executable, str(ROOT / "model" / "MFDM.py"),
                         "--plants", PLANTS, "--fuel", FUEL,
                         "--demand", DEMAND, "--profiles", PROFILES,
                         "--label", OUTPUT_NAME])
if model == 0:
    subprocess.call([sys.executable, str(ROOT / "dashboard" / "dashboard.py")])
