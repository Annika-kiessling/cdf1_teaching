"""
Geometry basics -- reusable Rhino.Geometry functions for Grasshopper.

Adding a new function with Copilot
-----------------------------------
1. Open this file and select this chat model, then ask Copilot something like:
   "Add a function here, all in Rhino geometry, that builds a <your shape/idea>.
   Follow the same style as create_cone / create_fractal_tree (defaults for
   optional inputs, a docstring listing params, return a Rhino.Geometry object)."
2. Once the function is added, ask Copilot:
   "Give me the Python code to use this function in a Grasshopper GHPython 3
   component, importing it from computational_design_and_fabrication."
3. Copy the snippet Copilot gives you into a GHPython component, wire up the
   inputs as sliders/panels, and set the output variable (e.g. `a`).
"""

import math
import Rhino.Geometry as rg
import random

def create_fractal_tree(
    base_point=None,
    base_plane=None,
    length=10.0,
    angle=25.0,
    length_factor=0.7,
    depth=8,
    branch_count=2,
):
    """
    Build a fractal (recursively branching) tree as a list of line segments.

    base_point    : Rhino.Geometry.Point3d -- start point of the trunk
    base_plane    : Rhino.Geometry.Plane   -- plane whose YAxis is the trunk
                     direction and ZAxis is the branching rotation axis
    length        : float -- trunk length
    angle         : float -- angle in degrees between sibling branches
    length_factor : float -- length multiplier applied at each new generation
    depth         : int   -- number of recursive branching generations
    branch_count  : int   -- number of branches spawned at each node

    Returns a list of Rhino.Geometry.Line.
    """
    if base_point is None:
        base_point = rg.Point3d(0, 0, 0)
    if base_plane is None:
        base_plane = rg.Plane.WorldXY

    lines = []

    def _grow(start, direction, branch_length, remaining_depth):
        if remaining_depth <= 0 or branch_length <= 1e-6:
            return

        end = start + direction * branch_length
        lines.append(rg.Line(start, end))

        if branch_count <= 1:
            offsets = [0.0]
        else:
            span = angle * (branch_count - 1)
            offsets = [-span / 2.0 + i * angle for i in range(branch_count)]

        for offset in offsets:
            rotated_direction = rg.Vector3d(direction)
            rotated_direction.Rotate(math.radians(offset), base_plane.ZAxis)
            _grow(end, rotated_direction, branch_length * length_factor, remaining_depth - 1)

    _grow(base_point, base_plane.YAxis, length, depth)

    return lines


def create_crochet_pseudosphere(
    rounds=3,
    first_round=100,
    increase=2,
    base_chain=1000.0,
    stitch_width=10.0,
    stitch_height=25.0,
    iterations=35,
    seed=1,
    max_stitches=1500,
    base_waviness=0.70,
):
    """Build an OPEN crocheted hyperbolic strip as a Rhino.Geometry.Mesh.

    Crochet pattern (3 rows of double-treble crochet stitches):
      1. Begin with an open chain about 1 metre long (NOT a closed ring).
      2. Crochet each row with one stitch in a normal position, but `increase`
         stitches into EVERY SECOND stitch of the previous row.
         For increase=2: 1, 2, 1, 2, 1, 2, ...
      3. The growing number of stitches produces hyperbolic ruffles.
      4. As the stitch count increases, the foundation gently bends too.

    The basic spring relaxation and mesh construction are retained from the
    original course example. This is a geometric approximation, not an exact
    yarn / fabric physics simulation.

    Inputs (use consistent Rhino units, e.g. millimetres):
        rounds: Number of crocheted rows after the starting chain (3).
        first_round: Number of starting chain stitches (e.g. 100).
        increase: Number worked into every second stitch (2 = double).
        base_chain: Length of the straight starting chain (e.g. 1000 mm).
        stitch_width: Typical width of a stitch (e.g. 10 mm).
        stitch_height: Height of one double-treble row (e.g. 25 mm).
        iterations: Spring-relaxation steps per row (35; more is slower).
        seed: Reproducible small random perturbations that initiate folds.
        max_stitches: Limit per row to avoid freezing Rhino.
        base_waviness: Bend of the foundation line (0 = straight, 1 = strong).
            The strength also grows with the actual stitch increase.

    Returns a Rhino.Geometry.Mesh with open short ends, a curved foundation,
    and a progressively ruffled outer edge.
    """
    first_round = int(first_round)
    rounds = int(rounds)
    increase = int(increase)
    if first_round < 2:
        raise ValueError("first_round must be at least 2")
    if rounds < 1 or increase < 1:
        raise ValueError("rounds and increase must be at least 1")
    if min(float(base_chain), float(stitch_width), float(stitch_height)) <= 0:
        raise ValueError("base_chain, stitch_width, stitch_height must be positive")
    if not 0.0 <= float(base_waviness) <= 1.0:
        raise ValueError("base_waviness must be between 0 and 1")

    rng = random.Random(seed)

    points = []    # [x, y, z] of every stitch
    fixed = []     # Starting chain stays fixed DURING relaxation; it bends afterward
    springs = []   # (i, j, rest_length, stiffness)
    linked = set() # pairs joined by a spring, these are skipped in collision
    faces = []     # (a, b, c) vertex indices

    def add_spring(i, j, rest, stiffness):
        springs.append((i, j, rest, stiffness))
        linked.add((min(i, j), max(i, j)))

    # ------------------------------------------------------------------
    # 1 + 2. Starting CHAIN: a straight, open line of the chosen length.
    # ------------------------------------------------------------------
    ring = []  # name kept from the original to change as little as possible
    for i in range(first_round):
        x = i * float(base_chain) / (first_round - 1)
        points.append([x, 0.0, 0.0])
        fixed.append(True)
        ring.append(i)

    # ------------------------------------------------------------------
    # Relaxation: springs keep stitch sizes, collisions keep stitches apart.
    # ------------------------------------------------------------------
    collision_distance = 0.9 * stitch_width

    def relax(steps):
        for _ in range(steps):
            # springs
            for i, j, rest, stiffness in springs:
                a = points[i]
                b = points[j]
                dx = b[0] - a[0]
                dy = b[1] - a[1]
                dz = b[2] - a[2]
                length = math.sqrt(dx * dx + dy * dy + dz * dz)
                if length < 1e-9:
                    continue
                move = stiffness * (length - rest) / length
                if fixed[i] and fixed[j]:
                    continue
                if fixed[i]:
                    b[0] -= dx * move
                    b[1] -= dy * move
                    b[2] -= dz * move
                elif fixed[j]:
                    a[0] += dx * move
                    a[1] += dy * move
                    a[2] += dz * move
                else:
                    move *= 0.5
                    a[0] += dx * move
                    a[1] += dy * move
                    a[2] += dz * move
                    b[0] -= dx * move
                    b[1] -= dy * move
                    b[2] -= dz * move

            # collisions: sort stitches into a grid, compare only neighbours
            cell = collision_distance
            grid = {}
            for index, p in enumerate(points):
                key = (int(math.floor(p[0] / cell)),
                       int(math.floor(p[1] / cell)),
                       int(math.floor(p[2] / cell)))
                grid.setdefault(key, []).append(index)

            for (cx, cy, cz), members in grid.items():
                for ox in (-1, 0, 1):
                    for oy in (-1, 0, 1):
                        for oz in (-1, 0, 1):
                            others = grid.get((cx + ox, cy + oy, cz + oz))
                            if not others:
                                continue
                            for i in members:
                                for j in others:
                                    if j <= i:
                                        continue
                                    if fixed[i] and fixed[j]:
                                        continue
                                    if (i, j) in linked:
                                        continue
                                    a = points[i]
                                    b = points[j]
                                    dx = b[0] - a[0]
                                    dy = b[1] - a[1]
                                    dz = b[2] - a[2]
                                    d2 = dx * dx + dy * dy + dz * dz
                                    if d2 >= cell * cell or d2 < 1e-12:
                                        continue
                                    dist = math.sqrt(d2)
                                    push = (cell - dist) / dist
                                    if fixed[i]:
                                        b[0] += dx * push
                                        b[1] += dy * push
                                        b[2] += dz * push
                                    elif fixed[j]:
                                        a[0] -= dx * push
                                        a[1] -= dy * push
                                        a[2] -= dz * push
                                    else:
                                        push *= 0.5
                                        a[0] -= dx * push
                                        a[1] -= dy * push
                                        a[2] -= dz * push
                                        b[0] += dx * push
                                        b[1] += dy * push
                                        b[2] += dz * push

    # ------------------------------------------------------------------
    # 3 + 4. Work the rows: 1 stitch normally, `increase` every second stitch.
    # All 3 rows follow the same increase rule, including the first row.
    # ------------------------------------------------------------------
    grow_from = {}  # stitch index -> index of the stitch it was worked into

    for round_index in range(rounds):
        predicted_count = sum(increase if j % 2 == 1 else 1
                              for j in range(len(ring)))
        if predicted_count > max_stitches:
            break  # safety: avoid excessive mesh size / Rhino slowdown
        new_ring = []
        children_of = []

        for parent_index, parent in enumerate(ring):
            p = points[parent]
            per_stitch = increase if parent_index % 2 == 1 else 1

            # growth direction: continue the line from grandparent to parent
            if parent in grow_from:
                g = points[grow_from[parent]]
                direction = [p[0] - g[0], p[1] - g[1], p[2] - g[2]]
            else:
                # First row grows perpendicular to the straight foundation.
                direction = [0.0, 1.0, 0.0]
            size = math.sqrt(sum(c * c for c in direction)) or 1.0
            direction = [c / size for c in direction]

            children = []
            for _ in range(per_stitch):
                jitter = 0.3 * stitch_width
                points.append([
                    p[0] + direction[0] * stitch_height + rng.uniform(-jitter, jitter),
                    p[1] + direction[1] * stitch_height + rng.uniform(-jitter, jitter),
                    p[2] + direction[2] * stitch_height + rng.uniform(-jitter, jitter),
                ])
                fixed.append(False)
                child = len(points) - 1
                grow_from[child] = parent
                children.append(child)
                new_ring.append(child)
                # the post of the stitch
                add_spring(parent, child, stitch_height, 1.0)
            children_of.append(children)

        count = len(new_ring)
        for k in range(count - 1):
            # No modulo: the left and right ends of the strip remain OPEN.
            add_spring(new_ring[k], new_ring[k + 1], stitch_width, 1.0)
            if k + 2 < count:
                add_spring(new_ring[k], new_ring[k + 2],
                           2.0 * stitch_width, 0.15)

        # faces between the old round and the new round
        parents = len(ring)
        for j in range(parents - 1):
            children = children_of[j]
            next_parent = ring[j + 1]
            next_child = children_of[j + 1][0]
            for k in range(len(children) - 1):
                faces.append((ring[j], children[k], children[k + 1]))
            faces.append((ring[j], children[-1], next_child))
            faces.append((ring[j], next_child, next_parent))
        # Close only the final stitch fan, not the two open ends of the strip.
        for k in range(len(children_of[-1]) - 1):
            faces.append((ring[-1], children_of[-1][k], children_of[-1][k + 1]))

        ring = new_ring
        relax(iterations)

    # ------------------------------------------------------------------
    # 5. Bend the foundation together with the knitted/crocheted surface.
    #
    # The existing spring solver stays unchanged. We bend the FINISHED mesh
    # coherently, rather than moving only the starting row. Thus the first
    # chain curves along with the fabric instead of the fabric tearing away.
    #
    # More increases => more excess fabric => stronger foundation waves.
    # Note: this is a geometric approximation, not a cloth-force simulation.
    # ------------------------------------------------------------------
    growth = max(0.0, (len(ring) - first_round) / float(first_round))
    growth_strength = 1.0 - math.exp(-0.9 * growth)
    amplitude = float(base_waviness) * float(base_chain) * 0.14 * growth_strength

    if amplitude > 1e-9:
        length = float(base_chain)

        def backbone(u):
            """Smooth 3D waves; vanishes at the ends of the open chain."""
            if u <= 0.0 or u >= 1.0:
                return (0.0, 0.0)
            envelope = math.sin(math.pi * u) ** 2
            side = amplitude * envelope * (
                math.sin(2.0 * math.pi * 1.75 * u)
                + 0.26 * math.sin(2.0 * math.pi * 3.4 * u + 0.7)
            )
            up = 0.40 * amplitude * envelope * math.sin(
                2.0 * math.pi * 1.2 * u + 0.9
            )
            return side, up

        # Preserve the approximate chain LENGTH, not its previous straight
        # projected length. The curved baseline therefore gets shorter in X.
        samples = 160
        sample_length = 0.0
        prev_y, prev_z = backbone(0.0)
        for j in range(1, samples + 1):
            u = j / float(samples)
            y, z = backbone(u)
            dx = length / samples
            sample_length += math.sqrt(dx*dx + (y-prev_y)**2 + (z-prev_z)**2)
            prev_y, prev_z = y, z
        scale = length / sample_length

        for p in points:
            x, y_offset, z_offset = p
            u = min(1.0, max(0.0, x / length))
            by, bz = backbone(u)
            # Local direction of foundation in XY; offset the mesh along
            # the local perpendicular, so ruffles follow the curved chain.
            du = 0.001
            ya = backbone(max(0.0, u-du))[0]
            yb = backbone(min(1.0, u+du))[0]
            dydx = (yb-ya) / max(1e-9, (min(1.,u+du)-max(0.,u-du))*length)
            inv = 1.0 / math.sqrt(1.0 + dydx*dydx)
            p[0] = scale * (x - y_offset*dydx*inv)
            p[1] = scale * (by + y_offset*inv)
            p[2] = scale * bz + z_offset

    # ------------------------------------------------------------------
    # Build the Rhino mesh
    # ------------------------------------------------------------------
    mesh = rg.Mesh()
    for p in points:
        mesh.Vertices.Add(p[0], p[1], p[2])
    for a, b, c in faces:
        mesh.Faces.AddFace(a, b, c)
    mesh.Normals.ComputeNormals()
    mesh.Compact()
    return mesh

# -*- coding: utf-8 -*-
"""Floor Pattern V11 - VOLLSTAENDIGER Ersatz fuer den Floor-Pattern-Code
in src/cdf/algorithms.py. Du brauchst KEINE frueheren V05-V09-Funktionen.

Original-Kacheln 1-17 aus Floor pattern(2).dxf, mit echten DXF-Konturen.
Carcassonne: 0/90/180/270 Grad Drehung, nur passende Nachbar-Kanten.
Stadt: zusammenhaengend und mit mindestens einem Strassenanschluss;
       auch am Muster-Rand abgeschnitten moeglich.
Strasse: Road-Slider steuert zusaetzliche lange Wege und Netz-Aeste.
Fluss: Water-Slider steuert laengere Flusslaeufe und mehr Abzweigungen (#17),
       Querung mit Strasse (#6).

Parameter in Grasshopper: columns, rows, tile_size, road, water, city, seed.
Funktion: create_dxf_floor_pattern(...)
Outputs: display_geometry, display_colors, tile_info, invalid_edges,
         statistics.

In Rhino 8 Python-3 keine ezdxf/Shapely-Installation erforderlich:
alle originalen DXF-Flaechen sind als triangulierte Daten enthalten.
"""
import random as _fp_random
import heapq as _fp_heapq
import zlib as _fp_zlib
import base64 as _fp_base64
import ast as _fp_ast
from collections import Counter as _fp_Counter, defaultdict as _fp_defaultdict
from functools import lru_cache as _fp_cache

DXF_FLOOR_PATTERN_VERSION = '11_DXF17_NetworkDensitySliders'
_FP_COLORS = {'G':(182,207,79), 'R':(239,231,212),
              'C':(255,94,50), 'W':(26,0,136)}
_FP_EDGES = (('GGGGRGGGGG', 'GGGGGGGGGG', 'GGGGGGGGGG', 'GGGGRGGGGG'), ('GGGGRGGGGG', 'GGGGGGGGGG', 'GGGGRGGGGG', 'GGGGGGGGGG'), ('GGGGRGGGGG', 'GGGGRGGGGG', 'GGGGRGGGGG', 'GGGGGGGGGG'), ('GGGGRGGGGG', 'GGGGGGGGGG', 'GGGGGGGGGG', 'GGGGGGGGGG'), ('GGGGRGGGGG', 'GGGGWWGGGG', 'GGGGWWGGGG', 'GGGGRGGGGG'), ('GGGGRGGGGG', 'GGGGWWGGGG', 'GGGGRGGGGG', 'GGGGWWGGGG'), ('GGGGGGGGGG', 'GGGGGGGGGG', 'GGGGGGGGGG', 'GGGGWWGGGG'), ('GGGGGGGGGG', 'GGGGWWGGGG', 'GGGGGGGGGG', 'GGGGWWGGGG'), ('GGGGGGGGGG', 'GCCCCCCCCC', 'GGCCCCCCCC', 'GGGGGGGGGG'), ('GGGGGGGGGG', 'GGGGGGGGGG', 'GCCCCCCCCG', 'GGGGGGGGGG'), ('GCCCCCCCCC', 'CCCCCCCCCC', 'GCCCCCCCCC', 'GGGGGGGGGG'), ('CCCCCCCCCC', 'CCCCCCCCCC', 'CCCCCCCCCC', 'CCCCCCCCCC'), ('GGGGRGGGGG', 'GCCCCCCCCC', 'GGCCCCCCCC', 'GGGGGGGGGG'), ('GGGGRGGGGG', 'GGGGGGGGGG', 'GCCCCCCCCG', 'GGGGGGGGGG'), ('GCCCCCCCCC', 'CCCCCCCCCC', 'GCCCCCCCCC', 'GGGGRGGGGG'), ('GGGGGGGGGG', 'GGGGWWGGGG', 'GGGGWWGGGG', 'GGGGGGGGGG'), ('GGGGWWGGGG', 'GGGGWWGGGG', 'GGGGWWGGGG', 'GGGGGGGGGG'))
# Originale DXF-Flachen, vorab leicht trianguliert und gepackt
_FP_ARTWORK_PACKED = (
    'c-rk<Ns{Hbj=W0kewA4*IDx~uZ_t~*|4o{3cTm*J$jm>i+Bz0#`4o~UiUS6R1N!sNKmYOH|M>flKmROw^}qk<bCtjLVQx16{$pewm27DrrQUJQ'
    '`r1cjEF6tx`=}0_E2$2gn>g23^>c0DXrYyAiASm6J{|GOlG)1eqf*$)zI69&Wwz34{`(JWhNmy{PWN1KTj~4ZJvB5^``qVBPdIATU#P6UcvP~V'
    'D`>J>-;XP^p_NwBKDRGVx^lN!%jA{0wtbXq;S<tsvnAeF_p9u4Df0<^Hay)AETw&l?X}#_&$53S2d>V%hq2AcGs#~osXuuitjUKAzdi5vc;sEp'
    '+0dPqee84PEY<Gwl4~*@?K#VqGe^64R~yHEkJ^4fv)(w@c*U5r;R9T|HO{9GaGi!Wi}_o%F}V(U-cM*XagFqXHaQh}?(uD9;x@lW{og-LKTEN_'
    '9QqzMyh^J3jyi@$cJ9~Q17{inf6bBOLBksyobxg9CS1e&fxc2W2P1p?g<a2B4c2&9ZVN}5uT{Je8)<P~%08;A82fc5vdo3|om}^I`ekLXi@so+'
    'R#3*qvQ{{o=+m6qNzIR{an)B}PFA_E>fR`O0qu$4A~0XDg=5|JVDBNAT85+g(oXDR?mmBQmKaFy$r@bCb9cE{&3ePauIQF^pRSp?-RtmfrJ)9W'
    'W$u;3(ec);wW%@iY09f<bNCW2hId1!OuHeQkBF6uQ_B~$?M=?%@fE$_y8Pvbz9#%l(cu1nAEE2}lHGMQyr1#+A5(wbM|eW_U9tOuCifKiw%{W0'
    'O|buQ0sEHlOZn*CLtnHd#gT6dt}Dog;uC-)-^)H7JU3igxHLg8{jn}F*k>OQ-$2@SzKVUza9QYx8`OXK5~48h6<&NnQ2_X??SEV*jqkuM>C=|8'
    'R-wPM52i+A>8GE^bsP_WN57wwR{7SMNB)j}^*V3X;ywM%u=?|PGpvi~y`j%>)O?0<rSD|C0a~%@3ugc0`q_>6RB_Syy!c+@&R{PM{W9<KI6d)a'
    '`>mM8?j!E~qD-DHD)&D;yBA+t=h@BIyUP`v^WM9Lz_|`7;wq0zna`tIaRo<}cjm?w5}q(1N6r(}>%yJ0IAWAr-G6z{&`;m8-p_%)_zoMV6<p=-'
    'v7#?EMJwo|_Z8#kqI&F>2HJE<HO@L2zM8xToG%|QA2+<i#FM=T=jr?2$@zkM^{dfOf5Lv=#2dNf#g*)f&zQy9@hhi~271<gSNbS%Yr2WB|4|0|'
    'lhFgb-^7gUzeu#XY>(M=t=Tba6x#b9mrR`7SV=sGne_9N=)S`Ie5@?Yw8c4>1CssTg1^TWIDh>OnIjXZnL#9S+->;NYvQhH6tY9&a!x2o_QaO2'
    'tgUys7gok@p!~6cowqpBTM77;qw&qFk5Jd+E*s(bS<^sw*VGX;HJ1tHXj>Ff(*>9nZl<!5FN?u0m6@=hX$sZm&2Q@>$@p=dS-7=o!2nNA{#Hm>'
    '2ow(6(AfhrWkb~LeVIv0Il1VZb4hTxu$+yPxUY06U1f+hZ)MdrpI3EzhHu_o6R%M&v+11dINUe#WcH&aTd(@8wmtN`&v#ZR**!^aOl4Vc%bze4'
    '<vP!;k);G(=9Zz??G^G#gI0W{kI9|Z^75fr+=aG$$F{Z><sEj()M}{94dTv~vM0o)Yv#bT<d(r`RO;LQz;sH=cgTyzowf}yU(I#MUUk_%ss_7b'
    'H)q+h!?jP}`j#uqm%$!XwlZ9bZL_$3rE1+|d9)`71j>c`63Qi~&@R-gM>|>QP5f%-oXag}S(^3KHIkK8NA2ia{|mK5m-L@UE3G&h6pl$MFNK72'
    'VH3Ivy*oM?eS!=KUE=-Hf;Z{;eDr({i-7tk^mV~#JvzsA{tWe6OBfv97&f`~jNg7M)DhAQHp4s`wA@-5mV$*f;0<^~vOzN%>Bmke$G)f<ZLT1r'
    ')~Yhr)kc=JbhJj3wywvzpaIGCBRgarE#G3r$k5SpUA)k=jnRIs(V|-lbW&V58?57F8<b-=$ZFxUE$Lhh>&zc%pF(@vk*-P>h5Pp8Tq;y91DlXa'
    'i>CZGKYhvytyP;Y-e*%s;OC6BB#T`N?#<3tx=Wg^4U)F0Z@xwm-lwbXEkdaR4PwY>0ryUWgNtb-ysU96Za2<{#1a)LT+Z!|Rr<6TpuwI&{5^h>'
    '4#R`$=*<>mG%;+zku@0{J~FjY5N%%-My&jT3gNc+M1woDB_ziJeal8wx}}q^;Yt_6;O*BqHzw?VIjSpTn%mFSSz87vqT6BmudY$%=A-$y#h)L|'
    '9F4gs>Pw3rPXDBcY26zcIm_&zprq*E&byl@Sx#l8iz&_1V8V8qhL(XUOd46+Z-tjbLAAYcg9Bc_&{+0)=+9qrGcEhkOq_vHe6CC)eH4c$wz3e8'
    'QDFx0iQBEmxU!W7mDSUb(cnX9i_&I~ldr0*_l0^{CSzl{(A*{f=ePi2DIAM|v9Lm+%~iC`3e53J{c>LoYic{zQ!Ayo!j!ru_S0nQK+lgfwfbGT'
    'wIV|f>a0y}?Uf)eGWSVa08YBpU~=KTwY-kp_}r(oqG=6LEKaDwW)$n&4uWW<y51(4zmajpOxieEd!}R04DEykKfXwL7az|lU}($*;mTDp6HRTd'
    '_KDeyeh#dr+O&fV@7}0>xVyGwqIo@ZANSMrbFFj7?oq->NE{BsJJ4Ne`|&=4>ZehfXid-n>FG-!y2&Z*&>K^_GQVBqBtIH|e(Uyp^!_irXL!!X'
    '_n_x|bh}ZHa!~0xht{U&95z8HmB8hwJTIMl{AFm)6uS9W-ZT8*kUtZOX~dhh6)FqwT|?7ZmQ6E4!PB^=`AkhDWMIlOJw6w`w`1WPuhsibUpO=$'
    'wEUxIkB4IY<v$M?Hk6AwQGL=)#nc?9jxbF)!Z2fw1C0r3(M?Q-OVkohvUlflvU)tc!y7m*o=dEC99sW-4&{w!<>N#yI>|Iy;NF&SZ{aMBaLOUe'
    '54eH9Te#Z38z9}waiEWLO#nBRpSM1aa~&?F1sv4I@hFR$e7xxz7=Vi}7jF{KlO8iM01U#xD%@{N+F|b3&V2mk!WQY3dTa2dYk0x%r5lA3JyzO('
    'jqdXCx#z(Ryftr?Lfw@HyzHU7>hY=vu>h*f2{Gm_nGAVf`p3U_uyO{P*2Cg*k?ChBaHd>n{GP-h=D~j88(SbXy@!mzezjQF-XFM-5?by)Zb3st'
    'V(}b(HutC8(4ZlOU#`k99xjAu3uFO*_wys(+K+ZCpWZxB-CTunG~#B$ni}tuW`s7HG6Z}<7HQC0p$R`hd`m#Lg}VDI6{+LP)B$W?N&rzl`P<3X'
    '`UJF=6=Epf(bAXny9<LN&%G6w`lS|K3Hz?gI4^Lh<aX{Wffp~k@Zv5#T@265GWgM#BsUi*ep!lCv;o<WWFx`cpX^z04Q`1*u>vb0bB}eStHDiX'
    '9D3QI+a}5}u?^7p_N6I7DxwQEG};{wi~!L(0i(=l(N)osxHkhdBbcC}%`TZy2HND7wl<-nWY=}{GE3-o1bUL@+7d+a(tW;Bw~E)o&GoTHdtR`)'
    'Ei7r5!eNgYA|!$(w)+jWIOPbzvMJ%<PpA#qw6K2nD^F>6mz^u%CEsG(wg@1~pCB}4TN-{}>R}D~yU!x)+#_st$bJ~U8Fwpk^8i~9*-ijHYL-ME'
    '9dcZTJRq5Upr>QxyV-;D?44C#APk++;_BJMT~zZO&ZE?1qJ6YA$1gDd@-kiQ0V4WstK{(O@#{hQ^9z+2H*QHACQu1n*~8)~YV-GY3~`c!Nm#@K'
    '2%5|rhA5Bu^fso(2{%-t8l{C%L>+w_6)6yA3#3NsUzSMaQG|CCm3UhzO<JQ!88F6lLozhFPJp5w)26A32cYQ37^~Fi0ygw80UKRr+hdv?7zIXJ'
    '3796Zl6qi{#|VO@UjjC8UDl4V)?_YGOqVbP$1$wt9hiV`eXN9%!wLpO@t9`;KG;DwYG69JDj%4_bmcMD9*7z+bU7i7MvbZvL!xCRSY%1t=3{K6'
    'u+Ly)jj-}yN2M@Cx}bE~XGT>l`)nxq0nFr&KmYMx(2Lz*UnuA}8g9x>NG5Csxo`u4{w;#(lvao+lWSzKz;l&*2LK~+`3`_Eby1vb_mGeQpGPrk'
    'Q}$QG@+kFke<lU8&dE(12IbSU;una@E3Ubv7(lnAE8!?*>hn?9>nyVri`r<{@19{|vtlstN(68BfrV*Y;QQSx1QzY2Nqmkyd#k>I0O?jOGMITz'
    '%b_wVA}si&KpX6it;Ds66BgenKZ@CsE2Gsi^CzrUwo=A`@1wx}s=)6OrPsukGA`l*6}`2+?(+aa^t!-!u$&~C;9M>)u@52NTwXTe(%S+-a9igv'
    'N3AL#k$i=8i#R&m?6gE00ZbF5k>w(2m{bhRtJ#W(3zejiB|=F9Fejw~YqKemxe$G7qO2@81I84^q4^fxc7~qb8OYG+B34y2W&>7gn+l`A4woXX'
    '0G_rblb^nHx%GRZ{l2Q0dGgiMi=Lhsv7BP5!1<{Hm!NF-3XuQ?q*2+IIefK_Owl=ttI#><@XXmcF4}QUB$$)ZelA2H#?YQdXlBv|-+K(;X%#Hv'
    'J9R9sf_($PQ+i5!QY)keZSd^#utYhS-QZIQmZ=kM&gj_!pu%&Q+u3MP?&tZHS-W_;$+c3F2T-s=;vEowm7zGeCS<(qwE>8TD`apsJNNCLIY5O&'
    'o*LGf6#+5uXc`6n%n+kJd_TZWtqQtj+?%4hAP8qe5&q#%pCwea17dpw6jSEgYNl5KTCW*1-;I6IJs)VLSGKujGVlOJ+7Ut8O;HLPBCZP8jRa<m'
    '0B$#r-C0iZL;)KP$-08b_zIuWcR&vumT+9DLOTXjh@9@_>T}ARu5)3=MDfUg4Th;N36dyj%>0c^l5fu#)Zms&zXqt9>=I%gU0BsPM$_BkdvQAk'
    'B2@FYK-IrX>?pTEMT*DEQfi+x57|a0pr;<VD}|**$m-Z5fUJ(?GH-Z_0hD8N$O4hAVnl4@ZFL30=Q&#E%CK=tSRlYuN>~#9^oJ^OSrU^3fssy7'
    'J_VXH0`Pcf4K3gg;K4Hh3P2x+1OV}TU=vad0vbVN*$zlkNtF<;yodtH{r6uhAO(O3E|_Y-1}n&RFKfG9CVJqVE&POIU9XpE?6S$iK!^L14~E$^'
    '#deOy2>^PR4p^{;hMe7<GDp`jGLJ#%`U8{qn2syVN*KdE5UoA}f6*4n#8tRsXYfU8phB3Cai(XTDQLuxxbKOuc&k)zZjT_|{-S{>U?nuU9hd3&'
    'E&*&RRBg9M0qg#da}ccZ(O8H7<L@tUqv?(9#(an>(LOjBTPE%$S}B=eGHdX&29qW`$Fd+^a(fY4|G>oY{>L9c53^WnNegctObQE@)`lBXaQ!qR'
    'Rm?JZtw|FmOVd{fuqg^Pe=3ap94HwcmUI1)y_M-<ws4Fx0eggKFf$c5qKO0io@h5-8BVF($?97tP&bH0G<UGyen9orw9~jca$GC+r^{%+q3DfG'
    '^KiCO2B%ehPM6P*a~KV^G<h<un+ecQL>}kI&EU$C`rZnU=U;SyzNyaNROfH1^EcJ`o9g^cb^fM0e^Z_RpHZFv`12qC!^mj$7n@6l-3QCIf~_02'
    'gaLG#w1PVfnc1sW4j`z+XLW#$qjg2MuwDC5V0nOsDg@gwJB=$~wFD;IY!|()|Ag&U1|Upv?=sedfZlDXCBQ2(s!3Z6?vsHjB(_~%pcMv7inNcQ'
    'KVoMzy;EH@PGsjabgj29cwj3@@dptPxagE?4gJ}w$bO(l+S0=EWw$bg%N!HPE6+`KdvPkZ#sV5B<b1%0im3p4Y`F)f52aj%(qPbv5Wj)}RZP3*'
    '3EX#TLI<9(MBu`5EC&yV4KVVr5S;qbUGwWWo#IsT!upG8^CeVshuf+i6aG6<pNG9me?I(|++K<--QIlgH^`wV2MvHySPC@`>Df>ZNAf*^Hfa^v'
    '*ZGd);eq3jdSBWzNJYYh0$n=L18K^~Yd+katf(Ay_Zx=_oiA<iqGDvRZm1_oJqq0&T2~tAMYPJY2QEJIf_MM+soDhZJd0@#!hy|j7Z%V)8MXAC'
    'l`XN&e-|mT_A02SvuZPD1JGkS2e?S||4JgF(j6LN6kDLR-%~UjXoIT-qKPnd63fR(i=@5Qkp8f*5YL5!)`J>?s8*H==fH@N05Q2cDAkVzGZd6J'
    '&_&h|3E92<ZB^>&3uZtK5;BbQ`HSojxY5>?764CTJ1N`@=#q&);ohLjJh6By;-x0b4M{0uEn$+20XoJd;Q$wf!L}_7i$+FpVR%Watq|?&ir#{@'
    'H0hGrT!`k<VcLBvU{Gs}U0F_<N!ho|N}{tD=;x+%90b9p*bF_vqLPn03~aVQnV@^bJZ*rkMklP*x`AU7d<p7c`9B8O<s?~jxc6E^;2fJ=|B6<+'
    'II-K`29z&rAQL1Ab~60!I)4d#Qv~%NNt*K~!1s?L^hg=Vm4{dGb;?EhouwZ@%R|!450KhIhLJp0Zya^~n26vK@}XPQNU?bM2ak}JWh$?M1dw{='
    'pGcG`7oe^Xi0=#z_-29s)kD~z<t21?QvMyW`9Sp8$#&Bh@{yW@_FFqL6iT?gxC{qPEH5bk5G-5d%d~^~9%2KD|KVI5@<O?VbVQG708?Sm={QbF'
    'e+3I7qhlRnLq1H?B9!^$;MB)S8A7M~2{N=pbExb~Jw%-zUK;h-9<STt{Lla(n0FDkEB1UhF@QfdAq;2}PSAmk3T&u~C<`9~mb0bRdLnP8cww%@'
    'n1uH&+B|X?5zF7^khnmYUJ=B=pYH($BCV^5F^_0(Q~Vm#%0<yy$cjm#PlL+Nt1h$lGHKt!>a91+Ac>t@CD#R1SRg8p&o-LY23&+Jjq?)k1~_^v'
    '712%*+DUrD#x%h;{|V!J&ZHO~lNsQia0PfW#*;Q^3owd?$_Ca=X<rCZ1FmKw-?s&xY5hv5zeV--GH_Hh{<rO6h-NyqkaLKck`28V5Mq>BRx=#Y'
    '#C5nT-*3r*$XGKR`^7ZOL=n3xlSO8GBBUm6!73Uh1;>1C?@^+4Z*X<0cq*mXbq)l%z0fJ`k_*3cR1iyTimXzxw=8EDk)pBeCzw)uFr^DI>c340'
    'cz`6ils{EA{Y7wFhe?+oni&y(Md+b4%A?5gdD43M0z&}S3MCRUrb98l;i@Y$u|7CiIY#Z_?j3ElUbMdUuOnV%-RTKM7Ihgn;w7eOlHNExw;%B@'
    'ftW$tJF(*@A+D?&VMBZArG46oIcG(Z*R53QOUJeo5rzsnEIWD|q58^+KqD6Yr18Z_)R(H5N2#3XbX9i2liC1rkdIQSCvx3hAx|;l#4irE+{3b4'
    'KVi!iWhJbGM1e7P{1ss!Gl560B>-=FOwo&b2fHQ6#u)+Trb$P9HAkW|;G?F=EB-P|a6tv)JtL(oHCVPuK%VdKxh!&v4X{cTblveh@pUR82&EhP'
    'P|rvrG~|yb9Ssl4ZFx!4Y~TrnCik{f4U(1E0Z{2+UyX%agH|KS3EEg3k_N~_M*VC#Kc@5q$EnMcnb1JP;>geKzGtOhxd|==ViHnn3gCl1H<Dtx'
    '1qmR*-a(S$7+o0+8Af*&8iEBNhTMdl9dk%}E~HZkd;*nwt1XTTcwyUh5&DuKv&5}|R^QGi!5?tqvVftP+-of&Xpe+A@(LLY>V2ewWs<)0g}3aZ'
    'sViL$%A?&Q4}Y%-Y+Zbw`ho;VvGoRcZ>5Qi2)m#J!_jEcr(jzmlUSQ!!A%OJZz7Pa0ME9u@D9{>WIWX%(OY6GOIQ<tNfYeG@PSelI}PF!P(&_<'
    'GJ+OfL8<7)mHSenB5V>d{kK!<(-p8hV#yXzguizeZe5tH9Z@u3r(#-RHEfeankNH*RYU-YvdE};`AaW_YUV_yK84CYLcG5!L_*!9M61b|v?<0%'
    'Dz`w^0c$vThY3AN6k-Lb3BopuazIp*0StVLP}72&C`Ys`*eq<2pn#@6PY^uIj1hrO=u*arg($0}fY27X03}Ui28eK(nQdU|GHBx}QL#4z+$TlE'
    'W`T1O9wUH_-eo$IGa;%ZQfizO$#aMon`%=S%4L}H)BxTWj?g<q8m4D45{Wp%duKq(Dh;zTH;OoDnH|Y9dX<`yOQ@OQtc|K*5Ys-DkbsDUi5X(9'
    'F-Hm35-Aut;9Af(WVC@yx#vk61Mj?qG@#9_Y+p=v>oO|Z0%=O{3m6A;N!~Xj2O|at?o=0Wg6Ni(b%V%LZprA#;FGIj%Wo@Myakwc8A<+k1^raP'
    'YhdwhNV&;+41JQG$=>@GX+k3F7{J34JY1$EiyQ<?eQQ)&mB?tFB3XhovpolCYB=jjq(@5_BIRRuAO@9UIzxT684NIx;bi|-1+9g3)6*3<6TFK('
    'kLnjf!Yk5+^HT%G;CAJhIZ$h}R`Q~)ABnv#LHBL+J0?PkVpQkOgaY9Zok1yinP8J|2UKk9!Zj;X5s4OBZfzk6!Gc;<@&nstL<hFR8$22i|6)BO'
    'Ak`x~4KPa=*OXgYGCF65FeMl&lPt5mL&7tXb3iBe->S$r{bF=h_&H)K8+?*29(Z3#FyjL70gI(_lVr-kEOBh~Y$OVx@3#V@?y4QB8W9?Vrq=T^'
    '>aXmlDxU?$a8=L<=<hy9zX1U(8-m%D=q`Mp=SrCRV0@?qMCs6gE_VO9B<h=RDtPWf^U7~S@~_$`5f1n%N%fVabHR4@O7rb<UQVEb4$K`SE$dF_'
    'k>@5K@5@mBkejo<aAm>?`AOb&JGrGFbk=k`6C}MJmqe67QJdsseMxnlas$%K)UOeueOPpd&f0Fqq=LD>Bex#*B+Qh0XsLq%TY36J#8*45ln4nQ'
    '%4&`b;fLx<%Rd6=QyI9FJ>)nB$B-3=f}Mw7`A}Uesjj-u$T<}U(9N#(=7$0k7ke`}l2>Y24qrO*f0eoR4vZ%|A-jV&lT`VjvG&TJqk25v?ThJ9'
    'm2Yf^&CpKqmndb^o+SQs7EgG-^?;p+FF`J4eYu7$ND&M}<&*rKIMre@xqV80?4cl^MD&@($)u28F=^u@D<4KOY~JxuL7D%TpTSQ}44weguM9yF'
    'H!Yx-h%Jg_i7?|qt#icsW%^{{we{JHuVgd8TOxiU?KVBs$tik+NTYc1aX6SW^3fmm<{H89#j>*?@xoKkJJ-Wk#p{OJ!0!lWHPMm|bzOYcQ>Vxt'
    'J}OzF=yiEA<1NS>zT&a+?Qm|f38WFB#?iaz7)~OHL0L^u$qw<Bp|*7jF_f-6JiQ4!atOjC&j)EeLs??|hr-0~`D{zfEV`BI4fkhp-Ov?u>Hs3>'
    'LsnQA1*8DI7d;Zc5%Cp%-0*n+gFS<Q=hj2drpA&YozZ0IQvAkW`4$ND;29At#ue>(2I41pMj+LA=y*a|E83*^2XP}eyq;LFJ=zq-vX#?jXng;T'
    'zNi~)4=wW#xEd|5YeMjBJ$6K+BJE-^uu)xsE=+JsW!OZciqJ4Dg7}UUK2BnU)o6=G<#Zb8PJloarZ1;a{Q(#&IwlJWzhO&ck(8rRu|ZMI32n$z'
    'bE%iH&BYUECvi&>^YJt)oVT1t#XiMvG&E$Jo{q@?w$p}O4R8$EJDJGQh9WcA(41Q(YQu^J5UhT{U`p`gctwsjG-Bw&K%=?^AyAmLY7}lD6jgdg'
    '9aAY-VDxi~9R743t7*Uhp`mfSSl%MXnGe8xip;{3xa=8^dA$ox@-n?#jVolZLJso^Io1|}Lz)UTKU`#IN<J9vx<VS7V}nsT(ok1ufLcstpHCeP'
    'BBf<e^;*Q>fDZ<g&6FW==PPRJ)GjIv;x{eodmzJfN&bEvX`1t^z|%6aw~Cx+=)t^{j@n^CELF<@pth7YI|f)aa<eMyT&UIrQXQ+pU=4|#H9~S_'
    'BAG|!eo9^su0e*B{Sd~xUuI@N3z3eFIFj;nXI&_$BQy|cI;Ub4s#}Ui&T4Hv6@jGSb808f%7B^_1A?2V{RGnl4vu&i+wF$CBLf*|MQed;B;ew5'
    'Wsx}Cl{#1w5fG}Du{vv`(Y;4Lfho~-?|JgS1)+g2r@-In^Kv^0J~rW4eIiEDg0MzMeY?P4yI$#|8s$YUEB{jDs-7~9pJA+$K8rqF)^U4^P?Rg#'
    'FlfFxsxzSderJ<Cbs_ClAdCEfD|00r%wU&YgtYMPXh<DXdx@BpE~oSH7uU=0%ZJ#Z%9>XiV|~@zI&~&b^{Rf?>AGrh)nmG+&yts=++`f#K|TSr'
    'r{<-qT$XZ^E3_qxt~?bm0Ys+oGg*BgSQ0pDkK|&d1C=1@Nnt4<g^H#(<OGx`@dx{_h`d_XWZ5@WG-7a2IoV)uZZRSb0=OtGEOI1Bi9P0-B<{e-'
    't0hjUO0yLr&7^A!;s+xzEC9Y;Wr3NX(1+CH0#G@W%>}vLrv)_3y!oj%QE+QX6_L!O(qM=gPsO74F3$kwqc1mEPNMj$V~XZ+qfS6Fo8lm47G_lQ'
    'DJYsVWz=|F1C<{m?;P{nHKvGoMUD<ee^nFqYgnyvhzOwvh>K{^RP;vor67-^kdgALdSxufL|kLq-&$9tT@~rs4*-sqv_dDc5;Zf((w?UKSVtqc'
    'vqLFZe0Ku{d}==qV6GmW`V@BQiI`tmAcUNnq+y7fUq$Sr25<iYXNvg!i!S~p>Qp6&PMSpyK{T%{SrTavF`bmxSNwjy__rsN{gA){(W=29dVFAG'
    'QQtc-FMlUkR3|wbZPvS(&LiVac|(Y)9Nhq{^?G6EVuj?ra=P=ERehiP#+}m*@z{=VI;p`BT>VwT@KC?%x^uy6|DpQLQ!1|Ch(`;KKt5L<o^(@g'
    'OsSuual!drf=uT`QEW36lItj9Aj9n~0H&&5M12KU|1*iNjsS(p#~5J3)XD*zl|+Cj$jO4ilw*^%WFmS?DIzCpq9A9Ts*Hg8G?B14IvH?Ti3?0-'
    '<gT8qIM7w21sQv_QJ2Xqnj#@A6u9kCg#wir1btMx)rVLLU(CW=Cc``k+)T6(kE_8ss!<+^)XlEsA{0j}QzY6%KfOL0WIt3mEcUhJJ1d&xI>caK'
    'urq|LbvkB68VfpIewu4Fv?3{q2(*x&+9%|xczo~(Jr=33AW&vSypiR&HOL4xa4m{4P{`a)sU85RQ9A%>!lwcUvd=k33oztTuNR^lQxW#QP?Ah6'
    't}@`DS?-T!Ey`hND8Q)D>7G4Tkc#V6M3JgW@o&Q%fVir$L3K6Rzs3|nsbCbyA5Fz8J5gnE+lr&EHORiO(p7VB7)v2`MYlk1QE-cucv4tT5H3X>'
    'DYRhZ-NVOhVwB`g`(jE&U`O@T{`oSmr!Zq@0rx2X{nU6>X4?3V3TM2d5cM`;PlCi(gsSwiBY!NaF@F+ws5jl|g9^pGyLK{gPi`Si`SEDl7I5;6'
    '_b1Ej8KwH-rp-?%RuP%@s$E|dgURO&%T2|C(wTPw1hIhbut&RUp)je2EAtJu(+z5;_<KFYBucqmfG9S51yS;?KTb)IchXzb^tC6|q@Scnc@Dub'
    '75{j|eHW2y>S!I$VVpS7;C(&4;yL-Qm#fm|Nmrg?B^Sx7-KE>GTkWJiW|fzHYGt&0AW(qfi5Q(ENwjbh>44_WS2>g(h1G7g3NclMsX?z~@eKxn'
    'oX9fE&vzy|7MaQ{wTay#{x|AKC;_>niiG@*EqQ_b3-1Hav6Rr3|0xSTJ(nujK<`M<X9pgnlw8_c3e1D!Rs-DtKWwUCb*^OVNIxNZB1jG#tf=YG'
    '`9X$IfFSD>0YhW~2+0~KXSt#dl8->dyUDsK0W<<36Ub7@3`!&5FmU}N^}av#$};>s)gH);K`m83NDBn=zz1j_1#t(Y$vry1W!&~B5BN%A`z_;^'
    'i68a|_8yya-m-bUZf{}YPs#8=Cq|_4CyB7<o`Xk(TX2P#U!A)?)S(Y%$gLB}_PX+v?}iMrm&xB>SB^Wsq+H97vMV3>0-@=2@`azWmP_Z_9loef'
    '-N{$=%KU&C{T1%6r|#s(cE0z@_5as<>vJ)1+S6xQ;_VhACr<?_5;D?NY-^k2AkqXalpHESAPH#;D=<oMc$FPi!L4h3MRg985|Tp?+pI-S)f=J!'
    'Nu@<T7a)T$Z3@%fRuoJ|x<UO#GFm|bZm}8MI@km=Fb!x-d3b}~o-B#Z#7AMjV4&2fs?uohi}BLeRUUs^-q564P{=E2!CWy^$A}t<1I!NLIa^p@'
    'u;RNbH%7z?e^n@T#nC!7Yay9h6tIB$ml=&38=^dUrXRv6dUMvO(A1!&UQR+DdSeM2`+ZfktK9dM99I90+^{Dv>&M)%a&~$BDmN_0rVEk8aP;xQ'
    'qXMtpe3K^;?Sen`Wt}pgl(KSih3oOwo3e@Q#TT$EA?!%lCnr*V`#9!T)C<OXiL~E$%{IXp4-9%d`12{EddwFK8S|z$1mGdr6s3dHjWDAY(Nl}{'
    '8=?G0D8CWPZ-nw2p{$?v1h7+Uiz<phKE{gACqSQzS@;5S8gQ|ud>QMED5)+$M?%7qU;09F%s`-4#V7-bc|So_vH1z4q)#hkLPejZ5Tf~2A78sa'
    '1c5i1`dk2t>lc;uGFAgnRqIwbjQR!@mQq!C&tM1@eW(yTsyX!8Eqq!jiI)q@=OkT#O`KJBpPwAqvQUkHeNa|>^b1@kX=JiaN*0wJwfve=`#U)w'
    'W?xB%s$KW~bf9T*OC-!Mz9Lv&-wm{<J_kQdn6K{u%rCv6d_t`ReV%U)28%H(RQrT^QOE7&|J3_4fLC<*5kdA!E6lgY^R6*6ZWK&TS-<1G<+ydF'
    'zT&g(^#vij&nZ588xh}F{x_EYjpcu1`QKRnH<tg6<^LyG{%wF}h|_I3$&tmTFM{6(FlD6;XB7S4f<Ra_7>P^NWCPAP#3h_Cg=hUN0)j7wtAYDt'
    'ui!ei_}oQ7TSB0ySx0b!`To-6Fjwb{646tIZ2#r7ruJB2nYP{I%!N@UV=Gp74g+x9b=9j}!8cy@)E-MuQEr)m<z?c0$5p=LD&KLH|I2ZeSM80D'
    'f_!j$S5^_qk8-5QCEeSzf597{#$;LA2Mc9Qo60<YRxf%L3;n2V`B9$}1%$gkjmJ;x79q5)L(j(tNq=5s)bJgerqbFUB}WH}aObH~sr;UdzAg1G'
    'If~Ex4t-O*PZZUaSKb%CiK$H5cQMum#WCxt0&$mZ9gUSwlo<(}v&u7gR}P(XJ?dw&1bmI>y=#RUulzC$mVZPH+Y268Vc5=l^Ufc>^>PZaebfzl'
    'hdkccqD*4#?sqt3zP<yf!g+7NzC0h(eQd<H^_*Whj`_wUKS~R|zk?ih_B=-iNTeN?1*ANM`0P&T6;Sw21}wLs8kh@1F>%16)E`+MpL-I8xt2n7'
    '{qrQhA*(_MovTY92`&6?Q(Ir`*Dq`Ro*jC9Uv=jBD9XK+nD!^Qt02QtJE_4!l=aKHM)fl=xyF?R!IC{~hU1S~{O1#5C~Ke(bCd<6v5okk7!ucI'
    '>EI(?wp4@yo6n@kdS$BmkU@)7OjBKClm{6qTiOj3=9Ho0Ni`^OmacPMTOS1^x=N8YB;W7NDp(W6R8&BZNa56{Ct5?uMMY&iHOG^dm7Dr1HvE>J'
    'i{EQk+M20wjMg1KC6yJ4Hk2{TU1b6z-AiH!ICR!zE!BgO6M(>lN>6yEi<=|@1&n3*Vqpw^Tu^0e@KHjAa4HgNTG59f3coVSQTiyK{1RVtQIJdQ'
    '@C(2-fKh~E^bs#BtXOFw@)2eZm<ky+U3oH<IV~z6_Y#l;v$+lQ`D5|sx0vN;$(pizdY}BjUe)(<k@moBr*8a~r9wvdLhgQb9ksjSb>Vk6`}~!7'
    'E)RNJe*e|@bxY@UgAnVsxz;bD(fx<8&(A(5pLO(w_zfYh80>t7gysv_&{xmPc*S++t8l^t!mih+RFBkE-2@8>d_=3=@Q2-n;!IFTdL_$5F}$aQ'
    '+_=jw2r)TXKvzZPB#0!RqXVX7)t1Zo1+6^aVtUFm)YsR>-o+Y}F0Kz#4b|Fjaa7t}$e}#-+@$>SsXuKehaX4Bv9GEFSI7Bo!g0`9kn=zl>n{0F'
    'RTb_@1cKvnz6xve{+t#;h%df%mR_YIs*c+IMOCHBt7L$n1J#zhzP6eVIPv4RSNj1V#{JC$9G!v_kjN>%xWG>lMX#YNP>=%Z`mg^5RPcR)'
)
@_fp_cache(maxsize=1)
def _fp_artwork():
    return _fp_ast.literal_eval(_fp_zlib.decompress(
        _fp_base64.b85decode(_FP_ARTWORK_PACKED)).decode('utf-8'))

_FP_DIRS=((-1,0),(0,1),(1,0),(0,-1))  # N E S W
_FP_EMPTY='GGGGGGGGGG'

def _fp_turn_edges(edges, turn):
    n,e,s,w=edges
    for _ in range(turn%4):
        n,e,s,w=w[::-1],n,e[::-1],s
    return (n,e,s,w)

def _fp_turn_xy(x,y,rotation):
    rotation%=4
    if rotation==1:return (10000-y,x)
    if rotation==2:return (10000-x,10000-y)
    if rotation==3:return (y,10000-x)
    return (x,y)

def _fp_stitch_road(u,v,edges):
    # Strassen in Teil 5 eines Zehnerrasters liegen nach Drehung in Teil 6.
    # Nur unmittelbar am Rand minimal an einen Mittelpunkt anpassen.
    bend=1300.0
    dx=dy=0.
    for d in (0,2):
        side=edges[d]
        if 'R' not in side:continue
        distance=v if d==0 else 10000-v
        if distance<bend:
            middle=(side.index('R')+.5)*1000.
            dx+=(5000.-middle)*(1.-distance/bend)
    for d in (1,3):
        side=edges[d]
        if 'R' not in side:continue
        distance=10000-u if d==1 else u
        if distance<bend:
            middle=(side.index('R')+.5)*1000.
            dy+=(5000.-middle)*(1.-distance/bend)
    return (u+dx,v+dy)

def _fp_port(side):
    # Stadtanschluesse entsprechen Carcassonne-TERRAIN (nicht gleicher Breite).
    # Wasser entspricht zwei Zehntelstreifen, Strasse dem 5. Abschnitt,
    # dessen Position nach 180 Grad gedreht wird.
    if 'C' in side:return 'C'
    if 'R' in side:return 'R'
    if 'W' in side:return 'W'
    return 'G'

def _fp_match(a,b):
    return _fp_port(a)==_fp_port(b)

_FP_OPTIONS=tuple((i,rot,_fp_turn_edges(edges,rot))
                  for i,edges in enumerate(_FP_EDGES) for rot in range(4))
_FP_OPTION_PORTS=tuple((i,rot,edges,
    tuple(frozenset(d for d,s in enumerate(edges) if key in s)
          for key in ('R','W','C')))
    for i,rot,edges in _FP_OPTIONS)

@_fp_cache(maxsize=None)
def _fp_select_tile(roads,waters,cities):
    wanted=(frozenset(roads),frozenset(waters),frozenset(cities))
    for i,rot,e,ports in _FP_OPTION_PORTS:
        if ports==wanted:
            return (i,rot,e)
    return None

# ------------------ Regeln fuer die Kachel-Anordnung ------------------

def _fp_add(ports,p,d,kind,columns,rows):
    if not (0<=p[0]<rows and 0<=p[1]<columns):
        return False
    if d not in ports[p][kind]:ports[p][kind].add(d)
    dy,dx=_FP_DIRS[d]
    q=(p[0]+dy,p[1]+dx)
    if 0<=q[0]<rows and 0<=q[1]<columns:
        ports[q][kind].add((d+2)%4)
    return True

def _fp_join(ports,p,q,kind,columns,rows):
    dy=q[0]-p[0];dx=q[1]-p[1]
    d=_FP_DIRS.index((dy,dx))
    _fp_add(ports,p,d,kind,columns,rows)

def _fp_route(start,goal,forbidden,columns,rows,rng,limits=None,turncost=.18):
    """Leichter, zufaellig variierter kuerzester Weg mit Kurven.
    Nur 4-Nachbar-Schritte, keine schweren geometrischen Booleans.
    """
    def allowed(p):
        y,x=p
        if not (0<=y<rows and 0<=x<columns):return False
        if p in forbidden and p not in (start,goal):return False
        if limits is not None:
            ymin,xmin,ymax,xmax=limits
            if not (ymin<=y<ymax and xmin<=x<xmax):return False
        return True
    if not allowed(start) or not allowed(goal):return None
    # Fixierte Zellkosten fuer reproduzierbare, sanfte Unregelmaessigkeit
    jitter={(y,x):.18+1.45*rng.random()
            for y in range(rows) for x in range(columns)}
    counter=0
    source=(start,-1)
    dist={source:0.}
    prev={}
    queue=[(0.,0,source)]
    end=None
    while queue:
        val,_,state=_fp_heapq.heappop(queue)
        if val>dist.get(state,1e50)+1e-8:continue
        p,old=state
        if p==goal:
            end=state;break
        dirs=list(range(4));rng.shuffle(dirs)
        for d in dirs:
            dy,dx=_FP_DIRS[d];q=(p[0]+dy,p[1]+dx)
            if not allowed(q):continue
            delta=jitter[q]+(turncost if old>=0 and d!=old else 0.)
            nd=val+delta
            state2=(q,d)
            if nd<dist.get(state2,1e50)-1e-8:
                dist[state2]=nd;prev[state2]=state;counter+=1
                _fp_heapq.heappush(queue,(nd,counter,state2))
    if end is None:return None
    path=[];cur=end
    while cur!=source:
        path.append(cur[0]);cur=prev[cur]
    path.append(start);path.reverse()
    # Keine geschlossene Schleife innerhalb eines einzelnen Pfades
    if len(set(path))!=len(path):return None
    return path

def _fp_add_path(ports,path,kind,columns,rows):
    for a,b in zip(path,path[1:]):_fp_join(ports,a,b,kind,columns,rows)

def _fp_occupied(ports,kind):
    return {p for p,k in ports.items() if k[kind]}

def _fp_route_tree(rng,columns,rows,ports):
    """Hauptstrasse von Nord nach Sued, mit erzwungener Bruecke.
    Die Strasse darf den Aussenrand schneiden und endet nicht an Stadt.
    """
    ay=max(3,min(rows-4,rows//2+rng.choice((-1,0,1))))
    ax=max(3,min(columns-4,columns//2+rng.choice((-1,0,1))))
    anchor=(ay,ax)
    x0=max(0,min(columns-1,ax+rng.randint(-max(2,columns//4),max(2,columns//4))))
    x1=max(0,min(columns-1,ax+rng.randint(-max(2,columns//4),max(2,columns//4))))
    upper=_fp_route((0,x0),(ay-1,ax),set(),columns,rows,rng,
                    limits=(0,0,ay,columns))
    if upper is None:return None
    lower=_fp_route((ay+1,ax),(rows-1,x1),set(upper),columns,rows,rng,
                    limits=(ay+1,0,rows,columns))
    if lower is None:return None
    main=upper+[anchor]+lower
    _fp_add_path(ports,main,'R',columns,rows)
    _fp_add(ports,main[0],0,'R',columns,rows)
    _fp_add(ports,main[-1],2,'R',columns,rows)
    return anchor,main

def _fp_water_tree(rng,columns,rows,ports,anchor):
    """Hauptfluss von West nach Ost durch Bruecken-Kachel #6;
    meist mit Kurven und optionalen weiteren Verzweigungen #17.
    """
    ay,ax=anchor
    road=_fp_occupied(ports,'R')
    start_y=max(0,min(rows-1,ay+rng.choice((-4,-3,-2,2,3,4))))
    end_y=max(0,min(rows-1,ay+rng.choice((-4,-3,-2,2,3,4))))
    # Links und rechts getrennt suchen: die Strasse darf nur auf
    # der Original-Bruecken-Kachel gekreuzt werden.
    left=_fp_route((start_y,0),(ay,ax-1),road,columns,rows,rng,
                   limits=(0,0,rows,ax))
    right=_fp_route((ay,ax+1),(end_y,columns-1),road,columns,rows,rng,
                    limits=(0,ax+1,rows,columns))
    if left is None or right is None:return None
    main=left+[anchor]+right
    _fp_add_path(ports,main,'W',columns,rows)
    _fp_add(ports,main[0],3,'W',columns,rows)
    _fp_add(ports,main[-1],1,'W',columns,rows)
    return main

def _fp_branch(rng,ports,kind,columns,rows,prefer_end='boundary',min_length=3):
    # Abzweigung an vorhandener, ungekreuzter Strecke (zwei Anschluesse).
    # Strassen muessen ans Musterende laufen; Flussarme koennen enden.
    candidates=[p for p,s in ports.items()
                if len(s[kind])==2 and
                   not s['C'] and
                   not s['W' if kind=='R' else 'R'] and
                   2<=p[0]<rows-2 and 2<=p[1]<columns-2]
    rng.shuffle(candidates)
    candidates=candidates[:22]
    existing=_fp_occupied(ports,kind)
    other=_fp_occupied(ports,'W' if kind=='R' else 'R')
    city_cells=_fp_occupied(ports,'C')
    for p in candidates:
        free_dirs=[d for d in range(4) if d not in ports[p][kind]]
        rng.shuffle(free_dirs)
        for d in free_dirs:
            dy,dx=_FP_DIRS[d]
            start=(p[0]+dy,p[1]+dx)
            if not (0<=start[0]<rows and 0<=start[1]<columns):continue
            if start in existing or start in other or start in city_cells:continue
            ends=[]
            if prefer_end=='boundary':
                if kind=='R':
                    # Horizontale Abzweigungen reichen bis West/Ost.
                    x=0 if d==3 else (columns-1 if d==1 else rng.choice((0,columns-1)))
                    for yy in range(rows):
                        ends.append(((yy,x),3 if x==0 else 1))
                else:
                    y=0 if d==0 else (rows-1 if d==2 else rng.choice((0,rows-1)))
                    for xx in range(columns):
                        ends.append(((y,xx),0 if y==0 else 2))
            else:
                # Interner Fluss-Endpunkt (echtes DXF Tile #7)
                for yy in range(1,rows-1):
                    for xx in range(1,columns-1):
                        q=(yy,xx)
                        manhattan=abs(p[0]-yy)+abs(p[1]-xx)
                        if min_length+1<=manhattan<=min_length+5:
                            ends.append((q,None))
            rng.shuffle(ends)
            ends.sort(key=lambda e:abs(p[0]-e[0][0])+abs(p[1]-e[0][1]))
            # Branchroute soll nicht sofort um 180 Grad zuruecklaufen.
            blocked=(existing|other|city_cells)-{p}
            for end,boundary_dir in ends[:9]:
                if end in blocked or end==start:continue
                path=_fp_route(start,end,blocked|{p},columns,rows,rng)
                if path is None or len(path)+1<min_length:continue
                # Der Endpunkt braucht einen echten, freien Ausgang.
                if boundary_dir is not None:
                    dy2,dx2=_FP_DIRS[boundary_dir]
                    q=(end[0]+dy2,end[1]+dx2)
                    if 0<=q[0]<rows and 0<=q[1]<columns:continue
                _fp_join(ports,p,start,kind,columns,rows)
                _fp_add_path(ports,path,kind,columns,rows)
                if boundary_dir is not None:
                    _fp_add(ports,end,boundary_dir,kind,columns,rows)
                # Bei Wasseraesten ins Innere ist Tile #7 das Endmotiv.
                return True
    return False

def _fp_join_river_road_corner(ports,rng,columns,rows):
    """Originale DXF-Kachel #5: Strasse UND Wasser biegen im selben Tile.

    Bestehende Strassenkurve wird mit einem neuen, verbundenen Flussarm
    durch die beiden freien Kanten ergaenzt. Nur echte DXF-Drehungen.
    Falls ein Netz keinen freien Weg bietet, wird nichts erzwungen.
    """
    water=_fp_occupied(ports,'W')
    roads=_fp_occupied(ports,'R')
    sources=[p for p in water if len(ports[p]['W'])==2 and not ports[p]['R']]
    corners=[p for p in roads if len(ports[p]['R'])==2 and not ports[p]['W']
             and (ports[p]['R'] in ({0,1},{1,2},{2,3},{0,3}))
             and 2<=p[0]<rows-2 and 2<=p[1]<columns-2]
    rng.shuffle(corners)
    # nahe Strassenkurven bevorzugen
    corners.sort(key=lambda p:min((abs(p[0]-q[0])+abs(p[1]-q[1])
                                    for q in sources), default=999))
    for p in corners[:25]:
        free=[d for d in range(4) if d not in ports[p]['R']]
        assert len(free)==2
        if _fp_select_tile(tuple(sorted(ports[p]['R'])), tuple(free), ()) is None:
            continue
        for incoming in (free,free[::-1]):
            din,dout=incoming
            dy,dx=_FP_DIRS[din];a=(p[0]+dy,p[1]+dx)
            dy,dx=_FP_DIRS[dout];b=(p[0]+dy,p[1]+dx)
            if not all(0<=q[0]<rows and 0<=q[1]<columns
                       and q not in roads and q not in water for q in (a,b)):
                continue
            ranked=sorted(sources,key=lambda q:abs(q[0]-a[0])+abs(q[1]-a[1]))
            for start in ranked[:10]:
                dist=abs(start[0]-a[0])+abs(start[1]-a[1])
                if dist>max(5,(rows+columns)//3):continue
                first=_fp_route(start,a,(water|roads)-{start},columns,rows,rng)
                if first is None:continue
                if len(first)>max(11,(columns+rows)//2):continue
                first_occupied=set(first)
                if b in first_occupied:continue
                # Neue Wasserseite bis zum Rand verlaengern
                forbidden=(water|roads|first_occupied|{p})-{b}
                exits=[]
                for x in range(columns):
                    exits.append(((0,x),0));exits.append(((rows-1,x),2))
                for y in range(rows):
                    exits.append(((y,0),3));exits.append(((y,columns-1),1))
                exits=[x for x in exits if x[0] not in forbidden]
                exits.sort(key=lambda t:abs(t[0][0]-b[0])+abs(t[0][1]-b[1]))
                for (end,exit_dir) in exits[:24]:
                    second=_fp_route(b,end,forbidden,columns,rows,rng)
                    if second is None or len(second)<3:continue
                    # An Quelle entsteht neuer Fluss-Arm (#17).
                    nd=(first[1][0]-start[0],first[1][1]-start[1]) if len(first)>1 else None
                    if nd is None:continue
                    dr=_FP_DIRS.index(nd)
                    if dr in ports[start]['W']:continue
                    if _fp_select_tile((),tuple(sorted(ports[start]['W']|{dr})),()) is None:
                        continue
                    _fp_add_path(ports,first,'W',columns,rows)
                    _fp_join(ports,a,p,'W',columns,rows)
                    _fp_join(ports,p,b,'W',columns,rows)
                    _fp_add_path(ports,second,'W',columns,rows)
                    _fp_add(ports,end,exit_dir,'W',columns,rows)
                    return True
    return False




def _fp_extra_network(ports, kind, columns, rows, rng, min_length=5):
    """Zusatz-Netz von einem freien Muster-Rand zum anderen.

    Rueckfall, wenn an einem dichten bestehenden Netz keine lange
    Abzweigung mehr moeglich ist. Nur Original-DXF-Kachelanschluesse.
    """
    occupied={p for p,v in ports.items() if any(v[k] for k in ('R','W','C'))}
    ends=[]
    for y in range(rows):
        ends.extend([((y,0),3),((y,columns-1),1)])
    for x in range(columns):
        ends.extend([((0,x),0),((rows-1,x),2)])
    ends=[item for item in ends if item[0] not in occupied]
    if len(ends)<2:return False
    starts=list(ends);rng.shuffle(starts)
    for start,sd in starts[:6]:
        targets=list(ends)
        rng.shuffle(targets)
        targets.sort(key=lambda e:-(abs(start[0]-e[0][0])+abs(start[1]-e[0][1])))
        for end,ed in targets[:5]:
            if end==start:continue
            if abs(start[0]-end[0])+abs(start[1]-end[1])<min_length:continue
            path=_fp_route(start,end,occupied,columns,rows,rng)
            if path is None or len(path)<min_length:continue
            # Gegen U-Turns direkt am Muster-Rand
            if len(path)>1:
                forward=(path[1][0]-start[0],path[1][1]-start[1])
                reverse=(path[-2][0]-end[0],path[-2][1]-end[1])
                if _FP_DIRS.index(forward)==sd or _FP_DIRS.index(reverse)==ed:
                    continue
            _fp_add_path(ports,path,kind,columns,rows)
            _fp_add(ports,start,sd,kind,columns,rows)
            _fp_add(ports,end,ed,kind,columns,rows)
            return True
    return False


def _fp_grow_network(rng,ports,kind,columns,rows,amount,steps=6):
    """Stufenweiser, stabiler Ausbau: hoehere Sliderwerte addieren Netz.

    0 -> keine neuen Verbindungen, 1 -> bis zu `steps` weitere lange
    Netzabschnitte. Bei Platzmangel bleiben unmoegliche Schritte aus.
    """
    amount=max(0.,min(1.,float(amount)))
    count=int(amount*steps+1.e-8)
    for step in range(count):
        length=max(4,(columns+rows)//6)
        # Lange Netz-Aeste sind wichtiger als viele winzige Stummel.
        worked=_fp_branch(rng,ports,kind,columns,rows,
                          'boundary',min_length=length)
        if not worked and kind=='W':
            worked=_fp_branch(rng,ports,kind,columns,rows,
                              'inside',min_length=length)
        if not worked:
            _fp_extra_network(ports,kind,columns,rows,rng,
                              min_length=max(length+2,(columns+rows)//4))

def _fp_city_rectangle(p,d,width,height,tail,corner=False):
    dy,dx=_FP_DIRS[d];gate=(p[0]+dy,p[1]+dx)
    # Der rechteckige Stadtkern liegt VOR dem Tor (bei Schwanz-Tor +1).
    if d==1:  # ost
        xmin=gate[1]+int(tail);ymin=(gate[0] if corner else gate[0]-height//2)
    elif d==3:
        xmin=gate[1]-(width-1)-int(tail);ymin=(gate[0] if corner else gate[0]-height//2)
    elif d==2:
        xmin=(gate[1] if corner else gate[1]-width//2);ymin=gate[0]+int(tail)
    else:
        xmin=(gate[1] if corner else gate[1]-width//2);ymin=gate[0]-(height-1)-int(tail)
    core={(y,x) for y in range(ymin,ymin+height)
         for x in range(xmin,xmin+width)}
    if tail:core.add(gate)
    return core,gate

def _fp_place_city(ports,rng,columns,rows,width,height,tail=False,
                   prefer_border=False,prefer_corner=False,
                   reserve=None,max_width=None,max_height=None):
    """Ein Stadtkern wird an einer festen Position vorbereitet.

    Fuer alle City-Werte wird derselbe Platz fuer die maximale Groesse
    freigehalten: die Stadt waechst bei gleichem Seed und springt nicht.
    """
    if reserve is None:reserve=set()
    busy={p for p,v in ports.items() if v['R'] or v['W'] or v['C']}|reserve
    if max_width is None:max_width=width
    if max_height is None:max_height=height
    candidates=[p for p,v in ports.items() if len(v['R'])==2 and not v['W']]
    rng.shuffle(candidates)
    if prefer_border:
        candidates.sort(key=lambda p:min(p[0],rows-1-p[0],p[1],columns-1-p[1]))
    for p in candidates:
        for d in rng.sample(range(4),4):
            if d in ports[p]['R']:continue
            # Erst pruefen, ob auch die endgueltige maximale Stadt hier passt.
            maximum,mgate=_fp_city_rectangle(p,d,max_width,max_height,
                                               tail,prefer_corner)
            maxinside={q for q in maximum
                       if 0<=q[0]<rows and 0<=q[1]<columns}
            if len(maxinside)<3 or mgate not in maxinside or (maxinside&busy):
                continue
            # Die aktuelle Stadtgroesse belegt nur einen Teil dieser Reserve.
            region,gate=_fp_city_rectangle(p,d,width,height,tail,prefer_corner)
            inside={q for q in region if 0<=q[0]<rows and 0<=q[1]<columns}
            if len(inside)<3 or gate not in inside or (inside&busy):continue
            # Ein freier Stadtauslaeufer erzeugt Original-Tile #10.
            # Diese Zusatz-Kachel darf die reservierte Maximalflaeche
            # nicht ueberschreiten, sonst wuerde die Position springen.
            if width>=3 and height>=3:
                miny=min(q[0] for q in region);maxy=max(q[0] for q in region)
                minx=min(q[1] for q in region);maxx=max(q[1] for q in region)
                tips=[(miny+height//2,maxx+1),(miny+height//2,minx-1),
                      (maxy+1,minx+width//2),(miny-1,minx+width//2)]
                for tip in tips:
                    if tip not in region and tip not in busy and \
                       0<=tip[0]<rows and 0<=tip[1]<columns and \
                       sum((tip[0]+dy,tip[1]+dx) in region
                           for dy,dx in _FP_DIRS)==1:
                        region.add(tip);inside.add(tip);break
            changes={};okay=True
            for q in inside:
                cds={i for i,(dy,dx) in enumerate(_FP_DIRS)
                     if (q[0]+dy,q[1]+dx) in region}
                rd={((d+2)%4)} if q==gate else set()
                if _fp_select_tile(tuple(sorted(rd)),(),tuple(sorted(cds))) is None:
                    okay=False;break
                changes[q]=(cds,rd)
            if not okay or _fp_select_tile(tuple(sorted(ports[p]['R']|{d})),(),()) is None:
                continue
            for q,(cs,rs) in changes.items():
                ports[q]['C'].update(cs);ports[q]['R'].update(rs)
            ports[p]['R'].add(d)
            reserve.update(maxinside)
            reserve.update(inside)
            return {'gate':gate,'cells':inside,'tail':tail,
                    'touches_border':any(y in (0,rows-1) or x in (0,columns-1)
                                         for y,x in inside),
                    'size':len(inside)}
    return None


def _fp_mini_city(ports,rng,columns,rows):
    """Einzelnes original DXF-Stadtende #4 an langer T-Strasse."""
    places=[p for p,v in ports.items() if len(v['R'])==2 and not v['W']]
    rng.shuffle(places)
    for p in places:
        for d in rng.sample(range(4),4):
            if d in ports[p]['R']:continue
            dy,dx=_FP_DIRS[d];q=(p[0]+dy,p[1]+dx)
            if not (0<=q[0]<rows and 0<=q[1]<columns):continue
            if any(ports[q][k] for k in ('R','W','C')):continue
            if _fp_select_tile(tuple(sorted(ports[p]['R']|{d})),(),()) is None:
                continue
            if _fp_select_tile(((d+2)%4,),(),()) is None:continue
            ports[p]['R'].add(d)
            ports[q]['R'].add((d+2)%4)
            return True
    return False

def _fp_validate_grid(layout,columns,rows):
    errors=[]
    for n,(_,_,edges) in enumerate(layout):
        y,x=divmod(n,columns)
        if x and not _fp_match(edges[3],layout[n-1][2][1]):
            errors.append((y,x,'W'))
        if y and not _fp_match(edges[0],layout[n-columns][2][2]):
            errors.append((y,x,'N'))
    return errors

def _fp_network_components(layout,columns,rows,kind):
    ids=[i for i,(_,_,ee) in enumerate(layout)
         if any(kind in side for side in ee)]
    remaining=set(ids);components=[]
    while remaining:
        start=remaining.pop();found={start};stack=[start]
        while stack:
            i=stack.pop();y,x=divmod(i,columns)
            for d,(dy,dx) in enumerate(_FP_DIRS):
                ny=y+dy;nx=x+dx
                if not (0<=ny<rows and 0<=nx<columns):continue
                j=ny*columns+nx
                if j in remaining and (kind in layout[i][2][d]) and (kind in layout[j][2][(d+2)%4]):
                    remaining.remove(j);found.add(j);stack.append(j)
        components.append(found)
    return components

def _fp_city_access(layout,columns,rows):
    # Staedte aus echten C-Anschluessen (grosse Staedte)
    comps=_fp_network_components(layout,columns,rows,'C')
    # Plus die Original-Kachel #4: Einzelstadt mit internem Strassentor
    sizes=[len(comp) for comp in comps]
    bad=0
    for comp in comps:
        # #13/#14/#15: jeweils Stadt mit einem Strassenzugang
        if not any(layout[k][0] in (12,13,14) for k in comp):bad+=1
    mini=sum(t==3 for t,r,e in layout)
    sizes.extend([1]*mini)
    return sorted(sizes,reverse=True),bad

@_fp_cache(maxsize=12)
def _fp_layout(columns,rows,road,water,city,seed):
    """Stadt-, Strassen- und Fluss-Netz mit echten Carcassonne-Ports.
    Wiederholbarer Seed; keine Row-by-Row-Streifen oder kurzen Module.
    """
    rng=_fp_random.Random(seed*109343+191)
    ports=_fp_defaultdict(lambda:{'R':set(),'W':set(),'C':set()})
    # Kleine Raster: einfache Basis, ohne Fehlermeldung bei fehlendem Platz.
    if columns<8 or rows<8:
        return tuple((-1,0,(_FP_EMPTY,)*4) for i in range(columns*rows))

    # Gleicher Seed -> die Basisnetze sind immer dieselben. Mit hoeherem
    # road/water werden neue Aeste HINZUGEFUEGT statt komplett neu gelost.
    backbone_rng=_fp_random.Random(seed*109343+191)
    road_first=_fp_route_tree(backbone_rng,columns,rows,ports)
    if road_first is None:raise RuntimeError('Strassen-Netz konnte nicht erzeugt werden.')
    anchor,road_main=road_first
    if water>0.01:
        water_rng=_fp_random.Random(seed*48271+1019)
        water_main=_fp_water_tree(water_rng,columns,rows,ports,anchor)
        if water_main is None:
            raise RuntimeError('Fluss-Netz konnte nicht erzeugt werden.')
        if columns>=12 and rows>=12:
            _fp_join_river_road_corner(ports,water_rng,columns,rows)


    cities=[]
    if city>.01:
        grid_area=rows*columns
        target=1 if grid_area<140 else (2 if grid_area<280 else 3)
        reserve=set()
        for k in range(target):
            # Ein eigener fester Zufallsstrom pro Stadt: dieselben Positionen
            # bei city=.2, .6 und 1.0 (wenn die Platzierung moeglich ist).
            city_rng=_fp_random.Random(seed*754879+137*k+901)
            factor=.60+.38*city_rng.random()
            other=3.0+2*city_rng.random()
            width=2+int(factor*city*5.0)
            height=2+int(factor*city*other)
            max_width=2+int(factor*5.0)
            max_height=2+int(factor*other)
            placed=_fp_place_city(ports,city_rng,columns,rows,width,height,
                                  tail=(k%3==1),prefer_border=(k==0),
                                  prefer_corner=(k==0),reserve=reserve,
                                  max_width=max_width,max_height=max_height)
            if placed:cities.append(placed)
        if city>.13:
            _fp_mini_city(ports,_fp_random.Random(seed*4951+17),columns,rows)

    if water>0.01:
        # Wasser-Regler: von einem Hauptfluss zu einem verzweigten Netz.
        _fp_grow_network(water_rng,ports,'W',columns,rows,water,steps=6)

    # Weg-Regler: von einer Hauptstrasse zu einem dichteren Wegenetz.
    # Eine Grundstrasse bleibt auch bei road=0, damit Staedte einen
    # Strassenzugang bekommen koennen.
    road_rng=_fp_random.Random(seed*73727+409)
    _fp_grow_network(road_rng,ports,'R',columns,rows,road,steps=7)

    board=[]
    used=_fp_Counter()
    for y in range(rows):
        for x in range(columns):
            v=ports.get((y,x))
            if v is None or not any(v[k] for k in ('R','W','C')):
                board.append((-1,0,(_FP_EMPTY,)*4));continue
            found=_fp_select_tile(tuple(sorted(v['R'])),tuple(sorted(v['W'])),
                                  tuple(sorted(v['C'])))
            if found is None:
                raise RuntimeError('Keine DXF-Kachel fuer Zellanschluesse in {}: {}'.format((y,x),v))
            used[found[0]+1]+=1;board.append(found)
    layout=tuple(board)
    errs=_fp_validate_grid(layout,columns,rows)
    if errs:raise RuntimeError('Nachbaranschluss-Fehler: '+str(errs[:4]))
    sizes,unserved=_fp_city_access(layout,columns,rows)
    if unserved:raise RuntimeError('{} Staedte ohne Strassenanschluss'.format(unserved))
    return layout


def create_dxf_floor_pattern(columns=16,rows=18,tile_size=100.,
                             road=.65,water=.55,city=.55,seed=5):
    """EINZIGE Hauptfunktion fuer deine GH-Python-3-Komponente.
    Alle DXF-Flaechen sind in dieser algorithms.py bereits gespeichert.
    """
    import Rhino.Geometry as rg
    from System.Drawing import Color
    columns=int(columns);rows=int(rows);tile_size=float(tile_size)
    seed=int(seed);road=float(road);water=float(water);city=float(city)
    if not (1<=columns<=30 and 1<=rows<=30):
        raise ValueError('columns und rows muessen zwischen 1 und 30 liegen.')
    if tile_size<=0:raise ValueError('tile_size muss groesser als 0 sein.')
    if not all(0<=v<=1 for v in (road,water,city)):
        raise ValueError('road, water, city muessen zwischen 0 und 1 liegen.')
    layout=_fp_layout(columns,rows,round(road,4),round(water,4),round(city,4),seed)
    meshes={name:rg.Mesh() for name in 'GRWC'}
    width=columns*tile_size;height=rows*tile_size
    m=meshes['G']
    for x,y in ((-width/2,-height/2),(width/2,-height/2),
                (width/2,height/2),(-width/2,height/2)):
        m.Vertices.Add(x,y,0.)
    m.Faces.AddFace(0,1,2,3)
    artwork=_fp_artwork()
    counts=_fp_Counter()
    info=[]
    for i,(index,rot,edges) in enumerate(layout):
        if index<0:continue
        y,x=divmod(i,columns)
        counts[index+1]+=1
        bx=x*tile_size-width/2;by=height/2-y*tile_size
        for kind,coords,triangles in artwork[index]:
            mesh=meshes[kind];offset=mesh.Vertices.Count
            z=tile_size*{'W':.0002,'R':.0003,'C':.0004}[kind]
            for ux,uy in coords:
                xx,yy=_fp_turn_xy(ux,uy,rot)
                if kind=='R':xx,yy=_fp_stitch_road(xx,yy,edges)
                mesh.Vertices.Add(bx+xx*tile_size/10000.,
                                  by-yy*tile_size/10000.,z)
            for a,b,c in triangles:mesh.Faces.AddFace(offset+a,offset+b,offset+c)
        info.append('({},{})  Kachel {:02d} / Drehung {} Grad'.format(
                     y+1,x+1,index+1,90*rot))
    keys=[k for k in 'GRWC' if meshes[k].Faces.Count>0]
    for k in keys:meshes[k].Normals.ComputeNormals();meshes[k].Compact()
    roads=_fp_network_components(layout,columns,rows,'R')
    waters=_fp_network_components(layout,columns,rows,'W')
    sizes,unserved=_fp_city_access(layout,columns,rows)
    boundary_cities=0
    for component in _fp_network_components(layout,columns,rows,'C'):
        if any((k//columns in (0,rows-1) or k%columns in (0,columns-1))
               for k in component):boundary_cities+=1
    missing=[i for i in range(1,18) if counts[i]==0]
    stats=('DXF V11 | Raster {}x{} | Staedte: {} | davon am Rand: {} | '
           'ohne Strasse: {} | Strassen-Netze: {} (groesstes {} Kacheln) | '
           'Fluss-Netze: {} (groesstes {} Kacheln) | '
           'Road: {:.2f} ({} Kacheln) | Water: {:.2f} ({} Kacheln) | '
           'Bruecke #6: {} | Flusskurve #16: {} | Flussgabel #17: {} | '
           'genutzte Motive: {}/17 | fehlend: {}').format(
            columns,rows,','.join(map(str,sizes)) if sizes else 'keine',
            boundary_cities,unserved,len(roads),max(map(len,roads)) if roads else 0,
            len(waters),max(map(len,waters)) if waters else 0,
            road,sum(any('R' in side for side in t[2]) for t in layout),
            water,sum(any('W' in side for side in t[2]) for t in layout),
            counts[6],counts[16],counts[17],17-len(missing),
            ', '.join(map(str,missing)) if missing else 'keine')
    return {'display_geometry':[meshes[k] for k in keys],
            'display_colors':[Color.FromArgb(*_FP_COLORS[k]) for k in keys],
            'tile_info':info,'invalid_edges':0,'statistics':stats}
