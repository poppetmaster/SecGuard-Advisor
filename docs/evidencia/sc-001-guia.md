# Guía de SC-001 — recorrido cronometrado por una persona

**Validación recomendada y no bloqueante**. El umbral de referencia sigue siendo **15 minutos o
menos** para una persona que conoce el producto; no se cambia el umbral ni se excluyen pasos. La
decisión de gobierno del 2026-11-09 indica que su resultado no bloquea el segundo incremento.

Esta guía es para una persona. El recorrido automatizado de `tests/acceptance/` no sustituye esta
medición y no se presenta como SC-001.

## 1. Preparación previa (fuera del cronómetro)

Ejecutar una vez:

```bash
make corpus          # solo si data/corpus no tiene manifiesto y originales
make demo-prepare    # storage/demo: migraciones + corpus + dataset sintético
make demo            # arranca storage/demo en 127.0.0.1:8000
```

Abrir `http://127.0.0.1:8000/cases` en el navegador. Verificar que `/healthz` responde y que el caso
precargado «Evaluación de un asistente interno de IA» muestra la marca de escenario educativo y sus
hallazgos sintéticos.

Documentos que se van a subir durante el recorrido:

- [`docs/evidencia/sc-001/documento-a-politica-respaldo.md`](sc-001/documento-a-politica-respaldo.md)
- [`docs/evidencia/sc-001/documento-b-gestion-riesgos.md`](sc-001/documento-b-gestion-riesgos.md)

No crear todavía el caso del recorrido. No sembrar hallazgos en el caso nuevo: los conteos de la
pregunta de herramienta se consultan en el caso de demostración precargado. Un caso normal no recibe
hallazgos automáticamente. La instancia puede contener además los casos «Revisión SC-003» y
«SC-003 lista normativa», usados para la tabla de SC-003; no forman parte del recorrido cronometrado.

## 2. Punto de inicio y fin

- **Inicio**: el instante en que se hace clic en **Nuevo caso** para crear el caso del recorrido.
- **Fin**: después de comprobar el aislamiento del segundo caso y la persistencia tras el reinicio.
- El tiempo de preparación, arranque del servidor y lectura de esta guía queda fuera del cronómetro.
- Si el recorrido supera 15 minutos, registrar la duración real y las incidencias. No ajustar el
  umbral, no omitir pasos y no repetir hasta obtener un resultado favorable sin declararlo.

## 3. Recorrido

1. Crear un caso con título «Aceptación SC-001 — [fecha]», dejando vacíos los campos opcionales.
2. Subir los dos documentos de la sección 1. Comprobar que ambos quedan `Disponible`.
3. Preguntar: «¿Cada cuánto se prueba la restauración de las copias de seguridad?».
   Abrir la cita y comprobar el fragmento y el control automático.
4. Preguntar: «¿Quién conserva el registro de cada prueba?».
   Comprobar que el seguimiento usa el contexto anterior.
5. Preguntar: «¿Cada cuánto revisa el comité de riesgos el registro y qué hace con las excepciones?».
   Abrir la cita del segundo documento.
6. Abrir el caso precargado «Evaluación de un asistente interno de IA» y preguntar:
   «¿Cuántos hallazgos de severidad High están registrados? Agrúpalos por activo.».
   Comprobar Total 4, `api-gateway 2`, `customer-portal 1` e `internal-wiki 1`, y la etiqueta
   «Datos educativos sintéticos».
7. Reiniciar: detener el servidor con `Ctrl+C` y ejecutar `make demo` de nuevo. Recargar el caso del
   recorrido y comprobar que el caso, los dos documentos, la conversación, las citas y la ejecución
   siguen presentes.
8. Crear un segundo caso vacío y preguntar por hallazgos: debe responder Total 0 y aclarar que no
   demuestra ausencia de vulnerabilidades. Abrir una URL de documento del primer caso usando el
   identificador del segundo caso: debe responder 404. No debe aparecer ningún dato del primer caso.
9. Detener el cronómetro.

## 4. Registro

Completar a mano después del recorrido:

| Campo | Valor |
|---|---|
| Ejecutor (nombre) | |
| Fecha | |
| Hora de inicio | |
| Hora de fin | |
| Duración | |
| ¿Cumple ≤ 15 minutos? | |
| Incidencias | |

Adjuntar o referenciar capturas propias si se desea. No completar este registro con una ejecución
automatizada ni con la identidad «Aceptación de prueba».

## 5. Comunicación del resultado

- Si cumple: registrar el resultado en `docs/evidencia/sc-001-resultado.md` con la tabla anterior y
  las incidencias.
- Si no cumple: registrar igualmente la duración real, el paso que más tardó y las incidencias. No
  cambiar el criterio ni eliminar pasos para forzar el cumplimiento.
- SC-001 es recomendada y no bloqueante; si se ejecuta, registrar el resultado sin cambiar el umbral.
  El cierre del segundo incremento no depende de este registro.
