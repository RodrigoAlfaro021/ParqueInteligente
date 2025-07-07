from flask import Flask, render_template, redirect, jsonify, send_file
import RPi.GPIO as GPIO
import time, os, sqlite3, cv2
from time import strftime
from glob import glob
import threading

app = Flask(__name__)

# === Configuração GPIO ===
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Pinos dos sensores das 4 vagas [(TRIG, ECHO)]
VAGAS_PINS = [(20, 21), (19, 26), (5, 6), (23, 24)]

# Sensor de entrada (TRIG, ECHO)
ENTRADA_TRIG = 12
ENTRADA_ECHO = 13

# Servo motor (PWM)
SERVO_PIN = 4
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)
pwm.ChangeDutyCycle(0)  # evita espasmos iniciais

# Controle para evitar múltiplas ativações seguidas
ultimo_acionamento = 0

# === Funções ===
def medir_distancia(trig, echo):
    GPIO.setup(trig, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)

    GPIO.output(trig, False)
    time.sleep(0.05)

    GPIO.output(trig, True)
    time.sleep(0.00001)
    GPIO.output(trig, False)

    pulse_start = None
    pulse_end = None

    timeout = time.time() + 1
    while GPIO.input(echo) == 0:
        pulse_start = time.time()
        if pulse_start > timeout:
            return -1

    timeout = time.time() + 1
    while GPIO.input(echo) == 1:
        pulse_end = time.time()
        if pulse_end > timeout:
            return -1

    if pulse_start is None or pulse_end is None:
        return -1

    duration = pulse_end - pulse_start
    distancia = duration * 17150
    return round(distancia, 2)

def verificar_vagas():
    ocupadas = []
    for trig, echo in VAGAS_PINS:
        dist = medir_distancia(trig, echo)
        ocupadas.append(dist < 15 if dist != -1 else False)
    return ocupadas

def carro_na_entrada():
    dist = medir_distancia(ENTRADA_TRIG, ENTRADA_ECHO)
    print(f"[DEBUG] Distância medida na entrada: {dist} cm")
    return dist < 15 if dist != -1 else False

def set_angle(angle):
    duty = 2 + (angle / 18)
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)  # desliga PWM para evitar espasmos

def abrir_cancela():
    print("Abrindo cancela (90°)...")
    set_angle(90)
    time.sleep(4)
    print("Fechando cancela (0°)...")
    set_angle(0)

def capturar_imagem():
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    timestamp = strftime("%Y%m%d-%H%M%S")
    pasta_destino = "/home/estacionamento/Pictures"
    os.makedirs(pasta_destino, exist_ok=True)
    nome_arquivo = f"carro_{timestamp}.jpg"
    caminho = os.path.join(pasta_destino, nome_arquivo)
    if ret:
        cv2.imwrite(caminho, frame)
    cam.release()
    return caminho, timestamp

# === Thread para monitorar entrada ===
def vigiar_sensor_entrada():
    global ultimo_acionamento
    while True:
        if carro_na_entrada() and not all(verificar_vagas()):
            agora = time.time()
            if agora - ultimo_acionamento > 6:
                print("[AUTO] Carro detetado. Abrindo cancela...")
                ultimo_acionamento = agora
                abrir_cancela()
                caminho, timestamp = capturar_imagem()
                conn = sqlite3.connect('db.sqlite3')
                c = conn.cursor()
                c.execute("INSERT INTO entradas (imagem, data) VALUES (?, ?)", (caminho, timestamp))
                conn.commit()
                conn.close()
        time.sleep(1)

threading.Thread(target=vigiar_sensor_entrada, daemon=True).start()

# === Rotas Flask ===
@app.route('/')
def index():
    estados = verificar_vagas()
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("SELECT imagem, data FROM entradas ORDER BY id DESC LIMIT 5")
    entradas = c.fetchall()
    conn.close()
    return render_template("index.html", vagas=estados, entradas=entradas)

@app.route('/entrada')
def entrada():
    return redirect("/")

@app.route('/abrir_cancela')
def abrir_manual():
    abrir_cancela()
    return redirect("/")

@app.route('/entradas')
def listar_entradas():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("SELECT imagem, data FROM entradas ORDER BY id DESC")
    entradas = c.fetchall()
    conn.close()
    return render_template("entradas.html", entradas=entradas)

@app.route('/fotos/<filename>')
def servir_foto(filename):
    caminho = os.path.join("/home/estacionamento/Pictures", filename)
    return send_file(caminho, mimetype='image/jpeg')

@app.route('/limpar_fotos')
def limpar_fotos():
    fotos = glob("/home/estacionamento/Pictures/*.jpg")
    for foto in fotos:
        os.remove(foto)
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("DELETE FROM entradas")
    conn.commit()
    conn.close()
    return redirect("/")

@app.route('/shutdown')
def shutdown():
    GPIO.cleanup()
    return "GPIO limpo. Servidor encerrado."

@app.route('/api/vagas')
def api_vagas():
    estados = verificar_vagas()
    return jsonify(estados)

# === Iniciar Servidor ===
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        GPIO.cleanup()
