# log.json vs log.json. The first check compared the ultra CONSOLE dump against
# the medium log.json, which is not like-for-like: the console dump also prints
# options ODM COMPUTES, while log.json records the options dict. Comparing the
# same source on both sides is stronger evidence, not a weaker test, and it
# settles whether undistorted_image_max_size was passed or derived.
import json
import sys
from pathlib import Path

MED = Path(r"C:\odm\datasets\big_house\log.json")
ULT = Path(r"C:\odm\datasets\big_house_ultra\log.json")


def norm(v):
    s = "" if v is None else str(v).strip()
    return {"None": "", "{}": "", "[]": ""}.get(s, s)


med = {k: norm(v) for k, v in json.loads(MED.read_text())["options"].items()}
ult = {k: norm(v) for k, v in json.loads(ULT.read_text())["options"].items()}
print(f"medium log.json options: {len(med)}   ultra log.json options: {len(ult)}")
if not med or not ult:
    sys.exit("ASSERTION FAILED: an options dict is empty; the test is blind.")

IGNORE = {"name", "project_path", "rerun_from"}
diffs = [(k, med.get(k, "<absent>"), ult.get(k, "<absent>"))
         for k in sorted(set(med) | set(ult)) if k not in IGNORE
         and med.get(k, "<absent>") != ult.get(k, "<absent>")]

print("\nDIFFERENCES (medium -> ultra):")
for k, a, b in diffs or []:
    print(f"  {k}: {a!r} -> {b!r}")
if not diffs:
    print("  none")

print(f"\nundistorted_image_max_size present in medium options: "
      f"{'undistorted_image_max_size' in med}")
print(f"undistorted_image_max_size present in ultra  options: "
      f"{'undistorted_image_max_size' in ult}")

ok = (len(diffs) == 1 and diffs[0][0] == "pc_quality")
print(f"\nEXACTLY-ONE-CHANGE ASSERTION (log.json vs log.json): "
      f"{'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
