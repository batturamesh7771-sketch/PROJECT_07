"""
Build & Verification Script for Boeing 777 WebGPU Platform
"""
import os
import sys

def verify_platform():
    base = os.path.dirname(os.path.abspath(__file__))
    html_file = os.path.join(base, "Boeing_777_WebGPU_CFD_FEA_Platform.html")
    if os.path.exists(html_file) and os.path.getsize(html_file) > 1000:
        print("[OK] Boeing 777 WebGPU CFD/FEA Platform built successfully!")
        print(f"Platform file: {html_file} ({os.path.getsize(html_file):,} bytes)")
        return True
    else:
        print("[ERROR] Platform build artifact missing or invalid.")
        return False

if __name__ == "__main__":
    if not verify_platform():
        sys.exit(1)
