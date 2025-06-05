# Gemini Desktop Agent GUI

Esta aplicación permite controlar el escritorio de forma automática mediante instrucciones en lenguaje natural. Utiliza la API de Gemini para obtener una secuencia de acciones y las ejecuta con `pyautogui`.

## Requisitos

- Python 3.10 o superior
- Dependencias listadas en `requirements.txt`
- Una clave de API de Gemini configurada en el archivo `.env`:

4a7825-codex/mejorar-funcionalidad-y-precisión-de-ia
 ```env
 GEMINI_API_KEY=tu_clave
 ```

Es necesario ejecutar el programa en un entorno de escritorio donde la variable
`DISPLAY` esté disponible, ya que `pyautogui` requiere acceso a la pantalla.

```env
GEMINI_API_KEY=tu_clave
master

## Uso

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta el programa:
   ```bash
   python gemini_desktop_agent_gui.py
   ```
3. Introduce una instrucción en la ventana y confirma los pasos propuestos.

Las acciones permitidas incluyen mover y hacer clic con el ratón, escribir, esperar, abrir aplicaciones, desplazarse (scroll), pulsar teclas individuales o combinaciones de teclas.
