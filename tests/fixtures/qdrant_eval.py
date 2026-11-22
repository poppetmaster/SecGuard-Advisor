"""Conjuntos ficticios de calibración y evaluación (separados)."""

CALIBRATION_TEXTS = [
    "El control de acceso exige autenticación multifactor y revisión trimestral de permisos.",
    "El cifrado en reposo protege los datos almacenados con claves gestionadas localmente.",
    "La gestión de parches aplica actualizaciones críticas en un plazo máximo de siete días.",
]
CALIBRATION_RELEVANT = [
    ("¿Cómo se controla el acceso a los sistemas?", 0),
    ("¿Qué protección tienen los datos almacenados?", 1),
    ("¿En qué plazo se aplican las actualizaciones críticas?", 2),
]
CALIBRATION_NON_RELEVANT = [
    "receta de cocina para una cena",
    "historia del arte renacentista",
    "pronóstico del clima para mañana",
]

EVAL_TEXTS = [
    "Las contraseñas se almacenan con hash y se rotan cada noventa días.",
    "El registro de auditoría conserva eventos de acceso durante un año.",
]
EVAL_RELEVANT = [
    ("¿Cómo se almacenan y rotan las contraseñas?", 0),
    ("¿Cuánto tiempo se conservan los eventos de auditoría?", 1),
]
EVAL_NON_RELEVANT = [
    "mejores playas para vacacionar",
    "resultados del torneo de fútbol",
]
CASE_A_TEXT = "El procedimiento de respaldo diario conserva copias cifradas fuera del sitio."
CASE_B_TEXT = "El plan de continuidad activa un sitio alterno ante una caída prolongada."
EVAL_CASE_QUERIES = {
    "a": ("¿Cómo se respaldan los datos del caso?", CASE_A_TEXT),
    "b": ("¿Qué ocurre ante una caída prolongada?", CASE_B_TEXT),
}
SUPERSEDED_V1 = "La política de versiones anteriores permitía contraseñas de ocho caracteres."
SUPERSEDED_V2 = "La política vigente exige contraseñas de al menos dieciséis caracteres."
