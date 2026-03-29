# run.py
# This is the START BUTTON of your simulation.
# Run this file to launch the city alert simulation.

from model import CityModel
import pandas as pd

# ─────────────────────────────────────────────
# SIMULATION SETTINGS
# Easy to change these numbers to test different scenarios
# ─────────────────────────────────────────────

CITY_WIDTH      = 20    # Width of the city grid (in cells)
CITY_HEIGHT     = 20    # Height of the city grid (in cells)
POPULATION      = 100   # Total number of citizens
NUMBER_OF_STEPS = 20    # How many time steps the simulation runs

# ─────────────────────────────────────────────
# POPULATION GROUPS
# Each group has a name and a percentage of the total population
# All percentages must add up to exactly 1.0
# ─────────────────────────────────────────────

GROUP_DISTRIBUTION = {
    "north_district" : 0.40,   # 40 citizens — closest to the fire
    "south_district" : 0.35,   # 35 citizens — furthest from the fire
    "city_centre"    : 0.25,   # 25 citizens — mixed proximity
}

# ─────────────────────────────────────────────
# FIRE & ENVIRONMENT SETTINGS
# ─────────────────────────────────────────────

FIRE_SPREAD_CHANCE  = 0.30   # base probability of fire spreading per step
FIRE_BURN_DURATION  = 8      # steps a cell burns before becoming ash
WIND_DIRECTION      = "E"    # N | S | E | W
WIND_STRENGTH       = 0.20   # extra spread probability in wind direction
VISION_RADIUS       = 3      # how many cells away a citizen can see fire
MEDIA_ALERTS_ON     = True   # random noisy broadcast about fire location

# ─────────────────────────────────────────────
# LAUNCH THE SIMULATION
# ─────────────────────────────────────────────

print("=" * 55)
print("       CITY ALERT — EVACUATION SIMULATION")
print("=" * 55)
print(f"  City size   : {CITY_WIDTH} x {CITY_HEIGHT}")
print(f"  Population  : {POPULATION} citizens")
print(f"  Groups      : {list(GROUP_DISTRIBUTION.keys())}")
print(f"  Steps       : {NUMBER_OF_STEPS}")
print(f"  Spread      : {FIRE_SPREAD_CHANCE}  Burn: {FIRE_BURN_DURATION}  Wind: {WIND_DIRECTION} {WIND_STRENGTH}")
print(f"  Vision      : {VISION_RADIUS}  Media alerts: {MEDIA_ALERTS_ON}")
print("=" * 55)

# Create the city
city = CityModel(
    width              = CITY_WIDTH,
    height             = CITY_HEIGHT,
    population         = POPULATION,
    group_distribution = GROUP_DISTRIBUTION,
    fire_spread_chance = FIRE_SPREAD_CHANCE,
    fire_burn_duration = FIRE_BURN_DURATION,
    wind_direction     = WIND_DIRECTION,
    wind_strength      = WIND_STRENGTH,
    vision_radius      = VISION_RADIUS,
    media_alerts_on    = MEDIA_ALERTS_ON,
)

# ─────────────────────────────────────────────
# RUN THE SIMULATION STEP BY STEP
# ─────────────────────────────────────────────

for step in range(NUMBER_OF_STEPS):
    print(f"\n--- Step {step + 1} ---")
    city.step()

    # Print a live summary after each step
    informed  = city._count_informed()
    evacuated = city._count_evacuated()
    survivors = city._count_survivors()
    dead      = city._count_dead()

    print(f"  Informed   : {informed} / {POPULATION}")
    print(f"  Evacuated  : {evacuated} / {POPULATION}")
    print(f"  Survivors  : {survivors} / {evacuated if evacuated > 0 else 1}")
    print(f"  Dead       : {dead}")

# ─────────────────────────────────────────────
# FINAL RESULTS
# ─────────────────────────────────────────────

print("\n" + "=" * 55)
print("              FINAL RESULTS")
print("=" * 55)

# Break down results by group
agents = city.schedule.agents

for group_name in GROUP_DISTRIBUTION.keys():
    group_agents    = [a for a in agents if a.group == group_name]
    total           = len(group_agents)
    evacuated_group = [a for a in group_agents if a.evacuated]
    survivors_group = [a for a in group_agents if a.alive and a.evacuated]
    safe_dir        = [a for a in evacuated_group if a.escape_direction == "safe"]
    danger_dir      = [a for a in evacuated_group if a.escape_direction == "dangerous"]

    print(f"\n  Group : {group_name.upper()}")
    print(f"    Total citizens     : {total}")
    print(f"    Evacuated          : {len(evacuated_group)}")
    print(f"    Ran safe direction : {len(safe_dir)}")
    print(f"    Ran toward fire    : {len(danger_dir)}")
    print(f"    Survivors          : {len(survivors_group)}")

# ─────────────────────────────────────────────
# SAVE DATA TO A CSV FILE
# This file can be opened in a spreadsheet or used for graphs later
# ─────────────────────────────────────────────

print("\n" + "=" * 55)
print("  Saving simulation data...")

# Collect the step-by-step data recorded during the simulation
step_data = city.datacollector.get_model_vars_dataframe()
step_data.to_csv("simulation_results.csv")
print("  OK Data saved to: simulation_results.csv")

# Save individual citizen data
citizen_data = []
for agent in agents:
    citizen_data.append({
        "id"               : agent.unique_id,
        "group"            : agent.group,
        "belief_confidence": round(agent.belief_confidence, 2),
        "evacuated"        : agent.evacuated,
        "escape_origin"    : agent.escape_origin,
        "escape_direction" : agent.escape_direction,
        "alive"            : agent.alive,
    })

citizen_df = pd.DataFrame(citizen_data)
citizen_df.to_csv("citizen_results.csv", index=False)
print("  OK Citizen data saved to: citizen_results.csv")
print("=" * 55)
print("\n  Simulation complete!")