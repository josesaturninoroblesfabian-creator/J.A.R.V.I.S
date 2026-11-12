# Jarvis Personal · Windows beta y siguiente etapa

26 de octubre de 2026.

## Qué se corrigió

El 429 de los registros era una cuota real de Groq: 8.000 tokens por minuto.
No era un fallo de la webcam. El asistente enviaba mucho contexto y todas las
herramientas incluso para conversar; después leía el mensaje técnico de error.

La conversación simple ahora usa una petición sin catálogo de herramientas;
el historial enviado se limita a ocho mensajes y 4.000 caracteres. Las tareas
siguen usando herramientas. Se redujo el presupuesto de salida y se respeta
la espera comunicada por el proveedor. Solo se permite un reintento HTTP, de
la misma petición rechazada, si la espera es de hasta 12 segundos. No se reinicia
el agente ni se repite una herramienta ya ejecutada. Una espera larga se muestra
en español y no se lee en voz alta. La cuota externa puede volver a agotarse.

La cámara tiene selección de dispositivo y método. La apertura automática prueba
DirectShow, Media Foundation y el método predeterminado, verifica un fotograma y
libera cada intento fallido. «Enciende la cámara» y «apaga la cámara» son órdenes
locales; no necesitan una consulta a Groq. La presencia y la captura explícita
comparten el dispositivo para evitar dos aperturas simultáneas.

## Por qué consumía recursos

La configuración anterior cargaba Whisper small y Kokoro/Torch para escuchar y
hablar. Una instancia medida ocupaba alrededor de 1,5 GB. El modelo visual Qwen 9B
podía sumar varios GB de memoria y trabajo de CPU/GPU al analizar imágenes.

El modo ligero usa Vosk español pequeño para reconocimiento y una voz de Windows.
No descarga ni carga un modelo de lenguaje local. La cámara se procesa a baja
frecuencia y con un hilo de OpenCV. El análisis visual de IA local está desactivado
por defecto y requiere activación expresa en Cerebro. Encender la cámara del
compañero no carga Qwen. La voz avanzada sigue disponible en el entorno de
desarrollo; no forma parte del instalador ligero.

En pruebas puntuales, la síntesis de una frase tardó 0,15 s y su reconocimiento
0,64 s. El ejecutable instalado superó una prueba independiente con unos 219 MB de
memoria, sin Torch ni Whisper. La aplicación instalada, con ventana abierta y
escucha del micrófono, se mantuvo alrededor de 300 MB en cinco muestras. No había
modelos cargados en Ollama ni procesos hijos de Jarvis. Estas cifras no son una garantía: la ventana, la cámara,
otras aplicaciones, controladores y tareas ejecutadas pueden cambiar el consumo.

Vosk reconoce sin enviar el micrófono a una API. La voz depende de las voces de
Windows instaladas; para un acento español natural el equipo debe tener una voz
española. Puede ser menos expresiva que una voz neural, a cambio de menor consumo.

## Uso de la beta de Windows

El instalador es para Windows 10/11 de 64 bits. Incluye Python, interfaz, herramientas,
detector de cámara y reconocimiento español; el usuario no necesita instalar Python,
OpenJarvis ni Ollama para el modo ligero.

1. Ejecutar `Jarvis-Setup-0.2.0-beta-x64.exe`.
2. Abrir Jarvis Personal desde el escritorio o el menú Inicio.
3. En el primer arranque, introducir una clave propia de Groq en Cerebro,
   comprobarla y pulsar Aplicar y reconectar.
4. Probar la voz y el micrófono. Activar la cámara solo cuando se quiera utilizarla.

Las conversaciones, preferencias y claves cifradas se guardan por usuario en
`%LOCALAPPDATA%/JarvisPersonal/`. No se escriben dentro de la carpeta de instalación.
La desinstalación conserva los datos personales. El paquete compartible no lleva
la clave ni el historial de este proyecto. No compartas la carpeta de datos.

La beta no está firmada con un certificado comercial y todavía necesita pruebas
en varios equipos físicos. Si Windows bloquea su ejecución, no se modifican ni
desactivan sus protecciones: la firma y la reputación de distribución son trabajo
de publicación pendiente. No se ha publicado en una tienda ni se ha desplegado un
servidor de pago. El intérprete Python interno del ejecutable no se expone como
herramienta para ejecutar código; siguen disponibles archivos, shell, git,
calculadora, memoria y control del escritorio sujeto a sus confirmaciones.

### Validación en esta laptop

- 97 pruebas del escritorio y comprobación de estilo superadas.
- Apertura física de la cámara 0 con DirectShow: fotograma válido, presencia,
  captura compartida en memoria y liberación del dispositivo comprobadas.
- Síntesis y reconocimiento de órdenes en español con los componentes ligeros.
- Instalación real por usuario, acceso directo y apertura del ejecutable instalado.
- Primera apertura con datos limpios: solicita clave propia y no muestra historial.
- Prueba sin red del ejecutable instalado: calculadora real, 14 herramientas,
  voz de Windows, reconocimiento Vosk y ausencia de Torch/Whisper.
- Una única instancia personal quedó abierta y conectada a Groq. Se migraron
  conversaciones, memoria, preferencias, tareas y la credencial cifrada sin
  incorporarlos al instalador. El arranque automático existente apunta ahora
  a la aplicación instalada; se conservó una copia de su lanzador anterior.

La automatización de clics de la comprobación final quedó limitada por el error
Direct3D `0x887A0005` del controlador gráfico. La interfaz sí pudo inspeccionarse
mediante accesibilidad y confirmó la conexión y la escucha. No se completó una
nueva prueba de cámara mediante clics en el ejecutable instalado; la prueba
física del componente de cámara se hizo por separado. No se cambiaron opciones
de seguridad ni controladores de Windows.

El instalador compartible está en `release/Jarvis-Setup-0.2.0-beta-x64.exe`
(216.747.427 bytes). Su huella se guarda en `release/SHA256SUMS.txt`.

## Cómo convertirlo en un servicio comercial

Una aplicación .exe cambia cómo se instala; por sí sola no traslada el trabajo
a un servidor ni elimina las cuotas. La beta utiliza una cuenta API por usuario.
Para un servicio con suscripción, el siguiente diseño recomendado es:

- Clientes Windows y Android: interfaz, micrófono, reproducción, presencia local y
  permisos del dispositivo. El control del PC se ejecuta únicamente en Windows.
- Backend propio: cuentas, autenticación, cuotas por usuario, sesiones, facturación,
  presupuesto de tokens y selección de proveedores. Las claves del negocio viven
  en el servidor, no dentro del .exe ni del APK.
- Proveedores de IA o inferencia alojada: conversación y, si se contrata, voz/visión.
  No se debe prometer uso ilimitado sobre una única clave gratuita compartida.
- Canal de acciones por dispositivo: instrucciones estructuradas, permisos locales,
  auditoría, cancelación y confirmación para las operaciones sensibles.

Se debe validar el coste por sesión antes de fijar un precio premium. Hacen falta
pruebas con varios usuarios, firma del instalador, actualizaciones verificadas,
recuperación de errores y un flujo para borrar/exportar datos. La versión actual
es un piloto instalable, no una certificación de producción.

## Paso a Android

Tras validar Windows, Android puede consumir el mismo backend mediante una API
versionada y eventos de conversación. El cliente tendrá sus propios permisos de
cámara y micrófono y respetará las restricciones de segundo plano y batería de
Android. No puede heredar automáticamente el acceso a archivos y ratón del PC;
para comunicarse con Windows hará falta vincular ambos dispositivos.

Ya existe una beta Android independiente para Android 13 o posterior, con APK
firmado en `release/Jarvis-Personal-0.1.0-beta-android13.apk`. El uso y las
limitaciones están en [la guía Android](jarvis-android/README.md). Conversa
directamente con Groq con clave propia; no necesita la laptop encendida.
Incluye voz del teléfono, cámara frontal local, enfoque, notas y herramientas
sencillas. No incluye sincronización ni control de Windows. El backend comercial,
cuentas, pagos y alojamiento siguen pendientes.

## Construcción y fuentes

`packaging/Jarvis.spec` define los componentes públicos y excluye las bibliotecas
neuronales pesadas. `packaging/build.ps1` construye el ejecutable y el instalador
NSIS. `packaging/finalize_release.py` copia licencias e inventario y rechaza claves,
bases de datos y preferencias personales dentro del paquete. El ejecutable dispone
de `--self-test ruta.json` para comprobar herramientas y voz sin red.

El modelo de reconocimiento se obtiene de
[Vosk español pequeño](https://alphacephei.com/vosk/models), bajo Apache 2.0.
El formato de distribución utiliza [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html)
y [NSIS](https://nsis.sourceforge.io/License). Los límites de Groq están documentados
en [su página oficial](https://console.groq.com/docs/rate-limits).
