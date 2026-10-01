"""Software Environment and Dependency Auditor for Stage 42 (Section 9).

Safely discovers installed package versions using importlib metadata without
importing packages or triggering heavyweight initializations.
"""

from __future__ import annotations

import importlib.metadata
import sys
from typing import Dict, List, Optional

from local.compute.models import SoftwareProfile

CORE_ML_PACKAGES: List[str] = [
    "torch",
    "transformers",
    "peft",
    "accelerate",
    "datasets",
    "bitsandbytes",
    "vllm",
    "psutil",
    "pytest",
    "scipy",
    "numpy",
    "pydantic",
]


def get_safe_package_version(pkg_name: str) -> Optional[str]:
    """Safely retrieves the installed version of a package without importing it."""
    try:
        return importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def audit_software(packages_to_check: Optional[List[str]] = None) -> SoftwareProfile:
    """Audits Python runtime and installed ML/tooling packages."""
    py_ver = sys.version.split()[0]
    packages = packages_to_check or CORE_ML_PACKAGES

    installed_map: Dict[str, Optional[str]] = {}
    for pkg in packages:
        installed_map[pkg] = get_safe_package_version(pkg)

    return SoftwareProfile(
        python_version=py_ver,
        packages=installed_map,
    )
