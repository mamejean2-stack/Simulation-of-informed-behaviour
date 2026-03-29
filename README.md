# Simulation of Informed Behaviour

A multi-agent simulation exploring how **information spreads through a population during a fire emergency** — and how that affects who survives.

Built with Python and [Mesa](https://mesa.readthedocs.io/), the agent-based modelling framework.

---

## What it does

A city of citizens is placed on a grid. A fire breaks out at a random edge and spreads inward. Citizens who are informed flee in the right direction. Citizens who aren't may run straight toward it.

The core question: **does it matter how quickly people learn about a danger?**

Each citizen holds a `fire_belief` (estimated fire location) and a `belief_confidence` between 0.0 and 1.0. Information reaches citizens three ways:

- **Direct observation** — citizens within `vision_radius` cells of a burning cell gain awareness automatically each step
- **Peer exchange** — citizens on the same cell share belief estimates, weighted by confidence
- **Media alerts** — a 5% per-step chance of receiving a noisy broadcast of the fire's current centroid

Belief decays each step without fresh input. Once confidence crosses 0.3, a citizen evacuates. Their escape direction is probabilistic — higher confidence means a stronger bias toward moving away from the fire.

---

## Fire mechanics

The fire starts at a random grid edge and spreads each step. Wind always blows inward from the origin edge, boosting spread probability in the downwind direction and reducing it upwind. Each burning cell has a burn timer; when it expires the cell becomes ash and can no longer harm or block movement.

| Parameter | Default | Effect |
|-----------|---------|--------|
| `fire_spread_chance` | 0.30 | Base probability of igniting a neighbour each step |
| `fire_burn_duration` | 8 | Steps a cell burns before becoming ash |
| `wind_strength` | 0.20 | Added to spread chance in wind direction, halved against it |
| `vision_radius` | 3 | How many cells away a citizen can see fire |

---

## Project structure

```
agent.py        — The Citizen agent: belief system, evacuation, survival logic
model.py        — The city: grid, fire spread, wind, scheduling
run.py          — CLI simulation runner, exports CSV results
visualize.py    — Interactive animated visualisation
```

---

## How to run

**Install dependencies** (Python 3.9+ recommended):

```bash
pip install "mesa<3.0" pandas matplotlib
```

**Run the simulation (text output + CSV export):**

```bash
python run.py
```

**Run the interactive visualisation:**

```bash
python visualize.py
```

Use the **Play** and **Next** buttons to step through the simulation and watch information spread across the city in real time.

---

## Visualisation

The left panel shows the city map. Agent colour reflects belief confidence:

| Colour | Meaning |
|--------|---------|
| Purple | Uninformed (confidence ≈ 0) |
| White  | Partially informed |
| Orange | Highly confident |
| `^` triangle | Evacuated — moved away from fire |
| `v` triangle | Evacuated — moved toward fire |
| `X` | Did not survive |
| Star | Fire location |

The right panel plots informed, evacuated, and survivor counts over time.

---

## Output

After running `run.py`, two CSV files are created:

- `simulation_results.csv` — step-by-step population counts (informed, evacuated, alive, dead)
- `citizen_results.csv` — per-citizen data (group, belief confidence, escape direction, survival)

---

## Configuration

All parameters are at the top of `run.py` and `visualize.py`:

```python
CITY_WIDTH      = 20
CITY_HEIGHT     = 20
POPULATION      = 100
NUMBER_OF_STEPS = 20

GROUP_DISTRIBUTION = {
    "north_district" : 0.40,   # closest to the fire origin edge
    "south_district" : 0.35,   # furthest from the fire
    "city_centre"    : 0.25,
}

FIRE_SPREAD_CHANCE  = 0.30   # base ignition probability per step
FIRE_BURN_DURATION  = 8      # steps before a cell turns to ash
WIND_STRENGTH       = 0.20   # spread boost in wind direction
VISION_RADIUS       = 3      # cells a citizen can see
MEDIA_ALERTS_ON     = True   # noisy broadcast about fire centroid
```

Try increasing `NUMBER_OF_STEPS`, raising `fire_spread_chance`, or shifting the group distribution to see how outcomes change.

---

## What's next

The `Cell` class in `model.py` already has stubs for planned features:

- Smoke spread and visibility reduction
- Physical obstacles and road types
- Crowd density slowing movement
- Pathfinding instead of probabilistic direction choice
- Per-group traits (panic threshold, trust in strangers, information gain rate)
