# Motor OpenJarvis incluido en Jarvis

El código de este directorio procede de [OpenJarvis](https://github.com/open-jarvis/OpenJarvis),
con base `3135126a` y licencia [Apache 2.0](LICENSE). Jarvis conserva los avisos
originales y las adaptaciones locales de lectura y escritura de archivos,
memoria SQLite, reintentos, programación de tareas e interfaz original.
El historial de Jarvis vive en el repositorio de la raíz. Esta copia se incorpora
como código fuente ordinario. El binario Ollama para macOS y las automatizaciones
de publicación del proyecto original se mantienen fuera de Git en Jarvis.

Se revisó `open-jarvis/OpenJarvis` hasta `f21d902f` el 6 de noviembre de 2026.
Entre `3135126a` y esa revisión hay 27 commits, de los cuales 21 actualizan
estadísticas de clonación. Decisiones para los otros seis:

| Cambio original | Decisión en Jarvis |
| --- | --- |
| [Protección de archivos de credenciales](https://github.com/open-jarvis/OpenJarvis/pull/1144) | Incorporado en Python y Rust, con compatibilidad para extensiones Rust ya instaladas. |
| [Voz sin símbolos Markdown](https://github.com/open-jarvis/OpenJarvis/pull/1145) | Adaptado en `jarvis-native/desktop.py` para la interfaz Qt. Android ya prepara el texto hablado. |
| [GPT OSS local en el enrutador del servidor](https://github.com/open-jarvis/OpenJarvis/pull/1203) | Reservado para una integración futura del servidor. Jarvis selecciona Groq u Ollama mediante perfiles. |
| [OpenCode V2](https://github.com/open-jarvis/OpenJarvis/pull/1170) | Reservado para cuando Jarvis integre ese agente. |
| [ElevenLabs](https://github.com/open-jarvis/OpenJarvis/pull/1133) | Reservado como opción de voz en la nube. Windows usa voz del sistema y Android usa la del teléfono. |
| [Actualización de setup-uv](https://github.com/open-jarvis/OpenJarvis/pull/1150) | Aplica a los flujos de publicación de OpenJarvis. |

Para revisar otra actualización, comparar su revisión con la base indicada en
un clon separado de OpenJarvis y probar los parches elegidos en una rama de Jarvis.
