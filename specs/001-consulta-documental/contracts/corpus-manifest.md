# Contrato del manifiesto del corpus

## Objetivo

Registrar de forma reproducible qué documentos oficiales componen el corpus, de dónde se
obtuvieron, con qué licencia y con qué integridad. El manifiesto es la fuente de procedencia; los
originales viven fuera de Git.

## Ubicación

```text
data/corpus/
├── originals/
│   ├── csf2.pdf
│   ├── airmf.pdf
│   ├── ai6001.pdf
│   └── owasp-llm-2025.pdf
└── manifest.json        # versionado en Git
```

`data/corpus/originals/` está en `.gitignore`. `manifest.json` se versiona.

## Relación con la base de datos

El manifiesto es la fuente de verdad de título, versión, licencia y procedencia bibliográfica. No
existe una tabla que duplique esos datos: `documents.source_id` guarda el `id` del manifiesto y se
valida al arrancar. Un `source_id` que no exista en el manifiesto es un error de configuración, no
un documento público válido.

## Esquema

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-08T18:00:00Z",
  "sources": [
    {
      "id": "csf2",
      "title": "The NIST Cybersecurity Framework (CSF) 2.0",
      "publisher": "NIST",
      "published_at": "2024-02-26",
      "doi": "10.6028/NIST.CSWP.29",
      "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
      "license": "U.S. Government work",
      "version_label": "NIST CSWP 29",
      "retrieved_at": null,
      "sha256": null,
      "bytes": null,
      "page_count": null,
      "status": "pending",
      "notes": null
    }
  ]
}
```

Reglas:

- `sha256`, `bytes`, `page_count` y `retrieved_at` son `null` hasta la descarga real. **No se
  escribe un valor calculado a mano ni un hash inventado.**
- `status` ∈ `pending`, `downloaded`, `verified`, `failed`.
- `license` es el texto observado en la fuente; para NIST se registra el aviso del PDF al
  descargarlo.
- `version_label` fija la edición. Una nueva edición del mismo documento se registra como una
  entrada nueva con su propio `id`, no sobrescribiendo la anterior.

## Procedimiento

1. `make corpus` → `scripts/fetch_corpus.py --verify`.
2. Para cada fuente: descarga a un archivo temporal, calcula SHA-256 y bytes, compara con el
   manifiesto si ya existe un hash.
3. Si el hash difiere del registrado: no se sobrescribe el original; se informa y se detiene esa
   fuente con `status=failed`.
4. Si coincide o no había hash: se mueve a `originals/<id>.<ext>` y se actualiza el manifiesto con
   fecha, hash, bytes y páginas.
5. Se valida la extracción: se abre con pypdf, se cuentan páginas y se verifica que al menos una
   página tenga texto. Un documento sin texto se marca `failed`.
6. Se informa el resultado por fuente. Nunca se declara el corpus completo si alguna fuente falló.

## Idempotencia

- Volver a ejecutar el procedimiento con el mismo archivo no cambia el hash ni duplica filas.
- Un cambio de contenido obliga a una decisión explícita: se registra una versión nueva del
  corpus y se reconstruye el índice.

## Prohibiciones

- No se indexa nada de `docs/referencias/`, la constitución, instrucciones de agentes ni
  respuestas esperadas de pruebas.
- No se descargan fuentes desde espejos no oficiales.
- No se registra un hash sin haber descargado el archivo.
- No se presenta una fuente como verificada si falló la extracción.
