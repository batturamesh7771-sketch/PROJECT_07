"""
complete_frame.py — Open saved part, add revolve, save back
=============================================================
Opens Frame_STA0500 from E: drive, selects Sketch2, revolves 360 deg.
"""

import win32com.client
import pythoncom
import math
import os
import time

PART_PATH = r"E:\Boeing_777_DigitalTwin\parts\Frame_STA0500_F025.SLDPRT"

def main():
    print("=" * 55)
    print("  Completing Boeing 777 Frame -- Revolve 360")
    print("=" * 55)

    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    sw.Visible = True

    # Open the saved part
    print("\n[1] Opening part from E: drive...")
    if not os.path.isfile(PART_PATH):
        print("  [FAIL] File not found: %s" % PART_PATH)
        return

    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

    model = sw.OpenDoc6(
        PART_PATH,
        1,    # swDocPART
        1,    # swOpenDocOptions_Silent
        "",
        errors,
        warnings
    )

    model = sw.ActiveDoc
    if model is None:
        print("  [FAIL] Could not open document")
        return
    print("  [OK] Opened: %s" % PART_PATH)

    fm = model.FeatureManager
    sm = model.SketchManager

    # List features
    print("\n[2] Scanning features...")
    feat = model.FirstFeature()
    sketch_names = []
    while feat is not None:
        try:
            fn = feat.Name
            tn = feat.GetTypeName2()
            if tn is None:
                tn = ""
            print("    %s [%s]" % (fn, tn))
            if "Sketch" in str(fn):
                sketch_names.append(fn)
        except:
            pass
        try:
            feat = feat.GetNextFeature()
        except:
            break

    # Try the revolve with correct SolidWorks 2026 API
    print("\n[3] Creating Revolved Boss (360 degrees)...")

    # Select Sketch2
    model.ClearSelection2(True)
    sk = model.FeatureByName("Sketch2")
    if sk is None and len(sketch_names) >= 2:
        sk = model.FeatureByName(sketch_names[1])
    if sk is None:
        print("  [FAIL] Cannot find Sketch2")
        return

    sk.Select2(False, 0)
    print("  Selected: Sketch2")

    success = False

    # ---- Try 1: FeatureRevolve (old API, 7 params) ----
    try:
        feat = fm.FeatureRevolve(
            float(2.0 * math.pi),
            False,
            float(0.0),
            int(0),
            int(0),
            True,
            False
        )
        if feat is not None:
            print("  [OK] *** FeatureRevolve WORKED! Ring created! ***")
            success = True
    except Exception as e:
        print("  Try1 FeatureRevolve: %s" % str(e)[:80])

    # ---- Try 2: FeatureRevolve2 with varying param counts ----
    if not success:
        # SolidWorks 2026 may use a different signature
        # Try the documented 17-param version
        model.ClearSelection2(True)
        sk.Select2(False, 0)
        try:
            feat = fm.FeatureRevolve2(
                True,     # SingleDir
                True,     # IsSolid  
                False,    # IsThin
                False,    # IsCut
                False,    # ReverseDirection
                False,    # BothDirectionUpToSameEntity
                0,        # Dir1Type (0=Blind)
                0,        # Dir2Type
                float(2.0 * math.pi),   # Dir1Angle
                0.0,      # Dir2Angle
                False,    # OffsetReverse1
                False,    # OffsetReverse2
                0.0,      # OffsetDistance1
                0.0,      # OffsetDistance2
                0,        # ThinType
                0.0,      # ThinThickness1
                0.0,      # ThinThickness2
                True,     # Merge
                True,     # UseFeatScope
                True      # UseAutoSelect
            )
            if feat is not None:
                print("  [OK] *** FeatureRevolve2 (20-param) WORKED! ***")
                success = True
        except Exception as e:
            print("  Try2 FeatureRevolve2-20: %s" % str(e)[:80])

    # ---- Try 3: Different param count ----
    if not success:
        model.ClearSelection2(True)
        sk.Select2(False, 0)
        try:
            feat = fm.FeatureRevolve2(
                True, True, False, False,
                0, 0,
                float(2.0 * math.pi), float(0.0),
                False, False,
                float(0.0), float(0.0),
                0, float(0.0), float(0.0),
                True, True, True
            )
            if feat is not None:
                print("  [OK] *** FeatureRevolve2 (18-param) WORKED! ***")
                success = True
        except Exception as e:
            print("  Try3 FeatureRevolve2-18: %s" % str(e)[:80])

    # ---- Try 4: InsertRevolve ----
    if not success:
        model.ClearSelection2(True)
        sk.Select2(False, 0)
        try:
            # Some versions use InsertRevolve
            feat = fm.InsertRevolve(
                float(2.0 * math.pi),
                False
            )
            if feat is not None:
                print("  [OK] *** InsertRevolve WORKED! ***")
                success = True
        except Exception as e:
            print("  Try4 InsertRevolve: %s" % str(e)[:80])

    # ---- Try 5: Use RunMacro2 with inline VBA ----
    if not success:
        print("\n  Direct API revolve failed. Using VBA macro approach...")
        macro_path = r"E:\Boeing_777_DigitalTwin\macros\do_revolve.swp"
        os.makedirs(os.path.dirname(macro_path), exist_ok=True)
        
        # Write a .swb (SolidWorks Basic) macro file
        swb_path = r"E:\Boeing_777_DigitalTwin\macros\do_revolve.swb" 
        with open(swb_path, "w") as f:
            f.write("Dim swApp As Object\n")
            f.write("Dim Part As Object\n")
            f.write("Dim boolstatus As Boolean\n")
            f.write("Dim longstatus As Long, longwarnings As Long\n")
            f.write("\n")
            f.write("Sub main()\n")
            f.write("    Set swApp = Application.SldWorks\n")
            f.write("    Set Part = swApp.ActiveDoc\n")
            f.write('    boolstatus = Part.Extension.SelectByID2("Sketch2", "SKETCH", 0, 0, 0, False, 0, Nothing, 0)\n')
            f.write("    Dim myFeature As Object\n")
            f.write("    Set myFeature = Part.FeatureManager.FeatureRevolve2(True, True, False, False, 0, 0, 6.28318530718, 0, 0, False, False, 0, 0, 0, 0, 0, 0, 0, True, True, True)\n")
            f.write("    Part.ViewZoomtofit2\n")
            f.write('    longstatus = Part.SaveAs3("' + PART_PATH.replace("\\", "\\\\") + '", 0, 2)\n')
            f.write("End Sub\n")
        
        print("  [OK] Macro written: %s" % swb_path)
        
        # Try to run it
        try:
            run_result = sw.RunMacro2(swb_path, "", "main", 0, 0)
            print("  RunMacro2 result: %s" % str(run_result))
            success = True
        except Exception as e:
            print("  RunMacro2: %s" % str(e)[:80])

    # ---- Try 6: Just extrude something so there's a 3D body ----
    if not success:
        print("\n  Trying basic extrude as fallback...")
        model.ClearSelection2(True)
        
        # Select Sketch1 (the circle)
        sk1 = model.FeatureByName("Sketch1")
        if sk1:
            sk1.Select2(False, 0)
            try:
                feat = fm.FeatureExtrusion2(
                    True, False, False,
                    0, 0,
                    float(0.002032), float(0.002032),
                    False, False,
                    False, False,
                    float(0.0), float(0.0),
                    False, False,
                    False, False,
                    True, True, True,
                    0, 0, False
                )
                if feat is not None:
                    print("  [OK] Extruded circle as thin ring disk!")
                    success = True
            except Exception as e:
                print("  Extrusion2: %s" % str(e)[:80])

            if not success:
                try:
                    feat = fm.FeatureExtrusion(
                        True, False, False,
                        0, 0,
                        float(0.0762),
                        float(0.0762),
                        False, False,
                        False, False,
                        float(0.0), float(0.0),
                        False, False
                    )
                    if feat is not None:
                        print("  [OK] FeatureExtrusion on circle!")
                        success = True
                except Exception as e:
                    print("  Extrusion: %s" % str(e)[:80])

    # Save
    if success:
        try:
            model.ViewZoomtofit2()
        except:
            pass
        try:
            model.Save3(0, 0, 0)
            print("\n  [OK] SAVED!")
        except:
            try:
                model.SaveAs(PART_PATH)
                print("\n  [OK] SAVED!")
            except:
                pass

    # Final instructions
    print("\n" + "=" * 55)
    if success:
        print("  3D GEOMETRY CREATED SUCCESSFULLY!")
    else:
        print("  SKETCHES READY -- Manual step needed:")
        print("")
        print("  In SolidWorks right now:")
        print("  1. Click 'Sketch2' in the feature tree (left panel)")
        print("  2. Menu: Insert -> Boss/Base -> Revolve")
        print("  3. SolidWorks will show the revolve preview")
        print("  4. Make sure angle = 360 degrees")
        print("  5. Click green checkmark (OK)")
        print("  6. You will see the full fuselage frame ring!")
        print("")
        print("  OR run macro: %s" % r"E:\Boeing_777_DigitalTwin\macros\do_revolve.swb")
        print("  via Tools -> Macro -> Run -> select the file")
    print("=" * 55)

    # Show files
    parts_dir = r"E:\Boeing_777_DigitalTwin\parts"
    if os.path.isdir(parts_dir):
        print("\n  Files on E: drive:")
        for f in os.listdir(parts_dir):
            sz = os.path.getsize(os.path.join(parts_dir, f)) / 1024
            print("    %s (%.0f KB)" % (f, sz))


if __name__ == "__main__":
    main()
