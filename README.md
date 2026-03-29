# Simulation of Informed Behaviour

A multi-agent simulation exploring how **information spreads through a population during a fire emergency** — and how that affects who survives.

Built with Python and [Mesa](https://mesa.readthedocs.io/), the agent-based modelling framework.

---

## What it does

A city of 100 citizens is placed on a 20×20 grid. A fire breaks out. Citizens who are informed flee in the right direction. Citizens who aren't may run straight toward it.

The core question: **does it matter how quickly people learn about a danger?**

Each citizen has an `information_level` between 0.0 and 1.0. Information spreads two ways:

- **Proximity to fire** — citizens nearby gain awareness automatically each step
- **Social network** — citizens pass information to connected neighbours

Once a citizen's information level crosses a threshold (0.3), they evacuate. Their escape direction is probabilistic — higher information means higher odds of going the right way.

---

## Project structure

```
agent.py        — The Citizen agent: information, evacuation, survival logic
model.py        — The city: grid, social network, fire, scheduling
run.py          — CLI simulation runner, exports CSV results
visualize.py    — Interactive animated visualisation
```

---

## How to run

**Install dependencies** (Python 3.9+ recommended):

```bash
pip install "mesa<3.0" pandas networkx matplotlib
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

The left panel shows the city map. Agent colour reflects information level:

| Colour | Meaning |
|--------|---------|
| Purple | Uninformed |
| White  | Partially informed |
| Orange | Highly informed |
| `^` triangle | Evacuated — safe direction |
| `v` triangle | Evacuated — toward fire |
| `X` | Did not survive |
| Star | Fire location |

The right panel plots informed, evacuated, and survivor counts over time.

---

## Output

After running `run.py`, two CSV files are created:

- `simulation_results.csv` — step-by-step population counts (informed, evacuated, survivors)
- `citizen_results.csv` — per-citizen data (group, info level, escape direction, survival)

---

## Configuration

All parameters are at the top of `run.py` and `visualize.py`:

```python
CITY_WIDTH      = 20
CITY_HEIGHT     = 20
POPULATION      = 100
NUMBER_OF_STEPS = 10

GROUP_DISTRIBUTION = {
    "north_district" : 0.40,   # closest to the fire
    "south_district" : 0.35,   # furthest from the fire
    "city_centre"    : 0.25,
}
```

Try increasing `NUMBER_OF_STEPS` or shifting the group distribution to see how outcomes change.

---

## What's next

The `Cell` class in `model.py` already has stubs for planned features:

- Smoke spread and visibility reduction
- Physical obstacles and road types
- Crowd density slowing movement
- Pathfinding instead of probabilistic direction choice
- Per-group traits (panic threshold, trust in strangers, information gain rate)
