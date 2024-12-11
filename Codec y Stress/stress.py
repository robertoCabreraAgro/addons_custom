import socket
import threading
import random
import time
import struct

# Configuración del servidor (IP y Puerto)
SERVER_IP = '34.229.87.213'  # Cambia por la IP de tu servidor
SERVER_PORT = 5055           # Cambia por el puerto que estás utilizando

# Duración de la simulación en segundos (1 minuto)
SIMULATION_DURATION = 60

# Función para generar un IMEI en formato correcto
def generate_imei():
    imei_str = '867060038729378'  # Puedes cambiarlo por el IMEI que quieras
    imei_bytes = imei_str.encode('ascii')
    imei_length = len(imei_bytes)
    # El IMEI se envía precedido por su longitud en 2 bytes
    imei_length_bytes = struct.pack('>H', imei_length)
    imei_packet = imei_length_bytes + imei_bytes
    return imei_packet

# Función para calcular el CRC16 según el algoritmo utilizado por el dispositivo
def calculate_crc16(data_bytes):
    crc = 0
    for byte in data_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF  # Asegurarse de que el CRC es de 16 bits

# Función para generar un paquete Codec8 válido
def generate_codec8_packet():
    # Zero bytes (4 bytes)
    zero_bytes = b'\x00\x00\x00\x00'

    # Build data field
    codec_id = b'\x08'  # Codec ID for Codec8
    number_of_data = b'\x01'  # Enviaremos 1 registro por envío

    # Construir el registro AVL
    # Timestamp (8 bytes)
    timestamp = int(time.time() * 1000)
    timestamp_bytes = struct.pack('>Q', timestamp)

    priority = b'\x00'  # Priority

    longitude = int(random.uniform(-180, 180) * 10000000)
    latitude = int(random.uniform(-90, 90) * 10000000)
    longitude_bytes = struct.pack('>i', longitude)
    latitude_bytes = struct.pack('>i', latitude)

    altitude = random.randint(0, 3000)
    angle = random.randint(0, 360)
    satellites = random.randint(0, 12)
    speed = random.randint(0, 140)

    altitude_bytes = struct.pack('>H', altitude)
    angle_bytes = struct.pack('>H', angle)
    satellites_bytes = struct.pack('B', satellites)
    speed_bytes = struct.pack('>H', speed)

    event_io_id = b'\x00'  # Event ID (1 byte)
    total_io = b'\x00'     # Total IO elements (1 byte)

    # Contadores de elementos IO (todos en cero)
    number_of_1byte_io = b'\x00'
    number_of_2byte_io = b'\x00'
    number_of_4byte_io = b'\x00'
    number_of_8byte_io = b'\x00'

    # Construir el registro AVL
    avl_record = (
        timestamp_bytes + priority +
        longitude_bytes + latitude_bytes + altitude_bytes +
        angle_bytes + satellites_bytes + speed_bytes +
        event_io_id + total_io +
        number_of_1byte_io + number_of_2byte_io +
        number_of_4byte_io + number_of_8byte_io
    )

    # Número de datos al final
    number_of_data_2 = number_of_data

    # Construir el campo de datos completo
    data_field = codec_id + number_of_data + avl_record + number_of_data_2

    # Data length (número de bytes en data_field)
    data_length = len(data_field)
    data_length_bytes = struct.pack('>I', data_length)  # 4 bytes

    # Calcular CRC
    crc = calculate_crc16(data_field)
    crc_bytes = struct.pack('>I', crc)  # 4 bytes (se almacena en 4 bytes)

    # Construir el paquete completo
    packet = zero_bytes + data_length_bytes + data_field + crc_bytes

    return packet

# Función para simular una conexión de cliente con datos GPS
def simulate_client(client_id):
    try:
        # Crear el socket TCP/IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_IP, SERVER_PORT))

        # Enviar el IMEI
        imei_packet = generate_imei()
        sock.sendall(imei_packet)
        print(f"Cliente {client_id}: Enviando IMEI: {imei_packet.hex()}")

        # Esperar la respuesta del servidor
        imei_response = sock.recv(1024)
        print(f"Cliente {client_id}: Respuesta del servidor al IMEI: {imei_response.hex()}")

        if imei_response == b'\x01':
            print(f"Cliente {client_id}: El servidor reconoció el IMEI correctamente.")

            start_time = time.time()
            while time.time() - start_time < SIMULATION_DURATION:
                # Enviar el paquete Codec8
                codec8_packet = generate_codec8_packet()
                sock.sendall(codec8_packet)
                print(f"Cliente {client_id}: Enviando paquete Codec8: {codec8_packet.hex()}")

                # Esperar la respuesta del servidor
                data_response = sock.recv(1024)
                print(f"Cliente {client_id}: Respuesta del servidor al paquete de datos: {data_response.hex()}")

                # Opcional: esperar un tiempo antes de enviar el siguiente paquete
                time.sleep(random.uniform(0.5, 2))  # Espera entre 0.5 y 2 segundos

        else:
            print(f"Cliente {client_id}: El servidor no reconoció el IMEI.")

        # Cerrar la conexión
        sock.close()
        print(f"Cliente {client_id}: Conexión cerrada.")

    except Exception as e:
        print(f"Cliente {client_id}: Error en la conexión: {e}")

# Crear múltiples conexiones de clientes
def stress_test_simulation(num_clients):
    threads = []

    for client_id in range(1, num_clients + 1):
        # Crear un hilo para cada cliente
        client_thread = threading.Thread(target=simulate_client, args=(client_id,))
        client_thread.start()
        threads.append(client_thread)

    # Esperar a que todos los hilos terminen
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    # Simular 60 clientes conectándose al mismo tiempo
    num_clients = 60
    stress_test_simulation(num_clients)