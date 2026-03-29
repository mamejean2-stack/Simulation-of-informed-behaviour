# model.py
# Describes the city: the grid, the citizens, the fire, and how it all connects

import mesa
import random
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

        # ── DATA COLLECTION ──────────────────────────────────
        # Records simulation da