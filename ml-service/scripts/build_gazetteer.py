"""Build the offline gazetteer shipped with the ML service.

Inputs (from https://download.geonames.org/export/dump/, CC-BY 4.0):
  - cities15000.txt   all cities with population >= 15,000
  - countryInfo.txt   ISO codes and country names

Outputs (committed to the repo, loaded by services/geocode.py):
  - data/cities.tsv     name \t country \t admin1 \t lat \t lng \t population
  - data/countries.tsv  code \t name \t lat \t lng   (population-weighted centroid)

Usage: python scripts/build_gazetteer.py <cities15000.txt> <countryInfo.txt>
"""
import sys
import csv
import os
from collections import defaultdict


def main(cities_path: str, country_info_path: str):
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    country_acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])

    with open(cities_path, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 15:
                continue
            ascii_name = cols[2].strip().lower()
            lat, lng = float(cols[4]), float(cols[5])
            country = cols[8].strip().upper()
            admin1 = cols[10].strip().upper()
            try:
                pop = int(cols[14])
            except ValueError:
                pop = 0
            if not ascii_name or not country:
                continue
            rows.append((ascii_name, country, admin1, lat, lng, pop))
            acc = country_acc[country]
            acc[0] += lat * max(pop, 1)
            acc[1] += lng * max(pop, 1)
            acc[2] += max(pop, 1)

    rows.sort(key=lambda r: (-r[5], r[0]))

    with open(os.path.join(out_dir, "cities.tsv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        for r in rows:
            w.writerow([r[0], r[1], r[2], f"{r[3]:.4f}", f"{r[4]:.4f}", r[5]])

    with open(country_info_path, encoding="utf-8") as f, open(
        os.path.join(out_dir, "countries.tsv"), "w", newline="", encoding="utf-8"
    ) as out:
        w = csv.writer(out, delimiter="\t")
        for line in f:
            if line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            code, name = cols[0].strip().upper(), cols[4].strip()
            if not code or code not in country_acc:
                continue
            acc = country_acc[code]
            w.writerow([code, name, f"{acc[0] / acc[2]:.4f}", f"{acc[1] / acc[2]:.4f}"])

    print(f"cities: {len(rows)}, countries: {len(country_acc)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
