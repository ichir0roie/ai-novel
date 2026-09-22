#!/usr/bin/env python3
"""星一つぶんの平板図(経度=横、緯度=縦)を SVG 文字列にする。"""
from __future__ import annotations

from collections import defaultdict
from xml.sax.saxutils import escape

from DEM.tool.map.layout import fit_frame, place_labels

__all__ = ["COLORS", "layers_of", "marker", "alt_text", "render_svg"]

COLORS = ("#c0392b", "#2471a3", "#1e8449", "#b9770e", "#7d3c98",
          "#148f77", "#a04000", "#5d6d7e", "#d4ac0d", "#884ea0")

_MARGIN_RIGHT = 200     # 凡例
_MARGIN_BOTTOM = 40
_NO_PARENT = "(親なし)"


def layers_of(points: list[dict]) -> list[str]:
    """親の名でまとめる。大陸(面)の子を先に、それ以外を後に並べて色と記号を振る。"""
    seen: dict[str, str] = {}
    for p in points:
        seen.setdefault(p["parent_name"] or _NO_PARENT, p["parent_kind"] or "")
    return sorted(seen, key=lambda name: (seen[name] != "大陸", name))


def marker(kind_of_parent: str | None, x: float, y: float, r: float, color: str, extra: str = "") -> str:
    if kind_of_parent == "大陸":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" stroke="#fff" stroke-width="1" {extra}/>'
    d = f"M{x:.1f},{y - r:.1f} L{x + r:.1f},{y:.1f} L{x:.1f},{y + r:.1f} L{x - r:.1f},{y:.1f} Z"
    return f'<path d="{d}" fill="{color}" stroke="#fff" stroke-width="1" {extra}/>'


def alt_text(alt) -> str:
    if alt is None:
        return ""
    return f" ({alt:+,.0f} m)"


def _grid(frame) -> list[str]:
    out = []
    step = frame.grid_step()
    x0, x1, y0, y1 = frame.x(frame.lon_min), frame.x(frame.lon_max), frame.y(frame.lat_max), frame.y(frame.lat_min)
    for lon in range(int(frame.lon_min), int(frame.lon_max) + 1, step):
        x = frame.x(lon)
        strong = lon == 0
        out.append(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
                   f'stroke="{"#666" if strong else "#c8d0d8"}" stroke-width="{1.2 if strong else 0.6}"/>')
        out.append(f'<text x="{x:.1f}" y="{y1 + 14:.1f}" text-anchor="middle" fill="#555">{lon}°</text>')
    for lat in range(int(frame.lat_min), int(frame.lat_max) + 1, step):
        y = frame.y(lat)
        strong = lat == 0
        out.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
                   f'stroke="{"#666" if strong else "#c8d0d8"}" stroke-width="{1.2 if strong else 0.6}"/>')
        out.append(f'<text x="{x0 - 6:.1f}" y="{y + 4:.1f}" text-anchor="end" fill="#555">{lat}°</text>')
    return out


def render_svg(planet: dict, points: list[dict]) -> str:
    frame = fit_frame(points)
    width = frame.left + frame.plot_width + _MARGIN_RIGHT
    height = frame.top + frame.plot_height + _MARGIN_BOTTOM
    layers = layers_of(points)
    color_of = {name: COLORS[i % len(COLORS)] for i, name in enumerate(layers)}

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="sans-serif" font-size="11">',
           f'<rect width="{width:.0f}" height="{height:.0f}" fill="#fdfcf8"/>',
           f'<rect x="{frame.x(frame.lon_min):.1f}" y="{frame.y(frame.lat_max):.1f}" '
           f'width="{frame.plot_width:.1f}" height="{frame.plot_height:.1f}" fill="#eef3f7" stroke="#999"/>']
    out += _grid(frame)

    radius = planet.get("radius_km")
    title = escape(planet["name"] or "")
    subtitle = (f"半径 約{radius:,.0f} km、緯度1度 ≒ {radius * 3.14159 / 180:,.0f} km"
                if radius else "半径は不明(area が無い)")
    out.append(f'<text x="{frame.left:.0f}" y="24" font-size="18" font-weight="bold">{title}</text>')
    out.append(f'<text x="{frame.left + 20 + len(title) * 18:.0f}" y="24" fill="#555">{escape(subtitle)}</text>')

    # 同じ経緯度に重なる点(地上の国の真上・真下にある天上・地下の国など)は印を大きくし、ラベルを下へ積む
    groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for p in sorted(points, key=lambda p: (layers.index(p["parent_name"] or _NO_PARENT), p["id"])):
        groups[(p["lon"], p["lat"])].append(p)

    drawn = []
    for (lon, lat), members in groups.items():
        for i, p in enumerate(members):
            drawn.append((p, frame.x(lon), frame.y(lat), i))
    labels = place_labels([(x, y + 12 * i, (p["name"] or "") + alt_text(p["alt"])) for p, x, y, i in drawn])

    for (p, x, y, i), (lx, ly, anchor) in zip(drawn, labels):
        color = color_of[p["parent_name"] or _NO_PARENT]
        label = escape(p["name"] or "") + escape(alt_text(p["alt"]))
        out.append(f'<g><title>{escape(p["name"] or "")} / {escape(p["kind"] or "")} / '
                   f'{escape(p["parent_name"] or "")} / lon {p["lon"]:g} lat {p["lat"]:g}{escape(alt_text(p["alt"]))}</title>')
        out.append(marker(p["parent_kind"], x, y, 4 + 2 * i, color))
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="{color}" '
                   f'stroke="#fdfcf8" stroke-width="3" paint-order="stroke">{label}</text>')
        out.append("</g>")

    lx = frame.x(frame.lon_max) + 20
    out.append(f'<text x="{lx:.0f}" y="{frame.top + 12:.0f}" font-weight="bold">親ごとの色</text>')
    for i, name in enumerate(layers):
        y = frame.top + 32 + i * 18
        kind = next((p["parent_kind"] for p in points if (p["parent_name"] or _NO_PARENT) == name), None)
        out.append(marker(kind, lx + 6, y - 4, 5, color_of[name]))
        out.append(f'<text x="{lx + 18:.0f}" y="{y:.0f}">{escape(name)}'
                   f'{"" if not kind else " (" + escape(kind) + ")"}</text>')
    out.append(f'<text x="{lx:.0f}" y="{frame.top + 44 + len(layers) * 18:.0f}" fill="#555">● 大陸の子  ◆ それ以外の子</text>')
    out.append(f'<text x="{lx:.0f}" y="{frame.top + 60 + len(layers) * 18:.0f}" fill="#555">同じ経緯度は印を重ね、名を下に積む</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"
