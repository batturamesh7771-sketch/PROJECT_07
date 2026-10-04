"""
build_rivet.py — Create a Boeing 777 Fastener (CherryMAX Rivet)
================================================================
Builds a standard aerospace blind rivet used for frame-to-skin attachments.
Saves to the E: drive.
"""

import win32com.client
import pythoncom
import os
import time

OUTPUT_DIR = r"E:\Boeing_777_DigitalTwin\parts"

def main():
    print("=" * 60)
    print("  BOEING 777-300ER -- Fastener Generator")
    print("  Type: CherryMAX Blind Rivet CR2249-4-2")
    print("=" * 60)

    pythoncom.CoInitialize()
    try:
        sw = win32com.client.Dispatch("SldWorks.Application")
    except:
        print("[FAIL] Could not connect to SolidWorks.")
        return
        
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
        return

    print("[1] New fastener part created")

    sm = model.SketchManager

    # Shank
    print("[2] Drawing shank...")
    try:
        # Select Front Plane
        feat = model.FirstFeature()
        for _ in range(5):
            if feat:
                if "Plane" in str(feat.GetTypeName2()):
                    feat.Select2(False, 0)
                    break
                feat = feat.GetNextFeature()
    except:
        pass

    sm.InsertSketch(True)
    time.sleep(0.5)
    # Shank diameter = 4.0 mm (R = 2.0 mm)
    sm.CreateCircleByRadius(0.0, 0.0, 0.0, 0.002)
    sm.InsertSketch(True)
    model.ClearSelection2(True)
    
    # Head
    print("[3] Drawing flush head...")
    try:
        feat = model.FirstFeature()
        for _ in range(5):
            if feat:
                if "Plane" in str(feat.GetTypeName2()):
                    feat.Select2(False, 0)
                    break
                feat = feat.GetNextFeature()
    except:
        pass

    sm.InsertSketch(True)
    time.sleep(0.5)
    # Head diameter = 6.4 mm (R = 3.2 mm)
    sm.CreateCircleByRadius(0.0, 0.0, 0.0, 0.0032)
    sm.InsertSketch(True)
    model.ClearSelection2(True)

    # Properties
    print("[4] Setting metadata...")
    try:
        cpm = model.Extension.CustomPropertyManager("")
        cpm.Add3("PartNumber", 30, "CR2249-4-2", 0)
        cpm.Add3("Description", 30, "CherryMAX Blind Rivet", 0)
        cpm.Add3("Material", 30, "A-286 CRES", 0)
        cpm.Add3("ATA_Chapter", 30, "53 - Fuselage", 0)
    except:
        pass

    # Save
    print("[5] Saving to E: drive...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_path = os.path.join(OUTPUT_DIR, "CherryMAX_CR2249.SLDPRT")
    
    try:
        model.ViewZoomtofit2()
        model.SaveAs(save_path)
        print("  [OK] SAVED: %s" % save_path)
    except:
        print("  [MANUAL] Please save manually to E: drive")

    print("\n============================================================")
    print("  FASTENER GENERATION COMPLETE")
    print("  Sketches created. You can manually extrude:")
    print("  1. Extrude Sketch1 to 3.18mm (Shank)")
    print("  2. Extrude Sketch2 to 1.5mm (Head)")
    print("============================================================")

if __name__ == "__main__":
    main()
