import pytest

import build_state_fdi_iem as sfi


@pytest.mark.parametrize("raw,canon", [
    ("JAMMU AND KASHMIR", "Jammu and Kashmir"),
    ("Jammu & Kashmir", "Jammu and Kashmir"),
    ("ORISSA", "Odisha"),
    ("Dadra & Nagar Haveli", "Dadra and Nagar Haveli and Daman and Diu"),
    ("DAMAN AND DIU", "Dadra and Nagar Haveli and Daman and Diu"),
    ("  Tamil   Nadu. ", "Tamil Nadu"),
    (None, ""),
])
def test_norm_reconciles_fdi_and_iem_labels(raw, canon):
    assert sfi.norm(raw) == canon


def test_window_excludes_defective_2019():
    assert "2019" not in sfi.IEM_YEARS_IN_WINDOW and "2019" in sfi.IEM_YEARS_EXCLUDED
