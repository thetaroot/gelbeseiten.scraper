"""
Pytest Konfiguration und gemeinsame Fixtures.
"""

import sys
from pathlib import Path

# Projekt-Root zum Path hinzufügen
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
