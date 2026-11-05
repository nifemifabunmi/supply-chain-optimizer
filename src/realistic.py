# detailed explanation
# an illustration on a real map. it is NOT company data.
#
# what is real:
#   - the 25 customer regions are the 25 largest US metro areas, and demand is
#     proportional to their 2020 population. the populations come from the US
#     census figures listed at
#     https://www.currentresults.com/Weather-Extremes/US/largest-cities-list-2020.php
#   - distances are great-circle (haversine) distances between city centres.
#     the coordinates are approximate city centres, good to about 0.01 degrees.
#
# what is made up (assumptions, like everywhere else in this project):
#   - the 8 candidate warehouse hubs are well-known logistics cities that
#     we picked. no real company is implied.
#   - every hub gets the same capacity and the same opening cost, so the
#     answer is driven by geography and not by invented differences.
#   - one unit of demand = 100,000 people. the shipping rate and the opening
#     cost are in made-up dollars. only the SHAPE of the answer means anything.
#
# the point: the same models that ran on random networks also run on a
# network with real geography, and the chosen hubs can be sanity-checked by eye.
import math

from src.data import build_instance

# (metro name, latitude, longitude, 2020 population)
METROS = [
    ("New York", 40.71, -74.01, 20_140_470),
    ("Los Angeles", 34.05, -118.24, 13_200_998),
    ("Chicago", 41.88, -87.63, 9_618_502),
    ("Dallas", 32.78, -96.80, 7_637_387),
    ("Houston", 29.76, -95.37, 7_122_240),
    ("Washington", 38.91, -77.04, 6_385_162),
    ("Philadelphia", 39.95, -75.17, 6_245_051),
    ("Miami", 25.76, -80.19, 6_138_333),
    ("Atlanta", 33.75, -84.39, 6_089_815),
    ("Boston", 42.36, -71.06, 4_941_632),
    ("Phoenix", 33.45, -112.07, 4_845_832),
    ("San Francisco", 37.77, -122.42, 4_749_008),
    ("Riverside", 33.95, -117.40, 4_599_839),
    ("Detroit", 42.33, -83.05, 4_392_041),
    ("Seattle", 47.61, -122.33, 4_018_762),
    ("Minneapolis", 44.98, -93.27, 3_690_261),
    ("San Diego", 32.72, -117.16, 3_298_634),
    ("Tampa", 27.95, -82.46, 3_175_275),
    ("Denver", 39.74, -104.99, 2_963_821),
    ("Baltimore", 39.29, -76.61, 2_844_510),
    ("St. Louis", 38.63, -90.20, 2_820_253),
    ("Orlando", 28.54, -81.38, 2_673_376),
    ("Charlotte", 35.23, -80.84, 2_660_329),
    ("San Antonio", 29.42, -98.49, 2_558_143),
    ("Portland", 45.52, -122.68, 2_512_859),
]

# (hub name, latitude, longitude). chosen by us as plausible hub cities.
HUBS = [
    ("Reno", 39.53, -119.81),
    ("Phoenix hub", 33.45, -112.07),
    ("Dallas hub", 32.78, -96.80),
    ("Chicago hub", 41.88, -87.63),
    ("Memphis", 35.15, -90.05),
    ("Atlanta hub", 33.75, -84.39),
    ("Columbus", 39.96, -83.00),
    ("Harrisburg", 40.27, -76.88),
]

EARTH_RADIUS_KM = 6371.0
PEOPLE_PER_UNIT = 100_000


# great-circle distance in km between two (lat, lon) points in degrees.
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# build the real-map instance. capacity_share is each hub's capacity as a
# share of total demand (8 hubs at 0.25 gives 2x spare capacity overall).
# rate and fixed_cost are assumptions in made-up dollars.
def build_realistic_instance(rate=0.01, capacity_share=0.25, fixed_cost=1500.0):
    demand = {name: pop / PEOPLE_PER_UNIT for name, _, _, pop in METROS}
    total = sum(demand.values())

    # positions are stored as (longitude, latitude) so they plot as (x, y).
    reg_pos = {name: (lon, lat) for name, lat, lon, _ in METROS}
    wh_pos = {name: (lon, lat) for name, lat, lon in HUBS}

    dist = {
        (h, m): haversine_km(wh_pos[h][1], wh_pos[h][0], reg_pos[m][1], reg_pos[m][0])
        for h in wh_pos
        for m in reg_pos
    }
    return build_instance(
        wh_pos=wh_pos,
        reg_pos=reg_pos,
        demand=demand,
        capacity={h: capacity_share * total for h in wh_pos},
        fixed_cost={h: fixed_cost for h in wh_pos},
        rate=rate,
        dist=dist,
    )
