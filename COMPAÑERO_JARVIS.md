# Jarvis, compañero y coach de enfoque

Actualizado el 25 de octubre de 2026.

**Actualización del 26 de octubre:** consulta [Windows y Android](WINDOWS_Y_ANDROID.md)
para el instalador beta, la voz ligera, las correcciones de cámara y el manejo de
cuotas. Las mediciones siguientes corresponden a la etapa original del compañero.

## Para empezar hoy

Abre **Iniciar-Jarvis.cmd** y entra en **Compañero**. Escribe una sola meta concreta,
por ejemplo «terminar una función de mi proyecto», y pulsa **Empezar conmigo**.
El bloque inicial dura 25 minutos y le sigue una pausa de cinco minutos. Puedes
cambiar ambos tiempos. No se inicia ninguna sesión de trabajo por abrir Jarvis.

La cara flotante parpadea, sigue el cursor y cambia su boca y color al escuchar,
pensar y hablar. Puedes volver a la esfera desactivando la cara en Compañero.

Prueba también estas peticiones por voz o texto:

- «Jarvis, inicia enfoque de 25 minutos para programar».
- «Jarvis, pausa el enfoque» o «reanuda la sesión».
- «Jarvis, me distraje».
- «Jarvis, no me interrumpas por 10 minutos».
- «Jarvis, termina la sesión».

Después de una respuesta hablada, Jarvis acepta una contestación durante 15 segundos
sin repetir su nombre, cuando la escucha continua está activada. La opción se puede
desactivar. Transcurrido ese tiempo vuelve a exigir «Jarvis» si esa era tu preferencia.

## Cómo te ayuda sin agobiarte

Durante una sesión, compara localmente la aplicación y el título activos con tu
lista de ocio. Una coincidencia debe mantenerse unos 45 segundos antes del primer
aviso; hay al menos tres minutos entre avisos. Cambiar unos segundos de ventana
no basta. Las excepciones de trabajo tienen prioridad: si usas YouTube para aprender,
añade, por ejemplo, «tutorial python». Las listas y los tiempos se pueden ajustar.

Un aviso es una hipótesis («Parece que abriste contenido de ocio»), no una medición
de tu atención. No bloquea aplicaciones, no cierra pestañas y no mueve el ratón
para obligarte a trabajar. El botón **Me distraje · ayúdame** consulta al modelo
para ofrecerte un paso pequeño y una pregunta concreta sobre tu meta.

También puede invitarte a conversar aproximadamente cada 30 minutos si estás
presente y hay un momento de inactividad. Espera si Jarvis está respondiendo o
hablando. De 22:00 a 08:00 no inicia avisos; ambos horarios son configurables.
Los botones y las peticiones expresas siguen disponibles en ese horario.

**Silencio 10 min** suspende los avisos. **Pausar sesión** detiene el temporizador.
**Detener** cancela la operación de Jarvis, pausa la sesión y silencia al compañero
temporalmente. Al terminar un descanso, propone otro bloque; no lo inicia por ti.

Los bloques completados, sus minutos y los últimos avisos quedan guardados localmente.
El tiempo indica duración del bloque, no una medida de atención real. Una sesión
abierta al cerrar o reiniciar se marca como interrumpida. El portátil y Jarvis deben
permanecer encendidos; no es un servicio alojado en la nube.

## Cámara opcional

Permanece apagada al iniciar. Si activas **Activar cámara local para presencia y
mirada del avatar**, busca un rostro aproximadamente una vez por segundo y orienta
los ojos según su posición. No reconoce identidades, no interpreta emociones y no
comprueba si miras el teléfono. No graba, no conserva fotogramas y no los envía a Groq.
Apagar la casilla libera la cámara. El sistema funciona también sin webcam.

## Groq y funcionamiento local

La clave suministrada quedó protegida con el cifrado de Windows para tu usuario,
fuera del código y de los archivos de configuración compartibles. El perfil activo
es **Groq · GPT OSS 120B**. Puedes volver al modelo local desde **Cerebro**.
En esa página también puedes guardar y comprobar una clave nueva sin mostrarla.

Groq recibe las conversaciones que le envías y el contexto de la meta para el apoyo
personalizado. El detector de distracciones no le envía títulos de ventanas ni
capturas. El perfil Groq usa **Qwen 3.5 9B local**, el modelo que está instalado, para peticiones de
visión, por lo que no pierde la función de observar la pantalla. Ollama necesita
estar disponible para esa parte. Los recordatorios automáticos usan frases locales
y no realizan consultas periódicas de pago a una IA.

La cuota de Groq pertenece a la cuenta y puede agotarse. No se contrató un plan ni se
activó facturación. Si la API no responde, el botón de apoyo ofrece una alternativa
local breve; para conversación y herramientas puedes seleccionar un perfil local.
No se reenvía una acción fallida automáticamente a otro modelo.

Referencias oficiales: [modelos de Groq](https://console.groq.com/docs/models),
[límites de uso](https://console.groq.com/docs/rate-limits) y
[configuración de razonamiento](https://console.groq.com/docs/reasoning).

## Validación y alcance

- 79 pruebas automáticas del escritorio, incluidas reglas de distracción, excepciones,
  pausa, equipo bloqueado o suspendido, silencio, persistencia, conversación posterior
  a la voz y almacenamiento cifrado de la clave.
- Groq real: respuesta breve inicial de unos 1,3 segundos; apoyo sobre una tarea de
  programación de unos 1,4 segundos; calculadora del agente de unos 2,4 segundos.
  Son mediciones puntuales, no garantías de velocidad.
- Comprobación visual de la aplicación abierta: cara animada, inicio, pausa,
  apoyo personalizado y finalización del bloque.
- La ruta visual híbrida se comprobó con una imagen de texto creada para la prueba.
  Usó Qwen 9B local, sin pasar la imagen a Groq. La primera carga tardó unos 46 s
  y leyó mal parte del texto. La visión necesita más validación antes de confiarle
  navegación autónoma; no se presupone que un modelo grande vea correctamente.
- La cámara física permanece apagada durante la comprobación; la detección depende
  de la iluminación y puede no encontrar un rostro. Las reglas de ocio también pueden
  equivocarse y necesitan tus excepciones.
- Se instaló OpenCV headless 4.14, compatible con el detector y su archivo de rostros.
  Las pruebas de presencia usan fotogramas y cámara simulados y comprueban la
  liberación del dispositivo. No constituyen una prueba física de tu webcam.

Esta mejora prepara una función independiente de compañero; no añade todavía un
robot físico, un instalador .exe, una aplicación Android, cuentas comerciales ni
cobros premium. Esas son etapas posteriores del producto. Tu versión tiene el modo
compañero completo, sin bloqueo premium.

## Componentes del proyecto

Las reglas y el reloj viven en `jarvis-native/companion.py`; la integración de voz
y ventanas en `companion_runtime.py`; el panel en `companion_panel.py`; la cara
dibujada en `avatar.py`; la detección local en `attention.py`; las credenciales en
`credential_store.py`. Los datos se guardan en `jarvis-native/data/companion.sqlite3`
y `jarvis-native/data/credentials/`. No distribuyas esas carpetas personales dentro
de un futuro instalador o APK. Cada usuario del producto necesitará sus credenciales
y sus preferencias propias.
