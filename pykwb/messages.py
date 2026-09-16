"""Load the bundled KWB Comfort 3 message definitions."""

import csv
from importlib.resources import files


def load_messages():
    """Return message definitions as dictionaries of strings (Python 3.9+)."""
    resource = files("pykwb").joinpath("messages.csv")
    with resource.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))
