"""
scripts/make_sample_data.py – generate synthetic SAMPLE bids for BidMitra.

All bids have data_source=SAMPLE and bid_number starting with SAMPLE/.
Includes deliberate near-miss cases:
  - EMD slightly above the limit (exact margin configurable)
  - Consignee 20-40 km beyond the delivery radius
Also generates bids for the Mohali office furniture and Ludhiana safety
equipment demo profiles.
Run: python scripts/make_sample_data.py
"""

from __future__ import annotations
import csv
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from repo root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "data" / "bids.csv"
SNAPSHOT_DATE = datetime(2026, 10, 3, tzinfo=timezone.utc)

FIELDNAMES = [
    "bid_number", "title", "quantity", "consignee_state", "consignee_district",
    "buyer_org", "emd_inr", "end_datetime", "doc_url", "data_source",
]

# ---------------------------------------------------------------------------
# Bid title templates (mapped to keyword families)
# ---------------------------------------------------------------------------

ITEM_TITLES = {
    "timing_belts": [
        "Supply of Timing Belt for Industrial Conveyor",
        "Procurement of Synchronous Belt Drive System",
        "Toothed Belt for Packaging Machinery Maintenance",
        "Cogged Belt Supply for Refinery Equipment",
        "Timing Belt Replacement for Pumping Unit",
        "Supply of V-Belt and Timing Belt Assembly",
    ],
    "pulleys": [
        "Supply of Timing Pulley for Drive System",
        "Procurement of Sheave and Pulley Set",
        "Industrial Pulley for Conveyor Belt System",
        "Replacement Pulley for Rotating Equipment",
        "Timing Pulley Drive Assembly Supply",
        "Supply of Variable Speed Pulley Unit",
    ],
    "valves": [
        "Supply of Gate Valve DN50 PN16",
        "Procurement of Ball Valve Stainless Steel",
        "Globe Valve Supply for Process Piping",
        "Check Valve NRV for Water Treatment Plant",
        "Butterfly Valve Supply for HVAC System",
        "Safety Valve for Steam Line Maintenance",
        "Relief Valve Supply for Pressure Vessel",
        "Supply of Ball Valve and Gate Valve Set",
        "Procurement of Industrial Valves for Refinery",
    ],
    "adjacent": [
        "Supply of Industrial Bearing Set",
        "Procurement of Shaft Coupling for Pumps",
        "Gasket Supply for Flange Connections",
        "Industrial Strainer Basket Replacement",
        "Mechanical Seal Supply for Centrifugal Pumps",
        "Flange Set and Bolting Supply",
        "Hydraulic Hose Assembly Supply",
    ],
    "unrelated": [
        "Supply of Office Furniture and Chairs",
        "Procurement of Computer Hardware",
        "Supply of Stationery Items",
        "Civil Works for Boundary Wall",
        "Electrical Cable and Wire Supply",
        "Supply of Personal Protective Equipment",
    ],
}

# Districts within 250 km of Panipat (roughly)
NEAR_DISTRICTS = [
    ("Karnal", "Haryana"),
    ("Sonipat", "Haryana"),
    ("Rohtak", "Haryana"),
    ("Ambala", "Haryana"),
    ("Kurukshetra", "Haryana"),
    ("Ludhiana", "Punjab"),
    ("New Delhi", "Delhi"),
    ("Faridabad", "Haryana"),
    ("Gurugram", "Haryana"),
    ("Meerut", "Uttar Pradesh"),
    ("Saharanpur", "Uttar Pradesh"),
    ("Noida", "Uttar Pradesh"),
    ("Patiala", "Punjab"),
    ("Mohali", "Punjab"),
    ("Haridwar", "Uttarakhand"),
    ("Dehradun", "Uttarakhand"),
    ("Muzaffarnagar", "Uttar Pradesh"),
    ("Shamli", "Uttar Pradesh"),
    ("Yamunanagar", "Haryana"),
    ("Panipat", "Haryana"),
]

# Districts beyond 250 km
FAR_DISTRICTS = [
    ("Amritsar", "Punjab"),
    ("Mumbai", "Maharashtra"),
    ("Ahmedabad", "Gujarat"),
    ("Lucknow", "Uttar Pradesh"),
    ("Jaipur", "Rajasthan"),
    ("Vadodara", "Gujarat"),
    ("Nagpur", "Maharashtra"),
    ("Shimla", "Himachal Pradesh"),
    ("Bikaner", "Rajasthan"),
    ("Kanpur Nagar", "Uttar Pradesh"),
]

# Near-miss districts (just beyond 250 km, ~20-40 km over)
NEAR_MISS_DISTRICTS = [
    ("Ludhiana", "Punjab"),    # ~180 km – actually near, use for variety
    ("Amritsar", "Punjab"),    # ~240-260 km depending on exact coords
    ("Bathinda", "Punjab"),    # ~280 km
    ("Moga", "Punjab"),
]

BUYER_ORGS = [
    "Indian Oil Corporation Ltd", "Bharat Petroleum", "Hindustan Petroleum",
    "NTPC Limited", "Steel Authority of India", "National Fertilizers Ltd",
    "ONGC Videsh", "GAIL India Ltd", "Coal India Ltd",
    "Mazagon Dock Shipbuilders", "Airports Authority of India",
    "Border Roads Organisation", "Central Public Works Department",
    "Northern Railway", "Haryana State Industrial Corp",
    "Punjab State Power Corp", "Delhi Metro Rail Corp",
]

MAX_EMD = 50000  # from profile
# Buyer orgs for Mohali / Ludhiana profile bids
MOHALI_ORGS = [
    "Central Government Office Chandigarh", "Punjab State Board of Education",
    "Post Graduate Institute of Medical Sciences", "National Institute of Technology Jalandhar",
    "Punjab Police Housing Corporation", "Food Corporation of India Punjab",
    "Chandigarh Housing Board", "PGIMER Chandigarh",
]

SAFETY_DISTRICTS_NEAR_LUDHIANA = [
    ("Ludhiana", "Punjab"), ("Jalandhar", "Punjab"), ("Patiala", "Punjab"),
    ("Amritsar", "Punjab"), ("Mohali", "Punjab"), ("Chandigarh area", "Punjab"),
    ("Gurdaspur", "Punjab"), ("Hoshiarpur", "Punjab"),
    ("Ambala", "Haryana"), ("Panipat", "Haryana"),
]

def random_end(days_min: int, days_max: int) -> str:
    """Random closing datetime between days_min and days_max from snapshot."""
    days = random.uniform(days_min, days_max)
    dt = SNAPSHOT_DATE + timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def make_bid(n: int, title: str, district: str, state: str, emd: float,
             days_min: int, days_max: int) -> dict:
    qty = random.randint(1, 100)
    org = random.choice(BUYER_ORGS)
    end = random_end(days_min, days_max)
    return {
        "bid_number": f"SAMPLE/{n:04d}",
        "title": title,
        "quantity": str(qty),
        "consignee_state": state,
        "consignee_district": district,
        "buyer_org": org,
        "emd_inr": round(emd, 2),
        "end_datetime": end,
        "doc_url": f"https://gem.gov.in/bids/SAMPLE{n:04d}",
        "data_source": "SAMPLE",
    }


def generate() -> list[dict]:
    random.seed(42)
    bids: list[dict] = []
    n = 1

    # ── TIER 1: Excellent matches – near district, low EMD, plenty of time ──────
    # Scores ~80-95 (Bid verdicts)
    for family in ["timing_belts", "pulleys", "valves"]:
        for title in ITEM_TITLES[family][:4]:
            d, s = random.choice(NEAR_DISTRICTS[:10])  # closest districts
            emd = random.uniform(8000, 35000)           # well within 50k limit
            bids.append(make_bid(n, title, d, s, emd, 7, 21))
            n += 1

    # ── TIER 2: Good matches – slightly farther, moderate EMD, normal timing ────
    # Scores ~60-80 (Bid/Maybe)
    for family in ["timing_belts", "pulleys", "valves"]:
        for title in ITEM_TITLES[family][2:5]:
            d, s = random.choice(NEAR_DISTRICTS[8:])   # 150-240 km districts
            emd = random.uniform(30000, 48000)          # near the 50k limit
            bids.append(make_bid(n, title, d, s, emd, 3, 7))  # short window
            n += 1

    # ── TIER 3: Marginal matches – 200-240 km, EMD 40-48k, closing 2-4 days ────
    # Scores ~45-65 (Maybe verdicts)
    for family in ["timing_belts", "valves"]:
        for title in ITEM_TITLES[family][:3]:
            d, s = random.choice([
                ("Yamunanagar", "Haryana"), ("Muzaffarnagar", "Uttar Pradesh"),
                ("Dehradun", "Uttarakhand"), ("Haridwar", "Uttarakhand"),
                ("Patiala", "Punjab"), ("Mohali", "Punjab"),
            ])
            emd = random.uniform(38000, 48000)
            bids.append(make_bid(n, title, d, s, emd, 2, 4))
            n += 1

    # ── TIER 4: EMD near-miss – 5–25% above limit, near district ────────────────
    # Scores ~35-55 (Skip or low Maybe – EMD component = 0)
    for title in ITEM_TITLES["valves"][:4]:
        d, s = random.choice(NEAR_DISTRICTS[:10])
        over_pct = random.uniform(0.05, 0.25)
        emd = 50000 * (1 + over_pct)
        bids.append(make_bid(n, title, d, s, emd, 5, 14))
        n += 1

    # ── TIER 5: Distance near-miss – 260-310 km (just beyond 250 km radius) ─────
    for title in ITEM_TITLES["timing_belts"][:3]:
        d, s = random.choice([
            ("Bathinda", "Punjab"), ("Moga", "Punjab"),
            ("Amritsar", "Punjab"), ("Shimla", "Himachal Pradesh"),
        ])
        emd = random.uniform(15000, 40000)
        bids.append(make_bid(n, title, d, s, emd, 4, 12))
        n += 1

    # ── TIER 6: Far bids – 500+ km (mostly hidden/skip) ─────────────────────────
    for family in ["timing_belts", "valves"]:
        for title in ITEM_TITLES[family][:3]:
            d, s = random.choice(FAR_DISTRICTS)
            emd = random.uniform(10000, 40000)
            bids.append(make_bid(n, title, d, s, emd, 3, 14))
            n += 1

    # ── Adjacent items (need include_adjacent=True to appear) ────────────────────
    for title in ITEM_TITLES["adjacent"]:
        for _ in range(2):
            d, s = random.choice(NEAR_DISTRICTS)
            emd = random.uniform(5000, 40000)
            bids.append(make_bid(n, title, d, s, emd, 3, 14))
            n += 1

    # ── Urgency variety – closing very soon ──────────────────────────────────────
    for title in [ITEM_TITLES["valves"][0], ITEM_TITLES["timing_belts"][0],
                  ITEM_TITLES["pulleys"][0]]:
        d, s = random.choice(NEAR_DISTRICTS[:8])
        emd = random.uniform(20000, 45000)
        bids.append(make_bid(n, title, d, s, emd, 0, 1))   # closing <24h
        n += 1

    for title in ITEM_TITLES["pulleys"][:3]:
        d, s = random.choice(NEAR_DISTRICTS)
        emd = random.uniform(15000, 38000)
        bids.append(make_bid(n, title, d, s, emd, 1, 2))   # closing 1-2 days
        n += 1

    # ── Long-horizon bids – plenty of time but variable on other dimensions ──────
    for family in ["timing_belts", "pulleys", "valves"]:
        for title in ITEM_TITLES[family][:2]:
            d, s = random.choice(NEAR_DISTRICTS)
            emd = random.uniform(5000, 50000)
            bids.append(make_bid(n, title, d, s, emd, 30, 60))  # 1-2 months
            n += 1

    # ── Unrelated items (always hidden – item score = 0) ─────────────────────────
    for title in ITEM_TITLES["unrelated"]:
        d, s = random.choice(NEAR_DISTRICTS)
        bids.append(make_bid(n, title, d, s, 10000, 3, 14))
        n += 1

    # ── Missing/null EMD ─────────────────────────────────────────────────────────
    for title in ITEM_TITLES["valves"][:2]:
        d, s = random.choice(NEAR_DISTRICTS[:8])
        row = make_bid(n, title, d, s, 0, 3, 10)
        row["emd_inr"] = ""   # simulate missing
        bids.append(row)
        n += 1

    # ── Very high EMD (well above limit) ─────────────────────────────────────────
    for title in ITEM_TITLES["timing_belts"][:2]:
        d, s = random.choice(NEAR_DISTRICTS)
        emd = random.uniform(120000, 400000)
        bids.append(make_bid(n, title, d, s, emd, 3, 14))
        n += 1

    # ── Unknown district (data quality) ──────────────────────────────────────────
    bids.append(make_bid(n, "Supply of Gate Valve", "Unknown District", "Haryana",
                         20000, 3, 10))
    n += 1

    # ── Already closed ────────────────────────────────────────────────────────────
    for title in ITEM_TITLES["valves"][:2]:
        d, s = random.choice(NEAR_DISTRICTS[:6])
        bids.append(make_bid(n, title, d, s, 20000, -10, -1))
        n += 1

    # ── Combined stretch: good item + good EMD + medium distance + short time ────
    # These produce ~55-70 (maybe) due to time penalty
    for title in [ITEM_TITLES["valves"][2], ITEM_TITLES["pulleys"][1]]:
        d, s = random.choice([("Rohtak", "Haryana"), ("Sonipat", "Haryana"),
                               ("Karnal", "Haryana")])
        emd = random.uniform(20000, 40000)
        bids.append(make_bid(n, title, d, s, emd, 1, 3))
        n += 1

    # ── Mohali office furniture profile bids ─────────────────────────────────────
    MOHALI_TITLES = {
        "office_chairs": [
            "Supply of Office Chair Revolving Type",
            "Procurement of Ergonomic Chair for Staff",
            "Executive Chair Supply for Admin Block",
            "Visitor Chair Supply for Reception Area",
        ],
        "office_furniture": [
            "Supply of Office Desk and Workstation",
            "Procurement of Computer Table for Lab",
            "Conference Table Supply for Meeting Room",
            "Writing Desk Supply for Library",
        ],
        "storage": [
            "Filing Cabinet Supply for Record Room",
            "Storage Rack Procurement for Warehouse",
            "Almirah Supply for Hostel Block",
        ],
    }
    MOHALI_NEAR = [
        ("Mohali", "Punjab"), ("Ludhiana", "Punjab"), ("Patiala", "Punjab"),
        ("Amritsar", "Punjab"), ("Ambala", "Haryana"), ("Rohtak", "Haryana"),
        ("New Delhi", "Delhi"),
    ]
    for family, titles in MOHALI_TITLES.items():
        for i, title in enumerate(titles):
            d, s = random.choice(MOHALI_NEAR)
            # Vary EMD across the full range to produce different scores
            emd = random.uniform(10000, 80000)
            days = random.choice([2, 5, 8, 14, 21, 30])
            bids.append(make_bid(n, title, d, s, emd, days - 1, days + 1))
            n += 1
    # Near-miss for Mohali
    for title in MOHALI_TITLES["office_chairs"][:2]:
        d, s = random.choice(MOHALI_NEAR)
        emd = 75000 * random.uniform(1.05, 1.20)
        bids.append(make_bid(n, title, d, s, emd, 3, 14))
        n += 1

    # ── Ludhiana safety equipment profile bids ────────────────────────────────────
    SAFETY_TITLES = {
        "helmets": [
            "Supply of Safety Helmet IS 2925 Compliant",
            "Procurement of Hard Hat for Construction Site",
            "Industrial Helmet Supply for Factory Workers",
        ],
        "safety_shoes": [
            "Supply of Safety Shoes Steel Toe Cap",
            "Procurement of Industrial Footwear for Workers",
            "Safety Boots Supply for Plant Maintenance Staff",
        ],
        "ppe_kits": [
            "Procurement of PPE Kit for COVID Safety",
            "Supply of Personal Protective Equipment Set",
            "Safety Kit for Industrial Workers Supply",
        ],
        "gloves": [
            "Supply of Safety Gloves Nitrile Type",
            "Industrial Hand Gloves Procurement",
        ],
        "safety_goggles": [
            "Supply of Safety Goggles Anti-Scratch",
            "Eye Protection Glasses for Laboratory",
        ],
    }
    LUDHIANA_NEAR = [
        ("Ludhiana", "Punjab"), ("Jalandhar", "Punjab"), ("Amritsar", "Punjab"),
        ("Patiala", "Punjab"), ("Mohali", "Punjab"), ("Ambala", "Haryana"),
        ("Panipat", "Haryana"), ("Rohtak", "Haryana"), ("New Delhi", "Delhi"),
        ("Meerut", "Uttar Pradesh"), ("Dehradun", "Uttarakhand"),
    ]
    for family, titles in SAFETY_TITLES.items():
        for title in titles:
            d, s = random.choice(LUDHIANA_NEAR)
            emd = random.uniform(15000, 95000)  # varied – some above 100k limit
            days = random.choice([1, 3, 5, 10, 14, 20, 35])
            bids.append(make_bid(n, title, d, s, emd, max(0, days - 1), days + 1))
            n += 1
    for title in [SAFETY_TITLES["helmets"][0], SAFETY_TITLES["ppe_kits"][0]]:
        d, s = random.choice(LUDHIANA_NEAR)
        bids.append(make_bid(n, title, d, s, 50000, 1, 2))
        n += 1
    for title in SAFETY_TITLES["safety_shoes"][:2]:
        d, s = random.choice([("Mumbai", "Maharashtra"), ("Ahmedabad", "Gujarat")])
        bids.append(make_bid(n, title, d, s, 40000, 3, 14))
        n += 1

    print(f"Generated {len(bids)} bids (bid_number SAMPLE/0001 … SAMPLE/{n-1:04d})")
    return bids



def write_csv(bids: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(bids)
    print(f"Written to {path}")


if __name__ == "__main__":
    bids = generate()
    write_csv(bids, OUTPUT)
    print("\nNOTE: All rows have data_source=SAMPLE. Run the app and look for the red SAMPLE DATA banner.")
    print("Replace data/bids.csv with your real GeM snapshot to use real data.")
