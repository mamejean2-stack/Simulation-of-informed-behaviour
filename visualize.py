# visualize.py
# Launches the animated visual simulation
# Purple = low information | White = medium | Orange = high information

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
from matplotlib.widgets import Button
from model import CityModel

# ─────────────────────────────────────────────
# SIMULATION SETTINGS
# ─────────────────────────────────────────────

CITY_WIDTH      = 20
CITY_HEIGHT     = 20
POPULATION      = 100
NUMBER_OF_STEPS = 10

GROUP_DISTRIBUTION = {
    "north_district" : 0.40,
    "south_district" : 0.35,
    "city_centre"    : 0.25,
}

# ─────────────────────────────────────────────
# INFORMATION LEVEL COLOR GRADIENT
# Purple (0.0) → White (0.5) → Orange (1.0)
# ─────────────────────────────────────────────

info_cmap = mcolors.LinearSegmentedColormap.from_list(
    "info_gradient",
    ["#7B2D8B", "#FFFFFF", "#FF8C00"]  # purple → white → orange
)

# ─────────────────────────────────────────────
# BUILD THE CITY
# ─────────────────────────────────────────────

city = CityModel(
    width=CITY_WIDTH,
    height=CITY_HEIGHT,
    population=POPULATION,
    group_distribution=GROUP_DISTRIBUTION
)

# Tracks what has happened across all steps (for the graph)
history = {
    "step"      : [],
    "informed"  : [],
    "evacuated" : [],
    "survivors" : [],
}

# State variables
current_step = [0]
is_playing   = [False]
ani          = [None]

# ─────────────────────────────────────────────
# FIGURE LAYOUT
# ─────────────────────────────────────────────

fig = plt.figure(figsize=(15, 7))
fig.patch.set_facecolor("#1a1a2e")
fig.suptitle(
    "CITY ALERT — Evacuation Simulation",
    color="white", fontsize=14, fontweight="bold", y=0.98
)

# Map panel (left)
ax_map = fig.add_axes([0.03, 0.18, 0.44, 0.74])

# Gradient colorbar (between map and graph)
ax_cbar = fig.add_axes([0.485, 0.18, 0.015, 0.74])

# Graph panel (right)
ax_graph = fig.add_axes([0.54, 0.18, 0.42, 0.74])

# Buttons (bottom left)
ax_btn_play = fig.add_axes([0.03, 0.04, 0.10, 0.07])
ax_btn_next = fig.add_axes([0.15, 0.04, 0.10, 0.07])

btn_play = Button(ax_btn_play, "▶  Play",  color="#2d6a4f", hovercolor="#52b788")
btn_next = Button(ax_btn_next, "⏭  Next",  color="#1d3557", hovercolor="#457b9d")

for btn in [btn_play, btn_next]:
    btn.label.set_color("white")
    btn.label.set_fontsize(10)

# Colorbar setup
sm = plt.cm.ScalarMappable(
    cmap=info_cmap,
    norm=plt.Normalize(vmin=0.0, vmax=1.0)
)
sm.set_array([])
cbar = fig.colorbar(sm, cax=ax_cbar)
cbar.set_label("Information Level", color="white", fontsize=8, labelpad=6)
cbar.ax.yaxis.set_tick_params(color="white")
cbar.set_ticks([0.0, 0.5, 1.0])
cbar.set_ticklabels(["Low\n(purple)", "Medium\n(white)", "High\n(orange)"])
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=7)

# ─────────────────────────────────────────────
# DRAW THE CITY MAP
# ─────────────────────────────────────────────

def draw_map(step_num):
    ax_map.clear()
    ax_map.set_facecolor("#0d1b2a")
    ax_map.set_xlim(-1, CITY_WIDTH)
    ax_map.set_ylim(-1, CITY_HEIGHT)
    ax_map.set_title(
        f"City Map — Step {step_num} / {NUMBER_OF_STEPS}",
        color="white", fontsize=10, pad=8
    )
    ax_map.tick_params(colors="#888888", labelsize=7)
    for spine in ax_map.spines.values():
        spine.set_edgecolor("#333355")

    for agent in city.schedule.agents:
        x, y     = agent.position
        # Gradient color based on information level
        color    = info_cmap(agent.information_level)

        if not agent.alive:
            # Dead citizen — black X
            ax_map.scatter(
                x, y, c=[[0.1, 0.1, 0.1]], s=70,
                marker="X", edgecolors="white",
                linewidths=0.4, zorder=4
            )

        elif agent.evacuated:
            # Evacuated — triangle showing direction taken
            marker = "^" if agent.escape_direction == "safe" else "v"
            ax_map.scatter(
                x, y, c=[color], s=90,
                marker=marker, edgecolors="white",
                linewidths=0.5, zorder=3
            )

        else:
            # Still in the city — circle with gradient color
            ax_map.scatter(
                x, y, c=[color], s=55,
                marker="o", edgecolors="none",
                zorder=2
            )

    # Fire position
    fx, fy = city.fire_position
    ax_map.scatter(
        fx, fy, c="orangered", s=350,
        marker="*", edgecolors="yellow",
        linewidths=1.2, zorder=5
    )

    # ── Legend ──────────────────────────
    legend_items = [
        mlines.Line2D([], [], marker="o",  linestyle="None",
                      color="white",     markerfacecolor=info_cmap(0.0),
                      markersize=8,      label="Not yet informed"),
        mlines.Line2D([], [], marker="o",  linestyle="None",
                      color="white",     markerfacecolor=info_cmap(1.0),
                      markersize=8,      label="Highly informed"),
        mlines.Line2D([], [], marker="^",  linestyle="None",
                      color="white",     markerfacecolor=info_cmap(0.8),
                      markersize=8,      label="Evacuated — safe direction"),
        mlines.Line2D([], [], marker="v",  linestyle="None",
                      color="white",     markerfacecolor=info_cmap(0.3),
                      markersize=8,      label="Evacuated — toward fire"),
        mlines.Line2D([], [], marker="X",  linestyle="None",
                      color="white",     markerfacecolor="#111111",
                      markersize=8,      label="Did not survive"),
        mlines.Line2D([], [], marker="*",  linestyle="None",
                      color="white",     markerfacecolor="orangered",
                      markersize=12,     label="🔥 Fire"),
    ]
    ax_map.legend(
        handles=legend_items,
        loc="upper right",
        fontsize=7,
        facecolor="#111122",
        labelcolor="white",
        framealpha=0.85,
        edgecolor="#333355"
    )

# ─────────────────────────────────────────────
# DRAW THE POPULATION GRAPH
# ─────────────────────────────────────────────

def draw_graph():
    ax_graph.clear()
    ax_graph.set_facecolor("#0d1b2a")
    ax_graph.set_title(
        "Population Status Over Time",
        color="white", fontsize=10, pad=8
    )
    ax_graph.set_xlabel("Simulation Step", color="#aaaaaa", fontsize=8)
    ax_graph.set_ylabel("Number of Citizens", color="#aaaaaa", fontsize=8)
    ax_graph.tick_params(colors="#888888", labelsize=8)
    ax_graph.set_xlim(0, NUMBER_OF_STEPS)
    ax_graph.set_ylim(0, POPULATION + 8)

    for spine in ax_graph.spines.values():
        spine.set_edgecolor("#333355")

    # Total population reference line
    ax_graph.axhline(
        y=POPULATION, color="white",
        linestyle="--", linewidth=0.7,
        alpha=0.3, label=f"Total population ({POPULATION})"
    )

    if history["step"]:
        ax_graph.plot(
            history["step"], history["informed"],
            color="#FFD700", linewidth=2,
            marker="o", markersize=5, label="Informed"
        )
        ax_graph.plot(
            history["step"], history["evacuated"],
            color="#52b788", linewidth=2,
            marker="s", markersize=5, label="Evacuated"
        )
        ax_graph.plot(
            history["step"], history["survivors"],
            color="#a8dadc", linewidth=2,
            marker="^", markersize=5, label="Survivors"
        )

    ax_graph.legend(
        fontsize=8, facecolor="#111122",
        labelcolor="white", framealpha=0.85,
        edgecolor="#333355"
    )
    ax_graph.grid(color="#222244", linestyle="--", linewidth=0.5, alpha=0.5)

# ─────────────────────────────────────────────
# SIMULATION STEP LOGIC
# ─────────────────────────────────────────────

def run_one_step():
    """Advances the simulation by one step and redraws everything."""
    if current_step[0] >= NUMBER_OF_STEPS:
        return

    city.step()
    current_step[0] += 1

    history["step"].append(current_step[0])
    history["informed"].append(city._count_informed())
    history["evacuated"].append(city._count_evacuated())
    history["survivors"].append(city._count_survivors())

    draw_map(current_step[0])
    draw_graph()
    fig.canvas.draw_idle()

# ─────────────────────────────────────────────
# BUTTON HANDLERS
# ─────────────────────────────────────────────

def on_next(event):
    """Manual step — only works when not auto-playing."""
    if not is_playing[0]:
        run_one_step()

def on_play(event):
    """Toggle between Play and Pause."""
    if current_step[0] >= NUMBER_OF_STEPS:
        return

    if is_playing[0]:
        # ── PAUSE ──
        is_playing[0] = False
        btn_play.label.set_text("▶  Play")
        if ani[0]:
            ani[0].event_source.stop()
    else:
        # ── PLAY ──
        is_playing[0] = True
        btn_play.label.set_text("⏸  Pause")

        def animate(frame):
            if not is_playing[0] or current_step[0] >= NUMBER_OF_STEPS:
                is_playing[0] = False
                btn_play.label.set_text("▶  Play")
                ani[0].event_source.stop()
                return
            run_one_step()

        ani[0] = animation.FuncAnimation(
            fig, animate,
            frames=NUMBER_OF_STEPS - current_step[0],
            interval=900,   # milliseconds between steps
            repeat=False
        )
        ani[0].event_source.start()

btn_play.on_clicked(on_play)
btn_next.on_clicked(on_next)

# ─────────────────────────────────────────────
# INITIAL DRAW (step 0 — before simulation runs)
# ─────────────────────────────────────────────

draw_map(0)
draw_graph()
plt.show()