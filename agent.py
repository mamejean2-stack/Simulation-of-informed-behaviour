# agent.py
# Each citizen navigates the city, builds a belief about the fire,
# and tries to evacuate by reaching the grid border.

import mesa
import random
import math


class Citizen(mesa.Agent):
    """
    A single citizen. Movement and evacuation decisions are driven by
    a continuously updated belief about where the fire is.
    """

    def __init__(self, unique_id, model, group, position):
        super().__init__(unique_id, model)

        self.group    = group
        self.position = position   # (x, y) — current cell

        # ── Belief about fire location ───────────────────────────────
        # fire_belief       : estimated (x, y) of the fire — None until
        #                     the citizen has seen or heard something
        # belief_confidence : 0.0 (clueless) → 1.0 (certain)
        self.fire_belief       = None
        self.belief_confidence = 0.0

        # ── Status ───────────────────────────────────────────────────
        self.alive     = True
        self.evacuated = False

        # ── For CSV output / visualiser compatibility ────────────────
        self.escape_origin    = None   # cell they were on when they left
        self.escape_direction = None   # "safe" | "dangerous"

        # ── For smooth animation in the GUI ──────────────────────────
        # prev_position : where this agent was at the start of the last step
        # _info_event   : what caused a confidence gain this step
        #                 None | "fire" | "peer" | "media"
        self.prev_position = position
        self._info_event   = None

    # ── Convenience alias (visualiser reads this) ────────────────────
    @property
    def information_level(self):
        return self.belief_confidence

    # ────────────────────────────────────────────────────────────────
    # INFORMATION
    # ────────────────────────────────────────────────────────────────

    def _scan_for_fire(self):
        """
        Look at every cell within vision_radius (Manhattan distance).
        Each burning cell seen updates the belief; closer = higher confidence.
        """
        x, y = self.position
        r    = self.model.vision_radius

        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) + abs(dy) > r:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.model.grid_width and
                        0 <= ny < self.model.grid_height):
                    continue
                if self.model.cells[nx][ny].fire_state == "burning":
                    dist       = max(1, abs(dx) + abs(dy))
                    confidence = 1.0 / dist
                    self._merge_belief((float(nx), float(ny)), confidence)

    def _merge_belief(self, pos, confidence):
        """
        Weighted-average merge of a new observation into the current belief.
        Higher-confidence observations pull the estimate further.
        """
        if self.fire_belief is None:
            self.fire_belief       = pos
            self.belief_confidence = min(1.0, confidence)
            return

        w_old = self.belief_confidence
        w_new = confidence
        total = w_old + w_new
        self.fire_belief = (
            (self.fire_belief[0] * w_old + pos[0] * w_new) / total,
            (self.fire_belief[1] * w_old + pos[1] * w_new) / total,
        )
        # Merging two sources increases confidence, but with diminishing returns
        self.belief_confidence = min(1.0, total * 0.55)

    def _exchange_info(self):
        """
        Talk to every other citizen on the same cell.
        Each pair merges their beliefs; shared knowledge boosts confidence.
        """
        x, y = self.position
        for other in self.model._agents_by_id.values():
            if (other is self
                    or not other.alive
                    or other.evacuated
                    or other.position != (x, y)
                    or other.fire_belief is None):
                continue
            if self.fire_belief is None:
                self.fire_belief       = other.fire_belief
                self.belief_confidence = other.belief_confidence * 0.8
            else:
                wa    = self.belief_confidence
                wb    = other.belief_confidence
                total = wa + wb
                self.fire_belief = (
                    (self.fire_belief[0] * wa + other.fire_belief[0] * wb) / total,
                    (self.fire_belief[1] * wa + other.fire_belief[1] * wb) / total,
                )
                # Talking to someone who agrees raises confidence slightly
                self.belief_confidence = min(1.0, (wa + wb) * 0.5 + 0.1)

    def _receive_media_alert(self):
        """
        5 % chance per step of a noisy broadcast about the fire origin.
        Adds Gaussian noise to the real position, so it helps but isn't perfect.
        Only active when model.media_alerts_on is True.
        """
        if not self.model.media_alerts_on:
            return
        if random.random() < 0.05:
            ox, oy    = self.model.fire_origin
            noisy_pos = (ox + random.gauss(0, 2.0),
                         oy + random.gauss(0, 2.0))
            self._merge_belief(noisy_pos, 0.3)

    # ────────────────────────────────────────────────────────────────
    # MOVEMENT
    # ────────────────────────────────────────────────────────────────

    def _choose_direction(self):
        """
        Pick one of the four cardinal directions to move in.
        With probability = belief_confidence, take the direction
        most away from the believed fire; otherwise move randomly.
        """
        if self.fire_belief is None or self.belief_confidence < 0.05:
            return random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])

        x, y   = self.position
        bx, by = self.fire_belief
        # Vector pointing away from the estimated fire
        away_x = x - bx
        away_y = y - by

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        scores     = [dx * away_x + dy * away_y for dx, dy in directions]

        if random.random() < self.belief_confidence:
            return directions[scores.index(max(scores))]
        return random.choice(directions)

    def _moving_away_from_fire(self, dx, dy):
        """Return True if the step (dx, dy) moves away from the believed fire."""
        if self.fire_belief is None:
            return False
        x, y   = self.position
        bx, by = self.fire_belief
        return (dx * (x - bx) + dy * (y - by)) > 0

    def _try_move(self, dx, dy):
        """
        Attempt one step in direction (dx, dy).
        - Off the grid       → evacuated, record direction quality
        - Burning cell ahead → blocked, return False so caller can try another
        - Empty cell         → move, return True
        """
        x, y   = self.position
        nx, ny = x + dx, y + dy

        # Stepping off the grid evacuates the citizen
        if not (0 <= nx < self.model.grid_width and
                0 <= ny < self.model.grid_height):
            self.evacuated        = True
            self.escape_origin    = self.position
            self.escape_direction = (
                "safe" if self._moving_away_from_fire(dx, dy) else "dangerous"
            )
            return True

        # Won't walk into fire
        if self.model.cells[nx][ny].fire_state == "burning":
            return False

        self.position = (nx, ny)
        return True

    # ────────────────────────────────────────────────────────────────
    # STEP
    # ────────────────────────────────────────────────────────────────

    def step(self):
        if not self.alive or self.evacuated:
            return

        # Snapshot position before any movement (used by GUI interpolation)
        self.prev_position = self.position
        self._info_event   = None

        # Die if fire has reached this cell
        x, y = self.position
        if self.model.cells[x][y].fire_state == "burning":
            self.alive = False
            return

        # Gather information — track which source caused a meaningful gain
        conf_before = self.belief_confidence
        self._scan_for_fire()
        if self.belief_confidence > conf_before + 0.05:
            self._info_event = "fire"

        conf_before = self.belief_confidence
        self._exchange_info()
        if self._info_event is None and self.belief_confidence > conf_before + 0.05:
            self._info_event = "peer"

        conf_before = self.belief_confidence
        self._receive_media_alert()
        if self._info_event is None and self.belief_confidence > conf_before + 0.05:
            self._info_event = "media"

        # Move — try preferred direction first, then others in random order
        preferred = self._choose_direction()
        fallbacks = [(dx, dy) for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
                     if (dx, dy) != preferred]
        random.shuffle(fallbacks)

        for direction in [preferred] + fallbacks:
            if self._try_move(*direction):
                break
