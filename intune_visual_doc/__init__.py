"""
Intune Visual Doc
Automated Microsoft Intune settings documentation with Microsoft Graph and Playwright.
Licensed under GNU AGPLv3.
"""

import sys

__version__ = "0.2.0"

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
