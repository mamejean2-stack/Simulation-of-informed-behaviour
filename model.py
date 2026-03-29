# model.py
# The city: grid of cells, fire spread, citizens, and the social network.

import mesa
import random
import math
import networkx as nx
from agent import Citizen


# ─────────────────────────────────────────────────────────────────────
# CELL
# ─────────────────────────────────────────────────────────────────────

class Cell:
    """One tile on the city grid."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

        # ── Fire ────────────────────────────────────────────────────
        # fire_state : "empty" | "burning" | "burnt"
        # burn_timer : steps remaining before this cell burns out
        # intensity  : 0.0 – 1.0 normalised from burn_timer, used by visuals
        self.fire_state = "empty"
        self.burn_timer = 0
        self.intensity  = 0.0

        # ── Passability ─────────────────────────────────────────────
        self.passable = True

        # ── Future stubs ────────────────────────────────────────────
        self.smoke_level = 0.0
        self.obstacle    = None
        self.agent_count = 0
        self.road_type   = "road"


# Cardinal wind vectors
WIND_VECTORS = {
    "N": ( 0,  1),
    "S": ( 0, -1),
    "E": ( 1,  0),
    "W": (-1,  0),
}


# ─────────────────────────────────────────────────────────────────────
# CITY MODEL
# ─────────────────────────────────────────────────────────────────────

class CityModel(mesa.Model):
    """
    The city simulation.
    Fire spreads via a cellular automaton; citizens move, share information,
    and try to escape across the grid border.
    """

    def __init__(
        self,
        width              = 20,
        height             = 20,
        population         = 100,
        group_distribution = None,
        fire_spread_chance = 0.30,
        fire_burn_duration = 8,
        wind_direction     = "E",
        wind_strength      = 0.20,
        vision_radius      = 3,
        media_alerts_on    = True,
    ):
        super().__init__()

        if group_distribution is None:
            group_distribution = {
                "north_district": 0.40,
                "south_district": 0.35,
                "city_centre":    0.25,
            }

        # ── Grid ────────────────────────────────────────────────────
        self.grid_width  = width
        self.grid_height = height

        # ── Fire parameters ─────────────────────────────────────────
        # Fire starts at a random position along a random edge.
        # Wind always blows inward from that edge so fire spreads into the city.
        edge = random.choice(["N", "S", "E", "W"])
        if edge == "N":
            ox, oy         = random.randrange(width), height - 1
            inward_wind    = "S"
        elif edge == "S":
            ox, oy         = random.randrange(width), 0
            inward_wind    = "N"
        elif edge == "E":
            ox, oy         = width - 1, random.randrange(height)
            inward_wind    = "W"
        else:  # W
            ox, oy         = 0, random.randrange(height)
            inward_wind    = "E"

        self.fire_origin        = (ox, oy)
        self.fire_position      = self.fire_origin
        self.fire_spread_chance = fire_spread_chance
        self.fire_burn_duration = fire_burn_duration

        # ── Wind ────────────────────────────────────────────────────
        # Direction is auto-set so fire always blows inward; strength is configurable.
        self.wind_direction = inward_wind
        self.wind_strength  = wind_strength

        # ── Citizen behaviour ────────────────────────────────────────
        self.vision_radius   = vision_radius
        self.media_alerts_on = media_alerts_on

        # ── Build cell grid ─────────────────────────────────────────
        self.cells = [
            [Cell(x, y) for y in range(height)]
            for x in range(width)
        ]

        # Light the starting fire
        ox, oy = self.fire_origin
        c = self.cells[ox][oy]
        c.fire_state = "burning"
        c.burn_timer = fire_burn_duration
        c.intensity  = 1.0

        # ── Social network (kept for future use) ────────────────────
        self.social_network = nx.Graph()

        # ── Citizens ────────────────────────────────────────────────
        self.schedule = mesa.time.RandomActivation(self)
        self._create_citizens(population, group_distribution)
        self._build_social_network()

        # Fast id → agent lookup used inside agent.step()
        self._agents_by_id = {a.unique_id: a for a in self.schedule.agents}

        # ── Data collection ─────────────────────────────────────────
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Informed"  : lambda m: m._count_informed(),
                "Evacuated" : lambda m: m._count_evacuated(),
                "Survivors" : lambda m: m._count_survivors(),
                "Dead"      : lambda m: m._count_dead(),
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # SETUP
    # ─────────────────────────────────────────────────────────────────

    def _create_citizens(self, population, group_distribution):
        """
        Distribute citizens across geographic zones.

        Zone layout (fire starts at (2, 2) — bottom-left area):
          north_district  →  y in [0 .. 6]   — closest to the fire
          city_centre     →  y in [7 .. 12]
          south_district  →  y in [13 .. 19] — furthest from the fire
        """
        zones = {
            "north_district": (0,  6),
            "city_centre":    (7,  12),
            "south_district": (13, 19),
        }
        agent_id = 0
        for group_name, fraction in group_distribution.items():
            count        = round(population * fraction)
            y_min, y_max = zones.get(group_name, (0, self.grid_height - 1))

            for _ in range(count):
                x = random.randrange(self.grid_width)
                y = random.randint(y_min, y_max)
                # Don't spawn on the ignition cell
                ox, oy = self.fire_origin
                if x == ox and y == oy:
                    x = (x + 2) % self.grid_width

                citizen = Citizen(agent_id, self, group_name, (x, y))
                self.schedule.add(citizen)
                self.social_network.add_node(agent_id)
                agent_id += 1

    def _build_social_network(self):
        """Connect citizens within 4 cells of each other."""
        agents = self.schedule.agents
        for i, a in enumerate(agents):
            for b in agents[i + 1:]:
                ax, ay = a.position
                bx, by = b.position
                if math.sqrt((ax - bx) ** 2 + (ay - by) ** 2) <= 4:
                    self.social_network.add_edge(a.unique_id, b.unique_id)

    # ─────────────────────────────────────────────────────────────────
    # FIRE SPREAD — cellular automaton
    # ─────────────────────────────────────────────────────────────────

    def _spread_fire(self):
        """
        Each burning cell:
          1. Ages by one step (burns out when timer hits 0 → becomes ash)
          2. Tries to ignite each of its 4 cardinal neighbours

        Wind biases spread: following-wind neighbours get +wind_strength,
        against-wind neighbours get a small penalty.
        """
        wind_vec  = WIND_VECTORS[self.wind_direction]
        anti_wind = (-wind_vec[0], -wind_vec[1])
        new_ignitions = []

        for x in range(self.grid_width):
            for y in range(self.grid_height):
                cell = self.cells[x][y]
                if cell.fire_state != "burning":
                    continue

                # Age the cell
                cell.burn_timer -= 1
                if cell.burn_timer <= 0:
                    cell.fire_state = "burnt"
                    cell.intensity  = 0.0
                    continue

                cell.intensity = cell.burn_timer / self.fire_burn_duration

                # Attempt to spread to each cardinal neighbour
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < self.grid_width and
                            0 <= ny < self.grid_height):
                        continue
                    if self.cells[nx][ny].fire_state != "empty":
                        continue

                    chance = self.fire_spread_chance
                    if (dx, dy) == wind_vec:
                        chance += self.wind_strength
                    elif (dx, dy) == anti_wind:
                        chance -= self.wind_strength * 0.5
                    chance = max(0.0, min(1.0, chance))

                    if random.random() < chance:
                        new_ignitions.append((nx, ny))

        for nx, ny in new_ignitions:
            if self.cells[nx][ny].fire_state == "empty":
                self.cells[nx][ny].fire_state = "burning"
                self.cells[nx][ny].burn_timer = self.fire_burn_duration
                self.cells[nx][ny].intensity  = 1.0

    # ─────────────────────────────────────────────────────────────────
    # STEP
    # ─────────────────────────────────────────────────────────────────

    def step(self):
        """
        Each tick:
        1. Citizens react to the current fire state (move, scan, talk)
        2. Fire spreads and ages
        3. Data is recorded
        """
        self.schedule.step()
        self._spread_fire()
        self.datacollector.collect(self)

    # ─────────────────────────────────────────────────────────────────
    # COUNTING HELPERS
    # ─────────────────────────────────────────────────────────────────

    def _count_informed(self):
        """Living citizens whose belief confidence has crossed the awareness threshold."""
        return sum(1 for a in self.schedule.agents
                   if a.belief_confidence >= 0.3 and a.alive)

    def _count_evacuated(self):
        return sum(1 for a in self.schedule.agents if a.evacuated)

    def _count_survivors(self):
        return sum(1 for a in self.schedule.agents if a.evacuated and a.alive)

    def _count_alive(self):
        return sum(1 for a in self.schedule.agents if a.alive)

    def _count_dead(self):
        return sum(1 for a in self.schedule.agents if not a.alive)
