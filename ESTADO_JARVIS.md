# Jarvis · escritorio personal

Actualizado el 26 de octubre de 2026.

**Android beta:** [guía de instalación y funciones](jarvis-android/README.md).
APK para Android 13 o posterior en `release/`, con conversación Groq, voz,
cámara local y enfoque. Funciona independientemente de la laptop. Las pruebas
Android son separadas de las 97 comprobaciones del escritorio.

**Windows beta y correcciones:** [instalación, consumo y siguiente etapa Android](WINDOWS_Y_ANDROID.md).
Se añadieron voz ligera, recuperación acotada de 429 y selección/órdenes locales
de cámara. La validación actual del código comprende 97 pruebas.
La beta está instalada como **Jarvis Personal**, con un único proceso personal
abierto. Con ventana y escucha activa se midieron unos 300 MB de memoria. El
instalador para compartir está en `release/`; cada persona configura su propia clave.

**Nueva etapa:** [Compañero y coach de enfoque](COMPAÑERO_JARVIS.md), con cara animada,
sesiones de enfoque, pausas, recordatorios locales y Groq configurado. La validación
actual del escritorio comprende 79 pruebas; las cifras siguientes describen la etapa
del 21 de octubre y se conservan como registro de sus comprobaciones.

## Lo que ya puedes utilizar

- Una sola instancia de escritorio: abrir el lanzador de nuevo muestra la sesión
  existente. La ventana y la voz comparten cerebro e historial.
- Interfaz en español con conversaciones guardadas, formato Markdown, copia de
  respuestas, atajo **Ctrl + Enter**, actividad de herramientas y tiempo de respuesta.
- Páginas para voz, modelos, herramientas, control del escritorio, memoria, tareas
  programadas y apariencia del holograma.
- Historial separado por conversación. La migración conserva los mensajes que ya
  tenías. «Nueva conversación» no borra las anteriores.
- Notas persistentes y búsqueda en la memoria documental de OpenJarvis.
- Trabajos recurrentes con ejecución real, pausa/reanudación y registro de resultados.
  Necesitan que Jarvis y el equipo permanezcan encendidos. No se creó ninguna tarea
  personal durante estas comprobaciones. Los trabajos tienen historial independiente.

## Holograma

| Color inicial | Significado |
| --- | --- |
| Verde | Escuchando |
| Turquesa | Reconociendo voz |
| Violeta | Pensando |
| Naranja | Ejecutando una herramienta |
| Azul | Hablando |
| Rojo | Error |
| Cian | En espera |
| Ámbar | Iniciando o preparando voz |
| Gris | En pausa |

La esfera completa cambia de color, muestra el nombre del estado y reacciona al
nivel del micrófono. En **Holograma** puedes personalizar cada color. También puedes
pedir «Cambia el holograma a rojo»: ahora existe una herramienta que aplica el
cambio y lo guarda, sin editar código. Muestra una vista previa de cuatro segundos
y después vuelve al color correspondiente a la actividad actual.

## Control de pantalla

Las herramientas del agente pueden inspeccionar ventanas y cursor, observar una
captura con un modelo visual, mover el ratón, hacer clic, desplazar contenido,
activar ventanas, usar teclas y escribir texto Unicode. La vista **Control de
pantalla** incluye un cuadro donde probar el movimiento y la escritura.

**Detener** interrumpe la respuesta en curso y pausa el control de pantalla. Puede
reactivarse desde su casilla. El control del ratón conserva la interrupción de
PyAutoGUI al mover el cursor a una esquina. Windows puede impedir actuar sobre
ventanas elevadas o protegidas. Las coordenadas corresponden a la pantalla principal;
las tareas con varios monitores todavía requieren validación adicional.

## Fluidez

- El modelo local se precarga al iniciar.
- El texto aparece progresivamente sin perder el ciclo de herramientas del agente.
- El micrófono termina tras unos 0,9 segundos de silencio y descarta gran parte del
  silencio anterior a la voz.
- Whisper usa una búsqueda más corta para conversación, filtra silencio y recibe
  el audio en memoria. La detección de «Jarvis» tolera algunas transcripciones comunes.
- Las respuestas habladas extensas se limitan a unos 600 caracteres; el contenido
  completo permanece visible en el chat.
- Los controles sencillos del holograma tienen una ruta directa. La prueba local
  de cambio de color tardó unos 0,01 s. Una respuesta con calculadora y texto
  progresivo tardó unos 8,6 s en la prueba realizada. No es una garantía de latencia
  ni una comparación entre modelos: influyen el contexto y la carga de la GPU.

## Comprobaciones realizadas

- 45 pruebas dirigidas del escritorio: historial, migración, perfiles, voz,
  herramientas, color persistente, interrupción y reconstrucción de llamadas durante
  la respuesta progresiva, programación de tareas y teclado Unicode.
- Cambio de color solicitado al agente: aplicado y guardado.
- Cambio de color desde el chat de la aplicación abierta: aplicado y conservado
  después de reiniciar.
- Cálculo con herramienta real y respuesta progresiva: `137 × 29 = 3973`.
- Prueba en la aplicación abierta: movimiento del ratón y escritura de
  «Jarvis controla el teclado: español, acción y precisión.»
- Síntesis y reconocimiento local de una petición sobre el holograma; el
  reconocimiento tardó unos 2,7 s con el modelo cargado. Esta prueba usó audio
  generado localmente, no una nueva orden pronunciada por una persona.
- Se retiraron 52 carpetas de caché, unos 5,7 MB. Las cachés pueden regenerarse.
  Se conservaron los modelos, datos, fuentes, entorno Python y dependencias necesarias.

La prueba real de escritura detectó una carrera al pegar desde el portapapeles.
Se corrigió usando eventos Unicode de Windows y se repitió la prueba con éxito.

La primera lectura real de pantalla respondió en unos seis segundos, pero mezcló
la captura con suposiciones del historial. El análisis visual ahora utiliza solo
la imagen y la petición actuales, con respuesta progresiva e interrupción. Esto
reduce esa fuente de confusión; el modelo todavía puede interpretar mal una imagen.
Se sustituyó además la captura que abría una consola por una captura en memoria:
la consola podía aparecer dentro de su propia captura. Las respuestas visuales se
limitan a 256 tokens y usan una temperatura baja. El modelo 2B mostró errores de
interpretación en la prueba real, por lo que observar la pantalla no equivale a
una garantía de precisión para navegar autónomamente por cualquier aplicación.
La repetición final, con la captura en memoria y una conversación nueva, tardó
unos 4,5 segundos y describió el menú, el chat, los botones y el panel de actividad
de Jarvis sin introducir una ventana de consola.

## Archivos y arranque

Ejecuta **Iniciar-Jarvis.cmd**. El motor, herramientas y memoria siguen usando
OpenJarvis; `jarvis-native` es su aplicación de escritorio. Esas dos carpetas no
representan dos asistentes ejecutándose.

Los perfiles están en `jarvis-native/profiles.toml`. Los datos del escritorio están
en `jarvis-native/data/`, con conversaciones, preferencias, colores y programación
de tareas. Las dependencias adicionales del control visual se documentan en
`jarvis-native/requirements-desktop.txt`.

Las APIs necesitan claves y comprobaciones reales de acceso. No se probaron todas
las aplicaciones de Windows ni se garantiza que el modelo de 2B interprete bien
cualquier tarea. Para programación compleja conviene comparar el perfil de mayor
calidad o una API. El frontend web original se conserva como interfaz de desarrollo;
el lanzador del escritorio ya no lo inicia como una segunda aplicación.
