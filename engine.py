

from copy import deepcopy
from contextlib import closing
from database import get_connection


# ---------- LOAD DATA FROM SQLITE ----------

def load_data():
    with closing(get_connection()) as conn:
        routes = [
            {
                "name": row["id"],
                "passengers": row["passengers"],
                "capacity": row["capacity"],
                "delay": row["delay"]
            }
            for row in conn.execute(
                "SELECT * FROM routes ORDER BY id"
            )
        ]

        buses = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM buses WHERE available = 1 ORDER BY id"
            )
        ]

        compatibility = {}
        for row in conn.execute(
            "SELECT bus_id, route_id FROM bus_routes"
        ):
            compatibility.setdefault(row["bus_id"], []).append(
                row["route_id"]
            )

    spare_buses = [
        {
            "id": bus["id"],
            "capacity": bus["capacity"],
            "compatible_routes": compatibility.get(bus["id"], [])
        }
        for bus in buses
    ]

    return routes, spare_buses


# ---------- PHASE A: PREDICT ----------

def predict(routes):
    alerts = []

    for route in routes:
        shortage = max(
            0, route["passengers"] - route["capacity"]
        )

        if shortage:
            alerts.append(
                f'{route["name"]}: {shortage} passengers need seats'
            )

        if route["delay"] > 5:
            alerts.append(
                f'{route["name"]}: {route["delay"]} minutes late'
            )

    return alerts


# ---------- PHASE B: OPTIMIZE ----------

def optimize(routes, spare_buses):
    routes = deepcopy(routes)
    spare_buses = deepcopy(spare_buses)
    actions = []

    for route in routes:
        route["extra_capacity"] = 0
        route["unused_capacity"] = 0
        route["assigned_buses"] = []

    # Buses with fewer compatible routes get priority.
    spare_buses.sort(
        key=lambda bus: len(bus["compatible_routes"])
    )

    for bus in spare_buses:
        candidates = [
            route for route in routes
            if route["passengers"] >
               route["capacity"] + route["extra_capacity"]
            and route["name"] in bus["compatible_routes"]
        ]

        if not candidates:
            actions.append(
                f'{bus["id"]}: No assignment needed'
            )
            continue

        target = max(
            candidates,
            key=lambda route: (
                route["passengers"]
                - route["capacity"]
                - route["extra_capacity"]
            )
        )

        shortage = (
            target["passengers"]
            - target["capacity"]
            - target["extra_capacity"]
        )

        seats_used = min(shortage, bus["capacity"])
        unused_seats = bus["capacity"] - seats_used

        target["extra_capacity"] += seats_used
        target["unused_capacity"] += unused_seats
        target["assigned_buses"].append(bus["id"])

        # This is a simulation assumption, not real traffic prediction.
        old_delay = target["delay"]
        target["delay"] = max(0, old_delay - 3)

        actions.append(
            f'{bus["id"]} assigned to {target["name"]}'
        )
        actions.append(
            f'  Seats used: {seats_used}, unused: {unused_seats}'
        )
        actions.append(
            f'  Delay: {old_delay} -> {target["delay"]} min (simulated)'
        )

    return routes, actions


# ---------- PHASE C: PROVE ----------

def measure(routes):
    demand = sum(route["passengers"] for route in routes)

    total_capacity = sum(
        route["capacity"] + route.get("extra_capacity", 0)
        for route in routes
    )

    served = sum(
        min(
            route["passengers"],
            route["capacity"] + route.get("extra_capacity", 0)
        )
        for route in routes
    )

    return {
        "total_demand": demand,
        "passengers_served": served,
        "unmet_demand": demand - served,
        "seat_utilization_pct": round(
            served / total_capacity * 100, 1
        ) if total_capacity else 0,
        "average_delay_min": round(
            sum(route["delay"] for route in routes) / len(routes), 1
        ) if routes else 0
    }


# ---------- MAIN PROGRAM ----------

def main():
    routes, spare_buses = load_data()

    if not routes:
        print("No routes found. Add route data to the database first.")
        return

    print("\n========== ROUTEPULSE ==========")
    print("Data source: SQLite database")

    print("\n=== PHASE A: PREDICT ===")
    alerts = predict(routes)

    if alerts:
        for alert in alerts:
            print("ALERT:", alert)
    else:
        print("No problems detected.")

    baseline = measure(routes)

    print("\n=== PHASE B: OPTIMIZE ===")
    optimized_routes, actions = optimize(routes, spare_buses)

    for action in actions:
        print(action)

    print("\n=== ROUTE-WISE RESULTS ===")

    for route in optimized_routes:
        capacity = route["capacity"] + route["extra_capacity"]
        served = min(route["passengers"], capacity)

        print(f'\nRoute: {route["name"]}')
        print(f'  Passengers: {route["passengers"]}')
        print(f'  Effective capacity: {capacity}')
        print(f'  Passengers served: {served}')
        print(f'  Unmet demand: {route["passengers"] - served}')
        print(f'  Delay: {route["delay"]} minutes')
        print(f'  Assigned buses: {route["assigned_buses"]}')
        print(f'  Unused assigned seats: {route["unused_capacity"]}')

    after = measure(optimized_routes)

    print("\n=== PHASE C: PROVE ===")
    print("BEFORE:", baseline)
    print("AFTER: ", after)

    print(
        "Unmet demand reduced by:",
        baseline["unmet_demand"] - after["unmet_demand"]
    )

    print(
        "Average delay reduced by:",
        round(
            baseline["average_delay_min"] - after["average_delay_min"],
            1
        ),
        "minutes (simulated)"
    )

    print("\n=== FEASIBILITY CHECK ===")

    if after["unmet_demand"] == 0:
        print("PASS: All passenger demand can be accommodated.")
    else:
        print(
            "WARNING:",
            after["unmet_demand"],
            "passengers still need seats."
        )


if __name__ == "__main__":
    main()
