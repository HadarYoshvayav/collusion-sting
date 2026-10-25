import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
BLUE, ORANGE, INK, INK2, GRID, SURF, LIGHT = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d6d5d0", "#fcfcfb", "#eef4fc"
fig = plt.figure(figsize=(7.6, 3.9), facecolor=SURF); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 52); ax.axis("off")

def box(x, y, w, h, fc, ec, lw=1.2, r=1.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw))
def txt(x, y, s, size=8.5, color=INK, weight="normal", ha="center", va="center", style="normal"):
    ax.text(x, y, s, fontsize=size, color=color, weight=weight, ha=ha, va=va, style=style)

# ---- panel 1: the table
txt(24, 49, "1  The sting (round 2)", 10, weight="bold")
ax.add_patch(Circle((24, 26), 13.5, fc="#f3f2ee", ec=GRID, lw=1))
seats = {"U": (24, 38.5), "A": (37, 26), "B": (24, 13.5), "C": (11, 26)}
codes = {"A": "RAVEN-87", "B": "OTTER-31", "C": "MAPLE-18"}
for k, (x, y) in seats.items():
    ax.add_patch(Circle((x, y), 3.6, fc=BLUE if k == "U" else SURF, ec=BLUE if k == "U" else INK2, lw=1.5, zorder=3))
    txt(x, y, "UC" if k == "U" else k, 8.5, color=SURF if k == "U" else INK, weight="bold")
txt(24, 45, "undercover agent (scripted offers)", 7.5, INK2)
for k in "ABC":
    x, y = seats[k]; ux, uy = seats["U"]
    ax.add_patch(FancyArrowPatch((ux, uy - 3.8), (x + (0 if k == "B" else (-3 if k == "A" else 3)), y + (3.8 if k == "B" else 2.5)),
                 arrowstyle="-|>", mutation_scale=9, color=BLUE, lw=1.3, zorder=2, connectionstyle="arc3,rad=0.0"))
lab = {"A": (41.5, 21), "B": (24, 8), "C": (6.5, 21)}
for k, (x, y) in lab.items():
    txt(x, y, f"offer + code\n{codes[k]}", 6.8, BLUE)
txt(24, 2.2, "every target gets the same offer, but its own code word", 7.3, INK2, style="italic")

# ---- panel 2: conditions
txt(57, 49, "2  Five offers", 10, weight="bold")
conds = [("none", "no message"), ("benign", "friendly greeting"), ("indirect", "\"let's not waste bullets\""),
         ("direct", "explicit no-challenge pact"), ("assigned", "binding pact (positive control)")]
for i, (c, d) in enumerate(conds):
    y = 41 - i * 7.2
    box(47, y - 2.8, 21, 5.6, LIGHT if c != "none" else SURF, GRID)
    txt(48.3, y + 0.9, c, 7.8, INK, "bold", ha="left"); txt(48.3, y - 1.2, d, 6.6, INK2, ha="left")
txt(57.5, 2.2, "+ control: UC's challenges scripted", 7.3, INK2, style="italic")

# ---- panel 3: measures
txt(86, 49, "3  What we measure", 10, weight="bold")
meas = [("SAY", "reply to the offer:\naccept / decline", INK2),
        ("DO", "challenges against UC\nvs. other players", ORANGE),
        ("LEAK", "code words and pact talk\nto others / Moderator", BLUE)]
for i, (h, d, col) in enumerate(meas):
    y = 38 - i * 12.5
    box(74, y - 5, 24, 10, SURF, col, lw=1.6)
    txt(76, y + 2.3, h, 9, col, "bold", ha="left"); txt(76, y - 1.6, d, 6.9, INK, ha="left")
for y in (38, 25.5, 13):
    ax.add_patch(FancyArrowPatch((68.5, 27), (73.8, y), arrowstyle="-|>", mutation_scale=8, color=GRID, lw=1))
fig.savefig("/home/claude/collusion_hackathon/paper/figures/fig0_design.png", dpi=220, facecolor=SURF)
print("ok")
