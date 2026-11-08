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

def create_cone(base_point=None, height=10.0, radius=5.0, cap_bottom=True):
    """
    Build a cone as a Brep.

    base_point : Rhino.Geometry.Point3d -- center of the cone's base circle
    height     : float -- cone height along the base plane's normal (Z by default)
    radius     : float -- base circle radius
    cap_bottom : bool  -- whether to cap the base circle (closed vs open cone)

    Returns a Rhino.Geometry.Brep.
    """
    if base_point is None:
        base_point = rg.Point3d(15, 15, 0)

    plane = rg.Plane(base_point, rg.Vector3d.ZAxis)
    cone = rg.Cone(plane, height, radius)
    return cone.ToBrep(cap_bottom)

def create_sphere(center_point=None, radius=5.0):
    """Create a sphere as a Brep."""

    if center_point is None:
        center_point = rg.Point3d(0, 0, 0)

    sphere = rg.Sphere(center_point, radius)

    return sphere.ToBrep()


def create_torus_around_sphere(center_point=None, sphere_radius=5.0, tube_radius=1.0):
    """
    Create a torus surrounding a sphere, tangent to it at the equator.

    center_point : Rhino.Geometry.Point3d -- center of the sphere and torus
    sphere_radius : float -- radius of the sphere enclosed by the torus
    tube_radius : float -- radius of the torus tube

    Returns a Rhino.Geometry.Brep.
    """
    if center_point is None:
        center_point = rg.Point3d(-15,-15, 0)
    if sphere_radius <= 0:
        raise ValueError("sphere_radius must be greater than zero.")
    if tube_radius <= 0:
        raise ValueError("tube_radius must be greater than zero.")

    plane = rg.Plane(center_point, rg.Vector3d.ZAxis)
    torus = rg.Torus(plane, sphere_radius + tube_radius, tube_radius)
    return torus.ToBrep()


def create_rotated_spheres(
    center_point=None,
    radius=1,
    copy_count=4,
    angle_step_degrees=45.0,
    axis_origin=None,
    axis_direction=None,
):
    """Create spheres rotated around an axis, including the original.

    center_point : Rhino.Geometry.Point3d -- center of the original sphere
    radius : float -- radius of the first sphere; each next sphere adds 5 units
    copy_count : int -- total number of spheres, including the original
    angle_step_degrees : float -- rotation between consecutive spheres
    axis_origin : Rhino.Geometry.Point3d -- point on the rotation axis
    axis_direction : Rhino.Geometry.Vector3d -- direction of the rotation axis

    Returns a list of Rhino.Geometry.Brep objects. To see the copies move,
    place center_point off the rotation axis.
    """
    if center_point is None:
        center_point = rg.Point3d(1, 5, 1)
    if axis_origin is None:
        axis_origin = rg.Point3d(-5, 0, 0)
    if axis_direction is None:
        axis_direction = rg.Vector3d.ZAxis

    if not isinstance(copy_count, int) or isinstance(copy_count, bool):
        raise TypeError("copy_count must be an integer.")
    if copy_count < 1:
        raise ValueError("copy_count must be at least one.")

    axis_direction = rg.Vector3d(axis_direction)
    if not axis_direction.IsValid or not axis_direction.Unitize():
        raise ValueError("axis_direction must be a non-zero valid vector.")

    spheres = []

    for i in range(copy_count):
        sphere_copy = rg.Sphere(center_point, radius + 1 * i).ToBrep()
        if i > 0:
            angle = math.radians(angle_step_degrees * i)
            rotation = rg.Transform.Rotation(angle, axis_direction, axis_origin)
            if not sphere_copy.Transform(rotation):
                raise RuntimeError("Failed to rotate a sphere copy.")
        spheres.append(sphere_copy)

    return spheres


def create_box(width=10.0, depth=10.0, height=5.0):
    """Create a box as a Brep."""

    box = rg.Box(
        rg.Plane.WorldXY,
        rg.Interval(-width / 2, width / 2),
        rg.Interval(-depth / 2, depth / 2),
        rg.Interval(0, height)
    )

    return box.ToBrep()
def boolean_difference(brep_a, brep_b):
    """
    Subtract brep_b from brep_a, accepting a Brep or list of Breps for either input.

    brep_a : Rhino.Geometry.Brep or list -- the Brep(s) to subtract from
    brep_b : Rhino.Geometry.Brep or list -- the Brep(s) to subtract

    Returns a list of Rhino.Geometry.Brep resulting from the difference.
    """
    if brep_a is None or brep_b is None:
        raise ValueError("Both brep_a and brep_b must be provided.")

    if isinstance(brep_a, rg.Brep):
        brep_a = [brep_a]
    if isinstance(brep_b, rg.Brep):
        brep_b = [brep_b]

    result = rg.Brep.CreateBooleanDifference(brep_a, brep_b, 0.001)
    return result


def copy_brep_along_z(brep, distance, copy_count):
    """
    Create copies of a Brep, each offset in the +Z direction.

    brep : Rhino.Geometry.Brep -- the Brep to copy
    distance : float -- the Z spacing between consecutive copies
    copy_count : int -- the number of copies to create

    Returns a list of Rhino.Geometry.Brep copies; copy i is moved by distance * (i + 1).
    """
    if brep is None:
        raise ValueError("brep must be provided.")
    if copy_count < 0:
        raise ValueError("copy_count must not be negative.")

    copies = []
    for i in range(1, int(copy_count) + 1):
        copy = brep.DuplicateBrep()
        copy.Transform(rg.Transform.Translation(rg.Vector3d(0, 0, distance * i)))
        copies.append(copy)
    return copies

def mybool():
    spheres = create_rotated_spheres(copy_count=5)
    box = create_box(width=10, depth=10, height=5)
    a = boolean_difference( box, spheres)
    return a