from flask import Flask, render_template, redirect, jsonify, send_file
import RPi.GPIO as GPIO
import time, os, sqlite3
from time import strftime
from glob import glob
import threading

app = Flask(__name__)

# === Configuração GPIO ===
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Pinos dos sensores das 4 vagas [(TRIG, ECHO)]
VAGAS_PINS = [(12, 13),(5, 6),(23, 24),(20, 21)]

# Sensor de entrada (TRIG, ECHO)
ENTRADA_TRIG = 19
ENTRADA_ECHO = 26

# Servo motor (PWM)
SERVO_PIN = 4
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)
pwm.ChangeDutyCycle(0)

# Controlo de estado
ultimo_acionamento = 0
estado_anterior_vagas = [True, True, True, True]  # Assumir ocupadas inicialmente

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
    pwm.ChangeDutyCycle(0)

def abrir_cancela():
    print("Abrindo cancela (90°)...")
    set_angle(90)
    time.sleep(4)
    print("Fechando cancela (0°)...")
    set_angle(0)

# === Captura de imagem com libcamera ===
def capturar_imagem():
    timestamp = strftime("%Y%m%d-%H%M%S")
    pasta_destino = "/home/estacionamento/flask-project/Fotos"
    os.makedirs(pasta_destino, exist_ok=True)
    nome_arquivo = f"carro_{timestamp}.jpg"
    caminho = os.path.join(pasta_destino, nome_arquivo)

    comando = f"libcamera-still -t 100 --width 640 --height 480 -n -o {caminho}"
    resultado = os.system(comando)

    if resultado == 0 and os.path.exists(caminho):
        print(f"[OK] Imagem capturada: {caminho}")
        return nome_arquivo, timestamp
    else:
        print("[ERRO] Falha ao capturar imagem com libcamera.")
        return None, None

# === Thread: Monitorizar entrada ===
def vigiar_sensor_entrada():
    global ultimo_acionamento
    while True:
        if carro_na_entrada() and not all(verificar_vagas()):
            agora = time.time()
            nome_foto, timestamp = capturar_imagem()
            abrir_cancela()
            if agora - ultimo_acionamento > 6: 
                print("[AUTO] Carro detetado. Abrindo cancela...")
                ultimo_acionamento = agora
                if nome_foto:
                    conn = sqlite3.connect('db.sqlite3')
                    c = conn.cursor()
                    c.execute("INSERT INTO entradas (imagem, data) VALUES (?, ?)", (nome_foto, timestamp))
                    conn.commit()
                    conn.close()
        time.sleep(1)

# === Thread: Monitorizar saídas ===
def vigiar_saida_vagas():
    global estado_anterior_vagas
    while True:
        estado_atual = verificar_vagas()
        for i in range(len(estado_atual)):
            if estado_anterior_vagas[i] and not estado_atual[i]:
                print(f"[SAÍDA] Vaga {i+1} ficou livre. Abrindo cancela para saída...")
                abrir_cancela()
                break
        estado_anterior_vagas = estado_atual
        time.sleep(2)

# Iniciar threads de vigilância
threading.Thread(target=vigiar_sensor_entrada, daemon=True).start()
threading.Thread(target=vigiar_saida_vagas, daemon=True).start()

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
    global ultimo_acionamento
    agora = time.time()

    if agora - ultimo_acionamento > 6:
        print("[SIMULAÇÃO MANUAL] Entrada acionada manualmente. Abrindo cancela sem capturar imagem.")
        abrir_cancela()
        ultimo_acionamento = agora
        return "Cancela aberta manualmente."
    else:
        return "Aguarde antes de tentar novamente.", 429

    

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
    caminho = os.path.join("/home/estacionamento/flask-project/Fotos", filename)
    return send_file(caminho, mimetype='image/jpeg')


@app.route('/shutdown')
def shutdown():
    GPIO.cleanup()
    return "GPIO limpo. Servidor encerrado."

@app.route('/api/vagas')
def api_vagas():
    estados = verificar_vagas()
    return jsonify(estados)

@app.route('/api/ultima_entrada')
def api_ultima_entrada():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("SELECT imagem, data FROM entradas ORDER BY id DESC LIMIT 1")
    resultado = c.fetchone()
    conn.close()
    if resultado:
        imagem, data = resultado
        return jsonify({"imagem": imagem, "data": data})
    return jsonify({"imagem": None, "data": None})

@app.route('/fotos')
def todas_fotos():
    pasta = "/home/estacionamento/flask-project/Fotos"
    imagens = sorted(
        [f for f in os.listdir(pasta) if f.endswith(".jpg")],
        reverse=True
    )
    return render_template("fotos.html", imagens=imagens)

@app.route('/dados')
def consultar_dados():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("SELECT id, imagem, data FROM entradas ORDER BY id DESC")
    dados = c.fetchall()
    conn.close()
    return render_template("dados.html", dados=dados)

@app.route('/dados/limpar', methods=['POST'])
def limpar_dados():
    pasta = "/home/estacionamento/flask-project/Fotos"
    for f in glob(f"{pasta}/*.jpg"):
        os.remove(f)
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("DELETE FROM entradas")
    conn.commit()
    conn.close()
    return redirect("/dados")


# === Iniciar Servidor ===
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        GPIO.cleanup()
