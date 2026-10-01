"""Check the reproducible download and result-generation entry points."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd

from scripts.build_results import build_results
from scripts.download_data import MEMBER_NAME, download_data


class RepositoryWorkflowTests(unittest.TestCase):
    def test_download_extracts_expected_member_and_skips_existing_file(self):
        archive_bytes = io.BytesIO()
        with ZipFile(archive_bytes, "w") as archive:
            archive.writestr(MEMBER_NAME, "Date;Time\n01/01/2007;00:00:00\n")
        archive_bytes.seek(0)

        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "data" / MEMBER_NAME
            with patch("scripts.download_data.urlopen", return_value=archive_bytes) as urlopen:
                self.assertEqual(download_data(destination), destination)
                self.assertEqual(download_data(destination), destination)
                urlopen.assert_called_once()
            self.assertIn("01/01/2007", destination.read_text(encoding="utf-8"))

    def test_build_results_writes_machine_readable_tables_and_charts(self):
        timestamps = pd.date_range("2007-01-01", periods=120, freq="min")
        rng = np.random.default_rng(7)
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
        with tempfile.TemporaryDirectory() as folder:
            dataset = Path(folder) / MEMBER_NAME
            output = Path(folder) / "results"
            frame.to_csv(dataset, sep=";", index=False)
            build_results(dataset, output)

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["sample_size"], 120)
            self.assertEqual(summary["calendar_months"], 1)
            self.assertEqual(len(pd.read_csv(output / "monthly_energy.csv")), 1)
            self.assertEqual(len(pd.read_csv(output / "clustering_scores.csv")), 3)
            self.assertEqual(int(pd.read_csv(output / "kmeans_profile.csv")["sample_minutes"].sum()), 120)
            self.assertGreater((output / "figures" / "monthly_energy.png").stat().st_size, 0)
            self.assertGreater((output / "figures" / "cluster_comparison.png").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
