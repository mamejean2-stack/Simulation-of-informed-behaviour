# model.py
# Describes the city: the grid, the citizens, the fire, and how it all connects

import mesa
import random
import math
import networkx as nx
from agent import Citizen


# ─────────────────────────────────────────────
# CELL — One square tile of the city grid
# This is where future features like smoke and
# obstacles will live
# ─────────────────────────────────────────────

class Cell:
    """
    Represents one square tile on the city grid.
    Every feature that affects movement or visibility
    will be stored here in the future.
    """

    def __init__(self, x, y):
        # Position of this cell on the grid
        self.x = x
        self.y = y

        # --- PASSABILITY ---
        # Can agents walk through this cell?
        # True = open, False = blocked (wall, rubble, closed road)
        self.passable = True

        # --- FUTURE: SMOKE ---
        # How much smoke is in this cell? (0.0 = clear, 1.0 = deadly)
        # A high smoke level will reduce movement chance in a later stage
        self.smoke_level = 0.0

        # --- FUTURE: OBSTACLES ---
        # What physical object is blocking this cell, if any?
        # Examples: "building", "rubble", "fence", None
        self.obstacle = None

        # --- FUTURE: CROWD DENSITY ---
        # How many agents are currently in this cell?
        # Too many agents in one cell will slow movement down
        self.agent_count = 0

        # --- FUTURE: ROAD TYPE ---
        # What kind of path is this cell?
        # Examples: "road", "alley", "park", "building_interior"
        self.road_type = "road"

    def movement_cost(self):
        """
        Returns a value from 0.0 to 1.0 representing how easy
        it is to move through this cell.

        1.0 = completely free
        0.0 = completely impassable

        This method is ready to be expanded later with:
        - Smoke reducing movement chance
        - Crowd slowing agents down
        - Road type affecting speed
        """
        if not self.passable:
            return 0.0

        cost = 1.0

        # FUTURE: subtract from cost based on smoke
        # cost -= self.smoke_level * 0.5

        # FUTURE: subtract from cost based on crowd density
        # cost -= min(0.3, self.agent_count * 0.05)

        return max(0.0, cost)


# ─────────────────────────────────────────────
# CITY MODEL — The world where everything happens
# ─────────────────────────────────────────────

class CityModel(mesa.Model):
    """
    The city simulation.
    Contains the grid, the citizens, the fire, and the social network.
    """

    def __init__(self, width, height, population, group_distribution):
        """
        width              : number of columns in the city grid
        height             : number of rows in the city grid
        population         : total number of citizens
        group_distribution : a dictionary defining groups and their percentages
                             Example: {"north": 0.4, "south": 0.35, "centre": 0.25}
        """
        super().__init__()

        # City grid dimensions
        self.grid_width = width
        self.grid_height = height

        # The fire starts at a fixed position (top-left area of the city)
        # This can be changed or made random later
        self.fire_position = (2, 2)

        # ── BUILD THE CELL GRID ──────────────────────────────
        # Creates a 2D list of Cell objects
        # Access any cell with: self.cells[x][y]
        self.cells = [
            [Cell(x, y) for y in range(height)]
            for x in range(width)
        ]

        # ── BUILD THE SOCIAL NETWORK ─────────────────────────
        # Each citizen will be a node in this network
        # Connections (edges) represent who can talk to whom
        self.social_network = nx.Graph()

        # ── CREATE CITIZENS ──────────────────────────────────
        self.schedule = mesa.time.RandomActivation(self)
        self._create_citizens(population, group_distribution)

        # ── CONNECT CITIZENS IN THE SOCIAL NETWORK ───────────
        self._build_social_network()

        # ── AGENT LOOKUP TABLE ───────────────────────────────
        # Lets agents quickly find a neighbour by unique_id
        self._agents_by_id = {a.unique_id: a for a in self.schedule.agents}

        # ── DATA COLLECTION ──────────────────────────────────
        # Records informed / evacuated / survivor counts each step
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Informed"  : lambda m: m._count_informed(),
                "Evacuated" : lambda m: m._count_evacuated(),
                "Survivors" : lambda m: m._count_survivors(),
            }
        )

    # ─────────────────────────────────────────────
    # CITIZEN CREATION
    # ─────────────────────────────────────────────

    def _create_citizens(self, population, group_distribution):
        """
        Spawn citizens and distribute them across geographic zones.

        District layout (fire is at position (2, 2)):
          north_district  →  y in [0 .. 6]   — closest to the fire
          city_centre     →  y in [7 .. 12]  — mixed proximity
          south_district  →  y in [13 .. 19] — furthest from the fire
        """
        zones = {
            "north_district" : (0,  6),
            "city_centre"    : (7,  12),
            "south_district" : (13, 19),
        }

        agent_id = 0
        for group_name, fraction in group_distribution.items():
            count     = round(population * fraction)
            y_min, y_max = zones.get(group_name, (0, self.grid_height - 1))

            for _ in range(count):
                x = random.randrange(self.grid_width)
                y = random.randint(y_min, y_max)

                citizen = Citizen(agent_id, self, group_name, (x, y))

                # Citizens very close to the fire already have some awareness
                fire_x, fire_y = self.fire_position
                dist = math.sqrt((x - fire_x) ** 2 + (y - fire_y) ** 2)
                if dist < 3:
                    citizen.receive_information(0.5)

                self.schedule.add(citizen)
                self.social_network.add_node(agent_id)
                agent_id += 1

    # ─────────────────────────────────────────────
    # SOCIAL NETWORK
    # ─────────────────────────────────────────────

    def _build_social_network(self):
        """
        Connect citizens who live within 4 grid-cells of each other.
        These connections are how information spreads peer-to-peer.
        """
        agents = self.schedule.agents
        for i, a in enumerate(agents):
            for b in agents[i + 1:]:
                ax, ay = a.position
                bx, by = b.position
                dist = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                if dist <= 4:
                    self.social_network.add_edge(a.unique_id, b.unique_id)

    # ─────────────────────────────────────────────
    # SIMULATION STEP
    # ─────────────────────────────────────────────

    def step(self):
        """
        Advance the simulation by one time step:
        1. Fire broadcasts information to nearby citizens
        2. Every citizen takes their turn (spread info, maybe evacuate)
        3. Data collector records the new state
        """
        fire_x, fire_y = self.fire_position

        # Citizens within radius 5 of the fire gain direct awareness
        for agent in self.schedule.agents:
            if not agent.evacuated:
                ax, ay = agent.position
                dist = math.sqrt((ax - fire_x) ** 2 + (ay - fire_y) ** 2)
                if dist <= 5:
                    agent.receive_information(0.25)

        self.schedule.step()
        self.datacollector.collect(self)

    # ─────────────────────────────────────────────
    # COUNTING HELPERS  (used by run.py and visualize.py)
    # ─────────────────────────────────────────────

    def _count_informed(self):
        """Citizens with information_level above the evacuation threshold."""
        return sum(1 for a in self.schedule.agents if a.information_level >= 0.3)

    def _count_evacuated(self):
        return sum(1 for a in self.schedule.agents if a.evacuated)

    def _count_survivors(self):
        return sum(1 for a in self.schedule.agents if a.evacuated and a.alive)