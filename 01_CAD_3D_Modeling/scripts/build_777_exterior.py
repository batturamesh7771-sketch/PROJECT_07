"""
build_777_exterior.py — Generates a macroscopic Boeing 777 exterior model
===========================================================================
Safe for 8GB RAM. Uses basic extrusions and revolves to build the macro 
aerodynamic shape of the aircraft.
"""

import win32com.client
import pythoncom
import os
import time

OUTPUT_DIR = r"E:\Boeing_777_DigitalTwin\parts"

def main():
    print("=" * 60)
    print("  BOEING 777 -- Exterior Aerodynamic Model Generator")
    print("=" * 60)

    pythoncom.CoInitialize()
    try:
        sw = win32com.client.gencache.EnsureDispatch("SldWorks.Application")
    except:
        sw = win32com.client.Dispatch("SldWorks.Application")
        
    sw.Visible = True

    # New part
    template = sw.GetUserPreferenceStringValue(7) 
    if not template or not os.path.isfile(template):
        template = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2026\templates\Part.PRTDOT"
        
    if os.path.isfile(template):
        model = sw.NewDocument(template, 0, 0.0, 0.0)
    else:
        model = sw.NewPart()

    if model is None:
        model = sw.ActiveDoc
    if model is None:
        print("[FAIL] Could not create part.")
        return

    ext = model.Extension
    sm = model.SketchManager
    fm = model.FeatureManager

    # 1. FUSELAGE (Extrude a 63m long cylinder for the 777-200 length)
    print("[1] Building Fuselage Body...")
    try:
        model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    except:
        pass # Will fall back to default plane
        
    sm.InsertSketch(True)
    time.sleep(0.5)
    sm.CreateCircleByRadius(0.0, 0.0, 0.0, 3.1) # 6.2m diameter
    sm.InsertSketch(True)
    model.ClearSelection2(True)
    
    # Macro for Fuselage Extrude
    macro_path = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "extrude_fuse.swb")
    with open(macro_path, "w") as f:
        f.write("Dim swApp As Object, Part As Object\n")
        f.write("Sub main()\n")
        f.write("    Set swApp = Application.SldWorks\n")
        f.write("    Set Part = swApp.ActiveDoc\n")
        f.write('    Part.Extension.SelectByID2 "Sketch1", "SKETCH", 0, 0, 0, False, 0, Nothing, 0\n')
        # Extrude Mid-plane, 63 meters total length
        f.write('    Part.FeatureManager.FeatureExtrusion3 True, False, False, 4, 0, 63.0, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False\n')
        f.write("End Sub\n")
    sw.RunMacro2(macro_path, "", "main", 0, 0)
    time.sleep(1)

    # 2. MAIN WINGS (Draw on Top Plane, extrude thick)
    print("[2] Building Main Wings...")
    try:
        model.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    except:
        pass
        
    sm.InsertSketch(True)
    time.sleep(0.5)
    
    # Simple swept wing planform (Top down view)
    # Right wing
    sm.CreateLine(0, 5.0, 0,  30.0, -10.0, 0)  # Leading edge
    sm.CreateLine(30.0, -10.0, 0,  30.0, -15.0, 0) # Tip
    sm.CreateLine(30.0, -15.0, 0,  0, -10.0, 0)    # Trailing edge
    sm.CreateLine(0, -10.0, 0,  0, 5.0, 0)         # Root
    
    # Left wing
    sm.CreateLine(0, 5.0, 0,  -30.0, -10.0, 0)  # Leading edge
    sm.CreateLine(-30.0, -10.0, 0,  -30.0, -15.0, 0) # Tip
    sm.CreateLine(-30.0, -15.0, 0,  0, -10.0, 0)    # Trailing edge
    sm.CreateLine(0, -10.0, 0,  0, 5.0, 0)         # Root

    sm.InsertSketch(True)
    model.ClearSelection2(True)

    # Macro for Wing Extrude
    macro_path2 = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "extrude_wing.swb")
    with open(macro_path2, "w") as f:
        f.write("Dim swApp As Object, Part As Object\n")
        f.write("Sub main()\n")
        f.write("    Set swApp = Application.SldWorks\n")
        f.write("    Set Part = swApp.ActiveDoc\n")
        f.write('    Part.Extension.SelectByID2 "Sketch2", "SKETCH", 0, 0, 0, False, 0, Nothing, 0\n')
        # Extrude Mid-plane, 1.2m thick airfoil approximation
        f.write('    Part.FeatureManager.FeatureExtrusion3 True, False, False, 4, 0, 1.2, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False\n')
        f.write("End Sub\n")
    sw.RunMacro2(macro_path2, "", "main", 0, 0)
    time.sleep(1)

    # Save
    print("[3] Saving Exterior Model to E: drive...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_path = os.path.join(OUTPUT_DIR, "Boeing_777_Exterior_Model.SLDPRT")
    
    try:
        model.ViewZoomtofit2()
        model.SaveAs(save_path)
        print("  [OK] SAVED: %s" % save_path)
    except:
        print("  [MANUAL] Please save manually to E: drive")

    print("\n============================================================")
    print("  EXTERIOR MODEL GENERATED")
    print("  Basic aerodynamic shape is complete.")
    print("============================================================")

if __name__ == "__main__":
    main()
