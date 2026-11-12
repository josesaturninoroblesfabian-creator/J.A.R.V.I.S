# Jarvis Personal para Android · beta 0.1.1

Cliente Android nativo en español, para Android 13 (API 33) o posterior.
Java y vistas de Android; sin servidor en la laptop, WebView ni modelos grandes.
No modifica la aplicación Windows. No necesita tener la laptop encendida.

## Funciones incluidas

- Conversación con Groq y respuesta progresiva. Modelo rápido GPT OSS 20B por
  defecto; GPT OSS 120B seleccionable. Límite de historial de 8 mensajes y
  4.000 caracteres, salida de 640 tokens, cancelación y mensajes seguros de cuota.
- Voz española mediante los servicios del teléfono. Reconocimiento local cuando
  Android lo ofrece; el servicio de reconocimiento puede utilizar su propia red.
  El botón Hablar inicia una escucha; no hay micrófono permanente en segundo plano.
- Cara dibujada de forma nativa: verde al escuchar, violeta al pensar, dorado al
  hablar y rojo ante un error. Color de reposo personalizable.
- Enfoque de 15/25/50 minutos o 1–120 minutos mediante una orden. Pausa, continuación,
  objetivo y avisos de descanso. Tono cercano, suave o directo.
- Cámara frontal local, cerrada al cambiar de pestaña o salir de la app.
  Detección de presencia solo si el dispositivo la ofrece mediante su cámara.
  No se guardan ni se suben fotogramas; la IA conversacional no ve la cámara.
- Notas, historial local, calculadora, hora, batería y linterna. El chat abre con
  los 24 mensajes más recientes. **Ver mensajes anteriores** carga otra tanda.
  La lectura y el guardado del historial se ejecutan en segundo plano.

## Probar en un teléfono

1. Copiar `release/Jarvis-Personal-0.1.1-beta-android13.apk` al teléfono, por
   ejemplo mediante USB a Descargas, y abrirlo desde Mis archivos/Archivos.
2. Seguir la instalación normal que ofrezca Android. Esta beta se distribuye fuera
   de Google Play. No requiere root ni desactivar Play Protect. Si aparece un
   bloqueo de seguridad, conservarlo y comunicar el mensaje antes de continuar.
3. Abrir Jarvis Personal. En Ajustes pegar una clave propia de Groq y pulsar
   Guardar clave. La app no contiene la clave del desarrollador.
4. Opcionalmente elegir modelo, nombre, tono y lectura en voz alta; pulsar
   Guardar preferencias después de cambiarlos.
5. Probar primero `calcula 137 por 29`, `inicia enfoque de 25 minutos`,
   `recuerda que quiero estudiar programación`, `mis notas` y `qué puedes hacer`.
6. Pulsar Hablar para comprobar el micrófono. En Compañero, pulsar Encender cámara.
   Conceder únicamente los permisos que se quieran usar. Texto y enfoque siguen
   disponibles si se rechaza cámara o micrófono.

Si ya tienes la beta 0.1.0, instala el nuevo APK encima para conservar el historial,
las notas y la clave guardada. Los dos APK usan la misma firma.

El chat usa Groq directamente sobre HTTPS y su cuota depende de la cuenta. La
clave queda cifrada con Android Keystore y no participa en copias de seguridad
ni transferencias automáticas. Las notas solo se agregan a las peticiones cuando
se activa Compartir estas notas con Groq. Desinstalar borra los datos locales.
Si utilizas la misma cuenta de Groq en Windows y Android, ambos consumen sus
límites; el APK no crea una cuota gratuita adicional.

## Validación de la beta 0.1.1

19 pruebas JVM y 37 comprobaciones en Android 15. El emulador instaló 0.1.1
sobre 0.1.0 y comprobó la carga de mensajes anteriores, el guardado en segundo
plano, las herramientas locales, el enfoque, la cámara y Keystore.

## Validación de la beta 0.1.0

- 19 pruebas JVM superadas; lint sin errores (quedan advertencias de traducción
  futura y constructor del visor programático).
- APK de producción firmado e instalado en un emulador Android 15/API 35.
- 30 comprobaciones funcionales sin red: apertura real de la actividad, chat,
  calculadora, notas, colores, enfoque, pausa, continuación, cámara frontal
  encendida/apagada, persistencia y cifrado con Android Keystore.
- Una ejecución adicional incluyó una respuesta real de Groq desde el cliente
  Android: 32 comprobaciones superadas. La credencial de esa prueba se introdujo
  temporalmente en los datos privados del emulador y se eliminó. Nunca se incluyó
  en el APK ni en el APK de pruebas.
- Verificación de la firma del APK, alineación y ausencia de la clave personal y
  del código de pruebas en el paquete compartible. Tamaño: 2.160.888 bytes.
- Revisión visual de Conversación y Compañero; iconos de sistema claros sobre el
  fondo oscuro. Arranque en frío observado: aproximadamente 1,7 segundos en ese
  emulador. No es una promesa de rendimiento para teléfonos físicos.

La compatibilidad declarada empieza en Android 13. Todavía falta probar voces,
micrófono, cámara, notificaciones y batería en un Samsung u otro teléfono real;
no se han probado físicamente todas las versiones posteriores de Android. El
emulador de QA se detiene al terminar para liberar los recursos de la laptop.

## Límites de esta primera beta

No controla otras apps, no tiene acceso al PC, no identifica qué aplicación
distrae al usuario, no reconoce emociones y no interpreta imágenes. El enfoque
es un temporizador con mensajes de apoyo, no una medición de atención. No hay
cuentas, pagos, sincronización Windows–Android, escucha continua ni APK de tienda.

Android puede retrasar las alarmas de descanso por ahorro de batería. El contador
de la app usa la hora guardada y se recupera al abrirla. Tras reiniciar el celular,
hay que abrir Jarvis para reprogramar un aviso pendiente. Forzar la detención de
la app impide sus avisos hasta volver a abrirla. La cámara, voces y reconocimiento
dependen del equipo y deben confirmarse en el Samsung u otro teléfono real.

## Construcción

Herramientas fijadas: Android Gradle Plugin 9.1.1, Gradle 9.3.1 con checksum,
compile/target SDK 36, Build Tools 36.0.0. Se construyó con el JDK 25 de Android
Studio. El wrapper y el código están incluidos. Los requisitos de compatibilidad
están en [Android Developers](https://developer.android.com/build/releases/agp-9-1-0-release-notes).

Configurar `JAVA_HOME`, SDK y `local.properties` (este último no se distribuye).
Ejecutar `build-apk.ps1` desde PowerShell. Genera la firma local de beta si no
existe, ejecuta pruebas y lint y copia el APK firmado a `release/`. El paquete no
incluye herramientas de desarrollo, pruebas instrumentadas, claves ni historial.

La firma privada se conserva en `packaging/android-signing/`, excluida de Git.
Respaldarla de forma privada: se necesita la misma firma para actualizar la app
sin desinstalarla. Nunca distribuir esa carpeta junto con el APK. La firma de
beta no sustituye el proceso de publicación y verificación de Google Play.

Pruebas JVM: `gradlew.bat testReleaseUnitTest` (o `testDebugUnitTest`).
Pruebas en emulador: instalar APK y APK de pruebas firmado con la misma clave,
conceder permisos al paquete de QA y ejecutar el runner `SmokeInstrumentation`.
Los permisos se conceden solo en el emulador de pruebas; nunca por defecto en
el celular de una persona. El runner comprueba UI, herramientas, enfoque,
cámara, historial y Keystore. El APK de pruebas no se entrega al usuario.

## Fuentes de las APIs

- [Reconocimiento de Android](https://developer.android.com/reference/android/speech/SpeechRecognizer)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Límites de Groq](https://console.groq.com/docs/rate-limits)
