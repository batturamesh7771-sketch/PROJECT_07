"""
sw_common.py — SolidWorks COM Connection & Utility Library
===========================================================
Boeing 777-300ER Digital Twin Project
Provides the shared COM bridge to the running SolidWorks instance,
plus constants and helper functions used by all automation scripts.

Requirements:
  - SolidWorks 2023+ with API SDK installed
  - Python 3.10+ with `pywin32` (pip install pywin32)
  - SolidWorks must be running before script execution

Usage:
  from sw_common import connect_to_solidworks, SW_CONST
"""

import win32com.client
import pythoncom
import sys
import os
from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────
# SolidWorks API Constants (swconst.h equivalents)
# ─────────────────────────────────────────────────────────────
class SW_CONST:
    """Subset of SolidWorks API enum constants used throughout the project."""

    # Document types
    swDocPART        = 1
    swDocASSEMBLY    = 2
    swDocDRAWING     = 3

    # Mate types (swMateType_e)
    swMateCOINCIDENT = 0
    swMateCONCENTRIC = 1
    swMatePERPENDICULAR = 2
    swMatePARALLEL   = 3
    swMateTANGENT    = 4
    swMateDISTANCE   = 5
    swMateANGLE      = 6
    swMateLOCK       = 16
    swMateHINGE      = 22
    swMateSCREW      = 13
    swMateSLOT       = 24
    swMateCAMFOLLOWER = 27
    swMateRACKPINION = 14
    swMatePATH       = 15
    swMateLINEARCOUPLER = 17

    # Mate alignment
    swMateAlignALIGNED    = 0
    swMateAlignANTI_ALIGNED = 1

    # Feature types
    swTnExtrudeBoss   = "Boss-Extrude"
    swTnRevolveBoss   = "Boss-Revolve"
    swTnCut           = "Cut-Extrude"
    swTnFillet        = "Fillet"
    swTnShell         = "Shell"
    swTnLoftBoss      = "Loft-Boss"
    swTnPattern       = "LocalLPattern1"

    # Units (swLengthUnit_e)
    swMETERS      = 2
    swMILLIMETERS = 3
    swINCHES      = 5

    # Custom property manager
    swCustomInfoText   = 30  # swCustomInfoType_e
    swCustomInfoDouble = 31
    swCustomInfoNumber = 32

    # Save-as types
    swSaveAsCurrentVersion = 0

    # Component suppression states
    swComponentFullySuppressed = 0
    swComponentLightweight     = 1
    swComponentFullyResolved   = 2

    # Exploded view step type
    swExplodeStepType_Regular = 0


# ─────────────────────────────────────────────────────────────
# COM Connection
# ─────────────────────────────────────────────────────────────
def connect_to_solidworks() -> Tuple:
    """
    Connect to the running SolidWorks application via COM automation.

    Returns:
        Tuple of (swApp, ModelDoc2, AssemblyDoc | None)
        - swApp: ISldWorks application object
        - ModelDoc2: Currently active document (IModelDoc2)
        - AssemblyDoc: IAssemblyDoc if the active doc is an assembly, else None

    Raises:
        RuntimeError: If SolidWorks is not running or no document is open.
    """
    pythoncom.CoInitialize()

    try:
        sw_app = win32com.client.Dispatch("SldWorks.Application")
    except Exception as exc:
        raise RuntimeError(
            "Cannot connect to SolidWorks. Ensure it is running."
        ) from exc

    model = sw_app.ActiveDoc
    if model is None:
        raise RuntimeError(
            "No active document in SolidWorks. Open a part or assembly first."
        )

    assy_doc = None
    if model.GetType() == SW_CONST.swDocASSEMBLY:
        assy_doc = model  # Supports IAssemblyDoc methods

    return sw_app, model, assy_doc


def get_or_create_assembly(
    sw_app,
    assy_path: str,
    template_path: Optional[str] = None
):
    """
    Open an existing assembly or create a new one from a template.

    Args:
        sw_app: ISldWorks application object.
        assy_path: Full path to the .SLDASM file.
        template_path: Path to assembly template (.asmdot). If None, uses
                       the SolidWorks default assembly template.

    Returns:
        Tuple of (ModelDoc2, AssemblyDoc)
    """
    if os.path.isfile(assy_path):
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        model = sw_app.OpenDoc6(
            assy_path,
            SW_CONST.swDocASSEMBLY,
            1,   # swOpenDocOptions_Silent
            "",
            errors,
            warnings
        )
    else:
        if template_path is None:
            template_path = sw_app.GetUserPreferenceStringValue(
                21  # swDefaultTemplateAssembly
            )
        model = sw_app.NewDocument(template_path, 0, 0, 0)
        model.SaveAs(assy_path)

    return model, model


# ─────────────────────────────────────────────────────────────
# Coordinate Transform Helpers
# ─────────────────────────────────────────────────────────────
def make_transform_matrix(
    tx: float = 0.0,
    ty: float = 0.0,
    tz: float = 0.0,
    rx: float = 0.0,
    ry: float = 0.0,
    rz: float = 0.0,
) -> list:
    """
    Build a 16-element SolidWorks transform matrix (row-major 4×4)
    for translation only (rotation angles reserved for future use).

    SolidWorks matrix layout:
      [R11, R12, R13, 0,
       R21, R22, R23, 0,
       R31, R32, R33, 0,
       Tx,  Ty,  Tz,  1]

    For identity rotation with translation:
    """
    import math
    # Identity rotation + translation (simplified; ignoring rotation for now)
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        tx,  ty,  tz,  1.0,
    ]


def station_to_x(frame_station_inches: float) -> float:
    """
    Convert a Boeing fuselage frame station number (in inches from
    aircraft datum, positive aft) to SolidWorks model X coordinate in meters.

    The 777 fuselage datum is at the nose radome tip.
    Station values follow Boeing convention: STA 0 = datum.

    Args:
        frame_station_inches: Frame station number in inches.

    Returns:
        X position in meters.
    """
    return frame_station_inches * 0.0254  # inches → meters


# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
import logging

def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """Create a console logger with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(name)s — %(levelname)s — %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
