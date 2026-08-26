"""
Standalone Diagnostic Test for domain_engine.py
Tests the 4 Mothers and Archetype reasoning without any image or Cesium dependencies.
"""
from dotenv import load_dotenv
load_dotenv()

from domain_engine import analyze_spatial_domain, ViewScope

# Test target
address = "Royal Crescent, Bath, England"
print(f"\n[Test] Running Standalone Domain Reasoning for: {address}...")

result = analyze_spatial_domain(
    address=address,
    view_scope=ViewScope.STANDALONE,
    lighting_description="Late afternoon warm golden hour sun (3200K) casting raking shadows"
)

print("\n" + "=" * 65)
print("1. GEOLOGICAL FOUNDATION & LITHICS:")
print(result.geological_foundation)
print("\n" + "-" * 65)
print("2. ARCHITECTURE & PLANAR VERTICALITY:")
print(result.architectural_analysis)
print("\n" + "-" * 65)
print("3. MATERIALS & PATINA:")
print(result.material_and_lithics)
print("\n" + "-" * 65)
print("4. BOTANICAL ECOLOGY:")
print(result.botanical_ecology)
print("\n" + "-" * 65)
print("5. DOCUMENTARY PROMPT FOR SYNTHESIS:")
print(result.documentary_prompt)
print("=" * 65 + "\n")