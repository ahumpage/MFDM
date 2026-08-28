from pathlib import Path

import pandas as pd
import pytest

from model.MFDM import run_model


EXAMPLES = Path(__file__).resolve().parents[1] / "docs" / "examples" / "ramping"


def read_example(name):
    folder = EXAMPLES / name
    profile_path = folder / "profiles.csv"
    return (
        pd.read_csv(folder / "plants.csv", keep_default_na=False),
        pd.read_csv(folder / "fuel.csv"),
        pd.read_csv(folder / "demand.csv"),
        pd.read_csv(profile_path, header=[0, 1]),
    )


@pytest.mark.parametrize(
    "scenario, objective, spill",
    [
        ("scenario_1_holding_back", 6200.0, 0.0),
        ("scenario_2_spill", 55600.0, 50.0),
    ],
)
def test_run_model_solves_worked_examples(scenario, objective, spill):
    results, summary, diagnostics = run_model(*read_example(scenario))

    assert len(results) == 3
    assert set(summary["Plant"]) == {"Cheap", "Dear"}
    assert diagnostics["solver_status"] == "Optimal"
    assert diagnostics["objective"] == pytest.approx(objective)
    assert diagnostics["reported_objective"] == pytest.approx(objective)
    assert diagnostics["objective_error"] == pytest.approx(0.0, abs=1e-6)
    assert diagnostics["energy_balance_error"] == pytest.approx(0.0, abs=1e-6)
    assert results["Spill (MWh)"].sum() == pytest.approx(spill)
