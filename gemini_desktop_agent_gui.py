import os, json, base64, time, threading, queue, subprocess
import tkinter as tk
import tkinter.scrolledtext as st
from tkinter import messagebox
from dotenv import load_dotenv
import pyautogui  # Eliminamos la dependencia de mss
import google.generativeai as genai
from google.genai import types     # SDK ≥ v1.0
import sys
import tempfile
from io import BytesIO
from PIL import Image  # Asegúrate de tener pillow instalado (pip install pillow)

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("No se encontró la variable de entorno GEMINI_API_KEY. Por favor, crea un archivo .env con GEMINI_API_KEY=tu_clave.")
genai.configure(api_key=api_key)

MODEL          = "gemini-2.0-flash"
ALLOWED_ACTION = {
    "move_mouse", "click_mouse", "write", "wait", "open_app",
    "scroll", "press_key", "hotkey"
}
SYSTEM_PROMPT = (
    "Devuelve SOLO JSON array con objetos {action,x,y,rel_x,rel_y,text,seconds," 
    "amount}. Acciones válidas: move_mouse,click_mouse,write,wait,open_app," 
    "scroll,press_key,hotkey."
)

# ─── UTILIDADES ─────────────────────────────────────────────────────────────
def screen_b64() -> str:
    """Captura pantalla completa y devuelve base64 usando un directorio temporal."""
    try:
        print("Iniciando captura de pantalla...")
        # Usar el directorio temporal del usuario (garantizado con permisos)
        temp_dir = os.path.join(os.environ['TEMP'] if 'TEMP' in os.environ else '.', 'gemini_temp')
        os.makedirs(temp_dir, exist_ok=True)
        print(f"Directorio temporal: {temp_dir}")
        
        # Crear un nombre de archivo único
        temp_file = os.path.join(temp_dir, f"screenshot_{time.time()}.png")
        print(f"Archivo temporal: {temp_file}")
        
        # Capturar pantalla y guardar en el archivo temporal
        screenshot = pyautogui.screenshot()
        screenshot.save(temp_file)
        print(f"Captura guardada en: {temp_file}")
        
        # Leer el archivo y codificarlo
        with open(temp_file, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode()
        
        # Eliminar el archivo temporal
        try:
            os.remove(temp_file)
            print("Archivo temporal eliminado")
        except Exception as e:
            print(f"Advertencia: No se pudo eliminar archivo temporal: {e}")
        
        print("Captura de pantalla completada con éxito.")
        return b64_data
    except Exception as e:
        print(f"Error detallado capturando pantalla: {type(e).__name__}: {e}")
        raise

def ask_gemini(texto: str, img_b64: str) -> list[dict]:
    try:
        print("Enviando petición a Gemini...")
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(
            contents=[
                SYSTEM_PROMPT,
                types.Part.from_bytes(base64.b64decode(img_b64), mime_type="image/png"),
                texto
            ],
            generation_config={"temperature": 0},
            tools=[{
                "function_declarations": [{
                    "name": "execute",
                    "parameters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "rel_x": {"type": "number"},
                                "rel_y": {"type": "number"},
                                "text": {"type": "string"},
                                "seconds": {"type": "number"},
                                "amount": {"type": "integer"}
                            },
                            "required": ["action"]
                        }
                    }
                }]
            }]
        )

        # Extraer los argumentos como JSON
        print("Respuesta recibida de Gemini.")
        args_json = response.candidates[0].content.parts[0].function_call.args
        return json.loads(args_json)
    except Exception as e:
        print(f"Error en ask_gemini: {type(e).__name__}: {e}")
        raise

# ─── EJECUCIÓN DE ACCIONES ─────────────────────────────────────────────────
def run_actions(steps: list[dict], log_fn):
    """Ejecuta la lista de acciones validando todo antes."""
    width, height = pyautogui.size()
    pyautogui.FAILSAFE = True
    for idx, s in enumerate(steps, 1):
        act = s.get("action");   log_fn(f"[{idx}/{len(steps)}] {s}")
        if act not in ALLOWED_ACTION:
            raise ValueError(f"Acción no permitida: {act}")

        match act:
            case "move_mouse":
                x = s.get("x", int(s["rel_x"] * width))
                y = s.get("y", int(s["rel_y"] * height))
                if not (0 <= x <= width and 0 <= y <= height):
                    raise ValueError("Coordenadas fuera de pantalla")
                pyautogui.moveTo(x, y)
            case "click_mouse":
                pyautogui.click()
            case "write":
                pyautogui.write(s["text"], interval=0.05)
            case "wait":
                time.sleep(s.get("seconds", 1))
            case "open_app":
                subprocess.Popen(s["text"])
            case "scroll":
                pyautogui.scroll(int(s.get("amount", 0)))
            case "press_key":
                pyautogui.press(s.get("text", ""))
            case "hotkey":
                keys = s.get("text", "").split("+")
                if all(keys):
                    pyautogui.hotkey(*keys)

# ─── GUI (Tkinter) ─────────────────────────────────────────────────────────
class DesktopAgentGUI:
    def __init__(self):
        self.root   = tk.Tk()
        self.root.title("Gemini Desktop Agent")
        self.queue  = queue.Queue()

        # Entrada de instrucción
        tk.Label(self.root, text="Instrucción:").pack(anchor="w", padx=6, pady=(6,0))
        self.entry = tk.Entry(self.root, width=60)
        self.entry.pack(fill="x", padx=6)
        self.entry.bind("<Return>", self.send)

        # Entrada de número máximo de steps
        frm_steps = tk.Frame(self.root)
        frm_steps.pack(fill="x", padx=6, pady=(0,4))
        tk.Label(frm_steps, text="Máx. steps:").pack(side="left")
        self.steps_var = tk.IntVar(value=5)
        self.steps_entry = tk.Entry(frm_steps, textvariable=self.steps_var, width=5)
        self.steps_entry.pack(side="left", padx=(2,0))

        # Botón enviar
        tk.Button(self.root, text="Enviar", command=self.send).pack(pady=4)

        # Consola de log
        self.log = st.ScrolledText(self.root, height=20, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=6, pady=(0,6))

        # Comprobación periódica de la cola
        self.root.after(100, self.process_queue)

    def log_msg(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    # ── Eventos ────────────────────────────────────────────────────────────
    def send(self, *_):
        texto = self.entry.get().strip()
        if not texto:
            return
        try:
            max_steps = int(self.steps_var.get())
        except Exception:
            messagebox.showerror("Error", "El número de steps debe ser un entero.")
            return
        self.entry.delete(0, "end")
        threading.Thread(target=self.worker, args=(texto, max_steps), daemon=True).start()

    def worker(self, texto: str, max_steps: int):
        try:
            img   = screen_b64()
            steps = ask_gemini(texto, img)
            self.queue.put(("plan", steps, texto, max_steps, img))
        except Exception as e:
            self.queue.put(("error", str(e)))

    def process_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "plan":
                    _, steps, texto, max_steps, img = item
                    self.handle_plan(steps, texto, max_steps, img)
                elif kind == "error":
                    messagebox.showerror("Error", item[1])
                    self.log_msg(f"ERROR: {item[1]}")
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def handle_plan(self, steps, texto, max_steps, img_b64):
        plan_txt = json.dumps(steps, indent=2, ensure_ascii=False)
        self.log_msg("Plan propuesto inicial:\n" + plan_txt)
        if messagebox.askyesno("Confirmar", f"¿Ejecutar este plan? (máx. {max_steps} steps)"):
            threading.Thread(target=self.run_steps_with_feedback,
                             args=(texto, max_steps, img_b64), daemon=True).start()

    def run_steps_with_feedback(self, texto, max_steps, img_b64):
        steps_done = 0
        last_text = texto
        last_img = img_b64
        while steps_done < max_steps:
            try:
                steps = ask_gemini(last_text, last_img)
                if not steps:
                    self.log_msg(f"No hay más acciones propuestas. Total steps: {steps_done}")
                    break
                plan_txt = json.dumps(steps, indent=2, ensure_ascii=False)
                self.log_msg(f"\n[Step {steps_done+1}] Plan propuesto:\n" + plan_txt)
                run_actions([steps[0]], self.log_msg)  # Ejecuta solo el primer step
                steps_done += 1
                # Nueva captura tras cada acción
                last_img = screen_b64()
                last_text = texto  # O puedes ajustar el prompt si quieres feedback incremental
            except Exception as e:
                self.log_msg(f"❌ Error en step {steps_done+1}: {e}")
                break
        self.log_msg(f"✅ Proceso terminado. Steps ejecutados: {steps_done}\n")

    def run(self):
        self.root.mainloop()

# ─── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        DesktopAgentGUI().run()
    except Exception as e:
        print(f"\nERROR: {e}")
        input("\nPresione Enter para cerrar...")
    finally:
        if sys.stdin.isatty():
            input("\nPresione Enter para cerrar...")
