"""Prueba de humo: el paquete se importa y expone su punto de entrada."""

import secguard_advisor
from secguard_advisor import main


def test_package_exposes_version() -> None:
    assert secguard_advisor.__version__ == "0.1.0"


def test_main_is_callable() -> None:
    assert callable(main)
