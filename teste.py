
import RPi.GPIO as GPIO
import time

# === Pinos do Sensor de Entrada ===
TRIG = 12
ECHO = 13

# === Pino do Servo Motor ===
SERVO_PIN = 4

# === Inicialização ===
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.setup(SERVO_PIN, GPIO.OUT)

servo = GPIO.PWM(SERVO_PIN, 50)  # 50Hz
servo.start(0)

def set_angle(angle):
    duty = 2 + (angle / 18)
    servo.ChangeDutyCycle(duty)
    time.sleep(0.5)
    servo.ChangeDutyCycle(0)

def medir_distancia():
    GPIO.output(TRIG, False)
    time.sleep(0.05)

    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    pulse_start = time.time()
    timeout = pulse_start + 1
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()
        if time.time() > timeout:
            return -1

    pulse_end = time.time()
    timeout = pulse_end + 1
    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()
        if time.time() > timeout:
            return -1

    duracao = pulse_end - pulse_start
    distancia = duracao * 17150
    return round(distancia, 2)

try:
    print("Teste iniciado. Coloca a mão ou objeto perto do sensor (menos de 15 cm)...")
    while True:
        dist = medir_distancia()
        print(f"Distância: {dist} cm")
 
        if dist > 0 and dist < 15:
            print("➡️ Objeto detetado. Abrindo cancela...")
            set_angle(90)  # Abre
            time.sleep(3)
            print("🔒 Fechando cancela...")
            set_angle(0)   # Fecha
            time.sleep(2)

        time.sleep(1)

except KeyboardInterrupt:
    print("\nEncerrando...")
    GPIO.cleanup()
    servo.stop()
