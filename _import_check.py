# C:\T18\_import_check.py
import sys
from pathlib import Path
ROOT = Path(r"C:\T18")
print("sys.path has C:\\T18?", str(ROOT) in sys.path)
import t18_common.security as sec
print("Imported:", sec.__name__)
