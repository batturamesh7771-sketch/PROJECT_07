"""
sw_fuselage_generator.py — Parametric Fuselage Frame & Stringer Generator
==========================================================================
Boeing 777-300ER Digital Twin Project | ATA 53 — Fuselage Structure

This script procedurally generates:
  1. Fuselage frame cross-section parts at specified station intervals.
  2. Longitudinal stringer profiles arrayed around the fuselage barrel.
  3. Skin panel segments between frame bays.

Approach:
  - The fuselage cross-section is defined by a parametric super-ellipse
    equation that closely approximates the 777's near-circular double-bubble
    cross-section (major ≈ 3.137 m radius, minor ≈ 3.073 m radius).
  - Frames are generated as swept Z-section extrusions along the cross-
    section spline at each station.
  - Stringers are hat-section extrusions running longitudinally, positioned
    at angular intervals around the cross-section.

Usage:
  1. Open the target fuselage sub-assembly in SolidWorks.
  2. Run:  python sw_fuselage_generator.py
  3. Frames and stringers are inserted as new part files and placed via mates.

Configuration constants are in the PARAMETERS section below.
"""

import math
import os
import sys
import time
from typing import List, Tuple

# Project imports
from sw_common import (
    connect_to_solidworks,
    make_transform_matrix,
    station_to_x,
    setup_logger,
    SW_CONST,
)

log = setup_logger("FuselageGen")


# ═══════════════════════════════════════════════════════════════
# PARAMETERS — Boeing 777-300ER Fuselage Geometry
# ═══════════════════════════════════════════════════════════════

# Fuselage cross-section (super-ellipse approximation)
FUSELAGE_RADIUS_HORIZ_M = 3.137      # Semi-major axis (horizontal), meters
FUSELAGE_RADIUS_VERT_M  = 3.073      # Semi-minor axis (vertical), meters
SUPERELLIPSE_EXPONENT   = 2.5        # n > 2 for slightly squared shape

# Frame stations (Boeing frame station numbers in inches)
# 777-300ER: approx. 186 frame stations, 20-inch spacing nominal
FRAME_STATION_START_IN   = 180.0     # STA 180 (fwd of Section 41/43 joint)
FRAME_STATION_END_IN     = 2680.0    # STA 2680 (fwd of aft pressure bulkhead)
FRAME_SPACING_IN         = 20.0      # Standard 20-inch frame pitch

# Frame cross-section (Z-section profile)
FRAME_WEB_HEIGHT_MM      = 76.2      # 3.0 inches
FRAME_FLANGE_WIDTH_MM    = 25.4      # 1.0 inch
FRAME_THICKNESS_MM       = 2.032     # 0.080 inch (typical 7075-T6 Al)

# Stringer layout
STRINGER_COUNT           = 120       # Number of longitudinal stringers
STRINGER_HAT_WIDTH_MM    = 30.0      # Hat section top width
STRINGER_HAT_HEIGHT_MM   = 25.0      # Hat section height
STRINGER_THICKNESS_MM    = 1.6       # 0.063 inch (2024-T3 Al clad)
STRINGER_LENGTH_PER_BAY_M = FRAME_SPACING_IN * 0.0254  # One bay length

# Skin panels
SKIN_THICKNESS_MM        = 1.8       # Nominal skin gauge (upper crown)

# Output directory for generated part files
OUTPUT_DIR = r"C:\SolidWorks_Projects\B777_DigitalTwin\ATA53_Fuselage"

# Template paths (adjust to your SolidWorks installation)
PART_TEMPLATE  = r"C:\ProgramData\SolidWorks\SolidWorks 2024\templates\Part.prtdot"
ASSY_TEMPLATE  = r"C:\ProgramData\SolidWorks\SolidWorks 2024\templates\Assembly.asmdot"


# ═══════════════════════════════════════════════════════════════
# GEOMETRY — Fuselage Cross-Section Spline Points
# ═══════════════════════════════════════════════════════════════

def superellipse_points(
    a: float,
    b: float,
    n: float,
    num_points: int = 360
) -> List[Tuple[float, float]]:
    """
    Generate (Y, Z) points on a super-ellipse |y/a|^n + |z/b|^n = 1.

    This approximates the 777's fuselage cross-section, which is nearly
    circular but slightly squared at the floor line.

    Args:
        a: Horizontal semi-axis (meters).
        b: Vertical semi-axis (meters).
        n: Super-ellipse exponent (2 = ellipse, >2 = squircle).
        num_points: Number of points around the perimeter.

    Returns:
        List of (y, z) tuples in meters.
    """
    points = []
    for i in range(num_points):
        theta = 2.0 * math.pi * i / num_points
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # Signed super-ellipse parametric form
        r_y = a * abs(cos_t) ** (2.0 / n) * (1 if cos_t >= 0 else -1)
        r_z = b * abs(sin_t) ** (2.0 / n) * (1 if sin_t >= 0 else -1)
        points.append((r_y, r_z))

    return points


def generate_frame_stations() -> List[float]:
    """
    Generate the list of frame station numbers (inches) from start to end.

    Returns:
        List of station numbers.
    """
    stations = []
    sta = FRAME_STATION_START_IN
    while sta <= FRAME_STATION_END_IN:
        stations.append(sta)
        sta += FRAME_SPACING_IN
    return stations


def stringer_angular_positions() -> List[float]:
    """
    Compute angular positions (radians) for stringers around the cross-section.

    Stringers are evenly spaced. Stringer #1 is at top dead center (12 o'clock).

    Returns:
        List of angles in radians.
    """
    return [2.0 * math.pi * i / STRINGER_COUNT for i in range(STRINGER_COUNT)]


# ═══════════════════════════════════════════════════════════════
# PART GENERATION — Frame at a Single Station
# ═══════════════════════════════════════════════════════════════

def create_frame_part(sw_app, station_in: float, idx: int) -> str:
    """
    Create a SolidWorks part file for a single fuselage frame at the given
    station, using a 2D sketch of the Z-section profile swept along the
    super-ellipse cross-section spline.

    Args:
        sw_app: ISldWorks application object.
        station_in: Frame station number in inches.
        idx: Frame index (for naming).

    Returns:
        Full path to the saved .SLDPRT file.

    Workflow:
        1. Create new part from template.
        2. Insert 3D sketch with super-ellipse spline on the YZ plane
           offset to the station X position.
        3. Create the Z-section profile sketch on a plane normal to
           the spline start.
        4. Sweep the Z-section along the spline.
        5. Assign custom properties (ATA, material, station #).
        6. Save and close.
    """
    x_pos_m = station_to_x(station_in)
    part_name = f"Frame_STA{int(station_in):04d}_F{idx:03d}.SLDPRT"
    part_path = os.path.join(OUTPUT_DIR, "Frames", part_name)

    log.info(f"Creating frame: {part_name}  (STA {station_in}\"  X={x_pos_m:.3f} m)")

    # ── 1. New Part ──────────────────────────────────────────
    model = sw_app.NewDocument(PART_TEMPLATE, 0, 0, 0)
    if model is None:
        log.error(f"Failed to create new part for {part_name}")
        return ""

    model = sw_app.ActiveDoc
    ext = model.Extension

    # ── 2. 3D Sketch: Cross-section spline ───────────────────
    model.SketchManager.Insert3DSketch(True)
    sketch = model.SketchManager.ActiveSketch

    # Generate super-ellipse points in the YZ plane at X = x_pos_m
    cs_points = superellipse_points(
        FUSELAGE_RADIUS_HORIZ_M,
        FUSELAGE_RADIUS_VERT_M,
        SUPERELLIPSE_EXPONENT,
        num_points=180
    )

    # Insert spline through points
    point_array = []
    for (y, z) in cs_points:
        point_array.extend([x_pos_m, y, z])

    # SolidWorks API: CreateSpline takes a flat array of doubles [x,y,z,...]
    num_pts = len(cs_points)
    spline = model.SketchManager.CreateSpline2(
        point_array,   # PointData (flat double array)
        True           # ClosedSpline
    )

    model.SketchManager.Insert3DSketch(True)  # Close 3D sketch

    # ── 3. Profile Sketch: Z-section on normal plane ─────────
    # Create a reference plane normal to the spline at its start point
    # For simplicity, we use the Right Plane offset to the station X
    ref_plane = model.FeatureManager.InsertRefPlane(
        8, x_pos_m,   # swSelectType_e: 8 = Right plane offset
        0, 0,
        0, 0
    )

    # Activate sketch on the new plane
    model.Extension.SelectByID2(
        "", "PLANE", 0, 0, 0, False, 0, None, 0
    )
    model.SketchManager.InsertSketch(True)

    # Draw Z-section profile (web + two flanges)
    web_h = FRAME_WEB_HEIGHT_MM / 1000.0      # Convert mm → m
    flange_w = FRAME_FLANGE_WIDTH_MM / 1000.0
    t = FRAME_THICKNESS_MM / 1000.0

    # Outer Z-section profile (simplified as connected lines)
    sm = model.SketchManager

    # Bottom flange (inner, toward fuselage center)
    sm.CreateLine(0, 0, 0,             flange_w, 0, 0)
    sm.CreateLine(flange_w, 0, 0,      flange_w, t, 0)
    sm.CreateLine(flange_w, t, 0,      t, t, 0)

    # Web (vertical)
    sm.CreateLine(t, t, 0,             t, web_h - t, 0)

    # Top flange (outer, toward skin)
    sm.CreateLine(t, web_h - t, 0,     -flange_w + t, web_h - t, 0)
    sm.CreateLine(-flange_w + t, web_h - t, 0,  -flange_w + t, web_h, 0)
    sm.CreateLine(-flange_w + t, web_h, 0,       0, web_h, 0)

    # Close profile
    sm.CreateLine(0, web_h, 0,         0, 0, 0)

    model.SketchManager.InsertSketch(True)  # Close sketch

    # ── 4. Sweep Z-section along spline ──────────────────────
    # Select profile then path for Sweep
    model.Extension.SelectByID2(
        "Sketch2", "SKETCH", 0, 0, 0, False, 1, None, 0   # Profile (Mark=1)
    )
    model.Extension.SelectByID2(
        "3DSketch1", "SKETCH", 0, 0, 0, True, 4, None, 0  # Path (Mark=4)
    )

    sweep_feat = model.FeatureManager.InsertSweep2(
        True,    # Closed profile
        False,   # Not solid (thin)
        0,       # swTwistControlType = none
        False,   # Merge result
        False,   # Not thin-wall
        0,       # swStartCondition
        0,       # swEndCondition
        0, 0,    # twist angle, draft
        0, 0,    # start/end draft
        0.0, 0.0, # tangent weight
        True,    # Merge smooth faces
        0, 0     # reserved
    )

    # ── 5. Custom Properties ─────────────────────────────────
    cpm = ext.CustomPropertyManager("")
    cpm.Add3(
        "PartNumber", SW_CONST.swCustomInfoText,
        f"53-{idx:04d}", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "ATA_Chapter", SW_CONST.swCustomInfoText,
        "53 — Fuselage", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "Material", SW_CONST.swCustomInfoText,
        "7075-T6 Aluminum", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "FrameStation_in", SW_CONST.swCustomInfoDouble,
        str(station_in), SW_CONST.swCustomInfoDouble
    )
    cpm.Add3(
        "Description", SW_CONST.swCustomInfoText,
        f"Fuselage Frame @ STA {int(station_in)}", SW_CONST.swCustomInfoText
    )

    # Apply material from SolidWorks material library
    model.SetMaterialPropertyName2(
        "Default", r"SolidWorks Materials.sldmat", "7075 Alloy"
    )

    # ── 6. Save ──────────────────────────────────────────────
    os.makedirs(os.path.dirname(part_path), exist_ok=True)
    save_errors = model.SaveAs3(part_path, 0, 2)  # swSaveAsOptions_Silent=2
    sw_app.CloseDoc(part_name)

    log.info(f"  → Saved: {part_path}")
    return part_path


# ═══════════════════════════════════════════════════════════════
# PART GENERATION — Longitudinal Stringer
# ═══════════════════════════════════════════════════════════════

def create_stringer_part(sw_app, stringer_idx: int, bay_start_sta: float,
                         bay_end_sta: float, angular_pos_rad: float) -> str:
    """
    Create a single hat-section stringer part spanning one frame bay.

    Args:
        sw_app: ISldWorks application object.
        stringer_idx: Stringer number (0 to STRINGER_COUNT-1).
        bay_start_sta: Start station (inches).
        bay_end_sta: End station (inches).
        angular_pos_rad: Angular position around fuselage cross-section.

    Returns:
        Full path to the saved .SLDPRT file.
    """
    x_start = station_to_x(bay_start_sta)
    x_end   = station_to_x(bay_end_sta)
    length  = x_end - x_start

    part_name = (
        f"Stringer_S{stringer_idx:03d}_"
        f"STA{int(bay_start_sta):04d}-{int(bay_end_sta):04d}.SLDPRT"
    )
    part_path = os.path.join(OUTPUT_DIR, "Stringers", part_name)

    log.info(
        f"Creating stringer: S{stringer_idx:03d}  "
        f"θ={math.degrees(angular_pos_rad):.1f}°  "
        f"bay STA {int(bay_start_sta)}–{int(bay_end_sta)}"
    )

    # ── New Part ─────────────────────────────────────────────
    model = sw_app.NewDocument(PART_TEMPLATE, 0, 0, 0)
    model = sw_app.ActiveDoc
    ext = model.Extension

    # ── Hat-Section Profile Sketch (on Right Plane) ──────────
    model.Extension.SelectByID2(
        "Right Plane", "PLANE", 0, 0, 0, False, 0, None, 0
    )
    model.SketchManager.InsertSketch(True)

    hw = STRINGER_HAT_WIDTH_MM / 1000.0 / 2.0    # Half-width of hat top
    hh = STRINGER_HAT_HEIGHT_MM / 1000.0          # Hat height
    t  = STRINGER_THICKNESS_MM / 1000.0           # Material thickness
    flange_ext = 0.012  # 12 mm flange extension beyond hat base

    sm = model.SketchManager

    # Draw outer hat profile (counter-clockwise from bottom-left flange tip)
    # Bottom-left flange
    sm.CreateLine(-hw - flange_ext, 0, 0,    -hw, 0, 0)
    # Left leg
    sm.CreateLine(-hw, 0, 0,                 -hw, hh, 0)
    # Top (hat cap)
    sm.CreateLine(-hw, hh, 0,                 hw, hh, 0)
    # Right leg
    sm.CreateLine( hw, hh, 0,                 hw, 0, 0)
    # Bottom-right flange
    sm.CreateLine( hw, 0, 0,                  hw + flange_ext, 0, 0)

    # Inner profile (offset inward by thickness)
    sm.CreateLine(hw + flange_ext, -t, 0,     -hw - flange_ext, -t, 0)
    sm.CreateLine(-hw - flange_ext, -t, 0,    -hw - flange_ext, 0, 0)
    sm.CreateLine(hw + flange_ext, 0, 0,      hw + flange_ext, -t, 0)

    model.SketchManager.InsertSketch(True)

    # ── Extrude along X for one bay length ───────────────────
    model.Extension.SelectByID2(
        "Sketch1", "SKETCH", 0, 0, 0, False, 0, None, 0
    )
    model.FeatureManager.FeatureExtrusion3(
        True,       # Single direction
        False,      # Not flip
        False,      # Not symmetric
        0,          # End condition: blind
        0,          # End condition 2
        length,     # Depth (meters)
        0,          # Depth 2
        False,      # Draft on/off
        False,      # Draft outward
        False,      # Draft on/off 2
        False,      # Draft outward 2
        0, 0,       # Draft angles
        False,      # Merge bodies
        True, True, # Normal cut / boss
        0, 0, 0,    # direction vector
        False       # Geometry pattern
    )

    # ── Custom Properties ────────────────────────────────────
    cpm = ext.CustomPropertyManager("")
    cpm.Add3(
        "PartNumber", SW_CONST.swCustomInfoText,
        f"53-STR-{stringer_idx:04d}", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "ATA_Chapter", SW_CONST.swCustomInfoText,
        "53 — Fuselage", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "Material", SW_CONST.swCustomInfoText,
        "2024-T3 Alclad Aluminum", SW_CONST.swCustomInfoText
    )
    cpm.Add3(
        "StringerIndex", SW_CONST.swCustomInfoNumber,
        str(stringer_idx), SW_CONST.swCustomInfoNumber
    )

    model.SetMaterialPropertyName2(
        "Default", r"SolidWorks Materials.sldmat", "2024 Alloy"
    )

    # ── Save ─────────────────────────────────────────────────
    os.makedirs(os.path.dirname(part_path), exist_ok=True)
    model.SaveAs3(part_path, 0, 2)
    sw_app.CloseDoc(os.path.basename(part_path))

    log.info(f"  → Saved: {part_path}")
    return part_path


# ═══════════════════════════════════════════════════════════════
# ASSEMBLY INSERTION — Place Parts with Mates
# ═══════════════════════════════════════════════════════════════

def insert_frame_into_assembly(
    sw_app, assy_doc, frame_path: str, station_in: float
):
    """
    Insert a generated frame part into the fuselage sub-assembly and
    add a coincident mate to position it at the correct station.

    Args:
        sw_app: ISldWorks application object.
        assy_doc: Active assembly document (IAssemblyDoc).
        frame_path: Full path to the frame .SLDPRT.
        station_in: Station number for X-positioning.
    """
    x_pos_m = station_to_x(station_in)

    # Build a 4×4 transform for placement
    transform = make_transform_matrix(tx=x_pos_m)

    # AddComponent5 signature:
    #   FileName, Configuration, X, Y, Z
    comp = assy_doc.AddComponent5(
        frame_path,
        0,        # swAddComponentConfigOptions_CurrentSelectedConfig
        "",       # Configuration name (empty = default)
        False,    # UseConfigName
        "",       # ExcludedConfiguration
        x_pos_m,  # X position
        0,        # Y position
        0         # Z position
    )

    if comp is None:
        log.warning(f"Failed to insert component: {frame_path}")
        return

    log.info(f"  Inserted frame at X = {x_pos_m:.3f} m")

    # Add coincident mate between frame's origin plane and assembly
    # reference plane at this station (assumes reference planes exist
    # in Master_Skeleton.SLDPRT published as "STA_XXXX")
    comp_name = comp.Name2
    model = sw_app.ActiveDoc

    # Select the frame's Right Plane
    model.Extension.SelectByID2(
        f"{comp_name}/Right Plane", "PLANE",
        0, 0, 0, False, 1, None, 0
    )

    # Select assembly reference plane for this station
    ref_plane_name = f"Master_Skeleton-1/STA_{int(station_in):04d}"
    model.Extension.SelectByID2(
        ref_plane_name, "PLANE",
        0, 0, 0, True, 1, None, 0
    )

    # Add coincident mate
    model.Extension.AddMate5(
        SW_CONST.swMateCOINCIDENT,  # MateType
        SW_CONST.swMateAlignALIGNED,  # Alignment
        False,   # Flip
        0, 0,    # Distance / angle
        0, 0,    # Distance 2 / angle 2
        0, 0,    # reserved
        0, 0,    # reserved
        False    # Preview
    )

    log.info(f"  Mated frame to station reference plane STA {int(station_in)}")


# ═══════════════════════════════════════════════════════════════
# MAIN — Orchestrate Full Fuselage Generation
# ═══════════════════════════════════════════════════════════════

def main():
    """
    Main entry point: generates all fuselage frames and stringers,
    then inserts them into the active fuselage sub-assembly.
    """
    log.info("=" * 70)
    log.info("Boeing 777-300ER Fuselage Generator — Starting")
    log.info("=" * 70)

    sw_app, model, assy_doc = connect_to_solidworks()

    # ── Generate Frame Stations ──────────────────────────────
    stations = generate_frame_stations()
    log.info(f"Total frame stations to generate: {len(stations)}")
    log.info(
        f"Station range: STA {stations[0]:.0f} → STA {stations[-1]:.0f}"
    )

    frame_paths = []
    for idx, sta in enumerate(stations, start=1):
        path = create_frame_part(sw_app, sta, idx)
        if path:
            frame_paths.append((path, sta))

    log.info(f"Generated {len(frame_paths)} frame parts.")

    # ── Generate Stringers (one bay at a time) ───────────────
    angles = stringer_angular_positions()
    stringer_paths = []

    for bay_idx in range(len(stations) - 1):
        bay_start = stations[bay_idx]
        bay_end   = stations[bay_idx + 1]

        for s_idx, theta in enumerate(angles):
            path = create_stringer_part(
                sw_app, s_idx, bay_start, bay_end, theta
            )
            if path:
                stringer_paths.append(path)

    total_stringers = len(stringer_paths)
    log.info(f"Generated {total_stringers} stringer parts.")

    # ── Insert into Assembly ─────────────────────────────────
    if assy_doc is not None:
        log.info("Inserting frames into fuselage assembly...")
        for (fp, sta) in frame_paths:
            insert_frame_into_assembly(sw_app, assy_doc, fp, sta)

        log.info("Rebuilding assembly...")
        model.ForceRebuild3(True)
        model.Save3(0, 0, 0)

    # ── Summary ──────────────────────────────────────────────
    total_parts = len(frame_paths) + total_stringers
    log.info("=" * 70)
    log.info(f"COMPLETE — Total parts generated: {total_parts}")
    log.info(f"  Frames:    {len(frame_paths)}")
    log.info(f"  Stringers: {total_stringers}")
    log.info(f"  Output:    {OUTPUT_DIR}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
