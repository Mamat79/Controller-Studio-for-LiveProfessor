from silemio_control_hub import (
    BRAND_NAME,
    FULL_PRODUCT_NAME,
    HOST_EDITION,
    PRODUCT_NAME,
    __version__,
)
from silemio_control_hub.identity import WINDOWS_PRODUCT_FOLDER, WINDOWS_PRODUCT_SLUG


def test_current_product_identity_is_liveprofessor_specific():
    assert BRAND_NAME == "SiLeMI/O"
    assert PRODUCT_NAME == "Controller Studio"
    assert HOST_EDITION == "for LiveProfessor"
    assert FULL_PRODUCT_NAME == "Controller Studio for LiveProfessor"
    assert WINDOWS_PRODUCT_FOLDER == "Controller Studio for LiveProfessor"
    assert WINDOWS_PRODUCT_SLUG == "Controller-Studio-for-LiveProfessor"
    assert __version__ == "2026.4"
