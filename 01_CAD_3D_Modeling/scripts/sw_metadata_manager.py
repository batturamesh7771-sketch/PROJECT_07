"""
sw_metadata_manager.py — Custom Property Propagator
=====================================================
Boeing 777-300ER Digital Twin Project

Traverses every part and sub-assembly in the active assembly tree and
ensures mandatory custom properties are populated:
  - PartNumber        (ATA chapter prefix + sequential)
  - ATA_Chapter       (ATA iSpec 2200 chapter code)
  - Material          (Alloy designation)
  - Weight_kg         (Calculated mass from SolidWorks mass properties)
  - Supplier          (Default supplier tag)
  - Description       (Human-readable part description)

Also generates a Bill of Materials (BOM) CSV export.

Usage:
  1. Open the top-level 777 assembly in SolidWorks.
  2. Run:  python sw_metadata_manager.py
  3. CSV BOM is saved alongside the assembly.
"""

import csv
import os
import sys
from typing import Optional

from sw_common import connect_to_solidworks, setup_logger, SW_CONST

log = setup_logger("MetadataMgr")


# ═══════════════════════════════════════════════════════════════
# ATA CHAPTER INFERENCE
# ═══════════════════════════════════════════════════════════════

ATA_CHAPTER_MAP = {
    "Fuselage":     "53",
    "Frame":        "53",
    "Stringer":     "53",
    "Skin":         "53",
    "Bulkhead":     "53",
    "Wing":         "57",
    "Spar":         "57",
    "Rib":          "57",
    "Aileron":      "27",
    "Flap":         "27",
    "Slat":         "27",
    "Spoiler":      "27",
    "Elevator":     "27",
    "Rudder":       "27",
    "Stabilizer":   "27",
    "LandingGear":  "32",
    "Gear":         "32",
    "Wheel":        "32",
    "Brake":        "32",
    "Strut":        "32",
    "Engine":       "72",
    "Fan":          "72",
    "Compressor":   "72",
    "Turbine":      "72",
    "Combustor":    "72",
    "Nacelle":      "71",
    "Cowl":         "71",
    "Pylon":        "71",
    "ThrustRev":    "78",
    "Seat":         "25",
    "Galley":       "25",
    "Lavatory":     "25",
    "Bin":          "25",
    "Cargo":        "25",
    "CherryMAX":    "53",
    "HiLok":        "57",
    "AN":           "53",
    "MS":           "53",
    "Rivet":        "53",
    "Bolt":         "53",
    "Fastener":     "53",
}


def infer_ata_chapter(component_name: str) -> str:
    """
    Infer the ATA chapter from the component filename or feature name.

    Scans the component name for keywords and returns the matching ATA code.
    Falls back to "00" (General) if no match.
    """
    for keyword, ata_code in ATA_CHAPTER_MAP.items():
        if keyword.lower() in component_name.lower():
            return ata_code
    return "00"


# ═══════════════════════════════════════════════════════════════
# PROPERTY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

MANDATORY_PROPERTIES = [
    "PartNumber",
    "ATA_Chapter",
    "Material",
    "Weight_kg",
    "Supplier",
    "Description",
]

DEFAULT_SUPPLIER = "Boeing Commercial Airplanes"


def ensure_properties(comp, comp_idx: int) -> dict:
    """
    Ensure all mandatory custom properties exist on a component's model.

    If a property is missing, it is created with an inferred or default value.
    If it already exists, it is left untouched.

    Args:
        comp: IComponent2 object.
        comp_idx: Sequential index for part number generation.

    Returns:
        Dictionary of property name → value for BOM export.
    """
    comp_model = comp.GetModelDoc2()
    if comp_model is None:
        return {}

    comp_name = comp.Name2 or "Unknown"
    ext = comp_model.Extension
    cpm = ext.CustomPropertyManager("")

    # Read existing properties
    existing = {}
    names_tuple = cpm.GetNames()
    if names_tuple:
        for prop_name in names_tuple:
            _, val, resolved_val = cpm.Get6(
                prop_name, False, "", "", False, False
            )
            existing[prop_name] = resolved_val or val

    # Compute mass
    mass_kg = 0.0
    try:
        mass_props = comp_model.Extension.CreateMassProperty()
        if mass_props:
            mass_kg = mass_props.Mass  # kg (if units set to SI)
    except Exception:
        pass

    # Infer values
    ata = existing.get("ATA_Chapter", infer_ata_chapter(comp_name))
    part_no = existing.get(
        "PartNumber",
        f"{ata}-{comp_idx:05d}"
    )

    defaults = {
        "PartNumber":  part_no,
        "ATA_Chapter": ata,
        "Material":    existing.get("Material", "Aluminum Alloy (unspecified)"),
        "Weight_kg":   f"{mass_kg:.4f}",
        "Supplier":    existing.get("Supplier", DEFAULT_SUPPLIER),
        "Description": existing.get("Description", comp_name),
    }

    # Write missing properties
    for prop_name, default_val in defaults.items():
        if prop_name not in existing:
            cpm.Add3(
                prop_name,
                SW_CONST.swCustomInfoText,
                str(default_val),
                SW_CONST.swCustomInfoText
            )
            log.info(f"  Set {prop_name} = {default_val}")

    return defaults


# ═══════════════════════════════════════════════════════════════
# ASSEMBLY TREE TRAVERSAL
# ═══════════════════════════════════════════════════════════════

def traverse_assembly(
    sw_app,
    assy_doc,
    bom_rows: list,
    depth: int = 0
):
    """
    Recursively traverse the assembly tree and ensure metadata on every
    component. Collects BOM data into bom_rows.

    Args:
        sw_app: ISldWorks application.
        assy_doc: Assembly document (also IModelDoc2).
        bom_rows: Accumulator list for BOM export.
        depth: Current recursion depth (for logging indentation).
    """
    components = assy_doc.GetComponents(False)  # False = include sub-components
    if components is None:
        return

    indent = "  " * depth
    for idx, comp in enumerate(components):
        comp_name = comp.Name2 or "?"
        is_suppressed = comp.GetSuppression2() == SW_CONST.swComponentFullySuppressed

        if is_suppressed:
            log.info(f"{indent}[SUPPRESSED] {comp_name}")
            continue

        log.info(f"{indent}Processing: {comp_name}")
        props = ensure_properties(comp, len(bom_rows) + 1)

        if props:
            bom_rows.append({
                "Level": depth,
                "ComponentName": comp_name,
                **props,
            })

        # Recurse into sub-assemblies
        child_model = comp.GetModelDoc2()
        if child_model and child_model.GetType() == SW_CONST.swDocASSEMBLY:
            traverse_assembly(sw_app, child_model, bom_rows, depth + 1)


# ═══════════════════════════════════════════════════════════════
# BOM EXPORT
# ═══════════════════════════════════════════════════════════════

def export_bom_csv(bom_rows: list, output_path: str):
    """
    Export the collected BOM data as a CSV file.

    Args:
        bom_rows: List of dicts with component metadata.
        output_path: Full path for the CSV output.
    """
    if not bom_rows:
        log.warning("No BOM data to export.")
        return

    fieldnames = [
        "Level", "ComponentName", "PartNumber", "ATA_Chapter",
        "Material", "Weight_kg", "Supplier", "Description"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bom_rows)

    log.info(f"BOM exported: {output_path}  ({len(bom_rows)} rows)")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    log.info("=" * 70)
    log.info("Boeing 777-300ER Metadata Manager — Starting")
    log.info("=" * 70)

    sw_app, model, assy_doc = connect_to_solidworks()

    if assy_doc is None:
        log.error("Active document must be an assembly.")
        sys.exit(1)

    bom_rows = []
    traverse_assembly(sw_app, assy_doc, bom_rows)

    # Export BOM
    assy_path = model.GetPathName()
    bom_path = os.path.splitext(assy_path)[0] + "_BOM.csv"
    export_bom_csv(bom_rows, bom_path)

    log.info("=" * 70)
    log.info(f"METADATA PROCESSING COMPLETE")
    log.info(f"  Components processed: {len(bom_rows):,}")
    log.info(f"  BOM file: {bom_path}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
