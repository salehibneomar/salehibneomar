"""Render the public GitHub contribution calendar as local, theme-aware SVGs."""

from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen

USERNAME = "salehibneomar"
ASSETS = Path(__file__).resolve().parents[1] / "assets"


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.counts = {}
        self.tooltip_id = None
        self.tooltip_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.days[attrs["id"]] = (
                date.fromisoformat(attrs["data-date"]), int(attrs["data-level"])
            )
        if tag == "tool-tip":
            self.tooltip_id = attrs.get("for")
            self.tooltip_text = []

    def handle_data(self, data):
        if self.tooltip_id:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip_id:
            match = re.match(r"(No|[\d,]+) contributions? on ", "".join(self.tooltip_text))
            if match:
                self.counts[self.tooltip_id] = (
                    0 if match[1] == "No" else int(match[1].replace(",", ""))
                )
            self.tooltip_id = None


def render(parser, theme):
    days = sorted((day, level, parser.counts[key]) for key, (day, level) in parser.days.items())
    start, end = days[0][0], days[-1][0]
    origin = start - timedelta(days=(start.weekday() + 1) % 7)
    total = sum(count for _, _, count in days)
    active = sum(count > 0 for _, _, count in days)
    dark = theme == "dark"
    bg, ink, muted, border = ("#0d1117", "#f0f6fc", "#9ba9ba", "#263444") if dark else ("#f6f8fa", "#172b3a", "#526578", "#d4dee6")
    colors = ["#1b2632", "#14533e", "#16845b", "#2fbd87", "#63e6be"] if dark else ["#e1e8ed", "#b1e9d1", "#69cda5", "#26a775", "#087f64"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="310" viewBox="0 0 1200 310" role="img" aria-labelledby="title desc">',
             '<title id="title">GitHub contribution heatmap</title>',
             f'<desc id="desc">{total:,} contributions across {active} active days, {start.isoformat()} to {end.isoformat()}.</desc>',
             f'<rect x="1" y="1" width="1198" height="308" rx="20" fill="{bg}" stroke="{border}"/>',
             '<g font-family="DejaVu Sans,Arial,sans-serif">',
             f'<text x="36" y="42" fill="{ink}" font-size="20" font-weight="700">{total:,} contributions</text>',
             f'<text x="1164" y="42" text-anchor="end" fill="{muted}" font-size="14">{active} active days · past year</text>']
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        parts.append(f'<text x="36" y="{102 + row * 21}" fill="{muted}" font-size="12">{label}</text>')
    last_month = None
    for day, level, count in days:
        col, row = divmod((day - origin).days, 7)
        x, y = 81 + col * 20, 88 + row * 21
        if day.month != last_month and (day.day <= 7 or last_month is None):
            parts.append(f'<text x="{x}" y="75" fill="{muted}" font-size="12">{day.strftime("%b")}</text>')
            last_month = day.month
        label = escape(f'{day.isoformat()}: {count} contributions')
        parts.append(f'<rect x="{x}" y="{y}" width="15" height="15" rx="3" fill="{colors[level]}"><title>{label}</title></rect>')
    parts.append(f'<text x="36" y="278" fill="{muted}" font-size="12">{USERNAME} · {start:%d %b %Y} – {end:%d %b %Y}</text>')
    parts.append(f'<text x="985" y="278" fill="{muted}" font-size="12">Less</text>')
    for level, color in enumerate(colors):
        parts.append(f'<rect x="{1022 + level * 20}" y="266" width="15" height="15" rx="3" fill="{color}"/>')
    parts.append(f'<text x="1126" y="278" fill="{muted}" font-size="12">More</text></g></svg>')
    return "\n".join(parts) + "\n"


def main():
    request = Request(f"https://github.com/users/{USERNAME}/contributions", headers={"User-Agent": "GitHub-Profile-Calendar"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
    parser = CalendarParser()
    parser.feed(html)
    # Fail without replacing the existing images if GitHub changes its markup.
    if len(parser.days) < 350 or not parser.days.keys() <= parser.counts.keys():
        raise ValueError("Incomplete GitHub calendar; keeping existing heatmaps")
    if any(level not in range(5) for _, level in parser.days.values()):
        raise ValueError("Unknown contribution level")
    images = {theme: render(parser, theme) for theme in ("dark", "light")}
    for theme, svg in images.items():
        (ASSETS / f"contributions-{theme}.svg").write_text(svg)
    print(f"Updated contribution heatmaps: {len(parser.days)} days")


if __name__ == "__main__":
    main()
