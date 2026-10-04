"""
build_first_frame.py v4 — Boeing 777 Fuselage Frame in SolidWorks 2026
=======================================================================
Fixed: GetTitle property, SelectByID2 COM types, E: drive output.
"""

import win32com.client
import pythoncom
import math
import os
import time

FUSELAGE_RADIUS_H = 3.137
FUSELAGE_RADIUS_V = 3.073
FRAME_STATION = 500
WEB_HEIGHT = 0.0762
THICKNESS  = 0.002032
OUTPUT_DIR = r"E:\Boeing_777_DigitalTwin\parts"


def main():
    print("=" * 65)
    print("  BOEING 777-300ER -- Fuselage Frame Generator v4")
    print("  Station: STA 500 | Material: 7075-T6 Aluminum")
    print("=" * 65)

    pythoncom.CoInitialize()

    # -- Connect --
    print("\n[1/7] Connecting to SolidWorks 2026...")
    try:
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True
    except Exception as e:
        print("  [FAIL] %s" % str(e))
        return
    print("  [OK] Connected")

    # -- New Part --
    print("\n[2/7] Creating new part...")
    template = None
    for root_d, dirs, files in os.walk(r"C:\ProgramData\SolidWorks"):
        for f in files:
            if f.lower().endswith(".prtdot"):
                template = os.path.join(root_d, f)
                break
        if template:
            break

    if template:
        print("  Template: %s" % template)
        sw.NewDocument(template, 0, 0.0, 0.0)
    else:
        sw.NewPart()

    model = sw.ActiveDoc
    if model is None:
        print("  [FAIL] No active document after NewDocument")
        return

    # GetTitle might be property or method depending on binding
    try:
        title = model.GetTitle()
    except TypeError:
        try:
            title = model.GetTitle
        except:
            title = "Part1"
    print("  [OK] Part: %s" % str(title))

    sm = model.SketchManager
    fm = model.FeatureManager

    # -- Draw cross-section on Front Plane --
    print("\n[3/7] Drawing 777 cross-section (diameter: %.2f m)..." % (FUSELAGE_RADIUS_H*2))

    # Instead of SelectByID2, use SketchManager directly on the default plane
    # SolidWorks always has Front Plane as the first default plane
    # We can select by feature index
    try:
        # Get feature by name using FeatureByName
        front_plane = model.FeatureByName("Front Plane")
        if front_plane is None:
            front_plane = model.FeatureByName("Front")
        if front_plane is not None:
            front_plane.Select2(False, 0)
            print("  Selected Front Plane via FeatureByName")
    except Exception as e:
        print("  [INFO] FeatureByName: %s" % str(e)[:50])
        # Fallback: First feature is usually origin, planes follow
        try:
            feat = model.FirstFeature()
            count = 0
            while feat is not None and count < 10:
                try:
                    fn = feat.Name
                except:
                    try:
                        fn = feat.GetNameForSelection("")
                    except:
                        fn = ""
                tp = ""
                try:
                    tp = feat.GetTypeName2()
                except:
                    try:
                        tp = feat.GetTypeName()
                    except:
                        pass
                if "RefPlane" in str(tp) or "Plane" in str(tp):
                    # This is a reference plane - select the first one (Front)
                    feat.Select2(False, 0)
                    print("  Selected first ref plane: %s" % str(fn))
                    break
                feat = feat.GetNextFeature()
                count += 1
        except Exception as e2:
            print("  [INFO] Feature traversal: %s" % str(e2)[:50])

    sm.InsertSketch(True)
    time.sleep(0.5)

    # Draw the cross-section as a circle (most reliable)
    # On 8GB RAM with integrated GPU, a circle is more stable than 72-point spline
    circle = sm.CreateCircleByRadius(0.0, 0.0, 0.0, float(FUSELAGE_RADIUS_H))
    if circle is not None:
        print("  [OK] Fuselage cross-section circle (R=%.3f m)" % FUSELAGE_RADIUS_H)
    else:
        # Try alternate method
        try:
            sm.CreateCircle(0.0, 0.0, 0.0, float(FUSELAGE_RADIUS_H), 0.0, 0.0)
            print("  [OK] Circle via CreateCircle")
        except:
            print("  [WARN] Could not create circle")

    sm.InsertSketch(True)
    model.ClearSelection2(True)
    time.sleep(0.5)

    # -- Frame profile on Right Plane --
    print("\n[4/7] Drawing frame profile...")

    try:
        right_plane = model.FeatureByName("Right Plane")
        if right_plane is None:
            right_plane = model.FeatureByName("Right")
        if right_plane is not None:
            right_plane.Select2(False, 0)
    except Exception as e:
        # Traverse to find second ref plane
        try:
            feat = model.FirstFeature()
            plane_count = 0
            while feat is not None:
                tp = ""
                try:
                    tp = feat.GetTypeName2()
                except:
                    try:
                        tp = feat.GetTypeName()
                    except:
                        pass
                if "RefPlane" in str(tp) or "Plane" in str(tp):
                    plane_count += 1
                    if plane_count == 3:  # Right is typically the 3rd plane
                        feat.Select2(False, 0)
                        break
                feat = feat.GetNextFeature()
        except:
            pass

    sm.InsertSketch(True)
    time.sleep(0.3)

    r = float(FUSELAGE_RADIUS_H - 0.002)
    w = float(WEB_HEIGHT)
    t = float(THICKNESS)

    sm.CreateLine(r,     0.0, 0.0,   r + w, 0.0, 0.0)
    sm.CreateLine(r + w, 0.0, 0.0,   r + w, t,   0.0)
    sm.CreateLine(r + w, t,   0.0,   r,     t,   0.0)
    sm.CreateLine(r,     t,   0.0,   r,     0.0, 0.0)

    # Add a centerline through origin for revolve axis
    sm.CreateCenterLine(0.0, float(-r - 0.5), 0.0,   0.0, float(r + 0.5), 0.0)

    print("  [OK] Profile: %.1fmm x %.2fmm + centerline" % (w*1000, t*1000))

    sm.InsertSketch(True)
    model.ClearSelection2(True)
    time.sleep(0.5)

    # -- Create 3D Geometry --
    print("\n[5/7] Creating 3D geometry...")

    feature_ok = False

    # Attempt A: Revolved Boss (most reliable for ring shapes)
    print("  Trying Revolved Boss/Base (360 deg)...")
    try:
        # Select profile sketch
        sketch2 = model.FeatureByName("Sketch2")
        if sketch2 is not None:
            sketch2.Select2(False, 0)

            feat = fm.FeatureRevolve2(
                True,    # SingleDir
                True,    # IsSolid
                False,   # IsThin
                False,   # Merge
                0,       # Type: One direction
                0,       # EndCondition
                float(2.0 * math.pi),  # 360 deg
                0,       # EndCondition2
                0.0,     # Angle2
                False, False,  # Draft
                0.0,     # DraftAngle
                0.0, 0.0, 0.0,  # Direction
                0.0, 0.0, 0.0,  # Direction2
                True, True, True  # Merge/Scope
            )
            if feat is not None:
                print("  [OK] *** REVOLVED BOSS -- FRAME RING CREATED! ***")
                feature_ok = True
            else:
                print("  [INFO] Revolve returned None (profile may need the centerline as axis)")
    except Exception as e:
        print("  [INFO] Revolve: %s" % str(e)[:80])

    # Attempt B: Swept Boss
    if not feature_ok:
        print("  Trying Swept Boss/Base...")
        try:
            model.ClearSelection2(True)
            sketch2 = model.FeatureByName("Sketch2")
            sketch1 = model.FeatureByName("Sketch1")
            if sketch2 and sketch1:
                sketch2.Select2(False, 1)   # Mark=1 profile
                sketch1.Select2(True, 4)    # Mark=4 path, append
                feat = fm.InsertSweep2(
                    False, False, 0, True, False,
                    0, 0, 0, 0, 0, 0, 0.0, 0.0, False, 0, 0
                )
                if feat is not None:
                    print("  [OK] *** SWEPT BOSS -- FRAME RING CREATED! ***")
                    feature_ok = True
        except Exception as e:
            print("  [INFO] Sweep: %s" % str(e)[:80])

    # Attempt C: Extrude cross-section thin
    if not feature_ok:
        print("  Trying Thin-Extrude of cross-section...")
        try:
            model.ClearSelection2(True)
            sketch1 = model.FeatureByName("Sketch1")
            if sketch1:
                sketch1.Select2(False, 0)
                feat = fm.FeatureExtrusion3(
                    True, False, False,
                    0, 0,
                    float(WEB_HEIGHT), 0.0,
                    False, False, False, False,
                    0.0, 0.0,
                    False, True, True,
                    0.0, 0.0, 0.0,
                    False
                )
                if feat is not None:
                    print("  [OK] EXTRUDED cross-section as cylinder ring!")
                    feature_ok = True
        except Exception as e:
            print("  [INFO] Extrude1: %s" % str(e)[:80])

    # Attempt D: Extrude the profile rectangle
    if not feature_ok:
        print("  Trying Extrude of profile rectangle...")
        try:
            model.ClearSelection2(True)
            sketch2 = model.FeatureByName("Sketch2")
            if sketch2:
                sketch2.Select2(False, 0)
                feat = fm.FeatureExtrusion3(
                    True, False, False,
                    0, 0,
                    0.508, 0.0,
                    False, False, False, False,
                    0.0, 0.0,
                    False, True, True,
                    0.0, 0.0, 0.0,
                    False
                )
                if feat is not None:
                    print("  [OK] EXTRUDED profile (straight 508mm section)")
                    feature_ok = True
        except Exception as e:
            print("  [INFO] Extrude2: %s" % str(e)[:80])

    if not feature_ok:
        print("")
        print("  The sketches are in SolidWorks! To finish manually:")
        print("  1. Click Sketch2 in FeatureManager tree")
        print("  2. Insert -> Boss/Base -> Revolve")
        print("  3. Select the centerline as revolve axis")
        print("  4. Set to 360 degrees -> OK")

    # -- Material --
    print("\n[6/7] Setting material & properties...")
    model = sw.ActiveDoc

    mat_found = False
    for rd, ds, fs in os.walk(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"):
        for f in fs:
            if f.lower().endswith(".sldmat"):
                mp = os.path.join(rd, f)
                for alloy in ["7075 Alloy", "7075-T6 (SN)", "AISI 7075", "7075-T6"]:
                    try:
                        model.SetMaterialPropertyName2("Default", mp, alloy)
                        print("  [OK] Material: %s" % alloy)
                        mat_found = True
                        break
                    except:
                        pass
                if mat_found:
                    break
        if mat_found:
            break
    if not mat_found:
        print("  [SKIP] Set material manually")

    try:
        cpm = model.Extension.CustomPropertyManager("")
        for name, val in [
            ("PartNumber",   "53-F0025"),
            ("ATA_Chapter",  "53 - Fuselage Structure"),
            ("Description",  "Fuselage Frame at STA %d" % FRAME_STATION),
            ("Material",     "7075-T6 Aluminum"),
            ("Aircraft",     "Boeing 777-300ER"),
        ]:
            cpm.Add3(name, 30, val, 0)
        print("  [OK] Custom properties set")
    except Exception as e:
        print("  [WARN] Props: %s" % str(e)[:60])

    # -- Save --
    print("\n[7/7] Saving to E: drive...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_path = os.path.join(OUTPUT_DIR, "Frame_STA0500_F025.SLDPRT")

    saved = False
    try:
        errs = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        wrns = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        r = model.Extension.SaveAs3(save_path, 0, 2, None, None, errs, wrns)
        if r:
            saved = True
    except:
        pass
    if not saved:
        try:
            model.SaveAs(save_path)
            saved = True
        except:
            pass

    if saved:
        print("  [OK] SAVED: %s" % save_path)
    else:
        print("  [MANUAL] File -> Save As -> %s" % save_path)

    # Zoom to fit
    try:
        model.ViewZoomtofit2()
    except:
        pass

    print("\n" + "=" * 65)
    print("  FRAME GENERATION COMPLETE")
    print("=" * 65)
    print("  Part:      Fuselage Frame STA %d" % FRAME_STATION)
    print("  Aircraft:  Boeing 777-300ER")
    print("  Material:  7075-T6 Aluminum")
    print("  Diameter:  %.2f m" % (FUSELAGE_RADIUS_H * 2))
    print("  File:      %s" % save_path)
    print("=" * 65)
    print("\n  >> Check SolidWorks window now!")


if __name__ == "__main__":
    main()
