"""Download the UCI household electricity dataset into the local data directory."""

import argparse
import os
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


DATA_URL = "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"
MEMBER_NAME = "household_power_consumption.txt"
ROOT = Path(__file__).resolve().parents[1]


def download_data(destination: Path, force: bool = False) -> Path:
    destination = destination.resolve()
    if destination.exists() and not force:
        print(f"Dataset already exists: {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)

    zip_path = None
    data_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".zip", delete=False) as temporary:
            zip_path = Path(temporary.name)
            with urlopen(DATA_URL, timeout=60) as response:
                shutil.copyfileobj(response, temporary)
        with ZipFile(zip_path) as archive:
            if MEMBER_NAME not in archive.namelist():
                raise ValueError(f"The UCI archive did not contain {MEMBER_NAME}")
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".txt", delete=False) as temporary:
                data_path = Path(temporary.name)
                with archive.open(MEMBER_NAME) as source:
                    shutil.copyfileobj(source, temporary)
        os.replace(data_path, destination)
        data_path = None
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)
        if data_path is not None:
            data_path.unlink(missing_ok=True)
    print(f"Saved {destination} ({destination.stat().st_size:,} bytes)")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / MEMBER_NAME)
    parser.add_argument("--force", action="store_true", help="Replace an existing dataset file")
    args = parser.parse_args()
    download_data(args.output, force=args.force)
