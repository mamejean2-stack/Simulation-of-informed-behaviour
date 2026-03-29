# gui.py
# Full GUI — configure parameters, run the simulation, watch it live.

import tkinter as tk
from tkinter import ttk
import threading
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from model import CityModel

# ─────────────────────────────────────────────
# COLOUR SCHEME
# ─────────────────────────────────────────────

BG        = "#1a1a2e"
PANEL     = "#16213e"
ACCENT    = "#0f3460"
GREEN     = "#2d6a4f"
BLUE      = "#1d3557"
FG        = "#e0e0e0"
FG_DIM    = "#888888"
HIGHLIGHT = "#52b788"

info_cmap = mcolors.LinearSegmentedColormap.from_list(
    "info_gradient",
    ["#7B2D8B", "#FFFFFF", "#FF8C00"]
)


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("City Alert — Evacuation Simulation")
        self.configure(bg=BG)
        self.resizable(False, False)

        # State
        self.city         = None
        self.current_step = 0
        self.is_playing   = False
        self.ani          = None
        self.history      = {"step": [], "informed": [], "evacuated": [], "survivors": []}

        self._build_left_panel()
        self._build_right_panel()

    # ─────────────────────────────────────────
    # LEFT PANEL — controls
    # ─────────────────────────────────────────

    def _build_left_panel(self):
        left = tk.Frame(self, bg=BG, padx=16, pady=16)
        left.grid(row=0, column=0, sticky="ns")

        # Title
        tk.Label(left, text="CITY ALERT", bg=BG, fg=FG,
                 font=("Helvetica", 16, "bold")).pack(anchor="w")
        tk.Label(left, text="Evacuation Simulation", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(0, 16))

        self._section(left, "City Settings")

        self.var_population = self._slider(left, "Population",       50, 300, 100)
        self.var_steps      = self._slider(left, "Simulation Steps",  5,  50,  10)

        self._section(left, "District Split  (must sum to 100%)")

        self.var_north  = self._slider(left, "North District %", 10, 70, 40)
        self.var_south  = self._slider(left, "South District %", 10, 70, 35)
        self.var_centre = self._slider(left, "City Centre %",    10, 70, 25)

        self.pct_warning = tk.Label(left, text="", bg=BG, fg="#e63946",
                                    font=("Helvetica", 9))
        self.pct_warning.pack(anchor="w", pady=(2, 8))

        for v in (self.var_north, self.var_south, self.var_centre):
            v.trace_add("write", self._check_pct)

        # Run button
        self.btn_run = tk.Button(
            left, text="Run Simulation", command=self._start,
            bg=GREEN, fg="white", activebackground=HIGHLIGHT,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=12, pady=8, cursor="hand2"
        )
        self.btn_run.pack(fill="x", pady=(8, 4))

        # Play / Next / Reset row
        ctrl = tk.Frame(left, bg=BG)
        ctrl.pack(fill="x", pady=4)

        self.btn_play = tk.Button(
            ctrl, text="▶  Play", command=self._toggle_play,
            bg=BLUE, fg="white", activebackground="#457b9d",
            font=("Helvetica", 10), relief="flat",
            padx=8, pady=6, cursor="hand2", state="disabled"
        )
        self.btn_play.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_next = tk.Button(
            ctrl, text="⏭  Next", command=self._next_step,
            bg=BLUE, fg="white", activebackground="#457b9d",
            font=("Helvetica", 10), relief="flat",
            padx=8, pady=6, cursor="hand2", state="disabled"
        )
        self.btn_next.pack(side="left", expand=True, fill="x")

        self.btn_reset = tk.Button(
            left, text="Reset", command=self._reset,
            bg=ACCENT, fg=FG_DIM, activebackground="#1a3a5c",
            font=("Helvetica", 10), relief="flat",
            padx=8, pady=6, cursor="hand2", state="disabled"
        )
        self.btn_reset.pack(fill="x", pady=(4, 16))

        # Step counter
        self.lbl_step = tk.Label(left, text="Step: —", bg=BG, fg=FG_DIM,
                                  font=("Helvetica", 10))
        self.lbl_step.pack(anchor="w")

        self._section(left, "Live Stats")
        self.lbl_informed  = self._stat_row(left, "Informed")
        self.lbl_evacuated = self._stat_row(left, "Evacuated")
        self.lbl_survivors = self._stat_row(left, "Survivors")

        self._section(left, "Legend")
        self._legend(left)

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(10, 4))
        tk.Label(f, text=text.upper(), bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8, "bold")).pack(anchor="w")
        tk.Frame(f, bg=ACCENT, height=1).pack(fill="x", pady=(2, 0))

    def _slider(self, parent, label, lo, hi, default):
        var = tk.IntVar(value=default)
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=("Helvetica", 9), width=22, anchor="w").pack(side="left")
        val_lbl = tk.Label(row, textvariable=var, bg=BG, fg=HIGHLIGHT,
                           font=("Helvetica", 9, "bold"), width=4)
        val_lbl.pack(side="right")
        tk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var,
                 bg=BG, fg=FG, troughcolor=ACCENT, highlightthickness=0,
                 showvalue=False, length=140).pack(side="left")
        return var

    def _stat_row(self, parent, label):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG, fg=FG_DIM,
                 font=("Helvetica", 9), width=12, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="—", bg=BG, fg=FG,
                       font=("Helvetica", 9, "bold"))
        lbl.pack(side="left")
        return lbl

    def _legend(self, parent):
        items = [
            ("o", info_cmap(0.05), "Not yet informed"),
            ("o", info_cmap(1.0),  "Highly informed"),
            ("^", info_cmap(0.8),  "Evacuated — safe"),
            ("v", info_cmap(0.3),  "Evacuated — toward fire"),
            ("X", "#333333",       "Did not survive"),
            ("*", "orangered",     "Fire"),
        ]
        for marker, color, label in items:
            row = tk.Frame(parent, bg=BG)
            row.pack(anchor="w", pady=1)
            fig_icon, ax_icon = plt.subplots(figsize=(0.28, 0.28))
            fig_icon.patch.set_alpha(0)
            ax_icon.scatter([0], [0], marker=marker, color=[color], s=60)
            ax_icon.axis("off")
            canvas_icon = FigureCanvasTkAgg(fig_icon, master=row)
            canvas_icon.draw()
            canvas_icon.get_tk_widget().pack(side="left")
            plt.close(fig_icon)
            tk.Label(row, text=label, bg=BG, fg=FG,
                     font=("Helvetica", 8)).pack(side="left", padx=4)

    # ─────────────────────────────────────────
    # RIGHT PANEL — map + graph
    # ─────────────────────────────────────────

    def _build_right_panel(self):
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, padx=(0, 16), pady=16)

        self.fig = plt.figure(figsize=(12, 6.5))
        self.fig.patch.set_facecolor(BG)

        self.ax_map   = self.fig.add_axes([0.03, 0.08, 0.48, 0.88])
        self.ax_cbar  = self.fig.add_axes([0.535, 0.08, 0.015, 0.88])
        self.ax_graph = self.fig.add_axes([0.58, 0.08, 0.40, 0.88])

        sm = plt.cm.ScalarMappable(cmap=info_cmap, norm=plt.Normalize(0, 1))
        sm.set_array([])
        cbar = self.fig.colorbar(sm, cax=self.ax_cbar)
        cbar.set_label("Information Level", color=FG, fontsize=8, labelpad=6)
        cbar.ax.yaxis.set_tick_params(color=FG)
        cbar.set_ticks([0.0, 0.5, 1.0])
        cbar.set_ticklabels(["Low", "Medium", "High"])
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=FG, fontsize=7)

        self._draw_empty_map()
        self._draw_graph()

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()

    # ─────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────

    def _draw_empty_map(self):
        ax = self.ax_map
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_xlim(-1, 20)
        ax.set_ylim(-1, 20)
        ax.set_title("City Map — configure settings and press Run",
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
        w = self.var_width if hasattr(self, "var_width") else 20
        ax.set_xlim(-1, 20)
        ax.set_ylim(-1, 20)
        ax.set_title(f"City Map — Step {self.current_step} / {self.var_steps.get()}",
                     color=FG, fontsize=9, pad=8)
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

        for agent in self.city.schedule.agents:
            x, y  = agent.position
            color = info_cmap(agent.information_level)

            if not agent.alive:
                ax.scatter(x, y, c=[[0.1, 0.1, 0.1]], s=70,
                           marker="X", edgecolors="white", linewidths=0.4, zorder=4)
            elif agent.evacuated:
                marker = "^" if agent.escape_direction == "safe" else "v"
                ax.scatter(x, y, c=[color], s=90,
                           marker=marker, edgecolors="white", linewidths=0.5, zorder=3)
            else:
                ax.scatter(x, y, c=[color], s=55,
                           marker="o", edgecolors="none", zorder=2)

        fx, fy = self.city.fire_position
        ax.scatter(fx, fy, c="orangered", s=350,
                   marker="*", edgecolors="yellow", linewidths=1.2, zorder=5)

    def _draw_graph(self):
        ax = self.ax_graph
        ax.clear()
        ax.set_facecolor("#0d1b2a")
        ax.set_title("Population Status Over Time", color=FG, fontsize=9, pad=8)
        ax.set_xlabel("Step", color=FG_DIM, fontsize=8)
        ax.set_ylabel("Citizens", color=FG_DIM, fontsize=8)
        ax.tick_params(colors=FG_DIM, labelsize=8)
        steps = self.var_steps.get() if self.city else 10
        pop   = self.var_population.get() if self.city else 100
        ax.set_xlim(0, steps)
        ax.set_ylim(0, pop + 8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.axhline(y=pop, color="white", linestyle="--",
                   linewidth=0.7, alpha=0.3, label=f"Total ({pop})")
        ax.grid(color="#222244", linestyle="--", linewidth=0.5, alpha=0.5)

        if self.history["step"]:
            ax.plot(self.history["step"], self.history["informed"],
                    color="#FFD700", linewidth=2, marker="o", markersize=5, label="Informed")
            ax.plot(self.history["step"], self.history["evacuated"],
                    color="#52b788", linewidth=2, marker="s", markersize=5, label="Evacuated")
            ax.plot(self.history["step"], self.history["survivors"],
                    color="#a8dadc", linewidth=2, marker="^", markersize=5, label="Survivors")

        ax.legend(fontsize=8, facecolor="#111122", labelcolor=FG,
                  framealpha=0.85, edgecolor="#333355")

    def _redraw(self):
        self._draw_map()
        self._draw_graph()
        self.canvas.draw_idle()

    # ─────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────

    def _check_pct(self, *_):
        total = self.var_north.get() + self.var_south.get() + self.var_centre.get()
        if total != 100:
            self.pct_warning.config(text=f"Districts sum to {total}% (must be 100%)")
            self.btn_run.config(state="disabled")
        else:
            self.pct_warning.config(text="")
            self.btn_run.config(state="normal")

    # ─────────────────────────────────────────
    # SIMULATION CONTROL
    # ─────────────────────────────────────────

    def _start(self):
        self._reset_state()
        total = self.var_north.get() + self.var_south.get() + self.var_centre.get()
        if total != 100:
            return

        self.city = CityModel(
            width=20,
            height=20,
            population=self.var_population.get(),
            group_distribution={
                "north_district": self.var_north.get()  / 100,
                "south_district": self.var_south.get()  / 100,
                "city_centre":    self.var_centre.get() / 100,
            }
        )

        self.lbl_step.config(text="Step: 0")
        self.btn_play.config(state="normal")
        self.btn_next.config(state="normal")
        self.btn_reset.config(state="normal")
        self._redraw()

    def _step(self):
        if not self.city or self.current_step >= self.var_steps.get():
            return False

        self.city.step()
        self.current_step += 1

        informed  = self.city._count_informed()
        evacuated = self.city._count_evacuated()
        survivors = self.city._count_survivors()
        pop       = self.var_population.get()

        self.history["step"].append(self.current_step)
        self.history["informed"].append(informed)
        self.history["evacuated"].append(evacuated)
        self.history["survivors"].append(survivors)

        self.lbl_step.config(text=f"Step: {self.current_step} / {self.var_steps.get()}")
        self.lbl_informed.config( text=f"{informed} / {pop}")
        self.lbl_evacuated.config(text=f"{evacuated} / {pop}")
        self.lbl_survivors.config(text=f"{survivors} / {max(evacuated, 1)}")

        self._redraw()
        return self.current_step < self.var_steps.get()

    def _next_step(self):
        if not self.is_playing:
            self._step()

    def _toggle_play(self):
        if not self.city:
            return

        if self.is_playing:
            self.is_playing = False
            self.btn_play.config(text="▶  Play")
            if self.ani:
                self.ani.event_source.stop()
        else:
            if self.current_step >= self.var_steps.get():
                return
            self.is_playing = True
            self.btn_play.config(text="⏸  Pause")

            def animate(_frame):
                if not self.is_playing:
                    return
                still_going = self._step()
                if not still_going:
                    self.is_playing = False
                    self.btn_play.config(text="▶  Play")
                    self.ani.event_source.stop()

            self.ani = animation.FuncAnimation(
                self.fig, animate,
                frames=self.var_steps.get() - self.current_step,
                interval=800, repeat=False
            )
            self.ani.event_source.start()

    def _reset_state(self):
        self.is_playing   = False
        self.current_step = 0
        self.city         = None
        self.history      = {"step": [], "informed": [], "evacuated": [], "survivors": []}
        if self.ani:
            try:
                self.ani.event_source.stop()
            except Exception:
                pass
            self.ani = None
        self.btn_play.config(text="▶  Play", state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_reset.config(state="disabled")
        self.lbl_step.config(text="Step: —")
        self.lbl_informed.config(text="—")
        self.lbl_evacuated.config(text="—")
        self.lbl_survivors.config(text="—")

    def _reset(self):
        self._reset_state()
        self._draw_empty_map()
        self._draw_graph()
        self.canvas.draw_idle()


if __name__ == "__main__":
    app = App()
    app.mainloop()
