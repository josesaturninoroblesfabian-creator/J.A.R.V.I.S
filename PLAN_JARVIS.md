# Jarvis: diagnóstico y primera etapa

Revisión del 21 de octubre de 2026.

**Actualización:** la interfaz principal, el holograma, el control de pantalla y
la unificación de voz y chat ya avanzaron. Consulta [el estado actual](ESTADO_JARVIS.md)
para conocer las funciones disponibles y las pruebas más recientes.

## Decisión

Conservar OpenJarvis. Ya contiene agentes, motores de inferencia, herramientas,
memoria, habilidades, MCP, conectores, programación de tareas y opciones de
despliegue. Rehacer todo desde cero duplicaría trabajo. Su carpeta `src/openjarvis`
contiene 953 archivos: esta es una revisión de arquitectura y de los recorridos
principales, con pruebas dirigidas; no constituye una auditoría exhaustiva de cada
módulo ni una certificación de seguridad.

La personalización de escritorio está en `jarvis-native`. Antes estaba concentrada
en un único archivo y reproducía parcialmente el funcionamiento del backend.
Había cinco archivos modificados en OpenJarvis antes de esta revisión. Esos cambios
de interfaz y permisos de archivos se conservaron. Una copia del prototipo original
está en `jarvis-native/backups/jarvis_native.original.py`.

## Los siete componentes

| Componente | Situación y decisión |
| --- | --- |
| 1. Casa | La laptop sirve para desarrollar y usar el prototipo personal. Tiene unos 16 GB de RAM y una RTX 5060 Laptop con 8 GB de VRAM. No hace falta contratar un servidor para empezar. |
| 2. Cerebro | Están descargados Qwen 3.5 2B y 9B. Se añadieron perfiles para alternarlos y preparar Groq, Gemini y DeepSeek. El perfil inicial del escritorio es `local-fast` (2B). |
| 3. Manos y memoria | Se reutilizan el agente y las herramientas de OpenJarvis. La voz ahora comparte el mismo historial entre conversación y tareas. Se añadió persistencia de conversaciones. |
| 4. Programación y conocimiento | Ya existen intérprete de código, terminal, lectura/escritura, parches, Git y búsquedas. Falta evaluar tareas reales de programación con los modelos elegidos e indexar solo los proyectos que quieras consultar. |
| 5. Conexiones y máquina | Se conectaron también los servidores MCP configurados al agente nativo. Cada aplicación necesita su conector y credenciales. Tener terminal no equivale a disponer de control visual completo de todas las aplicaciones. |
| 6. Habilidades | El agente nativo ahora descubre las habilidades de OpenJarvis y las de `jarvis-native/skills`, si existe esa carpeta. No se descargaron habilidades externas durante esta revisión. |
| 7. Trabajo programado | El programador ya existía. Se corrigió su comando de arranque para conectar un sistema real: antes solo registraba simulaciones. No se creó ni activó ninguna tarea personal. |

Un **modelo** razona y propone acciones. El **arnés** mantiene la conversación,
le muestra herramientas, ejecuta llamadas, observa resultados y decide cuándo
terminar. Conectar DeepSeek V4 Pro por API no instala automáticamente DeepSeek
Harness. Aquí se conserva el arnés de OpenJarvis y se mejora su integración.

## Errores corregidos

- La interfaz nativa forzaba Ollama y un modelo local aunque hubiera otro proveedor
  configurado. Los perfiles hacen explícita la selección.
- El contexto del chat no llegaba a las tareas; una lista de palabras clave decidía
  el recorrido y fallaba con continuaciones como «ahora haz lo mismo». Ahora las
  peticiones usan un agente con el historial común.
- El historial desaparecía al cerrar. Ahora se guarda por turnos completos en
  SQLite: hasta 200 mensajes almacenados, con una ventana inicial de 20 mensajes y
  12 000 caracteres para el modelo. Es historial reciente persistente; no es memoria
  ilimitada ni aprendizaje del modelo. La memoria documental sigue siendo la de
  OpenJarvis y dispone de herramientas para guardar y buscar información.
- Se transcribía incluso después de grabar solo silencio. Ahora se descarta ese audio.
  La palabra de activación también respeta límites de palabra.
- Mencionar «pantalla» o «cámara» podía abrir una captura. Ahora se requieren
  peticiones visuales explícitas. Las capturas temporales se eliminan tras leerlas
  y los perfiles sin visión habilitada no capturan imágenes.
- La voz creaba ventanas desde un hilo secundario. Ahora envía una señal al hilo Qt.
- Un fallo de inicialización emitía igualmente la señal de éxito. Ahora comunica
  el fallo y evita arrancar el micrófono sin un backend de transcripción.
- La voz estaba fijada a Kokoro y a una voz concreta. Ahora respeta la configuración
  y usa una voz compatible si se selecciona otro backend.
- Las herramientas que requerían confirmación recibían siempre una aprobación
  automática. Ahora su confirmación existente llega a una ventana Qt o a la consola.
  Se conservan las políticas y permisos configurados en OpenJarvis.
- El arnés nativo omitía MCP y habilidades: ahora los carga y conserva las conexiones.
- Un componente de experimentación cambiaba globalmente los reintentos de las
  llamadas de IA, ignorando `max_retries=0`. Ahora respeta la desactivación explícita.
- La memoria SQLite de OpenJarvis tenía un `close()` vacío y conservaba su objeto
  Rust y el archivo abierto en Windows. Ahora libera ese propietario.
- El programador iniciado desde la consola no recibía un ejecutor. Ahora construye
  el sistema real y cierra sus recursos al salir.

## Cerebros y costo

Opciones verificadas en documentación oficial el 21 de octubre de 2026. Las cuotas,
modelos y condiciones pueden cambiar; el perfil no garantiza una cuota concreta.

| Perfil | Uso propuesto | Requisito |
| --- | --- | --- |
| `local-fast` | Conversación y pruebas rápidas sin enviar datos a una API de IA | Ollama y Qwen 3.5 2B, ya descargados |
| `local-quality` | Comparar calidad con el modelo mayor | Qwen 3.5 9B, ya descargado; consume más memoria |
| `groq` | Primera API a comparar para texto, herramientas y programación | Cuenta y `GROQ_API_KEY`; [Groq publica un nivel gratuito con límites](https://console.groq.com/docs/rate-limits) |
| `gemini` | Otra alternativa con cuota gratuita | `GEMINI_API_KEY` y dependencia `google-genai`; [Gemini 3.5 Flash Lite figura con nivel gratuito](https://ai.google.dev/gemini-api/docs/pricing) |
| `deepseek` | Comparar con el modelo que ya conoces | `DEEPSEEK_API_KEY`; [DeepSeek publica acceso por API](https://api-docs.deepseek.com/quick_start/pricing-details-usd/) con tarifas |
| `configured` | Usar el motor y modelo guardados por OpenJarvis | Configuración existente |

[GPT-6 Astra no admite el nivel gratuito de la API](https://developers.openai.com/api/docs/models/gpt-6-astra).
No se añadió como supuesto cerebro gratuito. El adaptador Groq utiliza su
[API compatible con OpenAI](https://console.groq.com/docs/openai): el proveedor es
Groq y el modelo del perfil es GPT OSS 120B.

No se introdujeron claves ni se hicieron peticiones a APIs de pago. La presencia
de una clave no demuestra que exista saldo, cuota o acceso al modelo. Un error de
cuota se muestra al usuario; no se cambia silenciosamente a otro proveedor ni se
repite una tarea que ya pudo haber ejecutado acciones.

Para esta laptop propongo probar primero 2B local y Groq con el mismo conjunto de
tareas. No se puede elegir un ganador por el nombre del modelo. Mediremos tiempo,
calidad en español, uso correcto de herramientas, errores y costo. El nivel gratuito
de Gemini permite que el proveedor use contenido para mejorar productos, según su
página de precios: eso debe considerarse al decidir qué proyectos enviarle.

## Uso

1. Ejecuta `Iniciar-Jarvis.cmd` para abrir la burbuja nativa. La aplicación anterior,
   si ya estaba abierta, debe cerrarse primero para cargar el código nuevo.
2. En el icono de bandeja, el menú **Cerebro (aplicar al reiniciar)** permite guardar
   otro perfil. Cierra y vuelve a abrir Jarvis para aplicarlo.
3. Los perfiles están en `jarvis-native/profiles.toml`. Las claves se leen de las
   variables de entorno del proceso; no deben escribirse en ese archivo.
4. Para visión local se puede decir «Jarvis, mira la pantalla» o «describe la cámara».
5. Para diagnóstico o chat de texto sin cargar la interfaz Qt, desde esta carpeta:

```powershell
& .\OpenJarvis\.venv\Scripts\python.exe .\jarvis-native\manage.py profiles
& .\OpenJarvis\.venv\Scripts\python.exe .\jarvis-native\manage.py check
& .\OpenJarvis\.venv\Scripts\python.exe .\jarvis-native\manage.py chat --profile local-fast
```

El diagnóstico no envía solicitudes ni comprueba credenciales contra el proveedor.
Para Gemini puede instalarse su dependencia dentro del entorno del proyecto:

```powershell
uv pip install --python .\OpenJarvis\.venv\Scripts\python.exe google-genai
```

**Actualización del escritorio:** la burbuja abre una ventana nativa en español.
Esa ventana y la voz comparten agente, perfiles y conversaciones. El frontend web
original se conserva para desarrollo y no se arranca automáticamente con la burbuja.
Consulta `ESTADO_JARVIS.md` para la programación, memoria y control de escritorio nuevos.

## Etapas siguientes

1. **Una sola sesión para voz y web.** La interfaz nativa debe consumir el backend
   compartido y mostrar herramientas, resultados, modelo activo y errores en el chat.
   Evitar mantener dos historiales y dos instancias de agente para la misma persona.
2. **Prueba comparativa de cerebros.** Preparar tareas de programación, búsqueda,
   memoria y español; comparar 2B, 9B y las APIs que habilites. Medir también la
   latencia de transcripción y síntesis por separado.
3. **Memoria y proyectos.** Perfil del usuario, hechos persistentes editables,
   recuperación por proyecto, exclusión de credenciales y eliminación de recuerdos.
   Versionar la personalización nativa, que actualmente está fuera del repositorio
   Git de OpenJarvis.
4. **Conectores y control visual.** Elegir aplicaciones concretas y comprobar cada
   herramienta de lectura y escritura. Ver una captura no permite pulsar botones:
   el control de escritorio necesita su propio adaptador y validación.
5. **Autonomía verificable.** Interfaz para crear, pausar y revisar trabajos;
   zona horaria explícita, límites de ejecución, recuperación después de reinicios
   y avisos solo ante resultados o fallos relevantes. La laptop debe permanecer
   encendida para ejecutar trabajos locales.
6. **Servidor e industrialización.** Separar interfaz, servicio de agentes y trabajador
   de escritorio. Un servidor por sí solo no puede manejar la laptop apagada.
   Para varios usuarios hacen falta sesiones y credenciales separadas, autenticación,
   aislamiento, copias de seguridad y observación del servicio. Se conservan las
   opciones Docker y servicios del proyecto como base; no se desplegó nada.

## Validación y límites

Resultado: **167 pruebas aprobadas** (23 del escritorio y 144 de OpenJarvis),
10 omitidas por sus condiciones de entorno. Las comprobaciones de estilo y de
formato del diff también pasaron. Hay una advertencia de deprecación de la
dependencia de pruebas de FastAPI/Starlette.

Las pruebas dirigidas verifican perfiles, contexto compartido, persistencia, silencio,
captura explícita, limpieza de archivos, llamadas de herramientas del adaptador Groq,
errores de cuota, políticas de reintento, memoria y conexión real del programador.
Los servicios cloud se prueban con respuestas simuladas, sin claves ni cargos.

Se comprobó una respuesta real de Qwen 3.5 2B. Ollama informó ejecución 100 % en GPU
y un contexto de 16 384 tokens. Una primera petición tardó unos 17 segundos y otra,
con el modelo cargado y diferente respuesta, unos 7 segundos. No son un benchmark
comparativo ni incluyen micrófono y síntesis de voz. La respuesta mostró que el
modelo pequeño aún puede atribuirse integraciones no comprobadas: hace falta
evaluar calidad, no solo velocidad. En una prueba adicional llamó realmente a
`calculator` para `137 * 29`, recibió `3973.0` y respondió en aproximadamente un
segundo. El cierre posterior liberó correctamente los archivos de memoria.

No se ha validado todavía la conversación completa por micrófono, cámara, todas
las aplicaciones, las APIs con credenciales reales ni funcionamiento permanente
tras reiniciar Windows. Las pruebas asíncronas y del servidor necesitaron permiso
para conexiones locales de prueba en Windows; al ejecutarlas con ese acceso,
pasaron, incluidas las de transmisión del SDK. No se ejecutó la batería completa
de los cientos de módulos del proyecto.
