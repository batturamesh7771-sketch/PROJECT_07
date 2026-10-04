"""
fix_revolve.py — Complete the 3D revolve on the frame sketches
================================================================
SolidWorks 2026 API - Uses correct FeatureRevolve parameter count.
The sketches are already in the active part from the previous run.
"""

import win32com.client
import pythoncom
import math
import os
import time

def main():
    print("=" * 55)
    print("  Completing 3D Revolve on Frame Part")
    print("=" * 55)

    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    model = sw.ActiveDoc

    if model is None:
        print("[FAIL] No active document in SolidWorks")
        return

    try:
        title = model.GetTitle
        if callable(title):
            title = title()
    except:
        title = "?"
    print("  Active doc: %s" % str(title))

    fm = model.FeatureManager
    sm = model.SketchManager

    # Check what sketches exist
    feat = model.FirstFeature()
    sketches = []
    while feat is not None:
        try:
            tn = feat.GetTypeName2()
            if tn is None:
                tn = feat.GetTypeName()
        except:
            try:
                tn = feat.GetTypeName()
            except:
                tn = ""
        try:
            fn = feat.Name
        except:
            fn = "?"

        if "Sketch" in str(tn) or "Sketch" in str(fn):
            sketches.append((fn, tn))
            print("  Found: %s (type=%s)" % (fn, tn))

        feat = feat.GetNextFeature()

    if len(sketches) < 2:
        print("[WARN] Expected 2 sketches, found %d" % len(sketches))
        print("  Will try to work with what we have")

    # =============================================
    # METHOD 1: Record-style macro approach
    # Use IModelDoc2.InsertFeatureRevolve which has fewer params
    # =============================================
    print("\n  Method 1: Selecting sketch + InsertFeatureRevolve...")
    model.ClearSelection2(True)

    # Select Sketch2 (the profile with centerline)
    sketch2 = model.FeatureByName("Sketch2")
    if sketch2 is not None:
        sketch2.Select2(False, 0)
        print("  Selected Sketch2")
    else:
        print("  [WARN] Sketch2 not found")
        return

    # Try FeatureRevolve (simpler, older API that still works)
    try:
        feat = fm.FeatureRevolve(
            float(2.0 * math.pi),  # Angle (radians) = 360 deg
            False,                  # Flip direction
            0.0,                    # Angle 2
            0,                      # End condition 1
            0,                      # End condition 2
            True,                   # Single direction thin = False -> Solid
            False,                  # Merge result
        )
        if feat is not None:
            print("  [OK] *** FeatureRevolve SUCCESS! ***")
            goto_save(model, sw)
            return
        else:
            print("  [INFO] FeatureRevolve returned None")
    except Exception as e:
        print("  [INFO] FeatureRevolve: %s" % str(e)[:70])

    # =============================================
    # METHOD 2: Use SendKeys to automate the GUI
    # This presses Insert -> Boss/Base -> Revolve via menu
    # =============================================
    print("\n  Method 2: GUI automation via SendKeys...")
    try:
        import subprocess
        # Create a VBScript that uses SendKeys
        vbs_content = '''
Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 500
' Activate SolidWorks
WshShell.AppActivate "SOLIDWORKS"
WScript.Sleep 500
' Press Insert menu -> Boss/Base -> Revolve
' Alt+I for Insert menu
WshShell.SendKeys "%i"
WScript.Sleep 300
WshShell.SendKeys "b"
WScript.Sleep 300
WshShell.SendKeys "r"
WScript.Sleep 2000
' Press Enter to accept defaults (360 degree revolve)
WshShell.SendKeys "{ENTER}"
WScript.Sleep 1000
WshShell.SendKeys "{ENTER}"
WScript.Sleep 500
'''
        vbs_path = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "sw_revolve.vbs")
        with open(vbs_path, "w") as f:
            f.write(vbs_content)

        subprocess.Popen(["cscript", "//nologo", vbs_path], shell=False)
        print("  [OK] SendKeys script launched")
        print("  Waiting 5 seconds for SolidWorks GUI...")
        time.sleep(5)

        # Check if a boss feature was created
        model = sw.ActiveDoc
        feat = model.FirstFeature()
        has_boss = False
        while feat is not None:
            try:
                tn = str(feat.GetTypeName2())
                if "Boss" in tn or "Revolve" in tn or "Extrude" in tn:
                    has_boss = True
                    print("  [OK] *** Found 3D feature: %s ***" % tn)
                    break
            except:
                pass
            feat = feat.GetNextFeature()

        if has_boss:
            goto_save(model, sw)
            return

    except Exception as e:
        print("  [INFO] SendKeys: %s" % str(e)[:70])

    # =============================================
    # METHOD 3: Create via macro file
    # =============================================
    print("\n  Method 3: Creating SolidWorks macro file...")
    macro_content = '''
Dim swApp As Object
Dim Part As Object
Dim boolstatus As Boolean

Sub main()
    Set swApp = Application.SldWorks
    Set Part = swApp.ActiveDoc
    
    ' Select Sketch2
    boolstatus = Part.Extension.SelectByID2("Sketch2", "SKETCH", 0, 0, 0, False, 0, Nothing, 0)
    
    ' Revolve 360 degrees
    Dim myFeature As Object
    Set myFeature = Part.FeatureManager.FeatureRevolve2(True, True, False, False, 0, 0, 6.28318530718, 0, 0, False, False, 0, 0, 0, 0, 0, 0, 0, True, True, True)
    
    ' Zoom to fit
    Part.ViewZoomtofit2
    
    ' Save
    Part.Save3 1, 0, 0
End Sub
'''
    macro_dir = r"E:\Boeing_777_DigitalTwin\macros"
    os.makedirs(macro_dir, exist_ok=True)
    macro_path = os.path.join(macro_dir, "revolve_frame.swp.txt")

    # SolidWorks macros need .swp binary format. 
    # Instead, write a .bas file that can be imported
    bas_path = os.path.join(macro_dir, "revolve_frame.bas")
    with open(bas_path, "w") as f:
        f.write("Attribute VB_Name = \"revolve_frame\"\n")
        f.write(macro_content)
    print("  [OK] Macro saved: %s" % bas_path)
    print("")
    print("  TO FINISH THE 3D FRAME MANUALLY:")
    print("  ================================")
    print("  Option A (easiest):")
    print("    1. In SolidWorks, click 'Sketch2' in the tree")
    print("    2. Go to Insert -> Boss/Base -> Revolve")
    print("    3. It should auto-detect the centerline as axis")
    print("    4. Set angle to 360 degrees")
    print("    5. Click the green checkmark")
    print("")
    print("  Option B (macro):")
    print("    1. Tools -> Macro -> New")
    print("    2. Paste the code from: %s" % bas_path)
    print("    3. Run")

    goto_save(model, sw)


def goto_save(model, sw):
    """Save and zoom to fit."""
    try:
        model.ViewZoomtofit2()
    except:
        pass

    save_path = r"E:\Boeing_777_DigitalTwin\parts\Frame_STA0500_F025.SLDPRT"
    try:
        model.SaveAs(save_path)
        print("\n  [OK] SAVED: %s" % save_path)
    except:
        try:
            errs = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            wrns = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            model.Extension.SaveAs3(save_path, 0, 2, None, None, errs, wrns)
            print("\n  [OK] SAVED: %s" % save_path)
        except:
            print("\n  [MANUAL] Save via File -> Save As")

    # List what's in the E: drive output
    parts_dir = r"E:\Boeing_777_DigitalTwin\parts"
    if os.path.isdir(parts_dir):
        print("\n  Files on E: drive:")
        for f in os.listdir(parts_dir):
            fp = os.path.join(parts_dir, f)
            sz = os.path.getsize(fp) / 1024
            print("    %s (%.0f KB)" % (f, sz))

    print("\n" + "=" * 55)
    print("  DONE -- Check SolidWorks!")
    print("=" * 55)


if __name__ == "__main__":
    main()
