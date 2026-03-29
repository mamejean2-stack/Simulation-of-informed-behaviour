# gui.py
# Full GUI — configure, run, and watch the simulation live.

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from model import CityModel

# ─────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────

BG        = "#1a1a2e"
ACCENT    = "#0f3460"
GREEN     = "#2d6a4f"
BLUE      = "#1d3557"
RED_DIM   = "#6b2737"
FG        = "#e0e0e0"
FG_DIM    = "#888888"
HIGHLIGHT = "#52b788"

# Citizens: purple (uninformed) → white → orange (informed)
info_cmap = mcolors.LinearSegmentedColormap.from_list(
    "info_gradient", ["#7B2D8B", "#FFFFFF", "#FF8C00"]
)

# Fire core: dark red (dying) → orange → bright yellow (freshly lit)
fire_cmap = mcolors.LinearSegmentedColormap.from_list(
    "fire_core",
    [(0.0, "#7a0000"), (0.35, "#FF2200"), (0.65, "#FF7700"), (1.0, "#FFD700")]
)


# ─────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("City Alert — Evacuation Simulation")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Simulation state
        self.city         = None
        self.current_step = 0
        self.is_playing   = False
        self.ani          = None
        self.history      = {"step": [], "informed": [], "evacuated": [],
                             "survivors": [], "dead": []}

        self._build_left_panel()
        self._build_right_panel()

    # ─────────────────────────────────────────────────────────────────
    # LEFT PANEL — controls
    # ─────────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        # Scrollable container
        outer = tk.Frame(self, bg=BG)
        outer.grid(row=0, column=0, sticky="ns")

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, width=230)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        left = tk.Frame(canvas, bg=BG, padx=12, pady=12)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")

        def _resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        left.bind("<Configure>", _resize)

        # Mouse-wheel scrolling
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        # ── Title ────────────────────────────────────────────────────
        tk.Label(left, text="CITY ALERT", bg=BG, fg=FG,
                 font=("Helvetica", 15, "bold")).pack(anchor="w")
        tk.Label(left, text="Evacuation Simulation", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 10))

        # ── City ─────────────────────────────────────────────────────
        self._section(left, "City")
        self.var_population = self._slider(left, "Population",      50, 300, 100)
        self.var_steps      = self._slider(left, "Steps",            5,  60,  20)

        # ── Districts ────────────────────────────────────────────────
        self._section(left, "Districts  (must sum to 100 %)")
        self.var_north  = self._slider(left, "North %", 10, 70, 40)
        self.var_south  = self._slider(left, "South %", 10, 70, 35)
        self.var_centre = self._slider(left, "Centre %", 10, 70, 25)
        self.lbl_pct_warn = tk.Label(left, text="", bg=BG, fg="#e63946",
                                     font=("Helvetica", 8))
        self.lbl_pct_warn.pack(anchor="w", pady=(0, 4))
        for v in (self.var_north, self.var_south, self.var_centre):
            v.trace_add("write", self._check_pct)

        # ── Fire ─────────────────────────────────────────────────────
        self._section(left, "Fire")
        self.var_spread_chance  = self._fslider(left, "Spread chance",  0.05, 0.80, 0.30)
        self.var_burn_duration  = self._slider( left, "Burn duration",  3,    20,   8)

        # ── Wind ─────────────────────────────────────────────────────
        self._section(left, "Wind")
        self.var_wind_dir      = self._wind_buttons(left)
        self.var_wind_strength = self._fslider(left, "Strength", 0.0, 0.5, 0.20)

        # ── Citizens ─────────────────────────────────────────────────
        self._section(left, "Citizens")
        self.var_vision_radius = self._slider(left, "Vision radius", 1, 8, 3)
        self.var_media_alerts  = self._toggle(left, "Media alerts", default=True)

        # ── Speed ────────────────────────────────────────────────────
        self._section(left, "Auto-run speed")
        self.var_interval = self._slider(left, "ms per step", 200, 2000, 1000)

        # ── Run button ───────────────────────────────────────────────
        self.btn_run = tk.Button(
            left, text="Run Simulation", command=self._start,
            bg=GREEN, fg="white", activebackground=HIGHLIGHT,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=8, pady=7, cursor="hand2"
        )
        self.btn_run.pack(fill="x", pady=(10, 4))

        # ── Play / Next / Reset ──────────────────────────────────────
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

        # ── Step counter ─────────────────────────────────────────────
        self.lbl_step = tk.Label(left, text="Step: —", bg=BG, fg=FG_DIM,
                                  font=("Helvetica", 9))
        self.lbl_step.pack(anchor="w")

        # ── Live stats ───────────────────────────────────────────────
        self._section(left, "Live Stats")
        self.lbl_informed  = self._stat_row(left, "Informed",  "#FFD700")
        self.lbl_evacuated = self._stat_row(left, "Evacuated", HIGHLIGHT)
        self.lbl_survivors = self._stat_row(left, "Survivors", "#a8dadc")
        self.lbl_dead      = self._stat_row(left, "Dead",      "#e63946")

        # ── Legend ───────────────────────────────────────────────────
        self._section(left, "Legend")
        legend_data = [
            ("o", info_cmap(0.05), "Uninformed"),
            ("o", info_cmap(1.0),  "Informed"),
            ("^", info_cmap(0.8),  "Evacuated — safe"),
            ("v", info_cmap(0.2),  "Evacuated — toward fire"),
            ("X", "#222222",       "Dead"),
            ("s", "#FF7700",       "Fire"),
            ("s", "#1c1c1c",       "Burnt"),
        ]
        for marker, color, label in legend_data:
            r = tk.Frame(left, bg=BG)
            r.pack(anchor="w", pady=1)
            fig_i, ax_i = plt.subplots(figsize=(0.26, 0.26))
            fig_i.patch.set_alpha(0)
            ax_i.scatter([0], [0], marker=marker, color=[color], s=55)
            ax_i.axis("off")
            ci = FigureCanvasTkAgg(fig_i, master=r)
            ci.draw()
            ci.get_tk_widget().pack(side="left")
            plt.close(fig_i)
            tk.Label(r, text=label, bg=BG, fg=FG,
                     font=("Helvetica", 8)).pack(side="left", padx=3)

        # Finalise scroll region after everything is packed
        left.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"),
                         height=min(700, left.winfo_reqheight()))

    # ── Widget helpers ────────────────────────────────────────────────

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
                 font=("Helvetica", 8), width=18, anchor="w").pack(side="left")
        tk.Label(row, textvariable=var, bg=BG, fg=HIGHLIGHT,
                 font=("Helvetica", 8, "bold"), width=4).pack(side="right")
        tk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var,
                 bg=BG, fg=FG, troughcolor=ACCENT, highlightthickness=0,
                 showvalue=False, length=110).pack(side="left")
        return var

    def _fslider(self, parent, label, lo, hi, default):
        """Float slider stored as an integer (×100) for tkinter compatibility."""
        var     = tk.IntVar(value=int(default * 100))
        display = tk.StringVar(value=f"{default:.2f}")

        def _update(*_):
            display.set(f"{var.get() / 100:.2f}")
        var.trace_add("write", _update)

        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=("Helvetica", 8), width=18, anchor="w").pack(side="left")
        tk.Label(row, textvariable=display, bg=BG, fg=HIGHLIGHT,
                 font=("Helvetica", 8, "bold"), width=4).pack(side="right")
        tk.Scale(row, from_=int(lo * 100), to=int(hi * 100), orient="horizontal",
                 variable=var, bg=BG, fg=FG, troughcolor=ACCENT,
                 highlightthickness=0, showvalue=False, length=110).pack(side="left")

        # Attach a .get_float() convenience method
        var.get_float = lambda: var.get() / 100
        return var

    def _wind_buttons(self, parent):
        """Four N/S/E/W toggle buttons that act as a radio group."""
        var = tk.StringVar(value="E")
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Direction", bg=BG, fg=FG,
                 font=("Helvetica", 8), width=18, anchor="w").pack(side="left")

        btn_frame = tk.Frame(row, bg=BG)
        btn_frame.pack(side="left")

        btns = {}
        for d in ("N", "E", "S", "W"):
            b = tk.Button(
                btn_frame, text=d, width=2,
                bg=BLUE, fg="white", relief="flat",
                font=("Helvetica", 8, "bold"),
                cursor="hand2",
                command=lambda _d=d: self._set_wind(_d, var, btns)
            )
            b.pack(side="left", padx=1)
            btns[d] = b

        # Highlight default
        btns["E"].config(bg=HIGHLIGHT, fg=BG)
        return var

    def _set_wind(self, direction, var, btns):
        var.set(direction)
        for d, b in btns.items():
            b.config(bg=HIGHLIGHT if d == direction else BLUE,
                     fg=BG        if d == direction else "white")

    def _toggle(self, parent, label, default=True):
        var = tk.BooleanVar(value=default)
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=("Helvetica", 8), width=18, anchor="w").pack(side="left")

        indicator = tk.Label(row, text="ON" if default else "OFF",
                             bg=HIGHLIGHT if default else ACCENT,
                             fg=BG if default else FG_DIM,
                             font=("Helvetica", 8, "bold"),
                             width=4, relief="flat")
        indicator.pack(side="left", padx=2)

        def _flip():
            new = not var.get()
            var.set(new)
            indicator.config(text="ON" if new else "OFF",
                             bg=HIGHLIGHT if new else ACCENT,
                             fg=BG if new else FG_DIM)

        tk.Button(row, text="toggle", command=_flip,
                  bg=ACCENT, fg=FG_DIM, relief="flat",
                  font=("Helvetica", 7), cursor="hand2").pack(side="left", padx=2)
        return var

    def _stat_row(self, parent, label, colour=FG):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8), width=11, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="—", bg=BG, fg=colour,
                       font=("Helvetica", 8, "bold"))
        lbl.pack(side="left")
        return lbl

    # ─────────────────────────────────────────────────────────────────
    # RIGHT PANEL — city map + population graph
    # ─────────────────────────────────────────────────────────────────

    def _build_right_panel(self):
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, padx=(0, 14), pady=14)

        self.fig = plt.figure(figsize=(12, 6.5))
        self.fig.patch.set_facecolor(BG)

        self.ax_map   = self.fig.add_axes([0.03, 0.08, 0.48, 0.88])
        self.ax_cbar  = self.fig.add_axes([0.535, 0.08, 0.015, 0.88])
        self.ax_graph = self.fig.add_axes([0.58, 0.08, 0.40, 0.88])

        # Citizen info-level colorbar
        sm = plt.cm.ScalarMappable(cmap=info_cmap, norm=plt.Normalize(0, 1))
        sm.set_array([])
        cbar = self.fig.colorbar(sm, cax=self.ax_cbar)
        cbar.set_label("Belief confidence", color=FG, fontsize=8, labelpad=6)
        cbar.ax.yaxis.set_tick_params(color=FG)
        cbar.set_ticks([0.0, 0.5, 1.0])
        cbar.set_ticklabels(["Low", "Med", "High"])
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=FG, fontsize=7)

        self._draw_empty_map()
        self._draw_graph()

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()

    # ─────────────────────────────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────────────────────────────

    def _draw_empty_map(self):
        ax = self.ax_map
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_xlim(-1, 20)
        ax.set_ylim(-1, 20)
        ax.set_title("Configure settings and press Run",
                     color=FG, fontsize=9, pad=8)
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

    def _draw_map(self):
        if not self.city:
            return
        ax = self.ax_map
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_xlim(-1, self.city.grid_width)
        ax.set_ylim(-1, self.city.grid_height)
        ax.set_title(
            f"City Map — Step {self.current_step} / {self.var_steps.get()}",
            color=FG, fontsize=9, pad=8
        )
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

        # ── Collect fire cell data ────────────────────────────────────
        burnt_x, burnt_y                   = [], []
        burn_x,  burn_y,  burn_intensity   = [], [], []

        for x in range(self.city.grid_width):
            for y in range(self.city.grid_height):
                cell = self.city.cells[x][y]
                if cell.fire_state == "burnt":
                    burnt_x.append(x)
                    burnt_y.append(y)
                elif cell.fire_state == "burning":
                    burn_x.append(x)
                    burn_y.append(y)
                    burn_intensity.append(cell.intensity)

        # ── Burnt cells — scorched earth ──────────────────────────────
        if burnt_x:
            ax.scatter(burnt_x, burnt_y, c="#151515", s=140,
                       marker="s", zorder=1, linewidths=0)

        # ── Burning cells — layered glow effect ───────────────────────
        if burn_x:
            bi = np.array(burn_intensity)

            # Layer 1 — wide outer halo (low alpha, large)
            outer = np.zeros((len(burn_x), 4))
            outer[:, 0] = 1.0
            outer[:, 1] = 0.35
            outer[:, 2] = 0.0
            outer[:, 3] = bi * 0.10
            ax.scatter(burn_x, burn_y, c=outer,
                       s=bi * 700 + 120, marker="o",
                       zorder=2, linewidths=0)

            # Layer 2 — mid corona
            mid = np.zeros((len(burn_x), 4))
            mid[:, 0] = 1.0
            mid[:, 1] = 0.55
            mid[:, 2] = 0.0
            mid[:, 3] = bi * 0.22
            ax.scatter(burn_x, burn_y, c=mid,
                       s=bi * 220 + 60, marker="o",
                       zorder=3, linewidths=0)

            # Layer 3 — bright core (colour-mapped, dark red → yellow)
            core_colors = fire_cmap(bi)
            ax.scatter(burn_x, burn_y, c=core_colors,
                       s=85, marker="s",
                       zorder=4, linewidths=0)

        # ── Citizens ──────────────────────────────────────────────────
        for agent in self.city.schedule.agents:
            x, y  = agent.position
            color = info_cmap(agent.information_level)

            if not agent.alive:
                ax.scatter(x, y, c=[[0.08, 0.08, 0.08]], s=65,
                           marker="X", edgecolors="white",
                           linewidths=0.4, zorder=6)
            elif agent.evacuated:
                marker = "^" if agent.escape_direction == "safe" else "v"
                ax.scatter(x, y, c=[color], s=85,
                           marker=marker, edgecolors="white",
                           linewidths=0.4, zorder=5)
            else:
                ax.scatter(x, y, c=[color], s=50,
                           marker="o", edgecolors="none", zorder=5)

    def _draw_graph(self):
        ax = self.ax_graph
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_title("Population Status Over Time", color=FG, fontsize=9, pad=8)
        ax.set_xlabel("Step", color=FG_DIM, fontsize=8)
        ax.set_ylabel("Citizens", color=FG_DIM, fontsize=8)
        ax.tick_params(colors=FG_DIM, labelsize=8)
        steps = self.var_steps.get()
        pop   = self.var_population.get()
        ax.set_xlim(0, steps)
        ax.set_ylim(0, pop + 8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

        ax.axhline(y=pop, color="white", linestyle="--",
                   linewidth=0.7, alpha=0.3, label=f"Total ({pop})")
        ax.grid(color="#222244", linestyle="--", linewidth=0.5, alpha=0.5)

        if self.history["step"]:
            ax.plot(self.history["step"], self.history["informed"],
                    color="#FFD700", lw=2, marker="o", ms=4, label="Informed")
            ax.plot(self.history["step"], self.history["evacuated"],
                    color=HIGHLIGHT, lw=2, marker="s", ms=4, label="Evacuated")
            ax.plot(self.history["step"], self.history["survivors"],
                    color="#a8dadc", lw=2, marker="^", ms=4, label="Survivors")
            ax.plot(self.history["step"], self.history["dead"],
                    color="#e63946", lw=2, marker="x", ms=5, label="Dead")

        ax.legend(fontsize=8, facecolor="#111122", labelcolor=FG,
                  framealpha=0.85, edgecolor="#333355")

    def _redraw(self):
        self._draw_map()
        self._draw_graph()
        self.canvas.draw_idle()

    # ─────────────────────────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────────────────────────

    def _check_pct(self, *_):
        total = self.var_north.get() + self.var_south.get() + self.var_centre.get()
        if total != 100:
            self.lbl_pct_warn.config(text=f"Sum = {total}%  (need 100%)")
            self.btn_run.config(state="disabled")
        else:
            self.lbl_pct_warn.config(text="")
            self.btn_run.config(state="normal")

    # ─────────────────────────────────────────────────────────────────
    # SIMULATION CONTROL
    # ─────────────────────────────────────────────────────────────────

    def _start(self):
        self._reset_state()
        self.city = CityModel(
            width              = 20,
            height             = 20,
            population         = self.var_population.get(),
            group_distribution = {
                "north_district": self.var_north.get()  / 100,
                "south_district": self.var_south.get()  / 100,
                "city_centre":    self.var_centre.get() / 100,
            },
            fire_spread_chance = self.var_spread_chance.get_float(),
            fire_burn_duration = self.var_burn_duration.get(),
            wind_direction     = self.var_wind_dir.get(),
            wind_strength      = self.var_wind_strength.get_float(),
            vision_radius      = self.var_vision_radius.get(),
            media_alerts_on    = self.var_media_alerts.get(),
        )
        self.lbl_step.config(text="Step: 0")
        self.btn_play.config(state="normal")
        self.btn_next.config(state="normal")
        self.btn_reset.config(state="normal")
        self._redraw()

    def _advance(self):
        """Run one simulation step and update the UI. Returns True while steps remain."""
        if not self.city or self.current_step >= self.var_steps.get():
            return False

        self.city.step()
        self.current_step += 1

        pop       = self.var_population.get()
        informed  = self.city._count_informed()
        evacuated = self.city._count_evacuated()
        survivors = self.city._count_survivors()
        dead      = self.city._count_dead()

        self.history["step"].append(self.current_step)
        self.history["informed"].append(informed)
        self.history["evacuated"].append(evacuated)
        self.history["survivors"].append(survivors)
        self.history["dead"].append(dead)

        self.lbl_step.config(
            text=f"Step: {self.current_step} / {self.var_steps.get()}"
        )
        self.lbl_informed.config( text=f"{informed}  / {pop}")
        self.lbl_evacuated.config(text=f"{evacuated} / {pop}")
        self.lbl_survivors.config(text=f"{survivors} / {max(evacuated, 1)}")
        self.lbl_dead.config(     text=f"{dead}")

        self._redraw()
        return self.current_step < self.var_steps.get()

    def _next_step(self):
        if not self.is_playing:
            self._advance()

    def _toggle_play(self):
        if not self.city:
            return
        if self.is_playing:
            self._pause()
        else:
            self._play()

    def _play(self):
        if self.current_step >= self.var_steps.get():
            return
        self.is_playing = True
        self.btn_play.config(text="⏸  Pause")

        def _frame(_f):
            if not self.is_playing:
                return
            still_going = self._advance()
            if not still_going:
                self.is_playing = False
                self.btn_play.config(text="▶  Play")
                self.ani.event_source.stop()

        interval = self.var_interval.get()
        self.ani = animation.FuncAnimation(
            self.fig, _frame,
            frames=self.var_steps.get() - self.current_step,
            interval=interval,
            repeat=False
        )
        self.ani.event_source.start()

    def _pause(self):
        self.is_playing = False
        self.btn_play.config(text="▶  Play")
        if self.ani:
            self.ani.event_source.stop()

    def _reset_state(self):
        self._pause()
        self.current_step = 0
        self.city         = None
        self.ani          = None
        self.history      = {"step": [], "informed": [], "evacuated": [],
                             "survivors": [], "dead": []}
        self.btn_play.config(text="▶  Play", state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_reset.config(state="disabled")
        self.lbl_step.config(text="Step: —")
        for lbl in (self.lbl_informed, self.lbl_evacuated,
                    self.lbl_survivors, self.lbl_dead):
            lbl.config(text="—")

    def _reset(self):
        self._reset_state()
        self._draw_empty_map()
        self._draw_graph()
        self.canvas.draw_idle()


if __name__ == "__main__":
    App().mainloop()
