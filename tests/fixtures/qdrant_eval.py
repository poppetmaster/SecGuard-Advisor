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

# --- Segunda iteración y conjunto final (fijados antes de medir) -------------

CAL2 = {
    "public": [
        "La autenticación multifactor es obligatoria para el acceso remoto y se revisa "
        "cada trimestre.",
        "El cifrado en reposo usa claves gestionadas localmente y rotación anual.",
        "La gestión de parches aplica actualizaciones críticas en un plazo de siete días.",
        "El inventario de activos identifica propietario y criticidad de cada servicio.",
    ],
    "cases": {
        "a": [
            "El respaldo diario conserva copias cifradas fuera del sitio con prueba mensual.",
            "El acceso de proveedores exige aprobación del responsable y registro de sesión.",
        ],
        "b": [
            "El plan de continuidad activa un sitio alterno ante una caída prolongada.",
        ],
    },
    "relevant": [
        ("public", "¿Se exige doble factor para el acceso remoto?", 0),
        ("public", "¿Cómo se protegen las claves de cifrado almacenadas?", 1),
        ("public", "¿En qué plazo se instalan las actualizaciones críticas?", 2),
        ("a", "¿Con qué frecuencia se prueba el respaldo del caso?", 0),
        ("a", "¿Qué control existe para el acceso de proveedores?", 1),
        ("b", "¿Qué se activa cuando la caída es prolongada?", 0),
    ],
    "non_relevant": [
        "receta de cocina para una cena",
        "historia del arte renacentista",
        "¿Cómo se gestionan los incidentes de seguridad?",
        "¿Qué herramienta de monitoreo de red se usa?",
    ],
}

FINAL = {
    "public": [
        "Las contraseñas se almacenan con hash y se rotan cada noventa días.",
        "El registro de auditoría conserva eventos de acceso durante un año.",
        "La segmentación de red separa servidores críticos del resto de la infraestructura.",
    ],
    "cases": {
        "a": [
            "La retención de datos del caso elimina registros a los dos años.",
            "El acceso temporal de proveedores se revoca al finalizar el contrato.",
        ],
        "b": [
            "La evaluación de terceros revisa controles de seguridad antes de contratar.",
        ],
    },
    "relevant": [
        ("public", "¿Cómo se protegen las contraseñas y cada cuánto cambian?", 0),
        ("public", "¿Cuánto tiempo se guardan los eventos de acceso?", 1),
        ("public", "¿Cómo se separan los servidores críticos?", 2),
        ("a", "¿Cuándo se eliminan los registros del caso?", 0),
        ("a", "¿Qué ocurre con el acceso del proveedor al terminar el contrato?", 1),
        ("b", "¿Qué se revisa antes de contratar a un tercero?", 0),
    ],
    "non_relevant": [
        "mejores playas para vacacionar",
        "resultados del torneo de fútbol",
        "¿Cómo se gestionan los incidentes de seguridad?",
        "¿Qué herramienta de monitoreo de red se usa?",
    ],
    "superseded": {
        "v1": "La política anterior permitía contraseñas de ocho caracteres.",
        "v2": "La política vigente exige contraseñas de al menos dieciséis caracteres.",
        "query": "¿Qué longitud mínima exige la política vigente?",
    },
}
