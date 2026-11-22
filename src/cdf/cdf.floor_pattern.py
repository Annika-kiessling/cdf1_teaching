"""Parametric 2D tile floor pattern inspired by modular graphic tiles.

Rhino 8 + Grasshopper Python 3 | Computational Design and Fabrication I

Design grammar per tile (inspired by the uploaded geometric reference):
    empty | one horizontal bar | two horizontal bars |
    one vertical bar | two vertical bars

The code deliberately does NOT modify the course's algorithms.py or
geometry_basics.py. Put this file in src/cdf/ as floor_pattern.py.

Geometry is planar in XY. Very small Z offsets are only for reliable preview
(the pattern is NOT extruded into a 3D object).
"""

import random

VERSION = "01"

# Palette: ivory / ceramic / graphite, close to the reference photo.
# The Rhino previews receive System.Drawing.Color objects created below.
TILE_RGB = ((238, 233, 225), (230, 224, 216), (244, 239, 231))
GROUT_RGB = (204, 198, 190)
BAR_RGB = (37, 37, 40)


def _check_parameters(columns, rows, tile_size, joint, density, double_ratio, phase):
    if columns < 1 or rows < 1 or columns * rows > 2400:
        raise ValueError("columns and rows must be positive; max 2400 tiles total")
    if tile_size <= 0:
        raise ValueError("tile_size must be > 0")
    if not 0 <= joint < tile_size * 0.25:
        raise ValueError("joint must be between 0 and 25% of tile_size")
    if not 0 <= density <= 1 or not 0 <= double_ratio <= 1:
        raise ValueError("density and double_ratio must be between 0 and 1")
    if phase not in (0, 1, 2):
        raise ValueError("phase must be 0, 1, or 2")


def generate_pattern_data(
    columns=8,
    rows=12,
    tile_size=100.0,
    joint=2.0,
    density=0.70,
    double_ratio=0.43,
    seed=5,
    phase=2,
):
    """Create a deterministic 2D tile layout, without any Rhino dependency.

    Args:
        columns, rows: grid dimensions
        tile_size: tile-grid pitch in Rhino units
        joint: gap (grout) between two tile edges, in Rhino units
        density: probability that a tile has dark bars
        double_ratio: probability of TWO bars among occupied tiles
        seed: reproducible random variant
        phase: display mode 0=tile grid, 1=bar axes, 2=filled bars

    Returns a dictionary of numerical tile / motif geometry specifications.
    Every bar stays INSIDE the visible tile (not across the grout line).
    """
    columns = int(columns)
    rows = int(rows)
    tile_size = float(tile_size)
    joint = float(joint)
    density = float(density)
    double_ratio = float(double_ratio)
    seed = int(seed)
    phase = int(phase)
    _check_parameters(columns, rows, tile_size, joint, density, double_ratio, phase)

    rng = random.Random(seed)
    visible = tile_size - joint
    bar_length = visible * 0.76
    bar_width = visible * 0.15
    pair_gap = visible * 0.065
    # Single bars may shift slightly within the cell; remain within margins.
    offset_amount = visible * 0.075

    tiles = []
    bars = []
    guides = []
    info = []
    categories = (
        "empty", "one_horizontal", "two_horizontal",
        "one_vertical", "two_vertical",
    )
    for row in range(rows):
        for col in range(columns):
            x = (col - 0.5 * (columns - 1)) * tile_size
            y = (0.5 * (rows - 1) - row) * tile_size
            color_index = rng.randrange(len(TILE_RGB))
            tiles.append((x, y, visible, visible, color_index))
            guides.append((x, y))

            occupied = rng.random() < density
            horizontal = rng.random() < 0.5
            two = (rng.random() < double_ratio) if occupied else False
            shift = rng.choice((-offset_amount, 0.0, offset_amount))
            if not occupied:
                motif = "empty"
                count = 0
            else:
                count = 2 if two else 1
                motif = ("two_" if two else "one_") + (
                    "horizontal" if horizontal else "vertical"
                )
                centerline_distance = (bar_width + pair_gap) if two else 0.0
                for j in range(count):
                    cross_offset = (j - (count - 1) * 0.5) * centerline_distance
                    if horizontal:
                        # Rectangle: x-center, y-center, width, height
                        bar = (x, y + cross_offset + (0.0 if two else shift),
                               bar_length, bar_width)
                    else:
                        bar = (x + cross_offset + (0.0 if two else shift), y,
                               bar_width, bar_length)
                    bars.append(bar)
            info.append({"row": row, "column": col, "motif": motif,
                         "bars": count, "x": x, "y": y,
                         "tile_color": color_index})

    return {
        "columns": columns, "rows": rows,
        "tile_size": tile_size, "joint": joint,
        "density": density, "double_ratio": double_ratio,
        "seed": seed, "phase": phase,
        "tiles": tiles, "bars": bars, "guides": guides,
        "motif_info": info, "motif_types": categories,
        "total_bars": len(bars),
        "occupied_tiles": sum(1 for m in info if m["bars"]),
        "width": columns * tile_size,
        "height": rows * tile_size,
    }


def _add_rectangle(mesh, cx, cy, width, height, z):
    """Append one quad face to a Rhino mesh (very fast for large tile grids)."""
    vertex = mesh.Vertices.Count
    left, right = cx - width * 0.5, cx + width * 0.5
    low, high = cy - height * 0.5, cy + height * 0.5
    mesh.Vertices.Add(left, low, z)
    mesh.Vertices.Add(right, low, z)
    mesh.Vertices.Add(right, high, z)
    mesh.Vertices.Add(left, high, z)
    mesh.Faces.AddFace(vertex, vertex + 1, vertex + 2, vertex + 3)


def _outline(rg, cx, cy, width, height):
    left, right = cx - 0.5 * width, cx + 0.5 * width
    low, high = cy - 0.5 * height, cy + 0.5 * height
    return rg.PolylineCurve([
        rg.Point3d(left, low, 0), rg.Point3d(right, low, 0),
        rg.Point3d(right, high, 0), rg.Point3d(left, high, 0),
        rg.Point3d(left, low, 0),
    ])


def create_floor_pattern(
    columns=8,
    rows=12,
    tile_size=100.0,
    joint=2.0,
    density=0.70,
    double_ratio=0.43,
    seed=5,
    phase=2,
):
    """Return the Grasshopper-compatible model with meshes and CAD curves.

    All layers are grouped by colour to keep Custom Preview performant.
    a: display geometry (Mesh list), b: matching System.Drawing.Color list.
    c / d: tile / dark-bar boundaries as 2D closed curves for export.
    """
    import Rhino.Geometry as rg
    from System.Drawing import Color

    data = generate_pattern_data(columns, rows, tile_size, joint,
                                 density, double_ratio, seed, phase)
    t = data["tile_size"]
    grout = rg.Mesh()
    tile_meshes = [rg.Mesh() for _ in TILE_RGB]
    bar_mesh = rg.Mesh()
    centerline_mesh = rg.Mesh()

    # Tiny visual layering; all export curves remain exactly on Z=0.
    _add_rectangle(grout, 0, 0, data["width"], data["height"], -0.012 * t)
    for cx, cy, w, h, col in data["tiles"]:
        _add_rectangle(tile_meshes[col], cx, cy, w, h, 0.0)

    for cx, cy, w, h in data["bars"]:
        _add_rectangle(bar_mesh, cx, cy, w, h, 0.006 * t)
        if w > h:  # horizontal axis
            _add_rectangle(centerline_mesh, cx, cy, w, 0.018 * t, 0.006 * t)
        else:      # vertical axis
            _add_rectangle(centerline_mesh, cx, cy, 0.018 * t, h, 0.006 * t)

    for mesh in [grout] + tile_meshes + [bar_mesh, centerline_mesh]:
        mesh.Normals.ComputeNormals()
        mesh.Compact()

    displayed = [grout] + tile_meshes
    colors = [Color.FromArgb(*GROUT_RGB)] + [Color.FromArgb(*rgb) for rgb in TILE_RGB]
    if data["phase"] == 1:
        displayed.append(centerline_mesh)
        colors.append(Color.FromArgb(*BAR_RGB))
    elif data["phase"] == 2:
        displayed.append(bar_mesh)
        colors.append(Color.FromArgb(*BAR_RGB))

    data["display_geometry"] = displayed
    data["display_colors"] = colors
    data["tile_outlines"] = [
        _outline(rg, x, y, w, h) for x, y, w, h, _ in data["tiles"]
    ]
    data["bar_outlines"] = [
        _outline(rg, x, y, w, h) for x, y, w, h in data["bars"]
    ]
    data["guide_points"] = [rg.Point3d(x, y, 0) for x, y in data["guides"]]
    return data
