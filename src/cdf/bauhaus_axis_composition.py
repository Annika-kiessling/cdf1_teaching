"""Bauhaus-Achsenfigur | Rhino 8 + Grasshopper Python 3 | Version 12

Die ganze Entwurfslogik liegt hier, Grasshopper steuert nur 5 Parameter.

Phasen:
  0  Bezugsquader
  1  Vertikale, seitlich verzweigte 3D-Beruehrungsgruppe (jedes Element verbunden)
  2  Nur die Paare (0,1), (2,3), ... beruehren sich
  3  Kein Element beruehrt ein anderes Element
  4  Phasen 0 bis 3 nebeneinander

WICHTIG:
- Kein Boolean im Generator und keine Drehung einzelner Elemente.
- Echte Kontakte werden durch gemeinsame geometrische Stuetzpunkte gesetzt.
- Fuer alle anderen Paarungen werden die achsparallelen Huellquader streng
  getrennt gehalten. Das ist bewusst konservativ und schliesst
  Koerperdurchdringungen auch ohne teure Boolean-Pruefungen aus.
- Nicht jede denkbare kompakte Position wird dadurch zugelassen.
- Vertikale Grundordnung aehnlich v08, aber seitlich verzweigt wie v11.
- Nur count und radius steuern die Verteilung; kein compactness-Slider.
- Sockel = 4 x 4 x 0.5 mal max_size, unabhaengig von count und radius.
- Die schwarzen Achsen und Sockel sind Konstruktionsobjekte und von der
  Element-Kollisionspruefung ausgenommen.
- Phasen sind unabhaengige Varianten DERSELBEN Elementliste (gleiche Formen,
  Groessen und Farben); nicht nur eine Animation einer einzigen Figur.
"""

import math
import random
from functools import lru_cache

import Rhino.Geometry as rg
from System.Drawing import Color

VERSION = "12"
SIZE_LEVELS = (0.25, 0.50, 0.75, 1.0)
TYPES = ("box", "cylinder", "sphere", "cone", "torus")
STAGE_NAMES = (
    "0 - Bezugsquader",
    "1 - vertikale und seitlich verzweigte Kontaktgruppe",
    "2 - nur Zweierpaare beruehren sich",
    "3 - alle Elemente haben Abstand",
    "4 - alle vier Phasen nebeneinander",
)


def bauhaus_palette():
    """Gedaempfte, warme Bauhaus-Toene: Rot, Blau, Ocker, Kohle, Stein, Grau."""
    return (
        Color.FromArgb(175, 65, 53),    # Ziegelrot
        Color.FromArgb(53, 78, 115),    # gedecktes Kobaltblau
        Color.FromArgb(202, 163, 73),   # Senfgelb / Ocker
        Color.FromArgb(41, 41, 40),     # Kohleschwarz
        Color.FromArgb(216, 207, 190),  # warmes Creme
        Color.FromArgb(129, 137, 135),  # Steingrau
    )


def _bag(rng, values, n):
    result = []
    while len(result) < n:
        batch = list(values)
        rng.shuffle(batch)
        if result and batch[0] == result[-1] and len(batch) > 1:
            swap = next(i for i in range(1, len(batch)) if batch[i] != result[-1])
            batch[0], batch[swap] = batch[swap], batch[0]
        result.extend(batch)
    return result[:n]


def _shape(kind, full_size, rng):
    """Geometrie-Rezept: groesste Aussenabmessung == full_size."""
    if kind == "box":
        return (kind, full_size, full_size * rng.uniform(.42, .88),
                full_size * rng.uniform(.42, .90))
    if kind == "cylinder":
        return (kind, full_size * rng.uniform(.28, .50), full_size)
    if kind == "sphere":
        return (kind, full_size / 2.0)
    if kind == "cone":
        return (kind, full_size * rng.uniform(.26, .50), full_size)
    if kind == "torus":
        minor = full_size * rng.uniform(.07, .13)
        return (kind, full_size / 2.0 - minor, minor)
    raise ValueError("Unbekannte Form: " + kind)


def _bounds(shape):
    """Exakte lokale AABB fuer unsere ungedrehten Primitive."""
    kind = shape[0]
    if kind == "box":
        _, x, y, z = shape
        return (-x/2, x/2, -y/2, y/2, -z/2, z/2)
    if kind in ("cylinder", "cone"):
        _, r, h = shape
        return (-r, r, -r, r, -h/2, h/2)
    if kind == "sphere":
        r = shape[1]
        return (-r, r, -r, r, -r, r)
    if kind == "torus":
        _, major, minor = shape
        r = major + minor
        return (-r, r, -r, r, -minor, minor)
    raise ValueError(kind)


def _support(shape, normal, orientation=0.0):
    """Echter Oberflaechen-Stuetzpunkt in Richtung normal.

    Wenn der nachfolgende Koerper den entgegengesetzten Stuetzpunkt an dieselbe
    Stelle legt, liegen die Koerper auf entgegengesetzten Seiten einer
    Stuetzebene und beruehren sich ohne Volumenueberschneidung.
    Auch der Torus hat eine gueltige Stuetzebene, obwohl er nicht konvex ist.
    """
    nx, ny, nz = normal
    length = math.sqrt(nx*nx + ny*ny + nz*nz)
    nx, ny, nz = nx/length, ny/length, nz/length
    q = math.hypot(nx, ny)
    ux, uy = ((nx/q, ny/q) if q > 1.e-10 else
              (math.cos(orientation), math.sin(orientation)))
    kind = shape[0]
    if kind == "box":
        _, a, b, c = shape
        return ((a/2 if nx > 1e-10 else (-a/2 if nx < -1e-10 else 0.0)),
                (b/2 if ny > 1e-10 else (-b/2 if ny < -1e-10 else 0.0)),
                (c/2 if nz > 1e-10 else (-c/2 if nz < -1e-10 else 0.0)))
    if kind == "cylinder":
        _, r, h = shape
        return (r*ux if q > 1e-10 else 0.0,
                r*uy if q > 1e-10 else 0.0,
                h/2 if nz > 0 else -h/2)
    if kind == "sphere":
        r = shape[1]
        return (r*nx, r*ny, r*nz)
    if kind == "cone":
        _, r, h = shape
        if nz*h >= r*q:
            return (0.0, 0.0, h/2)
        return (r*ux if q > 1e-10 else 0.0,
                r*uy if q > 1e-10 else 0.0, -h/2)
    if kind == "torus":
        _, major, tube = shape
        return (major*ux + tube*nx, major*uy + tube*ny, tube*nz)
    raise ValueError(kind)


def _world_bounds(local_bb, center):
    x, y, z = center
    return (local_bb[0]+x, local_bb[1]+x,
            local_bb[2]+y, local_bb[3]+y,
            local_bb[4]+z, local_bb[5]+z)


def _overlap(a, b, eps=1.e-9):
    """True auch fuer blosse AABB-Beruehrung (Nicht-Kontaktpaare)."""
    return (min(a[1], b[1]) >= max(a[0], b[0]) - eps and
            min(a[3], b[3]) >= max(a[2], b[2]) - eps and
            min(a[5], b[5]) >= max(a[4], b[4]) - eps)


def _tangent_position(parent, shape_a, shape_b, direction, orientation):
    pa = _support(shape_a, direction, orientation)
    pb = _support(shape_b, tuple(-n for n in direction), orientation)
    center = tuple(parent[i] + pa[i] - pb[i] for i in range(3))
    contact = tuple(parent[i] + pa[i] for i in range(3))
    return center, contact


def _candidate_directions(rng, radius_factor):
    """Bevorzugt flachere, radialere Kontakt-Richtungen.

    Ziel fuer Version 09:
    - Phase 1 soll weniger wie eine vertikale Saeule wirken.
    - Die Elemente duerfen also deutlich mehr in XY ausgreifen,
      waehrend die Hoehe nur langsam zunimmt.
    - Trotzdem bleiben alle Richtungen nach oben gerichtet, damit die
      Figur auf einem Sockel steht und nicht nach unten ausbricht.
    """
    start = rng.uniform(0, 2 * math.pi)
    # Kleinere nz-Werte = mehr horizontale Ausdehnung, weniger Hoehenzuwachs.
    # Bei grossem Radius werden noch flachere Richtungen bevorzugt.
    if radius_factor <= 1.25:
        slopes = (0.18, 0.30, 0.42, 0.55)
    elif radius_factor <= 2.5:
        slopes = (0.10, 0.22, 0.34, 0.48)
    else:
        slopes = (0.06, 0.16, 0.28, 0.40)
    for j in range(20):
        phi = start + j * (2.0 * math.pi / 20.0)
        nz = slopes[j % len(slopes)]
        horizontal = math.sqrt(max(0.0, 1.0 - nz * nz))
        yield ((horizontal * math.cos(phi), horizontal * math.sin(phi), nz), phi)
    # Kompakte Fallbacks mit etwas staerkerem Hoehenanteil.
    for j in range(6):
        phi = start + j * (2.0 * math.pi / 6.0)
        nz = 0.72
        horizontal = math.sqrt(1.0 - nz * nz)
        yield ((horizontal * math.cos(phi), horizontal * math.sin(phi), nz), phi)


def _branch_directions(rng, variation):
    """Raumrichtungen mit horizontalem UND vertikalem Anteil.

    Bei der alten Kette wuchs jedes Element nur vom letzten Element aus
    UND nach oben. Hier koennen wir um bereits vorhandene Elemente herum
    bauen und eine ausgewogene, verzweigte 3D-Gruppe entwickeln.
    """
    offset = rng.uniform(0.0, 2.0 * math.pi)
    phi_count = 12
    slopes = (0.0, 0.26, -0.26, 0.55, -0.55, 0.78, -0.78)
    for k, nz in enumerate(slopes):
        for j in range(phi_count):
            phi = offset + 2.0 * math.pi * (j / float(phi_count) + 0.017 * k)
            xy = math.sqrt(1.0 - nz * nz)
            yield ((xy * math.cos(phi), xy * math.sin(phi), nz), phi)
    # Reserveoptionen fuer sehr kleine Radien / volle Cluster.
    for sign in (1.0, -1.0):
        yield ((0.0, 0.0, sign), offset)


def _branch_layout(shapes, radius, unit, seed):
    """Vertikale Grundordnung + raeumlich verzweigte Kontakte.

    Im Gegensatz zu v11 wird regelmaessig eine neue Hoehenlage erzeugt.
    Dazwischen docken Elemente seitlich an beliebige bereits platzierte
    Koerper an. Die Regel bleibt rein geometrisch und benutzt KEINE Booleans.

    - Jeder neue Koerper hat mindestens einen echten Stuetzpunkt-Kontakt.
    - Alle anderen AABBs muessen streng getrennt bleiben.
    - Gleiche direkt verbundene Koerpertypen sind ausgeschlossen.
    - Radius begrenzt den Abstand der Elementmittelpunkte zur Z-Achse.
    """
    rng = random.Random(seed + 2317)
    limit = radius * unit
    n = len(shapes)
    local_bb = [_bounds(s) for s in shapes]
    positions = [(0.0, 0.0, 0.0)]
    boxes = [_world_bounds(local_bb[0], positions[0])]
    contacts = []
    degrees = [0] * n

    for i in range(1, n):
        # Bei ca. jedem zweiten Element eine zusaetzliche Hoehenlage.
        # Die anderen docken seitlich an: keine reine Saeule/Kette.
        rise_step = (i % 4 != 0)
        top = max(b[5] for b in boxes)
        min_z = min(b[4] for b in boxes)
        # Die Zielhoehe waechst mit der Anzahl der Elemente, nicht mit
        # einem separaten Compactness-Regler.

        # Alle schon vorhandenen Koerper sind als Eltern moeglich.
        # Fuer grosse Modelle Auswahl auf relevante Kandidaten begrenzen.
        if rise_step:
            anchors = sorted(range(i), key=lambda k: boxes[k][5], reverse=True)[:min(9, i)]
            if i > 9:
                anchors += [rng.randrange(i) for _ in range(3)]
        else:
            # Seitlich auch an Elemente weiter unten andocken.
            anchors = list(range(i)) if i <= 16 else sorted(
                range(i), key=lambda k: (degrees[k], -boxes[k][5]))[:12]
            if i > 16:
                anchors += [rng.randrange(i) for _ in range(4)]
        anchors = list(dict.fromkeys(anchors))
        rng.shuffle(anchors)

        old_x0 = min(b[0] for b in boxes)
        old_x1 = max(b[1] for b in boxes)
        old_y0 = min(b[2] for b in boxes)
        old_y1 = max(b[3] for b in boxes)
        best = None

        for parent_id in anchors:
            if shapes[parent_id][0] == shapes[i][0]:
                continue
            parent = positions[parent_id]
            for direction, phi in _branch_directions(rng, 0.0):
                nz = direction[2]
                # Steigende Ebenen: keine abwaerts gerichteten Kontakte.
                # Seitliche Ebenen: vertikale/schraege Kontakte moeglich.
                if rise_step and nz < 0.26:
                    continue
                if not rise_step and nz > 0.55:
                    continue
                center, point = _tangent_position(
                    parent, shapes[parent_id], shapes[i], direction, phi)
                distance = math.hypot(center[0], center[1])
                if distance > limit + 1e-8 * unit:
                    continue
                bb = _world_bounds(local_bb[i], center)
                if any(_overlap(bb, previous, 1e-8 * unit)
                       for k, previous in enumerate(boxes) if k != parent_id):
                    continue

                new_top = max(top, bb[5])
                new_bottom = min(min_z, bb[4])
                sx = max(old_x1, bb[1]) - min(old_x0, bb[0])
                sy = max(old_y1, bb[3]) - min(old_y0, bb[2])
                vertical_gain = new_top - top
                # Die vertikale Grundordnung bleibt erkennbar, aber
                # ein seitlicher Ast soll in beide XY-Richtungen wachsen.
                target_radial = min(limit * 0.78, unit * (0.45 + 0.24 * math.sqrt(i)))
                target_span = min(limit * 1.65, unit * (1.0 + 0.50 * math.sqrt(i)))
                flatness = min(sx, sy) / max(sx, sy, 1e-9)

                if rise_step:
                    score = (
                        -2.0 * vertical_gain / unit
                        + 0.22 * (sx + sy) / unit
                        + 0.20 * abs(distance - target_radial) / max(unit, limit)
                        + 0.18 * degrees[parent_id]
                        + 0.70 * (1.0-flatness)
                    )
                else:
                    score = (
                        1.35 * max(0.0, vertical_gain - unit * 0.12) / unit
                        + 0.38 * max(0.0, target_span - max(sx, sy)) / unit
                        + 0.30 * abs(distance - target_radial) / max(unit, limit)
                        + 0.25 * (1.0-flatness)
                        + 0.14 * degrees[parent_id]
                        + 0.08 * (sx + sy) / unit
                        + 0.05 * max(0.0, min_z-new_bottom) / unit
                    )
                score += 0.015 * rng.random()
                if best is None or score < best[0]:
                    best = (score, center, bb, point, parent_id)

        if best is None:
            # Nur begrenzte sichere Fallbacks; niemals kollidierende
            # Koerper erzwingen oder endlose Booleans starten.
            fallback_parents = sorted(range(i), key=lambda k: boxes[k][5], reverse=True)
            for parent_id in fallback_parents:
                if shapes[parent_id][0] == shapes[i][0]:
                    continue
                for direction in ((0.,0.,1.), (0.,0.,-1.)):
                    center, point = _tangent_position(
                        positions[parent_id], shapes[parent_id], shapes[i], direction, 0.0)
                    if math.hypot(center[0],center[1]) > limit + 1e-8*unit:
                        continue
                    bb = _world_bounds(local_bb[i], center)
                    if any(_overlap(bb, old, 1e-8 * unit)
                           for k,old in enumerate(boxes) if k != parent_id):
                        continue
                    best = (0.0, center, bb, point, parent_id)
                    break
                if best is not None:
                    break

        if best is None:
            raise RuntimeError(
                "Keine kollisionsfreie Kontaktposition fuer Element {}. "
                "Bitte radius erhoehen oder seed aendern.".format(i+1))

        _, center, bb, point, parent_id = best
        positions.append(center)
        boxes.append(bb)
        degrees[parent_id] += 1
        degrees[i] += 1
        contacts.append((parent_id, i, point))
    return positions, contacts


def _group_layout(shapes, radius, unit, seed, pairs):
    """Kompakte Gruppen in XY statt alte lineare Hoehenbaender.

    Phase 2: je zwei Elemente beruehren sich, Gruppen sind getrennt.
    Phase 3: alle einzelnen Koerper sind voneinander getrennt.
    Die getrennten Gruppen werden in einem begrenzten 3D-Punktfeld gepackt.
    """
    rng = random.Random(seed + (6409 if pairs else 8107))
    limit = radius * unit
    n = len(shapes)
    positions = [None] * n
    links = []
    bounds = [_bounds(s) for s in shapes]
    boxes = []
    clearance = unit * 0.13
    next_idx = 0

    while next_idx < n:
        group = [next_idx]
        if pairs and next_idx + 1 < n:
            group.append(next_idx + 1)
        local = [(0.0,0.0,0.0)]
        contact = None
        if len(group) == 2:
            candidates = []
            for direction, orientation in _branch_directions(rng, 0.0):
                p, touch = _tangent_position(local[0], shapes[group[0]],
                                               shapes[group[1]], direction, orientation)
                candidates.append((p,touch))
            rng.shuffle(candidates)
            # Bevorzugt schraege, seitliche Beruehrungen.
            p,touch = min(candidates, key=lambda c:abs(c[0][2])*0.8+
                          abs(math.hypot(c[0][0],c[0][1])-unit*.65)/unit)
            local.append(p)
            contact = (group[0],group[1],touch)

        lbs=[_world_bounds(bounds[idx],local[j]) for j,idx in enumerate(group)]
        gx0=min(b[0] for b in lbs); gx1=max(b[1] for b in lbs)
        gy0=min(b[2] for b in lbs); gy1=max(b[3] for b in lbs)
        gz0=min(b[4] for b in lbs); gz1=max(b[5] for b in lbs)
        gcx=(gx0+gx1)*.5; gcy=(gy0+gy1)*.5
        best=None
        # Suche in der Horizontalen. Nur wenn sie voll wird, eine weitere
        # Hoehenlage. Bounded fuer Rhino-Performance.
        # Pro Hoehenlage: ca. zwei Kontaktpaare oder drei Einzelelemente.
        # So bleibt auch Phase 2/3 aufrechter als im horizontalen v11-Raster.
        start_tier = (next_idx // 4) if pairs else (next_idx // 3)
        for tier in range(start_tier, start_tier + max(4, n//6+2)):
            # Hoehenraster: verschiedene Gruppen sind seitlich verzweigt,
            # erhalten aber mit zunehmender Anzahl neue Hoehenlagen.
            z_step=unit*0.75
            dz=tier*z_step - gz0
            for k in range(75):
                phi=(k*2.399963229728653 + rng.uniform(-.07,.07) +
                     next_idx*.913)
                norm=(k+.5)/75.0
                radial = limit*math.sqrt(norm)
                radial *= 0.88
                tx=radial*math.cos(phi)-gcx
                ty=radial*math.sin(phi)-gcy
                moved=[(x+tx,y+ty,z+dz) for x,y,z in local]
                if any(math.hypot(pt[0],pt[1])>limit+1e-8*unit for pt in moved):
                    continue
                moved_bounds=[_world_bounds(bounds[idx],pt)
                              for idx,pt in zip(group,moved)]
                if any(_overlap(box, old, clearance)
                       for box in moved_bounds for old in boxes):
                    continue
                # kompakt, aber nicht axial: nahe Z=0 und XY gleichmaessig.
                sc=1.30*tier + \
                   0.11*(abs(tx)+abs(ty))/unit + 0.05*rng.random()
                if best is None or sc < best[0]:
                    best=(sc,moved,moved_bounds,tx,ty,dz)
            if best is not None:
                break

        if best is None:
            # Garantierter schneller Fallback fuer sehr enge Radien:
            # die Gruppe direkt UEBER alle vorhandenen Gruppen setzen.
            # Fuer Paare bei Bedarf einen vertikalen Kontakt verwenden,
            # damit ihre Mittelpunkte innerhalb des Radius bleiben.
            if len(group) == 2:
                centered_radial = max(math.hypot(p[0]-gcx,p[1]-gcy)
                                      for p in local)
                if centered_radial > limit + 1e-8*unit:
                    p,touch = _tangent_position((0.,0.,0.),shapes[group[0]],
                                                shapes[group[1]],(0.,0.,1.),0.)
                    local=[(0.,0.,0.),p]
                    contact=(group[0],group[1],touch)
                    lbs=[_world_bounds(bounds[idx],pos)
                         for idx,pos in zip(group,local)]
                    gx0=min(b[0] for b in lbs);gx1=max(b[1] for b in lbs)
                    gy0=min(b[2] for b in lbs);gy1=max(b[3] for b in lbs)
                    gz0=min(b[4] for b in lbs);gz1=max(b[5] for b in lbs)
                    gcx=(gx0+gx1)*0.5;gcy=(gy0+gy1)*0.5
            tx=-gcx;ty=-gcy
            # Bei einem unguenstigen lokalen Schwerpunkt lieber auf
            # das erste Element ausrichten.
            if any(math.hypot(pos[0]+tx,pos[1]+ty)>limit+1e-8*unit
                   for pos in local):
                tx=-local[0][0];ty=-local[0][1]
            top=max((box[5] for box in boxes), default=-clearance)
            dz=top+clearance-gz0
            moved=[(x+tx,y+ty,z+dz) for x,y,z in local]
            moved_bounds=[_world_bounds(bounds[idx],pos)
                          for idx,pos in zip(group,moved)]
            if any(math.hypot(pos[0],pos[1])>limit+1e-8*unit
                   for pos in moved):
                raise RuntimeError("radius zu klein fuer dieses Beruehrpaar; "
                                   "mindestens radius=0.5 empfohlen.")
            best=(0.,moved,moved_bounds,tx,ty,dz)
        _,moved,moved_bounds,tx,ty,dz=best
        for idx,p in zip(group,moved):
            positions[idx]=p
        boxes.extend(moved_bounds)
        if contact:
            a,b,point=contact
            links.append((a,b,(point[0]+tx,point[1]+ty,point[2]+dz)))
        next_idx+=len(group)
    return positions,links

def _raise_layout(shapes, positions, links, unit):
    bottom = min(_world_bounds(_bounds(s), p)[4] for s,p in zip(shapes,positions))
    dz = unit-bottom
    places = [(x,y,z+dz) for x,y,z in positions]
    contacts = [(a,b,(t[0],t[1],t[2]+dz)) for a,b,t in links]
    return places, contacts


def _make_plan(max_size, count, seed, radius):
    rng = random.Random(seed)
    kinds = _bag(rng, TYPES, count)
    levels = _bag(rng, SIZE_LEVELS, count)
    colors = _bag(rng, bauhaus_palette(), count)
    shapes = [_shape(kinds[i], max_size*levels[i], rng) for i in range(count)]
    # Bei engem Radius kann eine zufaellige Andock-Reihenfolge scheitern.
    # Mit denselben Formen, Farben und Groessen bis zu 12 feste Layout-Seeds
    # probieren, statt eine ungueltige Kollisionsposition zu akzeptieren.
    stage1_layout = None
    for retry in range(12):
        try:
            stage1_layout = _branch_layout(
                shapes, radius, max_size, seed + 104729*retry)
            break
        except RuntimeError:
            if retry == 11:
                raise RuntimeError("Kein kollisionsfreies Kontaktnetz gefunden. "
                                   "Erhoehe radius oder wechsle seed.")
    stage1 = _raise_layout(shapes, *stage1_layout, max_size)
    stage2 = _raise_layout(shapes, *_group_layout(shapes,radius,max_size,seed,True), max_size)
    stage3 = _raise_layout(shapes, *_group_layout(shapes,radius,max_size,seed,False), max_size)
    return shapes, kinds, levels, colors, (stage1,stage2,stage3)


def _geometry(shape):
    kind = shape[0]
    if kind == "box":
        _, w, d, h = shape
        return rg.Box(rg.Plane.WorldXY,
            rg.Interval(-w/2,w/2),rg.Interval(-d/2,d/2),rg.Interval(-h/2,h/2)).ToBrep()
    if kind == "sphere":
        return rg.Sphere(rg.Point3d.Origin,shape[1]).ToBrep()
    if kind in ("cylinder", "cone"):
        _, r, h = shape
        plane = rg.Plane(rg.Point3d(0,0,-h/2),rg.Vector3d.ZAxis)
        if kind == "cylinder":
            return rg.Cylinder(rg.Circle(plane,r),h).ToBrep(True,True)
        return rg.Cone(plane,h,r).ToBrep(True)
    if kind == "torus":
        _,major,tube = shape
        return rg.Torus(rg.Plane.WorldXY,major,tube).ToBrep()
    raise ValueError(kind)


def _move(brep,xyz):
    copy = brep.DuplicateBrep()
    copy.Transform(rg.Transform.Translation(*xyz))
    return copy


def _base(width, depth, height):
    return rg.Box(rg.Plane.WorldXY,
        rg.Interval(-width/2,width/2),rg.Interval(-depth/2,depth/2),
        rg.Interval(-height,0)).ToBrep()


def _axis(height,max_size):
    axis = rg.Cylinder(rg.Circle(rg.Plane.WorldXY,max_size*.025),height).ToBrep(True,True)
    curve = rg.LineCurve(rg.Point3d(0,0,0),rg.Point3d(0,0,height))
    return axis,curve


def _build_stage(raw, shapes, colors, positions, links, max_size, count):
    bboxes = [_world_bounds(_bounds(s),p) for s,p in zip(shapes,positions)]
    top = max(b[5] for b in bboxes)
    height = top + max_size  # unten bereits max_size Abstand zur ersten Form
    axis_solid,axis_curve = _axis(height,max_size)
    # Konstanter Sockel: einzig max_size darf ihn veraendern.
    base_w = 4.0 * max_size
    base_d = 4.0 * max_size
    base_h = 0.5 * max_size
    base = _base(base_w,base_d,base_h)
    geos = [_move(g,p) for g,p in zip(raw,positions)]
    pts = [rg.Point3d(*point) for _,_,point in links]
    lines = [rg.LineCurve(rg.Point3d(*positions[a]),rg.Point3d(*positions[b]))
             for a,b,_ in links]
    return {
        "geometries": geos,
        "axis_solid":axis_solid,"axis_curve":axis_curve,
        "base_solid":base,"base_dimensions":(base_w,base_d,base_h),
        "contacts":pts,"lines":lines,
        "positions":positions, "bounds":bboxes,
        "height":height,
    }


@lru_cache(maxsize=4)
def create_bauhaus_axis_composition(max_size=10.0,count=8,seed=1,radius=2.5):
    """Cache: Wechsel von `phase` erzeugt keine neue Geometrie!"""
    max_size, count, seed, radius = float(max_size),int(count),int(seed),float(radius)
    if not 0 < max_size:
        raise ValueError("max_size muss positiv sein")
    if not 1 <= count <= 80:
        raise ValueError("count muss zwischen 1 und 80 liegen")
    if not .5 <= radius <= 5.:
        raise ValueError("radius muss zwischen 0.5 und 5 liegen")
    shapes,kinds,levels,colors,layouts = _make_plan(max_size,count,seed,radius)
    raw = [_geometry(s) for s in shapes]
    stages = [None]
    for positions,links in layouts:
        stages.append(_build_stage(raw,shapes,colors,positions,links,max_size,count))
    # Bezugsquader an denselben Zentren wie die beruehrende Phase 1.
    frames = []
    refshape = rg.Box(rg.Plane.WorldXY,rg.Interval(-max_size/2,max_size/2),
                       rg.Interval(-max_size/2,max_size/2),
                       rg.Interval(-max_size/2,max_size/2)).ToBrep()
    for p in stages[1]["positions"]:
        frames.append(_move(refshape,p))
    stage0 = dict(stages[1])
    stage0["geometries"] = frames
    stage0["contacts"] = []
    stage0["lines"] = []
    stages[0] = stage0
    # Rohfarben sind an Grasshoppers Custom Preview-M direkt kompatibel.
    # Fuer eine physisch matte Ansicht in GH: b -> Create Material (Kd),
    # Ks = Schwarz, S = 0, T = 0, Ke = Schwarz; dessen M -> Custom Preview M.
    materials = list(colors)
    axis_material = Color.FromArgb(20,20,21)
    base_material = Color.FromArgb(198,190,174)
    reference_material = Color.FromArgb(155,158,156)
    metadata = [{"index":i,"type":kinds[i],"size_percent":int(100*levels[i]),
                 "color":colors[i],"phase1_center":rg.Point3d(*stages[1]["positions"][i]),
                 "phase2_center":rg.Point3d(*stages[2]["positions"][i]),
                 "phase3_center":rg.Point3d(*stages[3]["positions"][i])}
                for i in range(count)]
    return {"stages":stages,"materials":materials,"colors":colors,
            "axis_material":axis_material,"base_material":base_material,
            "reference_material":reference_material,"metadata":metadata,
            "step_names":STAGE_NAMES,"max_size":max_size,"radius":radius,
            "count":count}


def get_display_state(composition,phase=3):
    phase = int(phase)
    if phase < 0 or phase > 4:
        raise ValueError("phase muss ein Integer von 0 bis 4 sein")
    stages=composition["stages"]
    unit=composition["max_size"]
    radius=composition["radius"]
    geometry=[]
    materials=[]
    contacts=[]
    lines=[]

    def add_stage(i, dx):
        s=stages[i]
        transform=rg.Transform.Translation(dx,0,0)
        parts=s["geometries"] + [s["axis_solid"],s["base_solid"]]
        all_mats=([composition["reference_material"]]*composition["count"]
                  if i==0 else composition["materials"])
        all_mats = list(all_mats)+[composition["axis_material"],composition["base_material"]]
        for geo,mat in zip(parts,all_mats):
            if dx == 0:
                geometry.append(geo)
            else:
                cp=geo.DuplicateBrep()
                cp.Transform(transform)
                geometry.append(cp)
            materials.append(mat)
        for p in s["contacts"]:
            contacts.append(rg.Point3d(p.X+dx,p.Y,p.Z))
        for line in s["lines"]:
            if dx == 0:
                lines.append(line)
            else:
                cp=line.DuplicateCurve()
                cp.Transform(transform)
                lines.append(cp)

    if phase != 4:
        add_stage(phase,0.0)
    else:
        # Sicherer Abstand zwischen den vier eigenstaendigen Phasen.
        w=max(stages[i]["base_dimensions"][0] for i in range(4))
        spacing=max(w*1.4,2.5*unit*(radius+1))
        for i in range(4):
            add_stage(i,i*spacing)
    return {"display_geometry":geometry,"display_materials":materials,
            "contact_points":contacts,"contact_lines":lines,
            "label":composition["step_names"][phase]}
