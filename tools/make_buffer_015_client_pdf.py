import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("tmp_matplotlib_cache").resolve()))

import matplotlib
matplotlib.use("Agg")

from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import numpy as np


OUT = "BUFFER_015_CLIENT_PRESENTATION_2026-07-01.pdf"

BG = "#071018"
PANEL = "#0d1b26"
TEXT = "#eaf2f8"
MUTED = "#9fb3c8"
GOLD = "#f6c453"
GREEN = "#25d083"
RED = "#ff5a6a"
CYAN = "#46d9ff"
BLUE = "#64a8ff"


def slide(title, subtitle=None):
    fig = plt.figure(figsize=(13.333, 7.5), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.text(0.055, 0.92, title, color=TEXT, fontsize=25, fontweight="bold", va="top")
    if subtitle:
        ax.text(0.057, 0.865, subtitle, color=MUTED, fontsize=12.5, va="top")
    ax.plot([0.055, 0.945], [0.84, 0.84], color="#17364a", lw=1.2)
    ax.text(0.945, 0.045, "QGAI | Buffer 0.15 Backtest Comparison | 2026-07-01",
            color="#6e8294", fontsize=8.5, ha="right")
    return fig, ax


def metric_card(ax, x, y, w, h, label, value, note="", color=TEXT):
    rect = plt.Rectangle((x, y), w, h, facecolor=PANEL, edgecolor="#1d4157", lw=1.1)
    ax.add_patch(rect)
    ax.text(x + 0.025, y + h - 0.06, label.upper(), color=MUTED, fontsize=9.5, fontweight="bold")
    ax.text(x + 0.025, y + h - 0.145, value, color=color, fontsize=24, fontweight="bold")
    if note:
        ax.text(x + 0.025, y + 0.045, note, color=MUTED, fontsize=9.5)


def add_table(ax, rows, col_labels, bbox, font_size=10.5, header_color="#123348"):
    tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", bbox=bbox)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(font_size)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#23495d")
        cell.set_linewidth(0.7)
        if r == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(color=TEXT, weight="bold")
        else:
            cell.set_facecolor("#091722" if r % 2 else "#0b1c28")
            cell.set_text_props(color=TEXT)
    return tbl


def save_title(pdf):
    fig, ax = slide("Buffer 0.15 Backtest Comparison",
                    "Old fixed-lot buffer sweep vs today's live_buffer_015 replay")
    ax.text(0.057, 0.72, "Client Presentation Summary", color=GOLD, fontsize=18, fontweight="bold")
    ax.text(0.057, 0.66, "Period tested: 2025-06-29 to 2026-06-29", color=TEXT, fontsize=15)
    ax.text(0.057, 0.60, "Core question: did today's run confirm the Buffer 0.15 edge?", color=MUTED, fontsize=14)

    metric_card(ax, 0.06, 0.34, 0.25, 0.16, "Total R", "+428.5R", "Today live_buffer_015", GREEN)
    metric_card(ax, 0.37, 0.34, 0.25, 0.16, "Win Rate", "65.7%", "Same as old buffer sweep", GREEN)
    metric_card(ax, 0.68, 0.34, 0.25, 0.16, "Move Capture", "9.7%", "Same captured efficiency", CYAN)

    ax.text(0.057, 0.22,
            "Executive read: the strategy edge is essentially unchanged. The main difference is sizing: today's run uses compounding/risk-based output, so drawdown and net return are not directly comparable to the fixed-lot sweep.",
            color=TEXT, fontsize=13.2, wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def save_kpi_comparison(pdf):
    fig, ax = slide("KPI Comparison", "Old buf_0.15 vs today's live_buffer_015")
    rows = [
        ["Trades", "600", "597", "-3"],
        ["Win rate", "65.7%", "65.7%", "Same"],
        ["Profit factor", "3.87", "4.27", "Today better"],
        ["Avg R", "+0.714", "+0.718", "Today slightly better"],
        ["Total R", "+428.6R", "+428.5R", "Almost same"],
        ["Real $ profit", "$43,070.00", "$1,989,022,277.36", "Today compounded"],
        ["Ending equity", "$53,070.00", "$1,989,032,277.36", "On $10,000 start"],
        ["Max drawdown", "2.9%", "10.8%", "Old safer"],
    ]
    add_table(ax, rows, ["Metric", "Old buf_0.15", "Today live_buffer_015", "Read"], [0.055, 0.13, 0.89, 0.68], 10.2)
    ax.text(0.07, 0.085,
            "Dollar values assume $10,000 starting equity. Today's dollar result is a compounding simulation.",
            color=GOLD, fontsize=12.5, fontweight="bold")
    pdf.savefig(fig)
    plt.close(fig)


def save_move_capture(pdf):
    fig, ax = slide("Move Capture", "Gold points captured are almost identical")
    labels = ["Old buf_0.15", "Today live_buffer_015"]
    values = [10767.4, 10750.2]
    colors = [GOLD, CYAN]
    bx = fig.add_axes([0.12, 0.26, 0.76, 0.45], facecolor=BG)
    bars = bx.bar(labels, values, color=colors, width=0.45)
    bx.set_ylim(10500, 10850)
    bx.set_ylabel("Total gold points", color=MUTED)
    bx.tick_params(colors=TEXT, labelsize=11)
    for spine in bx.spines.values():
        spine.set_color("#23495d")
    bx.grid(axis="y", color="#153040", alpha=0.45)
    for b, v in zip(bars, values):
        bx.text(b.get_x() + b.get_width() / 2, v + 10, f"{v:,.1f}", ha="center", color=TEXT, fontsize=13, fontweight="bold")

    ax.text(0.12, 0.17, "Difference: only 17.2 points across roughly 600 trades.", color=TEXT, fontsize=14)
    ax.text(0.12, 0.12, "Client read: movement capture is practically equal.", color=GOLD, fontsize=14, fontweight="bold")
    pdf.savefig(fig)
    plt.close(fig)


def save_risk_slide(pdf):
    fig, ax = slide("Risk And Sizing Read", "Why Max DD differs")
    metric_card(ax, 0.08, 0.56, 0.36, 0.18, "Old buf_0.15 DD", "2.9%", "Fixed lot 0.01, no compounding", GREEN)
    metric_card(ax, 0.56, 0.56, 0.36, 0.18, "Today DD", "10.8%", "Risk-based / compounding display", RED)

    bullets = [
        "The strategy results are nearly unchanged in R and move capture.",
        "The old report is the cleaner benchmark for risk comparison.",
        "Today's large net return is not a clean client KPI because compounding inflates the number.",
        "Use Total R, Profit Factor, Win Rate and Move Capture as the main comparison metrics.",
    ]
    y = 0.42
    for b in bullets:
        ax.text(0.11, y, "- " + b, color=TEXT, fontsize=14)
        y -= 0.075
    pdf.savefig(fig)
    plt.close(fig)


def save_compounding_100_trade_slide(pdf):
    fig, ax = slide("Compounding Reality Check", "Every 100 trades: R edge vs compounding display")
    rows = [
        ["1-100", "+116.2R", "+116.2R", "$34,872", "$259,427", "$269,427"],
        ["101-200", "+65.8R", "+182.1R", "$54,621", "$1,757,176", "$1,767,176"],
        ["201-300", "+48.1R", "+230.1R", "$69,038", "$6,898,845", "$6,908,845"],
        ["301-400", "+74.5R", "+304.6R", "$91,374", "$58,211,426", "$58,221,426"],
        ["401-500", "+52.8R", "+357.4R", "$107,220", "$260,045,257", "$260,055,257"],
        ["501-597", "+71.1R", "+428.5R", "$128,563", "$1,989,022,277", "$1,989,032,277"],
    ]
    add_table(
        ax,
        rows,
        ["Trades", "Block R", "Cum R", "Fixed 3% Profit", "Compounded Profit", "Ending Equity"],
        [0.055, 0.21, 0.89, 0.55],
        9.0,
    )
    ax.text(0.065, 0.135,
            "Dollar amounts assume $10,000 starting equity. Compounded profit is a growth simulation, not the clean strategy-quality metric.",
            color=GOLD, fontsize=12.4, fontweight="bold", wrap=True)
    ax.text(0.065, 0.085,
            "Old buf_0.15 exact per-trade CSV was not retained; this 100-trade compounding view uses today's full trade CSV.",
            color=MUTED, fontsize=10.5)
    pdf.savefig(fig)
    plt.close(fig)


def save_exit_reasons(pdf):
    fig, ax = slide("Exit Behavior", "Exit reason counts stayed nearly the same")
    rows = [
        ["FLIP", "237", "237", "Same"],
        ["TPCAP", "231", "229", "Today -2"],
        ["TRAIL", "74", "74", "Same"],
        ["SL", "58", "57", "Today -1"],
    ]
    add_table(ax, rows, ["Exit Reason", "Old buf_0.15", "Today live_buffer_015", "Difference"], [0.12, 0.25, 0.76, 0.45], 13)
    ax.text(0.12, 0.16, "Takeaway: exit behavior did not materially change.", color=GOLD, fontsize=14, fontweight="bold")
    pdf.savefig(fig)
    plt.close(fig)


def save_conclusion(pdf):
    fig, ax = slide("Conclusion", "Recommended client-facing message")
    ax.text(0.08, 0.70, "Buffer 0.15 remains the cleaner benchmark.", color=GOLD, fontsize=22, fontweight="bold")
    ax.text(0.08, 0.61, "Today's run confirms the same edge:", color=TEXT, fontsize=15)
    points = [
        "Win rate held at 65.7%",
        "Total R stayed around +428R",
        "Move capture stayed near +10,750 gold points",
        "Profit factor improved from 3.87 to 4.27",
    ]
    y = 0.53
    for p in points:
        ax.text(0.11, y, "- " + p, color=TEXT, fontsize=14)
        y -= 0.07

    ax.text(0.08, 0.20,
            "Client caveat: compare drawdown using fixed-lot outputs. Today's compounding view is useful for growth simulation, not clean strategy benchmarking.",
            color=RED, fontsize=13.5, fontweight="bold", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def main():
    with PdfPages(OUT) as pdf:
        save_title(pdf)
        save_kpi_comparison(pdf)
        save_move_capture(pdf)
        save_risk_slide(pdf)
        save_compounding_100_trade_slide(pdf)
        save_exit_reasons(pdf)
        save_conclusion(pdf)
    print(OUT)


if __name__ == "__main__":
    main()
