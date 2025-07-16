import os
import cv2
from time import strftime

def capturar_imagem():
    # Define nome e pasta
    timestamp = strftime("%Y%m%d-%H%M%S")
    pasta_destino = "/home/estacionamento/Fotosbd"
    os.makedirs(pasta_destino, exist_ok=True)
    nome_arquivo = f"carro_{timestamp}.jpg"
    caminho = os.path.join(pasta_destino, nome_arquivo)

    # Comando libcamera-still (sem pré-visualização, salva imagem)
    comando = f"libcamera-still -n -o {caminho}"
    resultado = os.system(comando)

    if resultado == 0 and os.path.exists(caminho):
        print(f"[OK] Imagem capturada: {caminho}")
        return caminho
    else:
        print("[ERRO] Falha ao capturar imagem com libcamera.")
        return None

def mostrar_imagem(caminho):
    imagem = cv2.imread(caminho)
    if imagem is None:
        print("[ERRO] Não foi possível carregar a imagem.")
        return
    cv2.imshow("Imagem capturada", imagem)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# === Execução ===
if __name__ == "__main__":
    caminho = capturar_imagem()
    if caminho:
        mostrar_imagem(caminho)
