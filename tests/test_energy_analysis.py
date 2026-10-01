"""Small regression checks for time-series totals and model comparison."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.energy_analysis import cluster_sample, compare_clusters, load_power_data, monthly_energy


class EnergyAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        timestamps = pd.date_range("2007-01-01", periods=120, freq="min")
        rng = np.random.default_rng(42)
        frame = pd.DataFrame({
            "Date": timestamps.strftime("%d/%m/%Y"),
            "Time": timestamps.strftime("%H:%M:%S"),
            "Global_active_power": rng.uniform(1, 4, 120),
            "Global_reactive_power": rng.uniform(0, 1, 120),
            "Voltage": rng.uniform(220, 240, 120),
            "Global_intensity": rng.uniform(1, 10, 120),
            "Sub_metering_1": rng.uniform(0, 6, 120),
            "Sub_metering_2": rng.uniform(0, 6, 120),
            "Sub_metering_3": rng.uniform(0, 6, 120),
        })
        frame["Global_active_power"] = frame["Global_active_power"].astype(object)
        frame.loc[3, "Global_active_power"] = "?"
        self.path = Path(self.folder.name) / "household_power_consumption.txt"
        frame.to_csv(self.path, sep=";", index=False)

    def test_missing_minute_does_not_gain_invented_energy(self):
        readings, counts = load_power_data(self.path)
        self.assertEqual(counts["raw_rows"], 120)
        self.assertEqual(counts["complete_rows"], 119)
        self.assertEqual(counts["negative_residual_rows"], int((readings["Other_Wh"] < 0).sum()))
        monthly = monthly_energy(readings)
        self.assertEqual(monthly.iloc[0]["observed_minutes"], 119)
        self.assertAlmostEqual(monthly.iloc[0]["Total_kWh"], readings["Total_Wh"].sum() / 1000)
        self.assertAlmostEqual(
            monthly.iloc[0]["Total_kWh"],
            monthly.iloc[0][[
                "Sub_metering_1_kWh", "Sub_metering_2_kWh", "Sub_metering_3_kWh", "Other_kWh"
            ]].sum(),
        )

    def test_models_use_same_sample_and_report_noise(self):
        readings, _ = load_power_data(self.path)
        sample, scaled = cluster_sample(readings, sample_size=100)
        scores, labels = compare_clusters(scaled)
        self.assertEqual(len(sample), 100)
        self.assertEqual(set(labels), {"K-Means", "Hierarchical", "DBSCAN"})
        self.assertTrue(all(len(value) == 100 for value in labels.values()))
        self.assertAlmostEqual(scores.loc["K-Means", "noise_fraction"], 0)


if __name__ == "__main__":
    unittest.main()
