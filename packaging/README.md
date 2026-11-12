# Construcción de Windows x64

La salida pública es una beta sin firma digital. Usar Python 3.11 x64 en Windows.

1. Crear `packaging/build-env` e instalar `packaging/requirements-build.txt`.
2. Desde la raíz de Jarvis, instalar `./OpenJarvis` con `--no-deps`. Esa carpeta
   trae el motor integrado. Construir o instalar su módulo Rust `openjarvis_rust`
   para Python 3.11 x64 desde `OpenJarvis/rust/crates/openjarvis-python`.
3. Obtener el modelo oficial `vosk-model-small-es-0.42` y extraerlo en
   `jarvis-native/assets/vosk-model-small-es-0.42`. URL:
   https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
4. Obtener NSIS 3.13 desde https://nsis.sourceforge.io/Download y extraer su
   distribución portátil en `packaging/tools/nsis-3.13`.
5. Ejecutar `packaging/build.ps1` desde PowerShell.

El script genera `dist/Jarvis/Jarvis.exe` con sus bibliotecas en `_internal` y
`release/Jarvis-Setup-0.2.1-beta-x64.exe`. No se debe distribuir solo el exe portátil:
necesita su carpeta `_internal`. El instalador ya contiene toda esa carpeta.

El compilador usa una lista de archivos públicos; no copia `jarvis-native/data/`,
claves, bases de datos ni configuración personal. Las licencias e inventario van
en `_internal/licenses`. Los modelos neuronales locales grandes, Torch, Kokoro,
Whisper y los entornos virtuales del desarrollo no forman parte del paquete.

Prueba sin red:

```powershell
$env:JARVIS_DATA_DIR = "$PWD/packaging/qa-customer/data"
./dist/Jarvis/Jarvis.exe --self-test "$PWD/packaging/exe-self-test.json"
```

La prueba crea un perfil limpio dentro de esa carpeta, utiliza un motor simulado,
ejecuta la calculadora real y comprueba la síntesis de Windows y la carga de Vosk.
No abre la cámara ni consulta una API. La prueba física de cámara es separada.

Se corrigieron dos particularidades de redistribución en `Jarvis.spec`: Qt necesita
las DLL de runtime MSVC que acompañan a su rueda; y el ICU ajeno de Poppler que pueda
existir en el PATH del constructor no debe reemplazar el ICU de Windows.

Antes de publicación comercial: probar en equipos limpios adicionales, comprobar
voces españolas, controladores de cámara y ausencia de Python/Ollama; firmar binarios
y establecer actualizaciones verificadas. La beta Android se construye por
separado desde `jarvis-android/`.
