# agent.py
import mesa
import random
import math

BELIEF_DECAY     = 0.95   # confidence multiplier per step without new info
BELIEF_THRESHOLD = 0.02   # below this, forget entirely


class Citizen(mesa.Agent):

    def __init__(self, unique_id, model, group, position):
        super().__init__(unique_id, model)

        self.group    = group
        self.position = position

        self.fire_belief       = None   # estimated (x, y) of fire
        self.belief_confidence = 0.0   # 0.0 → 1.0

        self.alive     = True
        self.evacuated = False

        # CSV / visualiser
        self.escape_origin    = None
        self.escape_direction = None

        # animation
        self.prev_position = position
        self._info_event   = None   # "fire" | "peer" | "media" | None

    @property
    def information_level(self):
        return self.belief_confidence

    # ── Information ──────────────────────────────────────────────────

    def _decay_belief(self):
        """Confidence fades each step without fresh observations."""
        if self.belief_confidence <= 0:
            return
        self.belief_confidence *= BELIEF_DECAY
        if self.belief_confidence < BELIEF_THRESHOLD:
            self.belief_confidence = 0.0
            self.fire_belief       = None

    def _scan_for_fire(self):
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
                    dist = max(1, abs(dx) + abs(dy))
                    self._merge_belief((float(nx), float(ny)), 1.0 / dist)

    def _merge_belief(self, pos, confidence):
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
        self.belief_confidence = min(1.0, total * 0.55)

    def _exchange_info(self):
        x, y = self.position
        for other in self.model._agents_by_id.values():
            if (other is self or not other.alive or other.evacuated
                    or other.position != (x, y)
                    or other.fire_belief is None):
                continue
            if self.fire_belief is None:
                self.fire_belief       = other.fire_belief
                self.belief_confidence = other.belief_confidence * 0.8
            else:
                wa, wb = self.belief_confidence, other.belief_confidence
                total  = wa + wb
                self.fire_belief = (
                    (self.fire_belief[0] * wa + other.fire_belief[0] * wb) / total,
                    (self.fire_belief[1] * wa + other.fire_belief[1] * wb) / total,
                )
                self.belief_confidence = min(1.0, (wa + wb) * 0.5 + 0.1)

    def _receive_media_alert(self):
        """Noisy broadcast using current fire centroid, not origin."""
        if not self.model.media_alerts_on:
            return
        if random.random() < 0.05:
            cx, cy    = self.model._fire_centroid()
            noisy_pos = (cx + random.gauss(0, 2.0),
                         cy + random.gauss(0, 2.0))
            self._merge_belief(noisy_pos, 0.3)

    # ── Movement ─────────────────────────────────────────────────────

    def _choose_direction(self):
        if self.fire_belief is None or self.belief_confidence < 0.05:
            return random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
        x, y   = self.position
        bx, by = self.fire_belief
        away_x, away_y = x - bx, y - by
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        scores     = [dx * away_x + dy * away_y for dx, dy in directions]
        if random.random() < self.belief_confidence:
            return directions[scores.index(max(scores))]
        return random.choice(directions)

    def _moving_away_from_fire(self, dx, dy):
        if self.fire_belief is None:
            return False
        x, y   = self.position
        bx, by = self.fire_belief
        return (dx * (x - bx) + dy * (y - by)) > 0

    def _try_move(self, dx, dy):
        x, y   = self.position
        nx, ny = x + dx, y + dy

        # Off grid → evacuate
        if not (0 <= nx < self.model.grid_width and
                0 <= ny < self.model.grid_height):
            # Decrement occupancy at departure cell
            self.model._occupancy[(x, y)] = max(
                0, self.model._occupancy.get((x, y), 1) - 1
            )
            self.evacuated        = True
            self.escape_origin    = self.position
            self.escape_direction = (
                "safe" if self._moving_away_from_fire(dx, dy) else "dangerous"
            )
            return True

        # Blocked by fire
        if self.model.cells[nx][ny].fire_state == "burning":
            return False

        # Blocked by crowd
        if self.model._occupancy.get((nx, ny), 0) >= self.model.MAX_CELL_CAPACITY:
            return False

        # Move — update occupancy in real time so later agents see accurate counts
        self.model._occupancy[(x, y)]  = max(0, self.model._occupancy.get((x, y), 1) - 1)
        self.model._occupancy[(nx, ny)] = self.model._occupancy.get((nx, ny), 0) + 1
        self.position = (nx, ny)
        return True

    # ── Step ─────────────────────────────────────────────────────────

    def step(self):
        if not self.alive or self.evacuated:
            return

        self.prev_position = self.position
        self._info_event   = None

        x, y = self.position
        if self.model.cells[x][y].fire_state == "burning":
            self.alive = False
            self.model._occupancy[(x, y)] = max(
                0, self.model._occupancy.get((x, y), 1) - 1
            )
            return

        # Decay first, then gather — so fresh info always wins
        self._decay_belief()

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

        preferred = self._choose_direction()
        fallbacks = [d for d in [(0, 1), (0, -1), (1, 0), (-1, 0)] if d != preferred]
        random.shuffle(fallbacks)
        for direction in [preferred] + fallbacks:
            if self._try_move(*direction):
                break
