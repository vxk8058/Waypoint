"""Fictional merchants per city. Names are invented so seeded Nessie data never
impersonates a real business. Addresses/geocodes are Waypoint-generated filler
for Nessie's merchant schema (Nessie-only fields)."""

CITIES = {
    "Richardson": {"state": "TX", "zip": "75080", "lat": 32.9857, "lng": -96.7502,
                   "streets": ["Campbell Rd", "Arapaho Rd", "Coit Rd", "Synergy Park Blvd", "Waterview Pkwy"]},
    "Denton": {"state": "TX", "zip": "76201", "lat": 33.2148, "lng": -97.1331,
               "streets": ["Hickory St", "Fry St", "Oak St", "Eagle Dr", "Carroll Blvd"]},
    "College Station": {"state": "TX", "zip": "77840", "lat": 30.6280, "lng": -96.3344,
                        "streets": ["University Dr", "Texas Ave", "George Bush Dr", "Wellborn Rd", "Holleman Dr"]},
    "Austin": {"state": "TX", "zip": "78705", "lat": 30.2849, "lng": -97.7341,
               "streets": ["Guadalupe St", "Rio Grande St", "San Antonio St", "Dean Keeton St", "Speedway"]},
}

# city -> category -> merchant names
MERCHANTS = {
    "Richardson": {
        "groceries": ["Comet Corner Market", "Prairie Fresh Grocers"],
        "dining": ["Arapaho Noodle House", "Synergy Taco Co"],
        "coffee": ["Orbit Coffee Lab"],
        "transport": ["Campbell Fuel Stop", "RideLoop Rides"],
        "shopping": ["Galaxy Outlet Goods", "Waterview Home & Dorm"],
        "entertainment": ["Starlight Cinema 8"],
        "school_supplies": ["Comet Book Exchange"],
    },
    "Denton": {
        "groceries": ["Hickory Street Grocery", "Square Deal Market"],
        "dining": ["Fry Street Pizza Works", "Eagle Burger Shack"],
        "coffee": ["Little d Coffee Co"],
        "transport": ["Carroll Gas & Go", "RideLoop Rides"],
        "shopping": ["Denton Square Outfitters", "Courthouse Gadget Shop"],
        "entertainment": ["Oak Street Lanes"],
        "school_supplies": ["Mean Green Book Nook"],
    },
    "College Station": {
        "groceries": ["Brazos Valley Foods", "Northgate Pantry"],
        "dining": ["Wellborn BBQ Pit", "Holleman Ramen Bar"],
        "coffee": ["Aggieland Roasters"],
        "transport": ["Texas Ave Fuel Center", "RideLoop Rides"],
        "shopping": ["University Dr Outfitters", "Bryan Tech Depot"],
        "entertainment": ["Northgate Cinema Grill"],
        "school_supplies": ["Maroon Textbook Co"],
    },
    "Austin": {
        "groceries": ["Drag Street Grocery", "West Campus Market"],
        "dining": ["Guadalupe Taqueria", "Speedway Pho"],
        "coffee": ["Forty Acres Coffee"],
        "transport": ["Rio Grande Fuel", "RideLoop Rides"],
        "shopping": ["Dean Keeton Thrift", "Longhorn Tech Shop"],
        "entertainment": ["Hyde Park Arcade"],
        "school_supplies": ["Campus Co-op Books"],
    },
}


def merchant_key(city: str, name: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"m-{city.lower().replace(' ', '-')}-{slug}"
