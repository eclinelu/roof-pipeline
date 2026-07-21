# Market analysis PDF for the roof-measurement pipeline.
#
#   python scripts/market_analysis_report.py
#
# This is GLUE, not analysis of the point cloud. It renders the market-research
# findings (gathered 2026-07-20, sourced on the last page) into a mostly-written
# report with supporting charts and tables. Every number here is a sourced
# figure or a clearly labeled estimate; nothing is invented at render time.
#
# Toolchain matches build_report.py on purpose: matplotlib for both the charts
# and the PDF assembly (PdfPages), so the market report is reproducible with a
# single command and sits visually alongside the per-house roof reports.
#
# Design: categorical color uses the Okabe-Ito colorblind-safe order (dataviz
# skill: fixed-order categorical, never cycled). Status colors (green/amber/red)
# are reserved for verdicts only. Ink/accent/rule reuse the house-report palette.
import datetime
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render to file; no display needed
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import numpy as np

# Treat "$" as a literal dollar sign, not the start of a math expression.
# Without this, any string with two dollar signs (e.g. "$13-38 and $87") gets
# the text between them rendered as italic math with the spaces eaten.
plt.rcParams["text.parse_math"] = False

REPO_ROOT = Path(__file__).resolve().parents[1]
LETTER = (8.5, 11.0)  # US Letter portrait, inches

# --- Palette (house-report ink/accent + reserved status + CVD-safe categorical)
INK = "#1a1a2e"
ACCENT = "#0b5394"
MUTED = "#6b7280"
RULE = "#c9ced6"
PANEL = "#eef3f8"
GREEN = "#2e7d32"   # status: strong / go
AMBER = "#b26a00"   # status: niche / caution
RED = "#c62828"     # status: closed / weak
# Okabe-Ito categorical order (colorblind-safe by construction).
CAT = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]

TODAY = datetime.date.today().isoformat()

# ==========================================================================
# Findings as data (sourced; see page_sources for the reference list)
# ==========================================================================

# Verticals ranked best-fit first: (name, fit 0-5, verdict word, status color)
VERTICALS = [
    ("Solar design", 5.0, "Strongest fit", GREEN),
    ("Complex / new-construction roofs", 4.0, "Real niche", GREEN),
    ("Telecom / structure inspection", 2.5, "Adjacent", AMBER),
    ("Insurance / claims", 2.0, "Big but closed", RED),
    ("Property assessment", 1.5, "Closed (data giants)", RED),
    ("Real estate (Tyco's world)", 1.0, "Weak fit", RED),
]

# Pricing gap: (provider, low, high, is_you)
PRICING = [
    ("Roofr report", 13, 19, False),
    ("EagleView report", 13, 38, False),
    ("You: drone job", 150, 400, True),
]

# Competitive landscape table rows.
COMPETITORS = [
    ["Roofr", "Satellite imagery", "$13-19 / report", "< 3 hr", "No"],
    ["EagleView", "Aerial imagery library", "$13-38 (to $87)", "Min-hours", "No"],
    ["Hover", "Phone photogrammetry", "Free / $149+/mo", "Same day", "Homeowner"],
    ["Scanifly", "Drone photogram. (solar)", "$1,499 / yr sw", "Same day", "Drone"],
    ["You (MaaS)", "Drone photogrammetry", "$150-400 / job", "Same/next day", "Drone"],
]

# TAM / SAM / SOM (label, value string, sub, note)
SIZING = [
    ("TAM", "$0.2-0.9B / yr",
     "US drone-based roof/property\nmeasurement + inspection niche",
     "Inside a $15B+ drone-services and $31B roofing economy. Growing 14-19%/yr."),
    ("SAM", "$50k-200k / yr",
     "Drone-worthy jobs in the\nBurlington (Chittenden) metro",
     "The precision/complex/inspection slice of local roof + solar work."),
    ("SOM", "$5k-35k / yr",
     "You, part-time, over 3-5 yr\n(~30-100 jobs/yr)",
     "A viable side income at this configuration. Not a company."),
]

# Bottom-up local funnel: (label, jobs_per_year, detail)
FUNNEL = [
    ("Annual roof + solar jobs\nin Chittenden County", 3600,
     "~3,100 re-roofs (4%/yr of 77,900 homes) + ~500 solar installs"),
    ("Drone-worthy, premium-paying\nslice", 400,
     "Complex / tall / new-build / tree-obscured roofs + solar-grade designs"),
    ("Realistic part-time capture\n(your SOM)", 65,
     "One certified solo operator, side project, mid-point of 30-100"),
]

SOURCES = [
    ("EagleView pricing", "getapp.com/construction-software/a/eagleview/pricing"),
    ("Roofr pricing update 2025", "roofr.com/product-blog (pricing update)"),
    ("EagleView vs Hover", "roofingsoftwareguide.com/comparisons/eagleview-vs-hover"),
    ("Drone vs satellite accuracy", "airteam.ai (2025 drone/satellite/aircraft)"),
    ("Scanifly accuracy", "scanifly.com/blog/how-accurate-is-scanifly-software"),
    ("Aurora Solar LIDAR shading", "aurorasolar.com/blog (LIDAR remote design)"),
    ("Cape Analytics + Vexcel", "prnewswire.com (Cape-Vexcel imagery partnership)"),
    ("US roofing market size", "mordorintelligence.com (United States roofing)"),
    ("Chittenden Co. housing (77,866 units)", "censusreporter.org (Chittenden Co, VT)"),
    ("VT solar net metering", "solarpowerworldonline.com (VT net metering 2024)"),
    ("US residential solar -31% in 2024", "pv-magazine.com (2025-03-14)"),
    ("Drone roof inspection $150-400/job", "homeguide.com (drone roof inspection cost)"),
    ("Drone tower inspection market", "factmr.com (drone tower inspection)"),
]


# ==========================================================================
# Page furniture
# ==========================================================================

def wrap(text, width):
    out = []
    for para in (text or "").split("\n"):
        out.append(textwrap.fill(para, width) if para else "")
    return "\n".join(out)


def new_page(page_no, section):
    """Header band + footer; return the figure."""
    fig = plt.figure(figsize=LETTER)
    fig.patches.append(Rectangle((0, 0.945), 1.0, 0.055,
                                 transform=fig.transFigure,
                                 facecolor=ACCENT, edgecolor="none", zorder=-1))
    fig.text(0.06, 0.973, "MARKET ANALYSIS", color="white", fontsize=9,
             fontweight="bold", va="center", alpha=0.9)
    fig.text(0.06, 0.958, "Drone-derived roof measurement pipeline",
             color="white", fontsize=11, va="center")
    fig.text(0.94, 0.966, section, color="white", fontsize=12,
             fontweight="bold", va="center", ha="right")
    fig.text(0.06, 0.02, "Prepared for Emmett Lucey  |  internal strategy memo",
             color=MUTED, fontsize=6.5, va="center")
    fig.text(0.94, 0.02, f"{TODAY}   p.{page_no}", color=MUTED, fontsize=6.5,
             va="center", ha="right")
    return fig


def body(fig, x, y, text, width=104, size=9, color=INK, bold=False, va="top"):
    fig.text(x, y, wrap(text, width), fontsize=size, color=color, va=va,
             fontweight="bold" if bold else "normal")


def head(fig, x, y, text, color=ACCENT, size=11):
    fig.text(x, y, text, fontsize=size, fontweight="bold", color=color)


def stat_tile(fig, rect, big, small, accent=ACCENT, big_size=15):
    ax = fig.add_axes(rect); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                           facecolor=PANEL, edgecolor=accent, lw=1.3))
    ax.text(0.5, 0.62, big, ha="center", va="center", fontsize=big_size,
            fontweight="bold", color=INK, transform=ax.transAxes)
    ax.text(0.5, 0.24, small, ha="center", va="center", fontsize=8,
            color=MUTED, transform=ax.transAxes)


def style_table(tbl, widths=None):
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor(RULE)
        if widths is not None:
            cell.set_width(widths[col])
        if row == 0:
            cell.set_facecolor(ACCENT)
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#f6f7f9")


# ==========================================================================
# Page 1: Cover / headline
# ==========================================================================

def page_cover(pdf):
    fig = new_page(1, "Summary")
    fig.text(0.06, 0.88, "Does this product have real-world validity?",
             fontsize=22, fontweight="bold", color=INK)
    fig.text(0.06, 0.845, "Roofing, solar, and adjacent industries  |  "
             "Burlington, Vermont focus", fontsize=11, color=MUTED)

    verdict = ("Bottom line: drone-based roof measurement is a proven, "
               "defensible product in one place, solar, where precision has "
               "money attached. In commodity roofing you cannot win: incumbents "
               "give away instant measurement reports for $13-38 with no site "
               "visit, and a drone job costs $150-400 just to show up. Your "
               "validated-accuracy edge is real, but it only pays where accuracy "
               "is worth a premium: solar design, complex or unmapped roofs, and "
               "defensible inspection. In Burlington, as a part-time solo "
               "operator, this is a good side income, not a company.")
    fig.add_axes([0.06, 0.63, 0.88, 0.16]).axis("off")
    fig.patches.append(Rectangle((0.06, 0.63), 0.88, 0.16,
                       transform=fig.transFigure, facecolor=PANEL,
                       edgecolor=ACCENT, lw=1.3, zorder=-1))
    body(fig, 0.08, 0.77, verdict, width=96, size=9.5)

    # Three headline stat tiles.
    stat_tile(fig, [0.06, 0.44, 0.27, 0.14], "Solar", "best-fit vertical")
    stat_tile(fig, [0.365, 0.44, 0.27, 0.14], "$5-35k/yr", "realistic SOM (side project)")
    stat_tile(fig, [0.67, 0.44, 0.27, 0.14], "Side income", "not a venture, as configured",
              accent=AMBER)

    head(fig, 0.06, 0.38, "What you are holding")
    body(fig, 0.06, 0.36,
         "A decision memo, not research theater. It ranks seven candidate "
         "verticals by fit, shows why commodity roofing is a price trap, sizes "
         "the Burlington opportunity bottom-up, resolves the Tyco question with "
         "evidence, and states the downside cases. Every figure is sourced on "
         "the final page or labeled an estimate.", width=104, size=9)

    head(fig, 0.06, 0.29, "How to read the recommendation")
    body(fig, 0.06, 0.27,
         "Three goals were in play: is it a real business, which vertical wins, "
         "and an honest validity check. The answer differs by goal, so the "
         "recommendation on p.5 is split three ways rather than forced into one "
         "verdict.", width=104, size=9)

    fig.text(0.06, 0.08, "Scope note", fontsize=8.5, fontweight="bold", color=MUTED)
    body(fig, 0.06, 0.065,
         "Measurement-as-a-service is the base case (you fly, sell a report per "
         "job). The national contractor-kit model is treated as an upside "
         "scenario, gated by the Part 107 adoption barrier. Software-for-"
         "installers is noted, not anchored on.", width=104, size=8, color=MUTED)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 2: Executive summary + vertical ranking chart
# ==========================================================================

def page_ranking(pdf):
    fig = new_page(2, "Where it fits")
    head(fig, 0.06, 0.90, "Vertical ranking (best fit first)", size=13)
    body(fig, 0.06, 0.885,
         "Fit is a judgment score (0-5) combining how much the buyer values "
         "measurement precision against how open the market is to a solo local "
         "operator. Bars are colored by verdict, not by rank.",
         width=108, size=8.5, color=MUTED)

    ax = fig.add_axes([0.34, 0.50, 0.60, 0.34])
    names = [v[0] for v in VERTICALS][::-1]
    scores = [v[1] for v in VERTICALS][::-1]
    colors = [v[3] for v in VERTICALS][::-1]
    verdicts = [v[2] for v in VERTICALS][::-1]
    ypos = np.arange(len(names))
    ax.barh(ypos, scores, color=colors, height=0.62, zorder=3)
    ax.set_yticks(ypos); ax.set_yticklabels(names, fontsize=8.5, color=INK)
    ax.set_xlim(0, 5.6); ax.set_xticks(range(6))
    ax.tick_params(labelsize=8, colors=MUTED)
    ax.set_xlabel("fit score (0-5)", fontsize=8, color=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor(RULE)
    ax.grid(axis="x", color=RULE, lw=0.6, zorder=0)
    for y, sc, vd in zip(ypos, scores, verdicts):
        ax.text(sc + 0.12, y, vd, va="center", fontsize=7.5, color=MUTED)

    # Status legend (reserved status colors, with words not color alone).
    lx = 0.06
    fig.text(lx, 0.50, "Verdict key", fontsize=8.5, fontweight="bold", color=INK)
    for i, (word, c) in enumerate([("Strong", GREEN), ("Adjacent", AMBER),
                                   ("Closed / weak", RED)]):
        yy = 0.478 - i * 0.022
        fig.patches.append(Rectangle((lx, yy - 0.004), 0.018, 0.013,
                           transform=fig.transFigure, facecolor=c,
                           edgecolor="none"))
        fig.text(lx + 0.026, yy, word, fontsize=8, color=INK, va="center")

    head(fig, 0.06, 0.42, "The two findings that matter")
    body(fig, 0.06, 0.40,
         "1. Solar is the one vertical where drone photogrammetry already won. "
         "Scanifly, effectively the company version of this pipeline, sells "
         "1-3 inch drone-derived solar designs because panel fit, shading, and "
         "lender bankability put real money on precision. Vermont's strong net-"
         "metering incentives keep local solar demand alive.", width=104, size=9)
    body(fig, 0.06, 0.315,
         "2. The vertical this project was born from, real estate, is the worst "
         "fit. Real estate buyers want imagery and video, not roof measurements. "
         "Your product does not serve Tyco's customers' actual need. That sounds "
         "like bad news but it dissolves the conflict: you are not competing with "
         "his business (see p.5).", width=104, size=9)

    head(fig, 0.06, 0.235, "Why the closed markets are closed")
    body(fig, 0.06, 0.215,
         "Insurance, claims, and property assessment are enormous and measurement-"
         "hungry, but already owned by aerial-data giants: Cape Analytics, Vexcel, "
         "and Nearmap sell property intelligence to all of the top-10 P&C carriers "
         "at national scale. That is an enterprise data business, not a job a "
         "certified solo pilot in Burlington can win. Telecom and structure "
         "inspection grow fast (~16%/yr) but are an inspection market needing "
         "different skills, not a measurement wedge for this pipeline.",
         width=104, size=9)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 3: The pricing crux + competitive table
# ==========================================================================

def page_pricing(pdf):
    fig = new_page(3, "The pricing crux")
    head(fig, 0.06, 0.90, "Why commodity roofing is a price trap", size=13)
    body(fig, 0.06, 0.885,
         "This one chart is the whole game. For a simple roof, incumbents deliver "
         "a measurement report from existing imagery in minutes for the price of "
         "lunch. Your drone has to physically show up. You are 5-10x the price "
         "and slower, and that gap is the market telling you the commodity report "
         "is a solved problem.", width=108, size=8.5, color=MUTED)

    ax = fig.add_axes([0.30, 0.55, 0.64, 0.28])
    labels = [p[0] for p in PRICING][::-1]
    lows = np.array([p[1] for p in PRICING][::-1])
    highs = np.array([p[2] for p in PRICING][::-1])
    is_you = [p[3] for p in PRICING][::-1]
    ypos = np.arange(len(labels))
    bar_colors = [ACCENT if not y else RED for y in is_you]
    ax.barh(ypos, highs - lows, left=lows, height=0.55, color=bar_colors,
            zorder=3)
    for y, lo, hi in zip(ypos, lows, highs):
        ax.text(hi + 8, y, f"${lo}-{hi}", va="center", fontsize=8.5,
                color=INK, fontweight="bold")
    ax.set_yticks(ypos); ax.set_yticklabels(labels, fontsize=9, color=INK)
    ax.set_xlim(0, 470); ax.set_xlabel("price per roof ($)", fontsize=8,
                                       color=MUTED)
    ax.tick_params(labelsize=8, colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor(RULE)
    ax.grid(axis="x", color=RULE, lw=0.6, zorder=0)

    head(fig, 0.06, 0.49, "Competitive landscape")
    rows = COMPETITORS
    ax2 = fig.add_axes([0.06, 0.27, 0.88, 0.20]); ax2.axis("off")
    tbl = ax2.table(cellText=rows,
                    colLabels=["Player", "Method", "Price", "Speed",
                               "Site visit?"],
                    loc="upper center", cellLoc="left")
    tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.6)
    style_table(tbl, widths=[0.15, 0.28, 0.20, 0.17, 0.20])
    # Highlight the "you" row.
    for col in range(5):
        c = tbl[len(rows), col]
        c.set_facecolor("#fdecea"); c.set_text_props(color=INK, fontweight="bold")

    body(fig, 0.06, 0.22,
         "The takeaway is not that your product is worse. It is that the drone "
         "visit only pays when it delivers something the $13 report cannot: solar-"
         "grade precision, a roof the satellite cannot see (new construction, "
         "heavy tree cover, very steep or tall), or an inspection with liability "
         "attached. Sell those jobs. Never try to beat $13 on a simple suburban "
         "roof, because you cannot.", width=104, size=9)
    body(fig, 0.06, 0.13,
         "Note the incumbents are also moving: EagleView One and Hover's 2026 "
         "relaunch both add 3D building models. If they close the complex-roof "
         "gap, the wedge narrows. This is tracked as a risk on p.6.",
         width=104, size=9, color=MUTED)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 4: Market sizing (TAM/SAM/SOM tiles + bottom-up funnel)
# ==========================================================================

def page_sizing(pdf):
    fig = new_page(4, "Market sizing")
    head(fig, 0.06, 0.90, "How big is it, honestly", size=13)
    body(fig, 0.06, 0.885,
         "TAM is national context; the number that matters to you is the bottom-"
         "up local funnel. The three tiers are in different units of scale (a "
         "national niche vs one part-time operator), so they are shown as tiles, "
         "not a single misleading funnel.", width=108, size=8.5, color=MUTED)

    xs = [0.06, 0.365, 0.67]
    for x, (label, val, sub, note) in zip(xs, SIZING):
        stat_tile(fig, [x, 0.70, 0.27, 0.135], val, label, big_size=13)
    # Full description under each tile (tier name is on the tile itself).
    for x, (label, val, sub, note) in zip(xs, SIZING):
        text = sub.replace("\n", " ") + "  " + note
        fig.text(x, 0.685, wrap(text, 44), fontsize=6.8, color=MUTED, va="top")

    # Bottom-up funnel (same unit: jobs/year), so it is honest.
    head(fig, 0.06, 0.58, "Bottom-up: annual jobs in Chittenden County")
    ax = fig.add_axes([0.06, 0.28, 0.58, 0.27]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 0.9)
    widths = [1.0, 0.55, 0.34]  # visual funnel proportions (not to scale)
    yb = [0.66, 0.36, 0.06]
    for (label, jobs, detail), w, y, c in zip(FUNNEL, widths, yb, CAT):
        left = (1 - w) / 2
        ax.add_patch(Rectangle((left, y), w, 0.22, facecolor=c, alpha=0.9,
                     edgecolor="white", lw=1.5))
        ax.text(0.5, y + 0.11, f"{jobs:,} jobs/yr", ha="center", va="center",
                fontsize=11, fontweight="bold", color="white")

    # Funnel step detail on the right, each aligned to its bar.
    for (label, jobs, detail), yy, c in zip(FUNNEL, [0.49, 0.41, 0.33], CAT):
        fig.patches.append(Rectangle((0.67, yy + 0.006), 0.015, 0.011,
                           transform=fig.transFigure, facecolor=c,
                           edgecolor="none"))
        fig.text(0.692, yy + 0.013, wrap(label.replace("\n", " "), 30),
                 fontsize=7.5, fontweight="bold", color=INK, va="top")
        fig.text(0.692, yy - 0.024, wrap(detail, 34), fontsize=6.8,
                 color=MUTED, va="top")

    head(fig, 0.06, 0.22, "Assumptions you confirmed")
    body(fig, 0.06, 0.20,
         "Two levers drive the SOM: a ~4%/yr roof-replacement rate (a 20-25 year "
         "roof life) applied to Chittenden's 77,900 housing units, and ~30-100 "
         "jobs/yr of realistic part-time capacity for one certified operator. At "
         "$150-350 per drone job, that lands at roughly $5k-35k/yr gross, low "
         "five figures net after drone, insurance, software, and Part 107 costs.",
         width=104, size=9)
    body(fig, 0.06, 0.11,
         "The national TAM (~$0.2-0.9B/yr for drone-based roof/property "
         "measurement and inspection) confirms the industry is real and growing "
         "14-19%/yr. It does not change the local reality: as a side project, the "
         "ceiling is a good second income, and the throughput cap is you, one "
         "pilot with a Part 107.", width=104, size=9, color=MUTED)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 5: Tyco + recommendation
# ==========================================================================

def page_recommendation(pdf):
    fig = new_page(5, "Tyco & the call")
    head(fig, 0.06, 0.90, "The Tyco question, answered with evidence", size=13)
    body(fig, 0.06, 0.88,
         "The research resolves this more easily than you feared. There is no "
         "conflict, because Tyco's customers do not want what you built. Real "
         "estate buyers want video and stills, not roof measurements. So you are "
         "not secretly competing with his business or repurposing his clients.",
         width=104, size=9.5)
    body(fig, 0.06, 0.80,
         "The real synergy with Tyco is not the product, it is the shared "
         "infrastructure: he already holds a Part 107, flies a drone, has capture "
         "skill and local reputation. That makes him a natural capture partner or "
         "referral source (he flies or refers the solar and complex-roof leads he "
         "cannot serve), not a customer and not someone you are deceiving. The "
         "honest framing costs you nothing to say out loud: you are building an "
         "adjacent thing that can ride alongside his operation, not a thing for "
         "him.", width=104, size=9.5)

    head(fig, 0.06, 0.67, "Recommendation, split by your three goals")
    recs = [
        ("If the goal is income now", GREEN,
         "Run it as a solar-and-complex-roof drone service in Chittenden County, "
         "not a general roof-measurement service. Skip commodity roofing "
         "entirely. Partner loosely with Tyco for capture and referrals, and tell "
         "him plainly what it is."),
        ("If the goal is a real business", AMBER,
         "The only version that scales is Scanifly's model, software for solar "
         "installers, and you would be entering behind a funded incumbent. Worth "
         "knowing; probably not worth doing as a student side project."),
        ("For the resume / interview goal", ACCENT,
         "This analysis is itself the asset. 'I built a validated-accuracy "
         "pipeline, then found through market analysis that the defensible market "
         "was solar, not the roofing/real-estate use I started from' is a strong, "
         "honest engineering-and-judgment story."),
    ]
    y = 0.64
    for title, c, txt in recs:
        fig.patches.append(Rectangle((0.06, y - 0.075), 0.88, 0.088,
                           transform=fig.transFigure, facecolor=PANEL,
                           edgecolor=c, lw=1.3, zorder=-1))
        fig.text(0.08, y - 0.005, title, fontsize=10, fontweight="bold", color=c)
        body(fig, 0.08, y - 0.028, txt, width=100, size=8.7)
        y -= 0.11

    head(fig, 0.06, 0.24, "The one-line strategy")
    body(fig, 0.06, 0.22,
         "Sell precision where precision is worth paying for (solar, complex "
         "roofs, defensible inspection), around Burlington, part-time, with Tyco "
         "as a capture ally. Do not compete on price, speed, or simple roofs; "
         "those belong to the imagery incumbents and always will.",
         width=104, size=9.5)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 6: Risks + sources
# ==========================================================================

def page_risks(pdf):
    fig = new_page(6, "Risks & sources")
    head(fig, 0.06, 0.90, "Risks and counterarguments", size=13)
    risks = [
        ("Incumbents move down-market", RED,
         "EagleView One and Hover's 2026 relaunch add 3D building models. If they "
         "close the complex-roof gap, your niche shrinks."),
        ("Solar is in a cyclical dip", AMBER,
         "US residential solar fell ~31% in 2024 on high interest rates and net-"
         "metering cuts. Your best vertical is soft right now."),
        ("Part 107 caps throughput", AMBER,
         "The certification is a moat against competitors, but also the reason the "
         "SOM is small: one part-time pilot has a hard capacity ceiling."),
        ("The scalable path is the one you dislike", AMBER,
         "Scanifly proves the winning model is software sold to installers, not "
         "measurement-as-a-service. The venture-scale version is the software play "
         "you set aside."),
    ]
    y = 0.855
    for title, c, txt in risks:
        fig.patches.append(Rectangle((0.06, y - 0.052), 0.018, 0.04,
                           transform=fig.transFigure, facecolor=c,
                           edgecolor="none"))
        fig.text(0.09, y, title, fontsize=10, fontweight="bold", color=INK)
        body(fig, 0.09, y - 0.016, txt, width=98, size=8.7, color=MUTED)
        y -= 0.078

    head(fig, 0.06, 0.50, "Method & honesty note")
    body(fig, 0.06, 0.48,
         "Sizing uses top-down market reports for context and a bottom-up job "
         "count for the local reality; every leap is labeled. Figures are as of "
         "July 2026 and will drift. This is a decision memo, so it commits to a "
         "recommendation rather than hedging, and states its downside cases above "
         "rather than burying them.", width=104, size=9)

    head(fig, 0.06, 0.40, "Sources")
    ax = fig.add_axes([0.06, 0.06, 0.88, 0.31]); ax.axis("off")
    rows = [[s[0], s[1]] for s in SOURCES]
    tbl = ax.table(cellText=rows, colLabels=["Claim", "Source"],
                   loc="upper center", cellLoc="left")
    tbl.auto_set_font_size(False); tbl.set_fontsize(7.5); tbl.scale(1, 1.35)
    style_table(tbl, widths=[0.40, 0.60])
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# main
# ==========================================================================

def main():
    out_dir = REPO_ROOT / "reports" / "market_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"market-analysis-{TODAY}.pdf"
    with PdfPages(out) as pdf:
        page_cover(pdf)
        page_ranking(pdf)
        page_pricing(pdf)
        page_sizing(pdf)
        page_recommendation(pdf)
        page_risks(pdf)
        d = pdf.infodict()
        d["Title"] = "Market Analysis - Drone Roof Measurement Pipeline"
        d["Subject"] = ("Validity of a drone-derived roof measurement product "
                        "across roofing, solar, and adjacent industries")
        d["Author"] = "Emmett Lucey"
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
