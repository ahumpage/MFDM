from pathlib import Path
import subprocess
import sys

PLANTS = "plants_basic.csv"
FUEL = "fuel.csv"
DEMAND = "demand.csv"
PROFILES = "profiles_renewables.csv"
OUTPUT_NAME = "output_profiles"

ROOT = Path(__file__).resolve().parent

model = subprocess.call([sys.executable, str(ROOT / "model" / "MFDM.py"),
                         "--plants", PLANTS, "--fuel", FUEL,
                         "--demand", DEMAND, "--profiles", PROFILES,
                         "--label", OUTPUT_NAME])
if model == 0:
    subprocess.call([sys.executable, str(ROOT / "dashboard" / "dashboard.py")])

# quickstart, just run dashboard.py, there are some examples ready to go
