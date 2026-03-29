# gui.py
import tkinter as tk
import math
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.colors as mcolors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from model import CityModel

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

GRID_SIZE      = 30     # city is GRID_SIZE × GRID_SIZE
DEFAULT_POP    = 60
FRAME_MS       = 150    # animation tick rate (ms) — controls smoothness

BG        = "#1a1a2e"
ACCENT    = "#0f3460"
GREEN     = "#2d6a4f"
BLUE      = "#1d3557"
FG        = "#e0e0e0"
FG_DIM    = "#888888"
HIGHLIGHT = "#52b788"

info_cmap = mcolors.LinearSegmentedColormap.from_list(
    "info_gradient", ["#7B2D8B", "#FFFFFF", "#FF8C00"]
)
fire_cmap = mcolors.LinearSegmentedColormap.from_list(
    "fire_core",
    [(0.0, "#7a0000"), (0.35, "#FF2200"), (0.65, "#FF7700"), (1.0, "#FFD700")]
)

# Pulse ring colours per info event type
RING_COLOUR = {"fire": "#FF6600", "peer": "#00CCDD", "media": "#AAAAAA"}


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("City Alert — Evacuation Simulation")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.city         = None
        self.current_step = 0
        self.is_playing   = False
        self.ani          = None
        self._anim_frame  = 0   # sub-frame counter within current sim step
        self.history      = {"step": [], "informed": [], "evacuated": [],
                             "alive": [], "dead": []}

        self._build_left_panel()
        self._build_right_panel()

    # ─────────────────────────────────────────
    # LEFT PANEL
    # ─────────────────────────────────────────

    def _build_left_panel(self):
        outer  = tk.Frame(self, bg=BG)
        outer.grid(row=0, column=0, sticky="ns")

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, width=220)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        left   = tk.Frame(canvas, bg=BG, padx=12, pady=12)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        left.bind("<Configure>", _resize)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # Title
        tk.Label(left, text="CITY ALERT", bg=BG, fg=FG,
                 font=("Helvetica", 15, "bold")).pack(anchor="w")
        tk.Label(left, text="Evacuation Simulation", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 10))

        # City
        self._section(left, "City")
        self.var_population = self._slider(left, "Population", 20, 200, DEFAULT_POP)
        self.var_steps      = self._slider(left, "Steps",       5, 100,  60)

        # Fire
        self._section(left, "Fire")
        self.var_spread     = self._fslider(left, "Spread chance",  0.05, 0.80, 0.30)
        self.var_burn       = self._slider( left, "Burn duration",  3,    20,   8)

        # Wind (direction is auto-set from fire start edge; only strength is exposed)
        self._section(left, "Wind")
        self.var_wind_str   = self._fslider(left, "Strength", 0.0, 0.5, 0.20)

        # Speed
        self._section(left, "Speed")
        self.var_interval   = self._slider(left, "ms / step", 300, 3000, 1000)

        # Buttons
        self.btn_run = tk.Button(
            left, text="Run Simulation", command=self._start,
            bg=GREEN, fg="white", activebackground=HIGHLIGHT,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=8, pady=7, cursor="hand2"
        )
        self.btn_run.pack(fill="x", pady=(12, 4))

        row_ctrl = tk.Frame(left, bg=BG)
        row_ctrl.pack(fill="x", pady=2)

        self.btn_play = tk.Button(
            row_ctrl, text="▶  Play", command=self._toggle_play,
            bg=BLUE, fg="white", activebackground="#457b9d",
            font=("Helvetica", 9), relief="flat",
            padx=6, pady=5, cursor="hand2", state="disabled"
        )
        self.btn_play.pack(side="left", expand=True, fill="x", padx=(0, 3))

        self.btn_next = tk.Button(
            row_ctrl, text="⏭  Next", command=self._next_step,
            bg=BLUE, fg="white", activebackground="#457b9d",
            font=("Helvetica", 9), relief="flat",
            padx=6, pady=5, cursor="hand2", state="disabled"
        )
        self.btn_next.pack(side="left", expand=True, fill="x")

        self.btn_reset = tk.Button(
            left, text="Reset", command=self._reset,
            bg=ACCENT, fg=FG_DIM, activebackground="#1a3a5c",
            font=("Helvetica", 9), relief="flat",
            padx=6, pady=5, cursor="hand2", state="disabled"
        )
        self.btn_reset.pack(fill="x", pady=(3, 12))

        self.lbl_step = tk.Label(left, text="Step: —", bg=BG, fg=FG_DIM,
                                  font=("Helvetica", 9))
        self.lbl_step.pack(anchor="w")

        # Stats
        self._section(left, "Live Stats")
        self.lbl_informed  = self._stat_row(left, "Informed",  "#FFD700")
        self.lbl_evacuated = self._stat_row(left, "Evacuated", HIGHLIGHT)
        self.lbl_alive     = self._stat_row(left, "Alive",     "#a8dadc")
        self.lbl_dead      = self._stat_row(left, "Dead",      "#e63946")

        # Legend
        self._section(left, "Legend")
        for marker, color, label in [
            ("o", info_cmap(0.02), "Uninformed"),
            ("o", info_cmap(1.0),  "Informed"),
            ("^", info_cmap(0.8),  "Evacuated — safe"),
            ("v", info_cmap(0.2),  "Evacuated — into fire"),
            ("X", "#222222",       "Dead"),
            ("s", "#FF7700",       "Fire"),
            ("s", "#1c1c1c",       "Burnt"),
            ("o", "#FF6600",       "Saw fire"),
            ("o", "#00CCDD",       "Heard from neighbour"),
            ("o", "#AAAAAA",       "Media alert"),
            ("line", "#a8dadc",    "Alive (graph)"),
        ]:
            r = tk.Frame(left, bg=BG)
            r.pack(anchor="w", pady=1)
            fig_i, ax_i = plt.subplots(figsize=(0.25, 0.25))
            fig_i.patch.set_alpha(0)
            if marker == "line":
                ax_i.plot([0, 1], [0.5, 0.5], color=color, lw=2)
            else:
                ax_i.scatter([0.5], [0.5], marker=marker, color=[color], s=50)
            ax_i.axis("off")
            ci = FigureCanvasTkAgg(fig_i, master=r)
            ci.draw()
            ci.get_tk_widget().pack(side="left")
            plt.close(fig_i)
            tk.Label(r, text=label, bg=BG, fg=FG,
                     font=("Helvetica", 8)).pack(side="left", padx=3)

        left.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"),
                         height=min(700, left.winfo_reqheight()))

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(8, 3))
        tk.Label(f, text=text.upper(), bg=BG, fg=FG_DIM,
                 font=("Helvetica", 7, "bold")).pack(anchor="w")
        tk.Frame(f, bg=ACCENT, height=1).pack(fill="x", pady=(1, 0))

    def _slider(self, parent, label, lo, hi, default):
        var = tk.IntVar(value=default)
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=("Helvetica", 8), width=16, anchor="w").pack(side="left")
        tk.Label(row, textvariable=var, bg=BG, fg=HIGHLIGHT,
                 font=("Helvetica", 8, "bold"), width=4).pack(side="right")
        tk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var,
                 bg=BG, fg=FG, troughcolor=ACCENT, highlightthickness=0,
                 showvalue=False, length=100).pack(side="left")
        return var

    def _fslider(self, parent, label, lo, hi, default):
        var     = tk.IntVar(value=int(default * 100))
        display = tk.StringVar(value=f"{default:.2f}")
        var.trace_add("write", lambda *_: display.set(f"{var.get()/100:.2f}"))
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=("Helvetica", 8), width=16, anchor="w").pack(side="left")
        tk.Label(row, textvariable=display, bg=BG, fg=HIGHLIGHT,
                 font=("Helvetica", 8, "bold"), width=4).pack(side="right")
        tk.Scale(row, from_=int(lo * 100), to=int(hi * 100), orient="horizontal",
                 variable=var, bg=BG, fg=FG, troughcolor=ACCENT,
                 highlightthickness=0, showvalue=False, length=100).pack(side="left")
        var.get_float = lambda: var.get() / 100
        return var

    def _wind_buttons(self, parent):
        var   = tk.StringVar(value="E")
        row   = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Direction", bg=BG, fg=FG,
                 font=("Helvetica", 8), width=16, anchor="w").pack(side="left")
        bf    = tk.Frame(row, bg=BG)
        bf.pack(side="left")
        btns  = {}
        for d in ("N", "E", "S", "W"):
            b = tk.Button(bf, text=d, width=2, relief="flat",
                          font=("Helvetica", 8, "bold"), cursor="hand2",
                          command=lambda _d=d: self._set_wind(_d, var, btns))
            b.pack(side="left", padx=1)
            btns[d] = b
        self._set_wind("E", var, btns)
        return var

    def _set_wind(self, d, var, btns):
        var.set(d)
        for k, b in btns.items():
            b.config(bg=HIGHLIGHT if k == d else BLUE,
                     fg=BG        if k == d else "white")

    def _stat_row(self, parent, label, colour=FG):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8), width=11, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="—", bg=BG, fg=colour,
                       font=("Helvetica", 8, "bold"))
        lbl.pack(side="left")
        return lbl

    # ─────────────────────────────────────────
    # RIGHT PANEL
    # ─────────────────────────────────────────

    def _build_right_panel(self):
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, padx=(0, 14), pady=14)

        self.fig = plt.figure(figsize=(13, 7))
        self.fig.patch.set_facecolor(BG)

        self.ax_map   = self.fig.add_axes([0.02, 0.06, 0.50, 0.90])
        self.ax_cbar  = self.fig.add_axes([0.545, 0.06, 0.013, 0.90])
        self.ax_graph = self.fig.add_axes([0.585, 0.06, 0.40, 0.90])

        sm = plt.cm.ScalarMappable(cmap=info_cmap, norm=plt.Normalize(0, 1))
        sm.set_array([])
        cbar = self.fig.colorbar(sm, cax=self.ax_cbar)
        cbar.set_label("Belief confidence", color=FG, fontsize=8, labelpad=5)
        cbar.ax.yaxis.set_tick_params(color=FG)
        cbar.set_ticks([0.0, 0.5, 1.0])
        cbar.set_ticklabels(["Low", "Med", "High"])
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=FG, fontsize=7)

        self._draw_map()
        self._draw_graph()

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()

        # Hover tooltips
        self._hover_ann     = None   # graph tooltip
        self._map_ann       = None   # map tooltip
        self._hover_vline   = []
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    # ─────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────

    def _agent_draw_pos(self, agent, t):
        """Interpolated display position for an agent at sub-frame t (0..1)."""
        if agent.prev_position is None or agent.evacuated:
            return agent.position
        px, py = agent.prev_position
        cx, cy = agent.position
        return (px + t * (cx - px), py + t * (cy - py))

    def _draw_map(self, t=1.0):
        ax = self.ax_map
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_xlim(-1, GRID_SIZE)
        ax.set_ylim(-1, GRID_SIZE)
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

        if not self.city:
            ax.set_title("Configure settings and press Run",
                         color=FG, fontsize=9, pad=8)
            return

        ax.set_title(
            f"Step {self.current_step} / {self.var_steps.get()}",
            color=FG, fontsize=9, pad=8
        )

        # ── Fire cells ───────────────────────────────────────────────
        burnt_x, burnt_y               = [], []
        burn_x,  burn_y,  burn_i       = [], [], []

        for x in range(self.city.grid_width):
            for y in range(self.city.grid_height):
                s = self.city.cells[x][y]
                if s.fire_state == "burnt":
                    burnt_x.append(x); burnt_y.append(y)
                elif s.fire_state == "burning":
                    burn_x.append(x); burn_y.append(y)
                    burn_i.append(s.intensity)

        if burnt_x:
            ax.scatter(burnt_x, burnt_y, c="#151515", s=160,
                       marker="s", zorder=1, linewidths=0)

        if burn_x:
            bi = np.array(burn_i)
            # Outer glow
            outer      = np.zeros((len(burn_x), 4))
            outer[:,0] = 1.0; outer[:,1] = 0.35
            outer[:,3] = bi * 0.10
            ax.scatter(burn_x, burn_y, c=outer,
                       s=bi * 800 + 150, marker="o", zorder=2, linewidths=0)
            # Mid corona
            mid        = np.zeros((len(burn_x), 4))
            mid[:,0]   = 1.0; mid[:,1] = 0.55
            mid[:,3]   = bi * 0.22
            ax.scatter(burn_x, burn_y, c=mid,
                       s=bi * 250 + 70, marker="o", zorder=3, linewidths=0)
            # Core
            ax.scatter(burn_x, burn_y, c=fire_cmap(bi),
                       s=95, marker="s", zorder=4, linewidths=0)

        # ── Agents ───────────────────────────────────────────────────
        # ── Fire origin marker ────────────────────────────────────────
        fox, foy = self.city.fire_origin
        ax.scatter(fox, foy, c="white", s=55, marker="+",
                   alpha=0.45, linewidths=1.5, zorder=5)

        # ── Wind direction indicator (top-left corner) ────────────────
        _wv = {"N": (0, 0.9), "S": (0, -0.9), "E": (0.9, 0), "W": (-0.9, 0)}
        _wu, _wv2 = _wv[self.city.wind_direction]
        ax.quiver([1.8], [GRID_SIZE - 2.2], [_wu], [_wv2],
                  color="white", alpha=0.55, scale=1, scale_units="xy",
                  angles="xy", width=0.004, headwidth=5, zorder=9)
        ax.text(1.8, GRID_SIZE - 3.4, f"wind {self.city.wind_direction}",
                color=FG_DIM, fontsize=6.5, ha="center")

        # ── Collect pulse ring data per event type ────────────────────
        ring_data = {"fire": ([], []), "peer": ([], []), "media": ([], [])}
        # Belief arrow data
        arr_x, arr_y, arr_u, arr_v = [], [], [], []

        for agent in self.city.schedule.agents:
            xd, yd = self._agent_draw_pos(agent, t)
            color  = info_cmap(agent.information_level)

            # Pulse ring (expanding ripple, fades over first half of step)
            if agent._info_event and t < 0.55:
                ring_data[agent._info_event][0].append(xd)
                ring_data[agent._info_event][1].append(yd)

            # Belief arrow pointing toward believed fire location
            if agent.alive and not agent.evacuated and agent.fire_belief is not None:
                bx, by = agent.fire_belief
                dx, dy = bx - xd, by - yd
                dist   = math.sqrt(dx * dx + dy * dy)
                if dist > 0.1:
                    scale = 0.38
                    arr_x.append(xd); arr_y.append(yd)
                    arr_u.append(dx / dist * scale)
                    arr_v.append(dy / dist * scale)

            # Agent marker
            if not agent.alive:
                ax.scatter(xd, yd, c=[[0.08, 0.08, 0.08]], s=60,
                           marker="X", edgecolors="white",
                           linewidths=0.4, zorder=7)
            elif agent.evacuated:
                m = "^" if agent.escape_direction == "safe" else "v"
                ax.scatter(xd, yd, c=[color], s=80,
                           marker=m, edgecolors="white",
                           linewidths=0.4, zorder=6)
            else:
                ax.scatter(xd, yd, c=[color], s=45,
                           marker="o", edgecolors="none", zorder=6)

        # Draw pulse rings (ripple effect: grows and fades)
        ring_alpha = max(0.0, (0.55 - t) / 0.55) * 0.55
        ring_size  = 90 + t * 500
        for event, (rxs, rys) in ring_data.items():
            if rxs:
                ax.scatter(rxs, rys, c=RING_COLOUR[event], s=ring_size,
                           alpha=ring_alpha, marker="o",
                           zorder=5, linewidths=0)

        # Draw belief arrows (stacking: overlapping arrows compound opacity)
        if arr_x:
            ax.quiver(arr_x, arr_y, arr_u, arr_v,
                      alpha=0.22, color="white",
                      scale=1, scale_units="xy", angles="xy",
                      width=0.0025, headwidth=5, headlength=5,
                      zorder=8)

    def _draw_graph(self):
        ax  = self.ax_graph
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_title("Population Status", color=FG, fontsize=9, pad=8)
        ax.set_xlabel("Step",    color=FG_DIM, fontsize=8)
        ax.set_ylabel("Citizens", color=FG_DIM, fontsize=8)
        ax.tick_params(colors=FG_DIM, labelsize=8)
        steps = self.var_steps.get()
        pop   = self.var_population.get()
        ax.set_xlim(0, steps)
        ax.set_ylim(0, pop + 5)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.axhline(y=pop, color="white", linestyle="--",
                   linewidth=0.7, alpha=0.25)
        ax.grid(color="#222244", linestyle="--", linewidth=0.5, alpha=0.5)

        h = self.history
        if h["step"]:
            ax.plot(h["step"], h["informed"],  color="#FFD700", lw=2,
                    marker="o", ms=4, label="Informed")
            ax.plot(h["step"], h["evacuated"], color=HIGHLIGHT, lw=2,
                    marker="s", ms=4, label="Evacuated")
            ax.plot(h["step"], h["alive"],     color="#a8dadc", lw=2,
                    marker="^", ms=4, label="Alive")
            ax.plot(h["step"], h["dead"],      color="#e63946", lw=2,
                    marker="x", ms=5, label="Dead")
        ax.legend(fontsize=8, facecolor="#111122", labelcolor=FG,
                  framealpha=0.85, edgecolor="#333355")

    # ─────────────────────────────────────────
    # HOVER TOOLTIP
    # ─────────────────────────────────────────

    def _on_map_hover(self, event):
        """Show info about the cell (and any agents on it) under the cursor."""
        if event.inaxes != self.ax_map or not self.city:
            if self._map_ann:
                self._map_ann.set_visible(False)
                self.canvas.draw_idle()
                self._map_ann = None
            return

        cx = int(round(event.xdata))
        cy = int(round(event.ydata))

        if not (0 <= cx < self.city.grid_width and 0 <= cy < self.city.grid_height):
            return

        cell = self.city.cells[cx][cy]

        # Cell info
        if cell.fire_state == "burning":
            cell_line = f"FIRE  intensity {cell.intensity:.2f}  ({cell.burn_timer} steps left)"
        elif cell.fire_state == "burnt":
            cell_line = "BURNT"
        else:
            cell_line = "empty"

        # Agents on this cell
        here = [a for a in self.city.schedule.agents if a.position == (cx, cy)]
        lines = [f"Cell ({cx},{cy}) — {cell_line}"]
        if here:
            for a in here[:4]:   # cap at 4 to keep tooltip tidy
                if not a.alive:
                    status = "dead"
                elif a.evacuated:
                    status = f"evacuated ({a.escape_direction})"
                else:
                    bf = f"({a.fire_belief[0]:.1f},{a.fire_belief[1]:.1f})" if a.fire_belief else "none"
                    status = f"conf {a.belief_confidence:.2f}  belief {bf}"
                lines.append(f"  [{a.group[:5]}] {status}")
            if len(here) > 4:
                lines.append(f"  … +{len(here)-4} more")
        else:
            lines.append("  no citizens")

        label = "\n".join(lines)
        ax    = self.ax_map

        if self._map_ann:
            try: self._map_ann.remove()
            except: pass

        # Anchor tooltip to avoid going off-screen
        x_off = 10 if cx < self.city.grid_width * 0.7 else -10
        ha    = "left" if x_off > 0 else "right"
        self._map_ann = ax.annotate(
            label,
            xy=(cx, cy),
            xytext=(x_off, 10), textcoords="offset points",
            fontsize=7.5, color=FG, ha=ha,
            bbox=dict(boxstyle="round,pad=0.4", fc="#111122", ec="#333355", alpha=0.93),
            zorder=20,
        )
        self.canvas.draw_idle()

    def _on_hover(self, event):
        self._on_map_hover(event)
        if event.inaxes != self.ax_graph or not self.history["step"]:
            if self._hover_ann:
                self._hover_ann.set_visible(False)
                self.canvas.draw_idle()
            return

        # Find nearest step
        steps = self.history["step"]
        mx    = event.xdata
        if mx is None:
            return
        idx = min(range(len(steps)), key=lambda i: abs(steps[i] - mx))
        s   = steps[idx]
        inf = self.history["informed"][idx]
        ev  = self.history["evacuated"][idx]
        al  = self.history["alive"][idx]
        d   = self.history["dead"][idx]

        label = (f"Step {s}\n"
                 f"Informed : {inf}\n"
                 f"Evacuated: {ev}\n"
                 f"Alive    : {al}\n"
                 f"Dead     : {d}")

        ax = self.ax_graph
        if self._hover_ann:
            self._hover_ann.remove()
        self._hover_ann = ax.annotate(
            label,
            xy=(s, al),
            xytext=(12, 12), textcoords="offset points",
            fontsize=8, color=FG,
            bbox=dict(boxstyle="round,pad=0.4", fc="#111122", ec="#333355", alpha=0.92),
        )
        # Vertical guide line
        for line in getattr(self, "_hover_vline", []):
            try: line.remove()
            except: pass
        self._hover_vline = [ax.axvline(s, color=FG_DIM, lw=0.8, alpha=0.5)]
        self.canvas.draw_idle()

    # ─────────────────────────────────────────
    # SIM CONTROL
    # ─────────────────────────────────────────

    def _start(self):
        self._reset_state()
        self.city = CityModel(
            width              = GRID_SIZE,
            height             = GRID_SIZE,
            population         = self.var_population.get(),
            group_distribution = {
                "north_district": 0.40,
                "south_district": 0.35,
                "city_centre":    0.25,
            },
            fire_spread_chance = self.var_spread.get_float(),
            fire_burn_duration = self.var_burn.get(),
            wind_strength      = self.var_wind_str.get_float(),
            vision_radius      = 3,
            media_alerts_on    = True,
        )
        self.lbl_step.config(text="Step: 0")
        self.btn_play.config(state="normal")
        self.btn_next.config(state="normal")
        self.btn_reset.config(state="normal")
        self._draw_map()
        self._draw_graph()
        self.canvas.draw_idle()
        self._play()

    def _sim_step(self):
        """Advance the simulation by one tick. Returns True while steps remain."""
        if not self.city or self.current_step >= self.var_steps.get():
            return False

        self.city.step()
        self.current_step += 1
        pop = self.var_population.get()

        i = self.city._count_informed()
        e = self.city._count_evacuated()
        a = self.city._count_alive()
        d = self.city._count_dead()

        self.history["step"].append(self.current_step)
        self.history["informed"].append(i)
        self.history["evacuated"].append(e)
        self.history["alive"].append(a)
        self.history["dead"].append(d)

        self.lbl_step.config(
            text=f"Step: {self.current_step} / {self.var_steps.get()}"
        )
        self.lbl_informed.config( text=f"{i} / {pop}")
        self.lbl_evacuated.config(text=f"{e} / {pop}")
        self.lbl_alive.config(    text=f"{a} / {pop}")
        self.lbl_dead.config(     text=str(d))

        return self.current_step < self.var_steps.get()

    def _play(self):
        if not self.city or self.current_step >= self.var_steps.get():
            return
        self.is_playing   = True
        self._anim_frame  = 0
        self.btn_play.config(text="⏸  Pause")

        def _tick(_f):
            if not self.is_playing:
                return

            frames_per_step = max(2, self.var_interval.get() // FRAME_MS)

            if self._anim_frame == 0:
                # Advance sim on the first sub-frame of each step
                still_going = self._sim_step()
                if not still_going:
                    self._pause()
                    return

            t = min(1.0, (self._anim_frame + 1) / frames_per_step)
            self._draw_map(t)
            if self._anim_frame == 0:
                self._draw_graph()
            self.canvas.draw_idle()

            self._anim_frame = (self._anim_frame + 1) % frames_per_step

        self.ani = animation.FuncAnimation(
            self.fig, _tick,
            interval=FRAME_MS,
            repeat=True,
            cache_frame_data=False
        )

    def _pause(self):
        self.is_playing = False
        self.btn_play.config(text="▶  Play")
        if self.ani:
            self.ani.event_source.stop()

    def _toggle_play(self):
        if not self.city:
            return
        if self.is_playing:
            self._pause()
        else:
            self._play()

    def _next_step(self):
        if self.is_playing:
            return
        self._sim_step()
        self._draw_map(1.0)
        self._draw_graph()
        self.canvas.draw_idle()

    def _reset_state(self):
        self._pause()
        self.current_step = 0
        self.city         = None
        self._anim_frame  = 0
        self.history      = {"step": [], "informed": [], "evacuated": [],
                             "alive": [], "dead": []}
        self.btn_play.config(text="▶  Play", state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_reset.config(state="disabled")
        self.lbl_step.config(text="Step: —")
        for lbl in (self.lbl_informed, self.lbl_evacuated,
                    self.lbl_alive, self.lbl_dead):
            lbl.config(text="—")

    def _reset(self):
        self._reset_state()
        self._draw_map()
        self._draw_graph()
        self.canvas.draw_idle()


if __name__ == "__main__":
    App().mainloop()
