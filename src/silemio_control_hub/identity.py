"""Stable public identity for the Controller Studio desktop product."""

BRAND_NAME = "SiLeMI/O"
PRODUCT_NAME = "Controller Studio"
HOST_EDITION = "for LiveProfessor"
FULL_PRODUCT_NAME = f"{PRODUCT_NAME} {HOST_EDITION}"

# The brand is shown as a signature, not embedded in the Windows product name.
WINDOWS_PRODUCT_FOLDER = "Controller Studio for LiveProfessor"
WINDOWS_PRODUCT_SLUG = "Controller-Studio-for-LiveProfessor"

# Development builds installed before V.2026 used the brand in their private
# data folder. Keep the path explicit so settings can be migrated read-only.
PREVIOUS_WINDOWS_PRODUCT_FOLDER = "SiLeMIO Controller Studio"
