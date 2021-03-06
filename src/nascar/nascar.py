import requests
import time
import logging
from sys import stdout
from datetime import datetime
from pathlib import Path
import pandas as pd
from pandas import ExcelWriter
import json

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=stdout))

with open("config.json", "r") as f:
    config = json.load(f)
API = config["NASCAR_API"]

INTERVAL = 5
DATA_PATH = "./data/nascar"


class Lap:
    def __init__(self, number, time, position):
        self.number = number
        self.time = time
        self.position = position

    def __str__(self):
        return f"Lap number: {self.number}, Lap time: {self.time}, Driver position: {self.position}"  # noqa: E501


class Laps:
    def __init__(self, laps_json=None):
        self.laps = []
        if laps_json is not None:
            self.add_laps_json(laps_json)

    def add_laps_json(self, laps_json):
        for lap in laps_json:
            self.laps.append(Lap(lap["Lap"], lap["LapTime"], lap["RunningPos"]))

    def add_laps(self, laps):
        self.laps.extend(laps)


class Driver:
    def __init__(self, number, name, manufacturer, id):
        self.number = number
        self.name = name
        self.manufacturer = manufacturer
        self.id = id
        self.position = None
        self.laps = Laps()

    def last_lap():
        pass

    def get_new_laps(self, laps_json):
        old_laps = set(self.laps.laps)
        old_lap_numbers = set([lap.number for lap in old_laps])
        updated_laps = set(Laps(laps_json).laps)
        new_laps = [lap for lap in updated_laps if lap.number not in old_lap_numbers]
        for lap in new_laps:
            logger.info(f"Driver: {self.name}, {str(lap)}")
            print(f"Driver: {self.name}, {str(lap)}")

        return new_laps


class Drivers:
    def __init__(self, laps):
        self.drivers = self.parse_drivers(laps)

    def parse_driver(self, driver):
        driver_id = driver["NASCARDriverID"]
        return {
            driver_id: Driver(
                driver["Number"], driver["FullName"], driver["Manufacturer"], driver_id
            )
        }

    def parse_drivers(self, laps):
        drivers = {}
        for driver in laps:
            drivers.update(self.parse_driver(driver))
        return drivers

    def update_lap_times(self, laps_json):
        drivers_new_laps = []
        for driver_json in laps_json:
            driver = self.drivers[driver_json["NASCARDriverID"]]
            new_laps = driver.get_new_laps(driver_json["Laps"])
            driver.laps.add_laps(new_laps)
            drivers_new_laps.append((driver, new_laps))
        return drivers_new_laps


def sort_laps(dict_laps):
    return sorted(dict_laps, key=lambda lap: (lap["Name"], lap["Lap Number"]))


def transform_laps(driver_laps):
    dict_laps = []
    for driver, laps in driver_laps:
        for lap in laps:
            dict_laps.append(
                {
                    "Name": driver.name,
                    "Lap Number": lap.number,
                    "Running Position": lap.position,
                    "Lap Time": lap.time,
                }
            )
    dict_laps = sort_laps(dict_laps)
    return dict_laps


def unstack_laps(dict_laps):
    stacked = pd.DataFrame(dict_laps)
    unstacked = stacked.pivot(
        index="Lap Number", columns="Name", values=["Lap Time", "Running Position"]
    )
    # For some reason Nascar returns Lap 0 times, but it's not filled in.
    try:
        return unstacked.drop([0])
    except KeyError:
        return unstacked


def check_data_path(fname):
    Path(DATA_PATH).mkdir(parents=True, exist_ok=True)
    return Path(DATA_PATH) / fname


def append_csv(dict_laps, writer, f):
    writer.writerows(dict_laps)
    f.flush()


def write_dataframe(df, fpath):
    with ExcelWriter(fpath) as writer:
        df["Lap Time"].to_excel(writer, sheet_name="Lap Time")
        df["Running Position"].to_excel(writer, sheet_name="Running Position")


def get_lap_data():
    res = requests.get(API)
    return res.json()


def main(drivers, fpath):
    while True:
        data = get_lap_data()
        drivers_new_laps = drivers.update_lap_times(data["laps"])
        if drivers_new_laps:
            # dict_laps = transform_laps(drivers_new_laps)
            all_laps = [(d, d.laps.laps) for id, d in drivers.drivers.items()]
            dict_laps = transform_laps(all_laps)
            if dict_laps:
                unstacked = unstack_laps(dict_laps)
                write_dataframe(unstacked, fpath)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    data = get_lap_data()
    fpath = check_data_path(f"{datetime.now().date().isoformat()}.xlsx")
    drivers = Drivers(data["laps"])
    main(drivers, fpath)
