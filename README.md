# Jarvis

Asistente personal en español para Windows y Android. La versión Windows combina
voz ligera, cámara, enfoque, memoria y herramientas de escritorio. La versión
Android funciona por cuenta propia y conversa con Groq con una clave del usuario.

En Windows, usa **Salir de Jarvis** o la **X** para cerrar la ventana y el holograma.
Desmarca **Mostrar holograma** si quieres seguir usando Jarvis con la pantalla libre.
En Android, **Ver mensajes anteriores** carga otra tanda del historial.

[Descargas de Windows y Android](https://github.com/josesaturninoroblesfabian-creator/J.A.R.V.I.S/releases)

| Componente | Código y construcción |
| --- | --- |
| Escritorio Windows | `jarvis-native/` y [empaquetado](packaging/README.md) |
| Aplicación Android | `jarvis-android/` y [guía Android](jarvis-android/README.md) |
| Motor integrado | `OpenJarvis/` y [origen y cambios](OpenJarvis/JARVIS-MODIFICATIONS.md) |

`OpenJarvis/` contiene la copia de código fuente que usa Windows. Se conserva el
nombre del paquete `openjarvis` para mantener sus interfaces y herramientas. El
desarrollo y los cambios de Jarvis se guardan desde la raíz de este repositorio.
Las actualizaciones de OpenJarvis se revisan por separado y se incorporan de
forma selectiva. Su licencia Apache 2.0 está en [OpenJarvis/LICENSE](OpenJarvis/LICENSE).

Los instaladores, datos personales, perfiles locales, modelos descargados, claves
y material de firma se mantienen fuera del historial de Git. Los perfiles de
Windows empiezan con `jarvis-native/profiles.default.toml`.
