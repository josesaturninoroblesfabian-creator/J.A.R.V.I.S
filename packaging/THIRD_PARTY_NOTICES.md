# Jarvis Personal 0.2.1 beta · avisos de distribución

Esta distribución integra OpenJarvis, modificado para el escritorio de Windows.
Se conserva su licencia Apache 2.0 en licenses/OpenJarvis/LICENSE.

Incluye Python (PSF), PySide6/Qt (LGPL v3, bibliotecas dinámicas), Vosk API y
vosk-model-small-es-0.42 (Apache 2.0), OpenCV (Apache 2.0), NumPy (BSD),
PyWin32 (PSF), OpenAI Python SDK (Apache 2.0), HTTPX (BSD), Pillow (HPND),
SoundDevice (MIT), libsndfile (LGPL), y sus dependencias redistribuibles.
Los textos de licencias de los paquetes se incluyen en licenses/paquetes.
NSIS se utiliza para producir el instalador bajo sus licencias zlib y la excepción
de enlace del compresor LZMA. El software de terceros no respalda este producto.

PySide6 y sus DLL de Qt permanecen separadas en _internal; no se modificaron.
Fuentes correspondientes: https://code.qt.io/cgit/pyside/pyside-setup.git/
y https://code.qt.io/cgit/qt/. Se puede sustituir la biblioteca dinámica por una
versión binariamente compatible. No se prohíbe la ingeniería inversa necesaria
para depurar modificaciones de dichas bibliotecas.

Esta es una beta de prueba, sin firma digital comercial. No contiene claves,
conversaciones ni preferencias del desarrollador. Cada usuario configura su
cuenta API propia. No incluye un plan de Groq ni una garantía de cuota gratuita.
