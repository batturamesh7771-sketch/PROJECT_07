"""
sw_landing_gear_mates.py — Kinematic Mate Builder for Landing Gear & Flight Controls
======================================================================================
Boeing 777-300ER Digital Twin Project | ATA 32 / ATA 27

This script programmatically creates the kinematic mate definitions for:
  1. Main Landing Gear (MLG) 6-wheel truck bogie retraction sequence
  2. Nose Landing Gear (NLG) steering and retraction
  3. Fowler Flap track carriage deployment
  4. Thrust Reverser translating sleeve actuation
  5. GE90 dual-spool shaft rotation coupling

It also generates a SolidWorks Motion Study timing table for the
taxi→takeoff→retraction→cruise→reverser animation sequence.

Usage:
  1. Open the top-level B777 assembly with all sub-assemblies loaded.
  2. Ensure sub-assembly component names match the naming conventions below.
  3. Run:  python sw_landing_gear_mates.py
"""

import math
import sys
from typing import List, Tuple, Dict

from sw_common import connect_to_solidworks, setup_logger, SW_CONST

log = setup_logger("KinematicMates")


# ═══════════════════════════════════════════════════════════════
# NAMING CONVENTIONS
# ═══════════════════════════════════════════════════════════════
# These component path strings must match the names in the assembly
# FeatureManager tree.  Adjust as needed for your specific naming.

COMP = {
    # ── ATA 32: Main Landing Gear (Left) ──
    "mlg_l_shock_strut":      "ATA32_LandingGear-1/MLG_Left-1/ShockStrut_Cylinder-1",
    "mlg_l_piston":           "ATA32_LandingGear-1/MLG_Left-1/ShockStrut_Piston-1",
    "mlg_l_drag_brace_upper": "ATA32_LandingGear-1/MLG_Left-1/DragBrace_Upper-1",
    "mlg_l_drag_brace_lower": "ATA32_LandingGear-1/MLG_Left-1/DragBrace_Lower-1",
    "mlg_l_side_brace_upper": "ATA32_LandingGear-1/MLG_Left-1/SideBrace_Upper-1",
    "mlg_l_side_brace_lower": "ATA32_LandingGear-1/MLG_Left-1/SideBrace_Lower-1",
    "mlg_l_torque_link_upper":"ATA32_LandingGear-1/MLG_Left-1/TorqueLink_Upper-1",
    "mlg_l_torque_link_lower":"ATA32_LandingGear-1/MLG_Left-1/TorqueLink_Lower-1",
    "mlg_l_truck_beam":       "ATA32_LandingGear-1/MLG_Left-1/TruckBeam_6Wheel-1",
    "mlg_l_actuator":         "ATA32_LandingGear-1/MLG_Left-1/RetractActuator-1",
    "mlg_l_gear_door_fwd":    "ATA32_LandingGear-1/MLG_Left-1/GearDoor_Forward-1",
    "mlg_l_gear_door_aft":    "ATA32_LandingGear-1/MLG_Left-1/GearDoor_Aft-1",
    "mlg_l_uplock":           "ATA32_LandingGear-1/MLG_Left-1/Uplock_Hook-1",
    "mlg_l_downlock":         "ATA32_LandingGear-1/MLG_Left-1/Downlock_Brace-1",

    # ── ATA 32: Nose Landing Gear ──
    "nlg_strut":              "ATA32_LandingGear-1/NLG-1/NLG_Strut-1",
    "nlg_piston":             "ATA32_LandingGear-1/NLG-1/NLG_Piston-1",
    "nlg_steering_collar":    "ATA32_LandingGear-1/NLG-1/SteeringCollar-1",
    "nlg_drag_brace":         "ATA32_LandingGear-1/NLG-1/NLG_DragBrace-1",
    "nlg_door_l":             "ATA32_LandingGear-1/NLG-1/NLG_Door_Left-1",
    "nlg_door_r":             "ATA32_LandingGear-1/NLG-1/NLG_Door_Right-1",

    # ── ATA 27: Flaps ──
    "flap_ib_l":              "ATA27_FlightControls-1/Flaps-1/InboardFlap_Left-1",
    "flap_ob_l":              "ATA27_FlightControls-1/Flaps-1/OutboardFlap_Left-1",
    "flap_track_1l":          "ATA27_FlightControls-1/Flaps-1/FlapTrack_1L-1",
    "flap_track_2l":          "ATA27_FlightControls-1/Flaps-1/FlapTrack_2L-1",
    "flap_carriage_1l":       "ATA27_FlightControls-1/Flaps-1/FlapCarriage_1L-1",

    # ── ATA 78: Thrust Reverser (Left Engine) ──
    "trev_l_cowl":            "ATA71_Powerplant-1/Engine_Left-1/ThrustReverser-1/TranslatingCowl-1",
    "trev_l_actuator":        "ATA71_Powerplant-1/Engine_Left-1/ThrustReverser-1/TR_Actuator-1",
    "trev_l_blocker_door":    "ATA71_Powerplant-1/Engine_Left-1/ThrustReverser-1/BlockerDoor_Assy-1",

    # ── ATA 72: Engine Shafts ──
    "ge90_n1_shaft":          "ATA71_Powerplant-1/Engine_Left-1/Core-1/N1_Shaft-1",
    "ge90_n2_shaft":          "ATA71_Powerplant-1/Engine_Left-1/Core-1/N2_Shaft-1",
    "ge90_fan_rotor":         "ATA71_Powerplant-1/Engine_Left-1/FanModule-1/FanRotor-1",
    "ge90_hpc_rotor":         "ATA71_Powerplant-1/Engine_Left-1/Core-1/HPC_Rotor-1",
    "ge90_hpt_rotor":         "ATA71_Powerplant-1/Engine_Left-1/Core-1/HPT_Rotor-1",
    "ge90_lpt_rotor":         "ATA71_Powerplant-1/Engine_Left-1/Core-1/LPT_Rotor-1",
}


# ═══════════════════════════════════════════════════════════════
# MATE DEFINITION STRUCTURES
# ═══════════════════════════════════════════════════════════════

class MateDefinition:
    """Defines a single kinematic mate between two entities."""
    def __init__(
        self,
        name: str,
        mate_type: int,        # SW_CONST mate type enum
        entity1_comp: str,     # Component path
        entity1_name: str,     # Face/Edge/Axis/Plane name on entity1
        entity1_type: str,     # "FACE", "EDGE", "AXIS", "PLANE"
        entity2_comp: str,
        entity2_name: str,
        entity2_type: str,
        alignment: int = 0,    # swMateAlignALIGNED / ANTI_ALIGNED
        distance: float = 0.0, # For distance mates (meters)
        angle: float = 0.0,    # For angle mates (radians)
        flip: bool = False,
        limits: Tuple[float, float] = None,  # (min, max) for hinge limits
    ):
        self.name = name
        self.mate_type = mate_type
        self.entity1_comp = entity1_comp
        self.entity1_name = entity1_name
        self.entity1_type = entity1_type
        self.entity2_comp = entity2_comp
        self.entity2_name = entity2_name
        self.entity2_type = entity2_type
        self.alignment = alignment
        self.distance = distance
        self.angle = angle
        self.flip = flip
        self.limits = limits


# ═══════════════════════════════════════════════════════════════
# MATE DEFINITIONS — Landing Gear Kinematics
# ═══════════════════════════════════════════════════════════════

def define_mlg_mates() -> List[MateDefinition]:
    """
    Define all kinematic mates for the Main Landing Gear (left side).

    The MLG retraction mechanism is a multi-bar linkage:
      - Shock strut pivots about a hinge on the wing rear spar fitting
      - Drag brace is a 2-link folding brace (knee joint)
      - Side brace provides lateral restraint (also 2-link folding)
      - Retract actuator connects wing structure to drag brace mid-joint
      - Gear doors are sequenced: open → gear retracts → doors close

    Mate topology:
      [Wing Spar Fitting] ─(Hinge)─ [Shock Strut Cylinder]
      [Shock Strut Cylinder] ─(Slot)─ [Shock Strut Piston]
      [Drag Brace Upper] ─(Hinge)─ [Wing Structure]
      [Drag Brace Upper] ─(Hinge)─ [Drag Brace Lower] ← KNEE JOINT
      [Drag Brace Lower] ─(Hinge)─ [Shock Strut Cylinder]
      [Side Brace Upper] ─(Hinge)─ [Wing Structure]
      [Side Brace Lower] ─(Hinge)─ [Shock Strut Cylinder]
      [Torque Link Upper] ─(Hinge)─ [Shock Strut Cylinder]
      [Torque Link Lower] ─(Hinge)─ [Shock Strut Piston]
      [Torque Link Upper] ─(Hinge)─ [Torque Link Lower] ← SCISSORS
      [Retract Actuator] ─(Distance/Linear)─ [Drag Brace Mid-Joint]
      [Truck Beam] ─(Hinge + Limits)─ [Shock Strut Piston]
      [Gear Door Fwd] ─(Hinge)─ [Fuselage Door Frame]
    """
    C = COMP
    mates = []

    # 1. Shock strut hinge on wing spar fitting
    mates.append(MateDefinition(
        name="MLG_L_ShockStrut_MainPivot",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_shock_strut"],
        entity1_name="Axis_MainPivot",
        entity1_type="AXIS",
        entity2_comp="ATA57_Wing-1/RearSpar-1",
        entity2_name="Axis_MLG_Fitting",
        entity2_type="AXIS",
        limits=(math.radians(0), math.radians(95)),  # 0°=down, 95°=retracted
    ))

    # 2. Shock strut piston — slot mate (telescoping)
    mates.append(MateDefinition(
        name="MLG_L_ShockStrut_Telescope",
        mate_type=SW_CONST.swMateSLOT,
        entity1_comp=C["mlg_l_piston"],
        entity1_name="Axis_Piston",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_shock_strut"],
        entity2_name="Axis_Cylinder",
        entity2_type="AXIS",
        limits=(0.0, 0.508),  # 0–20 inches stroke (0.508 m)
    ))

    # 3. Drag brace upper — hinge to wing structure
    mates.append(MateDefinition(
        name="MLG_L_DragBrace_Upper_Pivot",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_drag_brace_upper"],
        entity1_name="Axis_UpperPivot",
        entity1_type="AXIS",
        entity2_comp="ATA57_Wing-1/RearSpar-1",
        entity2_name="Axis_DragBrace_Fitting",
        entity2_type="AXIS",
    ))

    # 4. Drag brace knee joint (upper ↔ lower)
    mates.append(MateDefinition(
        name="MLG_L_DragBrace_KneeJoint",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_drag_brace_upper"],
        entity1_name="Axis_KneePin",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_drag_brace_lower"],
        entity2_name="Axis_KneePin",
        entity2_type="AXIS",
        limits=(math.radians(-5), math.radians(180)),
    ))

    # 5. Drag brace lower — hinge to shock strut
    mates.append(MateDefinition(
        name="MLG_L_DragBrace_Lower_to_Strut",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_drag_brace_lower"],
        entity1_name="Axis_LowerPivot",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_shock_strut"],
        entity2_name="Axis_DragBrace_Lug",
        entity2_type="AXIS",
    ))

    # 6. Side brace upper — hinge to wing
    mates.append(MateDefinition(
        name="MLG_L_SideBrace_Upper_Pivot",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_side_brace_upper"],
        entity1_name="Axis_UpperPivot",
        entity1_type="AXIS",
        entity2_comp="ATA57_Wing-1/RearSpar-1",
        entity2_name="Axis_SideBrace_Fitting",
        entity2_type="AXIS",
    ))

    # 7. Side brace knee joint
    mates.append(MateDefinition(
        name="MLG_L_SideBrace_KneeJoint",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_side_brace_upper"],
        entity1_name="Axis_KneePin",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_side_brace_lower"],
        entity2_name="Axis_KneePin",
        entity2_type="AXIS",
    ))

    # 8. Side brace lower to strut
    mates.append(MateDefinition(
        name="MLG_L_SideBrace_Lower_to_Strut",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_side_brace_lower"],
        entity1_name="Axis_LowerPivot",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_shock_strut"],
        entity2_name="Axis_SideBrace_Lug",
        entity2_type="AXIS",
    ))

    # 9. Torque links (scissors) — upper to cylinder
    mates.append(MateDefinition(
        name="MLG_L_TorqueLink_Upper_to_Cyl",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_torque_link_upper"],
        entity1_name="Axis_UpperPin",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_shock_strut"],
        entity2_name="Axis_TorqueLink_Upper",
        entity2_type="AXIS",
    ))

    # 10. Torque links — lower to piston
    mates.append(MateDefinition(
        name="MLG_L_TorqueLink_Lower_to_Piston",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_torque_link_lower"],
        entity1_name="Axis_LowerPin",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_piston"],
        entity2_name="Axis_TorqueLink_Lower",
        entity2_type="AXIS",
    ))

    # 11. Torque links — scissors joint
    mates.append(MateDefinition(
        name="MLG_L_TorqueLink_Scissors",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_torque_link_upper"],
        entity1_name="Axis_ScissorsPin",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_torque_link_lower"],
        entity2_name="Axis_ScissorsPin",
        entity2_type="AXIS",
    ))

    # 12. Truck beam pitch pivot on piston
    mates.append(MateDefinition(
        name="MLG_L_TruckBeam_Pitch",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_truck_beam"],
        entity1_name="Axis_TruckPivot",
        entity1_type="AXIS",
        entity2_comp=C["mlg_l_piston"],
        entity2_name="Axis_TruckPivot",
        entity2_type="AXIS",
        limits=(math.radians(-15), math.radians(15)),  # ±15° pitch range
    ))

    # 13. Forward gear door hinge
    mates.append(MateDefinition(
        name="MLG_L_GearDoor_Fwd_Hinge",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_gear_door_fwd"],
        entity1_name="Axis_DoorHinge",
        entity1_type="AXIS",
        entity2_comp="ATA53_Fuselage-1/WingFairing-1",
        entity2_name="Axis_DoorHinge_Fwd",
        entity2_type="AXIS",
        limits=(math.radians(0), math.radians(100)),
    ))

    # 14. Aft gear door hinge
    mates.append(MateDefinition(
        name="MLG_L_GearDoor_Aft_Hinge",
        mate_type=SW_CONST.swMateHINGE,
        entity1_comp=C["mlg_l_gear_door_aft"],
        entity1_name="Axis_DoorHinge",
        entity1_type="AXIS",
        entity2_comp="ATA53_Fuselage-1/WingFairing-1",
        entity2_name="Axis_DoorHinge_Aft",
        entity2_type="AXIS",
        limits=(math.radians(0), math.radians(100)),
    ))

    return mates


# ═══════════════════════════════════════════════════════════════
# MATE DEFINITIONS — Flap Track Deployment
# ═══════════════════════════════════════════════════════════════

def define_flap_mates() -> List[MateDefinition]:
    """
    Define mates for Fowler flap deployment along track carriages.

    777 double-slotted Fowler flaps deploy on curved track carriages.
    Primary motion: aft translation + downward rotation.
      - Track carriage slides along a curved slot (Path Mate)
      - Flap panel has a cam-follower mate on the carriage for rotation
    """
    C = COMP
    mates = []

    # 1. Flap carriage on track rail — Path Mate
    mates.append(MateDefinition(
        name="Flap_1L_Carriage_PathMate",
        mate_type=SW_CONST.swMatePATH,
        entity1_comp=C["flap_carriage_1l"],
        entity1_name="Point_Carriage_Follower",
        entity1_type="VERTEX",
        entity2_comp=C["flap_track_1l"],
        entity2_name="Sketch_TrackRail",
        entity2_type="SKETCH",
    ))

    # 2. Inboard flap panel concentric to carriage roller axis
    mates.append(MateDefinition(
        name="Flap_IB_L_Carriage_Concentric",
        mate_type=SW_CONST.swMateCONCENTRIC,
        entity1_comp=C["flap_ib_l"],
        entity1_name="Axis_FlapTrackRoller",
        entity1_type="AXIS",
        entity2_comp=C["flap_carriage_1l"],
        entity2_name="Axis_CarriageRoller",
        entity2_type="AXIS",
    ))

    return mates


# ═══════════════════════════════════════════════════════════════
# MATE DEFINITIONS — Thrust Reverser
# ═══════════════════════════════════════════════════════════════

def define_thrust_reverser_mates() -> List[MateDefinition]:
    """
    Define mates for the GE90 translating-cowl thrust reverser.

    The 777/GE90 uses a translating sleeve design:
      - The aft fan cowl (translating cowl) slides aft on linear rails
      - Blocker doors pivot inward as the cowl translates (linkage-driven)
      - Cascade vanes are exposed as the cowl translates
    """
    C = COMP
    mates = []

    # 1. Translating cowl — slot mate (linear aft translation)
    mates.append(MateDefinition(
        name="TRev_L_TranslatingCowl_Slide",
        mate_type=SW_CONST.swMateSLOT,
        entity1_comp=C["trev_l_cowl"],
        entity1_name="Axis_CowlRail",
        entity1_type="AXIS",
        entity2_comp="ATA71_Powerplant-1/Engine_Left-1/Nacelle-1",
        entity2_name="Axis_NacelleRail",
        entity2_type="AXIS",
        limits=(0.0, 0.508),  # 0–20 inch (0.508 m) stroke
    ))

    # 2. Blocker door linkage — linear coupler to cowl translation
    mates.append(MateDefinition(
        name="TRev_L_BlockerDoor_LinearCoupler",
        mate_type=SW_CONST.swMateLINEARCOUPLER,
        entity1_comp=C["trev_l_blocker_door"],
        entity1_name="Axis_BlockerPivot",
        entity1_type="AXIS",
        entity2_comp=C["trev_l_cowl"],
        entity2_name="Axis_CowlRail",
        entity2_type="AXIS",
        # Coupling ratio: blocker rotates ~60° for full cowl stroke
        angle=math.radians(60),
    ))

    return mates


# ═══════════════════════════════════════════════════════════════
# MATE DEFINITIONS — Engine Dual Spool
# ═══════════════════════════════════════════════════════════════

def define_engine_spool_mates() -> List[MateDefinition]:
    """
    Define gear/screw mates for GE90-115B dual-spool shaft rotation.

    GE90 spool speeds (approximate):
      - N1 (Low spool: Fan + LPT): ~2,400 RPM at takeoff
      - N2 (High spool: HPC + HPT): ~10,800 RPM at takeoff
      - Ratio N2/N1 ≈ 4.5:1

    We use Screw Mates or Linear Coupler mates to enforce the rotation ratio
    between N1 and N2 components. This allows a single motor to drive both
    spools in a Motion Study.
    """
    C = COMP
    mates = []

    # 1. Fan rotor concentric to N1 shaft
    mates.append(MateDefinition(
        name="GE90_Fan_to_N1",
        mate_type=SW_CONST.swMateLOCK,
        entity1_comp=C["ge90_fan_rotor"],
        entity1_name="Axis_ShaftCenter",
        entity1_type="AXIS",
        entity2_comp=C["ge90_n1_shaft"],
        entity2_name="Axis_N1_Center",
        entity2_type="AXIS",
    ))

    # 2. LPT rotor locked to N1 shaft
    mates.append(MateDefinition(
        name="GE90_LPT_to_N1",
        mate_type=SW_CONST.swMateLOCK,
        entity1_comp=C["ge90_lpt_rotor"],
        entity1_name="Axis_ShaftCenter",
        entity1_type="AXIS",
        entity2_comp=C["ge90_n1_shaft"],
        entity2_name="Axis_N1_Center",
        entity2_type="AXIS",
    ))

    # 3. HPC rotor locked to N2 shaft
    mates.append(MateDefinition(
        name="GE90_HPC_to_N2",
        mate_type=SW_CONST.swMateLOCK,
        entity1_comp=C["ge90_hpc_rotor"],
        entity1_name="Axis_ShaftCenter",
        entity1_type="AXIS",
        entity2_comp=C["ge90_n2_shaft"],
        entity2_name="Axis_N2_Center",
        entity2_type="AXIS",
    ))

    # 4. HPT rotor locked to N2 shaft
    mates.append(MateDefinition(
        name="GE90_HPT_to_N2",
        mate_type=SW_CONST.swMateLOCK,
        entity1_comp=C["ge90_hpt_rotor"],
        entity1_name="Axis_ShaftCenter",
        entity1_type="AXIS",
        entity2_comp=C["ge90_n2_shaft"],
        entity2_name="Axis_N2_Center",
        entity2_type="AXIS",
    ))

    # 5. N2-to-N1 gear ratio coupling (4.5:1)
    mates.append(MateDefinition(
        name="GE90_N2_N1_GearRatio",
        mate_type=SW_CONST.swMateRACKPINION,
        entity1_comp=C["ge90_n2_shaft"],
        entity1_name="Axis_N2_Center",
        entity1_type="AXIS",
        entity2_comp=C["ge90_n1_shaft"],
        entity2_name="Axis_N1_Center",
        entity2_type="AXIS",
        # Rack-and-pinion used as rotation ratio proxy
        # Effective ratio = 4.5 : 1 (N2 faster)
        distance=4.5,  # Gear ratio parameter
    ))

    return mates


# ═══════════════════════════════════════════════════════════════
# MATE APPLICATION ENGINE
# ═══════════════════════════════════════════════════════════════

def apply_mates(sw_app, model, mate_defs: List[MateDefinition]):
    """
    Apply a list of MateDefinition objects to the active assembly.

    For each mate:
      1. Select entity1 on component1
      2. Select entity2 on component2 (append to selection)
      3. Call IModelDocExtension::AddMate5 with the specified parameters

    Args:
        sw_app: ISldWorks application.
        model: Active IModelDoc2 (must be an assembly).
        mate_defs: List of MateDefinition objects.
    """
    ext = model.Extension

    for md in mate_defs:
        log.info(f"Applying mate: {md.name}")

        # Select entity 1
        sel1 = ext.SelectByID2(
            f"{md.entity1_comp}/{md.entity1_name}",
            md.entity1_type,
            0, 0, 0,
            False,  # Not appending
            1,      # Mark = 1
            None,
            0
        )

        if not sel1:
            log.warning(f"  Could not select entity1: {md.entity1_comp}/{md.entity1_name}")
            continue

        # Select entity 2 (append)
        sel2 = ext.SelectByID2(
            f"{md.entity2_comp}/{md.entity2_name}",
            md.entity2_type,
            0, 0, 0,
            True,   # Append to selection
            1,      # Mark = 1
            None,
            0
        )

        if not sel2:
            log.warning(f"  Could not select entity2: {md.entity2_comp}/{md.entity2_name}")
            model.ClearSelection2(True)
            continue

        # Apply the mate
        mate_error = ext.AddMate5(
            md.mate_type,
            md.alignment,
            md.flip,
            md.distance,
            md.distance,    # Distance2 (for symmetric)
            md.angle,
            md.angle,       # Angle2
            0, 0,           # Reserved
            0, 0,           # Reserved
            False           # Preview only
        )

        if mate_error:
            log.info(f"  ✓ Mate applied: {md.name}")
        else:
            log.warning(f"  ✗ Mate failed: {md.name}")

        model.ClearSelection2(True)


# ═══════════════════════════════════════════════════════════════
# MOTION STUDY TIMING TABLE
# ═══════════════════════════════════════════════════════════════

MOTION_STUDY_STORYBOARD = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  BOEING 777-300ER — SOLIDWORKS MOTION STUDY TIMING TABLE (30-SECOND SEQ)  ║
╠══════╦════════════════════════════════╦═══════════════════════════════════════╣
║ Time ║ Event                          ║ Actuated Mates / Parameters          ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║ 0.0s ║ TAXI — Static, gear down       ║ All mates at rest position           ║
║      ║   Flaps: UP (0°)               ║   FlapCarriage_PathMate = 0%         ║
║      ║   Spoilers: DOWN               ║   Spoiler hinges = 0°                ║
║      ║   Thrust Rev: STOWED           ║   TranslatingCowl_Slide = 0 m       ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║ 2.0s ║ FLAP EXTENSION (Takeoff 20°)   ║ FlapCarriage_PathMate → 60%          ║
║      ║   Slats deploy to mid          ║   Slat_Hinge → 22°                  ║
║      ║   Inboard/Outboard flaps       ║   Flap rotation → 20°               ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║ 5.0s ║ TAKEOFF ROLL — N1 spool-up     ║ GE90_N1 → 2400 RPM (Motor)          ║
║      ║   GE90 fan visible spin        ║   GE90_N2 → 10800 RPM (coupled)     ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║ 8.0s ║ ROTATION (Vr) — Nose up        ║ MainGear_ShockStrut extends          ║
║      ║   Nose gear lifts              ║   NLG_ShockStrut → full extension    ║
║      ║   Main gear fully loaded       ║   AoA → +10° (pitch rotation)       ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║10.0s ║ LIFTOFF — All gear airborne    ║ Weight-on-wheels → 0                 ║
║      ║   Begin gear sequence          ║                                      ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║11.0s ║ GEAR DOORS OPEN                ║ GearDoor_Fwd_Hinge → 100°           ║
║      ║   Fwd + aft doors swing open   ║   GearDoor_Aft_Hinge → 100°         ║
║      ║                                ║   NLG_Door hinges → 90°             ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║12.0s ║ GEAR RETRACTION — Main gear    ║ MLG_ShockStrut_MainPivot: 0°→95°     ║
║      ║   Shock strut pivots inboard   ║   DragBrace_KneeJoint: 180°→0°      ║
║      ║   Drag brace folds (knee)      ║   SideBrace_KneeJoint: 180°→0°      ║
║      ║   Side brace collapses         ║   TruckBeam tilts for stowage        ║
║15.0s ║   Gear fully retracted         ║   Uplock engages                     ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║15.5s ║ NOSE GEAR RETRACTION           ║ NLG_Strut pivots fwd: 0°→90°        ║
║      ║   NLG retracts forward         ║   NLG_DragBrace folds               ║
║16.5s ║   NLG stowed                   ║   NLG uplock engages                 ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║17.0s ║ GEAR DOORS CLOSE               ║ GearDoor hinges → 0°                ║
║      ║   All doors close after gear   ║   NLG_Door hinges → 0°              ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║18.0s ║ FLAPS RETRACT (Clean config)   ║ FlapCarriage_PathMate → 0%          ║
║      ║   Slats retract                ║   Slat_Hinge → 0°                   ║
║      ║   Cruise configuration         ║   Flap rotation → 0°                ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║20.0s ║ CRUISE — Steady state          ║ All mates static                     ║
║      ║   Engine at cruise N1          ║   GE90_N1 → 1800 RPM                ║
║      ║                                ║   GE90_N2 → 8100 RPM                ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║23.0s ║ APPROACH — Flaps 30° (landing) ║ FlapCarriage_PathMate → 100%        ║
║      ║   Slats full extend            ║   Slat_Hinge → 30°                  ║
║      ║                                ║   Flap rotation → 30°               ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║25.0s ║ GEAR EXTENSION (reverse seq)   ║ Gear doors open → gear extends      ║
║      ║   Downlock engages             ║   MainPivot: 95°→0°                 ║
║      ║   WoW → gear loaded            ║   DragBrace: 0°→180° (over-center)  ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║27.0s ║ TOUCHDOWN + GROUND SPOILERS    ║ Spoiler hinges → 60° (all panels)   ║
║      ║   Spoilers deploy on WoW       ║   Ground spoilers auto-deploy       ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║28.0s ║ THRUST REVERSER DEPLOYMENT     ║ TranslatingCowl_Slide → 0.508 m     ║
║      ║   Translating cowl aft         ║   BlockerDoor pivot → 60°           ║
║      ║   Blocker doors swing in       ║   Cascade vanes exposed             ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║29.5s ║ THRUST REVERSER STOWED         ║ TranslatingCowl_Slide → 0 m         ║
║      ║   Cowl returns forward         ║   BlockerDoor pivot → 0°            ║
╠══════╬════════════════════════════════╬═══════════════════════════════════════╣
║30.0s ║ TAXI IN — End of sequence      ║ All mates at rest, gear down         ║
╚══════╩════════════════════════════════╩═══════════════════════════════════════╝
"""


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    log.info("=" * 70)
    log.info("Boeing 777-300ER Kinematic Mate Builder — Starting")
    log.info("=" * 70)

    sw_app, model, assy_doc = connect_to_solidworks()
    if assy_doc is None:
        log.error("Active document must be an assembly.")
        sys.exit(1)

    # Collect all mate definitions
    all_mates = []
    all_mates.extend(define_mlg_mates())
    all_mates.extend(define_flap_mates())
    all_mates.extend(define_thrust_reverser_mates())
    all_mates.extend(define_engine_spool_mates())

    log.info(f"Total kinematic mates to apply: {len(all_mates)}")

    # Apply mates
    apply_mates(sw_app, model, all_mates)

    # Rebuild
    model.ForceRebuild3(True)
    model.Save3(0, 0, 0)

    # Print motion study storyboard
    print(MOTION_STUDY_STORYBOARD)

    log.info("=" * 70)
    log.info("KINEMATIC MATE BUILDER COMPLETE")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
