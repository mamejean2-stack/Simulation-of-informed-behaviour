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
NUMBER_OF_STEPS = 10    # How many time steps the simulation runs

# ─────────────────────────────────────────────
# POPULATION GROUPS
# Each group has a name and a percentage of the total population
# All percentages must add up to exactly 1.0
#
# FUTURE: each group will also have:
# - information_gain_rate  (how fast they receive info)
# - trust_in_strangers     (how much they trust other groups)
# - panic_threshold        (how much info they need before evacuating)
# ─────────────────────────────────────────────

GROUP_DISTRIBUTION = {
    "north_district" : 0.40,   # 40 citizens — closest to the fire
    "south_district" : 0.35,   # 35 citizens — furthest from the fire
    "city_centre"    : 0.25,   # 25 citizens — mixed proximity
}

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
print("=" * 55)

# Create the city
city = CityModel(
    width=CITY_WIDTH,
    height=CITY_HEIGHT,
    population=POPULATION,
    group_distribution=GROUP_DISTRIBUTION
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

    print(f"  Informed   : {informed} / {POPULATION}")
    print(f"  Evacuated  : {evacuated} / {POPULATION}")
    print(f"  Survivors  : {survivors} / {evacuated if evacuated > 0 else 1}")

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
print("  ✅ Data saved to: simulation_results.csv")

# Save individual citizen data
citizen_data = []
for agent in agents:
    citizen_data.append({
        "id"               : agent.unique_id,
        "group"            : agent.group,
        "information_level": round(agent.information_level, 2),
        "evacuated"        : agent.evacuated,
        "escape_origin"    : agent.escape_origin,
        "escape_direction" : agent.escape_direction,
        "survival_chance"  : agent.survival_chance,
        "alive"            : agent.alive,
    })

citizen_df = pd.DataFrame(citizen_data)
citizen_df.to_csv("citizen_results.csv", index=False)
print("  ✅ Citizen data saved to: citizen_results.csv")
print("=" * 55)
print("\n  Simulation complete! 🏙️")
```

---

## ✅ Run your simulation!

In your terminal (with **(venv)** active):
```
cd ~/mysimulation/city_alert
python3 run.py