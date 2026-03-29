# agent.py
# Describes each individual citizen in the city simulation

import mesa
import random
import math

class Citizen(mesa.Agent):
    """
    A single citizen living in the city.
    Each citizen has a position, belongs to a group,
    receives information about the fire, and tries to evacuate.
    Their survival depends on which direction they run.
    """

    def __init__(self, unique_id, model, group, position):
        super().__init__(unique_id, model)

        # Which district this citizen lives in
        self.group = group

        # Their (x, y) position on the city grid
        self.position = position

        # Where they were when they decided to evacuate
        # This is empty until they actually start evacuating
        self.escape_origin = None

        # How informed is this citizen about the fire? (0.0 to 1.0)
        self.information_level = 0.0

        # Has this citizen decided to evacuate?
        self.evacuated = False

        # Is this citizen still alive?
        self.alive = True

        # Their survival chance (0.0 to 1.0), calculated when they evacuate
        self.survival_chance = None

        # The direction they ran: "safe" or "dangerous"
        self.escape_direction = None

    def receive_information(self, amount):
        """
        Receive information from a neighbour or media.
        More informed citizens are more likely to run the right way.
        """
        self.information_level = min(1.0, self.information_level + amount)

    def calculate_escape_direction(self):
        """
        Decide which way the citizen runs when evacuating.

        - A well informed citizen (high information_level) is more likely
          to run AWAY from the fire = "safe" direction.
        - A poorly informed citizen may accidentally run TOWARD the fire
          = "dangerous" direction.

        Returns "safe" or "dangerous"
        """
        fire_x, fire_y = self.model.fire_position
        citizen_x, citizen_y = self.position

        # Calculate how far this citizen is from the fire
        distance_from_fire = math.sqrt(
            (citizen_x - fire_x) ** 2 + (citizen_y - fire_y) ** 2
        )

        # The more informed you are, the higher the chance you go the right way
        # Example: information_level = 0.9 → 90% chance of going safe direction
        chance_of_correct_direction = self.information_level

        if random.random() < chance_of_correct_direction:
            return "safe"
        else:
            return "dangerous"

    def calculate_survival_chance(self):
        """
        Calculate the probability of surviving based on:
        - Which direction the citizen ran
        - How far they were from the fire when they evacuated
        """
        fire_x, fire_y = self.model.fire_position
        origin_x, origin_y = self.escape_origin

        # Distance from the fire at the moment of evacuation
        distance = math.sqrt(
            (origin_x - fire_x) ** 2 + (origin_y - fire_y) ** 2
        )

        # Normalise distance: the further away, the better (max distance on grid)
        max_distance = math.sqrt(
            self.model.grid_width ** 2 + self.model.grid_height ** 2
        )
        distance_bonus = distance / max_distance  # value between 0.0 and 1.0

        # Running the safe way gives a big survival bonus
        if self.escape_direction == "safe":