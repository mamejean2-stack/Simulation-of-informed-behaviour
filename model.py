# model.py
import mesa
import random
import math
from agent import Citizen

MAX_CELL_CAPACITY = 3   # max citizens allowed on one cell at a time
# (also set on model instance so agent.py can reference self.model.MAX_CELL_CAPACITY)

WIND_VECTORS = {
    "N": ( 0,  1),
    "S": ( 0, -1),
    "E": ( 1,  0),
    "W": (-1,  0),
}


class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.fire_state = "empty"   # "empty" | "burning" | "burnt"
        self.burn_timer = 0
        self.intensity  = 0.0
        self.passable   = True
        # future stubs
        self.smoke_level = 0.0
        self.obstacle    = None
        self.road_type   = "road"


class CityModel(mesa.Model):

    def __init__(
        self,
        width              = 30,
        height             = 30,
        population         = 60,
        group_distribution = None,
        fire_spread_chance = 0.30,
        fire_burn_duration = 8,
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

        self.grid_width  = width
        self.grid_height = height

        # ── Fire: random edge start, wind always blows inward ────────
        edge = random.choice(["N", "S", "E", "W"])
        if edge == "N":
            ox, oy      = random.randrange(width), height - 1
            inward_wind = "S"
        elif edge == "S":
            ox, oy      = random.randrange(width), 0
            inward_wind = "N"
        elif edge == "E":
            ox, oy      = width - 1, random.randrange(height)
            inward_wind = "W"
        else:
            ox, oy      = 0, random.randrange(height)
            inward_wind = "E"

        self.fire_origin        = (ox, oy)
        self.fire_position      = self.fire_origin
        self.fire_spread_chance = fire_spread_chance
        self.fire_burn_duration = fire_burn_duration
        self.wind_direction     = inward_wind
        self.wind_strength      = wind_strength

        self.vision_radius    = vision_radius
        self.media_alerts_on  = media_alerts_on
        self.MAX_CELL_CAPACITY = MAX_CELL_CAPACITY

        # ── Cell grid ────────────────────────────────────────────────
        self.cells = [
            [Cell(x, y) for y in range(height)]
            for x in range(width)
        ]
        c = self.cells[ox][oy]
        c.fire_state = "burning"
        c.burn_timer = fire_burn_duration
        c.intensity  = 1.0

        # ── Citizens ─────────────────────────────────────────────────
        self.schedule      = mesa.time.RandomActivation(self)
        self._occupancy    = {}   # (x,y) -> current count, updated during step
        self._create_citizens(population, group_distribution)
        self._agents_by_id = {a.unique_id: a for a in self.schedule.agents}

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Informed"  : lambda m: m._count_informed(),
                "Evacuated" : lambda m: m._count_evacuated(),
                "Alive"     : lambda m: m._count_alive(),
                "Dead"      : lambda m: m._count_dead(),
            }
        )

    # ── Setup ────────────────────────────────────────────────────────

    def _create_citizens(self, population, group_distribution):
        zones = {
            "north_district": (0,                   self.grid_height // 3),
            "city_centre":    (self.grid_height // 3, 2 * self.grid_height // 3),
            "south_district": (2 * self.grid_height // 3, self.grid_height - 1),
        }
        agent_id = 0
        for group_name, fraction in group_distribution.items():
            count        = round(population * fraction)
            y_min, y_max = zones.get(group_name, (0, self.grid_height - 1))
            for _ in range(count):
                x = random.randrange(self.grid_width)
                y = random.randint(y_min, y_max)
                ox, oy = self.fire_origin
                if x == ox and y == oy:
                    x = (x + 2) % self.grid_width
                citizen = Citizen(agent_id, self, group_name, (x, y))
                self.schedule.add(citizen)
                self._occupancy[(x, y)] = self._occupancy.get((x, y), 0) + 1
                agent_id += 1

    # ── Fire centroid (used by media alerts) ─────────────────────────

    def _fire_centroid(self):
        """Current centre-of-mass of all burning cells."""
        pts = [(x, y)
               for x in range(self.grid_width)
               for y in range(self.grid_height)
               if self.cells[x][y].fire_state == "burning"]
        if not pts:
            return self.fire_origin
        return (sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts))

    # ── Fire spread ──────────────────────────────────────────────────

    def _spread_fire(self):
        wind_vec  = WIND_VECTORS[self.wind_direction]
        anti_wind = (-wind_vec[0], -wind_vec[1])
        new_ignitions = []

        for x in range(self.grid_width):
            for y in range(self.grid_height):
                cell = self.cells[x][y]
                if cell.fire_state != "burning":
                    continue
                cell.burn_timer -= 1
                if cell.burn_timer <= 0:
                    cell.fire_state = "burnt"
                    cell.intensity  = 0.0
                    continue
                cell.intensity = cell.burn_timer / self.fire_burn_duration

                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < self.grid_width and 0 <= ny < self.grid_height):
                        continue
                    if self.cells[nx][ny].fire_state != "empty":
                        continue
                    chance = self.fire_spread_chance
                    if (dx, dy) == wind_vec:
                        chance += self.wind_strength
                    elif (dx, dy) == anti_wind:
                        chance -= self.wind_strength * 0.5
                    if random.random() < max(0.0, min(1.0, chance)):
                        new_ignitions.append((nx, ny))

        for nx, ny in new_ignitions:
            if self.cells[nx][ny].fire_state == "empty":
                self.cells[nx][ny].fire_state = "burning"
                self.cells[nx][ny].burn_timer = self.fire_burn_duration
                self.cells[nx][ny].intensity  = 1.0

    # ── Step ─────────────────────────────────────────────────────────

    def step(self):
        # Rebuild occupancy map at the start of each tick so agents
        # can check real-time capacity as they move (RandomActivation
        # updates the dict in _try_move as each agent moves).
        self._occupancy = {}
        for a in self.schedule.agents:
            if a.alive and not a.evacuated:
                pos = a.position
                self._occupancy[pos] = self._occupancy.get(pos, 0) + 1

        self.schedule.step()
        self._spread_fire()
        self.datacollector.collect(self)

    # ── Counting ─────────────────────────────────────────────────────

    def _count_informed(self):
        return sum(1 for a in self.schedule.agents
                   if a.belief_confidence >= 0.3 and a.alive)

    def _count_evacuated(self):
        return sum(1 for a in self.schedule.agents if a.evacuated)

    def _count_alive(self):
        return sum(1 for a in self.schedule.agents if a.alive)

    def _count_dead(self):
        return sum(1 for a in self.schedule.agents if not a.alive)

    # kept for CSV compat
    def _count_survivors(self):
        return sum(1 for a in self.schedule.agents if a.evacuated and a.alive)
