import socket
import json
import os
import datetime
import struct
import decimal
import psycopg2
from pyproj import Transformer
import threading  # Importamos threading para manejar múltiples hilos

HOST = '0.0.0.0'  # Puede que '0.0.0.0' no funcione en algunos sistemas Linux; cambia a una cadena con la dirección IP, por ejemplo: '192.168.0.1'
PORT = 5055  # Cambia esto por el puerto que estás utilizando

def conectar_bd():
    return psycopg2.connect(
        dbname='test',
        user='odoo',
        password='odoo123',
        host='localhost',
        port='5432'
    )

def insertar_datos_gps(io_dict):
    conn = None
    cursor = None
    try:
        conn = conectar_bd()
        cursor = conn.cursor()

        # Paso 1: Mapear los campos
        imei = io_dict.get('device_IMEI', '')
        timestamp_str = io_dict.get('_timestamp_', '')
        priority = io_dict.get('priority', 0)
        longitude = io_dict.get('longitude', 0.0)
        latitude = io_dict.get('latitude', 0.0)
        altitude = io_dict.get('altitude', 0)
        angle = io_dict.get('angle', 0)
        satellites = io_dict.get('satelites', 0)
        speed = io_dict.get('speed', 0)
        event_id = io_dict.get('eventID', 0)

        # Convertir timestamp a objeto datetime
        try:
            timestamp_format = "%H:%M:%S %d-%m-%Y"
            timestamp_local_str = timestamp_str.split(' (')[0]  # Obtener la parte local
            timestamp = datetime.datetime.strptime(timestamp_local_str, timestamp_format)
        except Exception as e:
            print(f"Error al convertir timestamp: {e}")
            timestamp = datetime.datetime.now()

        # Paso 2: Calcular the_point
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        x, y = transformer.transform(longitude, latitude)  # Asegúrate del orden correcto (longitud, latitud)
        the_point = f'POINT({x} {y})'

        # Paso 3: Insertar en la base de datos incluyendo the_point
        insert_query = """
        INSERT INTO gps_tracking_data_history (
            imei, timestamp, priority, altitude, angle, satellites, speed, event_id,
            latitude, longitude, the_point
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 3857))
        """

        values = (
            imei,
            timestamp,
            priority,
            altitude,
            angle,
            satellites,
            speed,
            event_id,
            latitude,
            longitude,
            the_point
        )

        cursor.execute(insert_query, values)
        conn.commit()
        print("Datos insertados correctamente en la base de datos.")
    except Exception as e:
        print(f"Error al insertar datos en la base de datos: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def input_trigger():  # Espera la entrada del usuario
    print("Escribe 'SERVER' para iniciar el servidor o:")
    print("Escribe 'EXIT' para detener el programa")
    device_imei = "default_IMEI"
    user_input = input("Esperando entrada: ")
    if user_input.upper() == "EXIT":
        print(f"Saliendo del programa...")
        exit()

    elif user_input.upper() == "SERVER":
        start_server_trigger()
    else:
        print("Entrada no reconocida. Intenta de nuevo.")
        input_trigger()

####################################################
###############__CRC16/ARC Checker__################
####################################################

def crc16_arc(data):
    data_part_length_crc = int(data[8:16], 16)
    data_part_for_crc = bytes.fromhex(data[16:16+2*data_part_length_crc])
    crc16_arc_from_record = data[16+len(data_part_for_crc.hex()):24+len(data_part_for_crc.hex())]

    crc = 0

    for byte in data_part_for_crc:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1

    if crc16_arc_from_record.upper() == crc.to_bytes(4, byteorder='big').hex().upper():
        print("CRC check passed!")
        print(f"Record length: {len(data)} characters // {int(len(data)/2)} bytes")
        return True
    else:
        print("CRC check Failed!")
        return False

####################################################

def codec_8e_checker(codec8_packet):
    if str(codec8_packet[16:16+2]).upper() != "8E" and str(codec8_packet[16:16+2]).upper() != "08":
        print()
        print(f"Invalid packet!")
        return False
    else:
        return crc16_arc(codec8_packet)

def codec_parser_trigger(codec8_packet, device_imei, props):
    try:
        return codec_8e_parser(codec8_packet.replace(" ", ""), device_imei, props)
    except Exception as e:
        print(f"Error ocurrido: {e} ingresa un paquete Codec8 válido o escribe 'EXIT'!")
        input_trigger()

def imei_checker(hex_imei):  # Función para verificar el IMEI
    imei_length = int(hex_imei[:4], 16)
    if imei_length != len(hex_imei[4:]) / 2:
        return False
    else:
        pass

    ascii_imei = ascii_imei_converter(hex_imei)
    print(f"IMEI recibido = {ascii_imei}")
    if not ascii_imei.isnumeric() or len(ascii_imei) != 15:
        print(f"No es un IMEI válido: no es numérico o tiene longitud incorrecta!")
        return False
    else:
        return True

def ascii_imei_converter(hex_imei):
    return bytes.fromhex(hex_imei[4:]).decode()

def start_server_trigger():
    print("Iniciando servidor!")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"// {time_stamper()} // escuchando en el puerto: {PORT} // IP: {HOST}")
        while True:
            conn, addr = s.accept()
            conn.settimeout(20)  # Tiempo de espera de la conexión
            # Iniciar un nuevo hilo para manejar la conexión
            threading.Thread(target=handle_client_connection, args=(conn, addr)).start()

def handle_client_connection(conn, addr):
    with conn:
        print(f"// {time_stamper()} // Conectado por {addr}")
        device_imei = "default_IMEI"
        while True:
            try:
                data = conn.recv(1280)
                if not data:
                    break
                print(f"// {time_stamper()} // datos recibidos = {data.hex()}")
                if imei_checker(data.hex()) != False:
                    device_imei = ascii_imei_converter(data.hex())
                    imei_reply = (1).to_bytes(1, byteorder="big")
                    conn.sendall(imei_reply)
                    print(f"-- {time_stamper()} enviando respuesta = {imei_reply}")
                elif codec_8e_checker(data.hex().replace(" ", "")) != False:
                    record_number = codec_parser_trigger(data.hex(), device_imei, "SERVER")
                    print(f"Registros recibidos {record_number}")
                    print(f"del dispositivo IMEI = {device_imei}")
                    print()
                    record_response = (record_number).to_bytes(4, byteorder="big")
                    conn.sendall(record_response)
                    print(f"// {time_stamper()} // respuesta enviada = {record_response.hex()}")
                else:
                    print(f"// {time_stamper()} // Datos no esperados recibidos - cerrando conexión")
                    break
            except socket.timeout:
                print(f"// {time_stamper()} // Tiempo de espera agotado. Cerrando conexión con {addr}")
                break

####################################################
###############_Codec8E_parser_code_################
####################################################

def codec_8e_parser(codec_8E_packet, device_imei, props):
    print()

    io_dict_raw = {}
    io_dict_raw["device_IMEI"] = device_imei
    io_dict_raw["server_time"] = time_stamper_for_json()
    io_dict_raw["data_length"] = "Record length: " + str(int(len(codec_8E_packet))) + " characters" + " // " + str(int(len(codec_8E_packet) // 2)) + " bytes"
    io_dict_raw["_raw_data__"] = codec_8E_packet

    try:  # Escribir datos RAW en JSON
        json_printer_rawDATA(io_dict_raw, device_imei)
    except Exception as e:
        print(f"Error al escribir datos RAW en JSON: {e}")

    zero_bytes = codec_8E_packet[:8]
    print()
    print(f"zero bytes = {zero_bytes}")

    data_field_length = int(codec_8E_packet[8:8+8], 16)
    print(f"data field length = {data_field_length} bytes")
    codec_type = str(codec_8E_packet[16:16+2])
    print(f"codec type = {codec_type}")

    data_step = 4
    if codec_type == "08":
        data_step = 2
    else:
        pass

    number_of_records = int(codec_8E_packet[18:18+2], 16)
    print(f"number of records = {number_of_records}")

    avl_data_start = codec_8E_packet[20:]
    data_field_position = 0

    for record_number in range(1, number_of_records + 1):
        io_dict = {}
        io_dict["device_IMEI"] = device_imei
        io_dict["server_time"] = time_stamper_for_json()
        print()
        print(f"data from record {record_number}")
        print(f"########################################")

        timestamp = avl_data_start[data_field_position:data_field_position+16]
        io_dict["_timestamp_"] = device_time_stamper(timestamp)
        print(f"timestamp = {io_dict['_timestamp_']}")
        io_dict["_rec_delay_"] = record_delay_counter(timestamp)
        data_field_position += 16  # Timestamp es de 8 bytes (16 dígitos hex)

        priority = avl_data_start[data_field_position:data_field_position+2]
        io_dict["priority"] = int(priority, 16)
        print(f"record priority = {io_dict['priority']}")
        data_field_position += 2  # Priority es de 1 byte (2 dígitos hex)

        longitude = avl_data_start[data_field_position:data_field_position+8]
        io_dict["longitude"] = coordinate_formater(longitude)
        print(f"longitude = {io_dict['longitude']}")
        data_field_position += 8

        latitude = avl_data_start[data_field_position:data_field_position+8]
        io_dict["latitude"] = coordinate_formater(latitude)
        print(f"latitude = {io_dict['latitude']}")
        data_field_position += 8

        altitude = avl_data_start[data_field_position:data_field_position+4]
        io_dict["altitude"] = int(altitude, 16)
        print(f"altitude = {io_dict['altitude']}")
        data_field_position += 4

        angle = avl_data_start[data_field_position:data_field_position+4]
        io_dict["angle"] = int(angle, 16)
        print(f"angle = {io_dict['angle']}")
        data_field_position += 4

        satelites = avl_data_start[data_field_position:data_field_position+2]
        io_dict["satelites"] = int(satelites, 16)
        print(f"satelites = {io_dict['satelites']}")
        data_field_position += 2

        speed = avl_data_start[data_field_position:data_field_position+4]
        io_dict["speed"] = int(speed, 16)
        print(f"speed = {io_dict['speed']}")
        data_field_position += 4

        event_io_id = avl_data_start[data_field_position:data_field_position+data_step]
        io_dict["eventID"] = int(event_io_id, 16)
        print(f"event ID = {io_dict['eventID']}")
        data_field_position += len(event_io_id)

        total_io_elements = avl_data_start[data_field_position:data_field_position+data_step]
        total_io_elements_parsed = int(total_io_elements, 16)
        print(f"total I/O elements in record {record_number} = {total_io_elements_parsed}")
        data_field_position += len(total_io_elements)

        # Procesar IO de 1 byte
        byte1_io_number = avl_data_start[data_field_position:data_field_position+data_step]
        byte1_io_number_parsed = int(byte1_io_number, 16)
        print(f"1 byte io count = {byte1_io_number_parsed}")
        data_field_position += len(byte1_io_number)

        if byte1_io_number_parsed > 0:
            i = 1
            while i <= byte1_io_number_parsed:
                key = avl_data_start[data_field_position:data_field_position+data_step]
                data_field_position += len(key)
                value = avl_data_start[data_field_position:data_field_position+2]

                io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                data_field_position += len(value)
                print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                i += 1
        else:
            pass

        # Procesar IO de 2 bytes
        byte2_io_number = avl_data_start[data_field_position:data_field_position+data_step]
        byte2_io_number_parsed = int(byte2_io_number, 16)
        print(f"2 byte io count = {byte2_io_number_parsed}")
        data_field_position += len(byte2_io_number)

        if byte2_io_number_parsed > 0:
            i = 1
            while i <= byte2_io_number_parsed:
                key = avl_data_start[data_field_position:data_field_position+data_step]
                data_field_position += len(key)

                value = avl_data_start[data_field_position:data_field_position+4]
                io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                data_field_position += len(value)
                print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                i += 1
        else:
            pass

        # Procesar IO de 4 bytes
        byte4_io_number = avl_data_start[data_field_position:data_field_position+data_step]
        byte4_io_number_parsed = int(byte4_io_number, 16)
        print(f"4 byte io count = {byte4_io_number_parsed}")
        data_field_position += len(byte4_io_number)

        if byte4_io_number_parsed > 0:
            i = 1
            while i <= byte4_io_number_parsed:
                key = avl_data_start[data_field_position:data_field_position+data_step]
                data_field_position += len(key)

                value = avl_data_start[data_field_position:data_field_position+8]
                io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                data_field_position += len(value)
                print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                i += 1
        else:
            pass

        # Procesar IO de 8 bytes
        byte8_io_number = avl_data_start[data_field_position:data_field_position+data_step]
        byte8_io_number_parsed = int(byte8_io_number, 16)
        print(f"8 byte io count = {byte8_io_number_parsed}")
        data_field_position += len(byte8_io_number)

        if byte8_io_number_parsed > 0:
            i = 1
            while i <= byte8_io_number_parsed:
                key = avl_data_start[data_field_position:data_field_position+data_step]
                data_field_position += len(key)

                value = avl_data_start[data_field_position:data_field_position+16]
                io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                data_field_position += len(value)
                print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                i += 1
        else:
            pass

        # Si es Codec8E, procesar IO de tamaño variable
        if codec_type.upper() == "8E":
            byteX_io_number = avl_data_start[data_field_position:data_field_position+4]
            byteX_io_number_parsed = int(byteX_io_number, 16)
            print(f"X byte io count = {byteX_io_number_parsed}")
            data_field_position += len(byteX_io_number)

            if byteX_io_number_parsed > 0:
                i = 1
                while i <= byteX_io_number_parsed:
                    key = avl_data_start[data_field_position:data_field_position+4]
                    data_field_position += len(key)

                    value_length = avl_data_start[data_field_position:data_field_position+4]
                    data_field_position += 4
                    value = avl_data_start[data_field_position:data_field_position+(2*(int(value_length, 16)))]
                    io_dict[int(key, 16)] = sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                    i += 1
            else:
                pass
        else:
            pass

        try:  # Escribir el diccionario en JSON y guardar en la base de datos
            json_printer(io_dict, device_imei)
            insertar_datos_gps(io_dict)
        except Exception as e:
            print(f"Error al escribir en JSON o insertar en la base de datos: {e}")

    if props == "SERVER":
        total_records_parsed = int(avl_data_start[data_field_position:data_field_position+2], 16)
        print()
        print(f"total parsed records = {total_records_parsed}")
        print()
        return int(number_of_records)

    else:
        total_records_parsed = int(avl_data_start[data_field_position:data_field_position+2], 16)
        print()
        print(f"total parsed records = {total_records_parsed}")
        print()
        input_trigger()

####################################################
###############_End_of_MAIN_Parser_Code#############
####################################################

####################################################
###############_Coordinates_Function_###############
####################################################

def coordinate_formater(hex_coordinate):
    coordinate = int(hex_coordinate, 16)
    if coordinate & (1 << 31):
        new_int = coordinate - 2**32
        dec_coordinate = new_int / 1e7
    else:
        dec_coordinate = coordinate / 1e7
    return dec_coordinate

####################################################
###############____JSON_Functions____###############
####################################################

def json_printer(io_dict, device_imei):
    json_data = json.dumps(io_dict, indent=4)
    data_path = "./data/" + str(device_imei)
    json_file = str(device_imei) + "_data.json"

    if not os.path.exists(data_path):
        os.makedirs(data_path)
    else:
        pass

    if not os.path.exists(os.path.join(data_path, json_file)):
        with open(os.path.join(data_path, json_file), "w") as file:
            file.write(json_data)
    else:
        with open(os.path.join(data_path, json_file), "a") as file:
            file.write(json_data)
    return

def json_printer_rawDATA(io_dict_raw, device_imei):
    json_data = json.dumps(io_dict_raw, indent=4)
    data_path = "./data/" + str(device_imei)
    json_file = str(device_imei) + "_RAWdata.json"

    if not os.path.exists(data_path):
        os.makedirs(data_path)
    else:
        pass

    if not os.path.exists(os.path.join(data_path, json_file)):
        with open(os.path.join(data_path, json_file), "w") as file:
            file.write(json_data)
    else:
        with open(os.path.join(data_path, json_file), "a") as file:
            file.write(json_data)
    return

####################################################
###############____TIME_FUNCTIONS____###############
####################################################

def time_stamper():
    current_server_time = datetime.datetime.now()
    server_time_stamp = current_server_time.strftime('%H:%M:%S %d-%m-%Y')
    return server_time_stamp

def time_stamper_for_json():
    current_server_time = datetime.datetime.now()
    timestamp_utc = datetime.datetime.utcnow()
    server_time_stamp = f"{current_server_time.strftime('%H:%M:%S %d-%m-%Y')} (local) / {timestamp_utc.strftime('%H:%M:%S %d-%m-%Y')} (utc)"
    return server_time_stamp

def device_time_stamper(timestamp):
    timestamp_ms = int(timestamp, 16) / 1000
    timestamp_utc = datetime.datetime.utcfromtimestamp(timestamp_ms)
    utc_offset = datetime.datetime.fromtimestamp(timestamp_ms) - datetime.datetime.utcfromtimestamp(timestamp_ms)
    timestamp_local = timestamp_utc + utc_offset
    formatted_timestamp_local = timestamp_local.strftime("%H:%M:%S %d-%m-%Y")
    formatted_timestamp_utc = timestamp_utc.strftime("%H:%M:%S %d-%m-%Y")
    formatted_timestamp = f"{formatted_timestamp_local} (local) / {formatted_timestamp_utc} (utc)"

    return formatted_timestamp

def record_delay_counter(timestamp):
    timestamp_ms = int(timestamp, 16) / 1000
    current_server_time = datetime.datetime.now().timestamp()
    return f"{int(current_server_time - timestamp_ms)} seconds"

####################################################
###############_PARSE_FUNCTIONS_CODE_###############
####################################################

def parse_data_integer(data):
    return int(data, 16)

def int_multiply_01(data):
    return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.1'))

def int_multiply_001(data):
    return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.01'))

def int_multiply_0001(data):
    return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.001'))

def signed_no_multiply(data):
    try:
        binary = bytes.fromhex(data.zfill(8))
        value = struct.unpack(">i", binary)[0]
        return value
    except Exception as e:
        print(f"Valor inesperado en la función '{data}', error: '{e}'. Dejaré el valor sin parsear!")
        return f"0x{data}"

parse_functions_dictionary = {
    240: parse_data_integer,
    239: parse_data_integer,
    80: parse_data_integer,
    21: parse_data_integer,
    200: parse_data_integer,
    69: parse_data_integer,
    181: int_multiply_01,
    182: int_multiply_01,
    66: int_multiply_0001,
    24: parse_data_integer,
    205: parse_data_integer,
    206: parse_data_integer,
    67: int_multiply_0001,
    68: int_multiply_0001,
    241: parse_data_integer,
    299: parse_data_integer,
    16: parse_data_integer,
    1: parse_data_integer,
    9: parse_data_integer,
    179: parse_data_integer,
    12: int_multiply_0001,
    13: int_multiply_001,
    17: signed_no_multiply,
    18: signed_no_multiply,
    19: signed_no_multiply,
    11: parse_data_integer,
    10: parse_data_integer,
    2: parse_data_integer,
    3: parse_data_integer,
    6: int_multiply_0001,
    180: parse_data_integer
}

def sorting_hat(key, value):
    if key in parse_functions_dictionary:
        parse_function = parse_functions_dictionary[key]
        return parse_function(value)
    else:
        return f"0x{value}"

####################################################

def fileAccessTest():
    try:
        testDict = {}
        testDict["_Writing_Test_"] = "Writing_Test"
        testDict["Script_Started"] = time_stamper_for_json()

        json_printer(testDict, "file_Write_Test")

        print(f"---### Prueba de acceso a archivos superada! ###---")
        input_trigger()

    except Exception as e:
        print()
        print(f"---### Error de acceso a archivos ###---")
        print(f"'{e}'")
        print(f"---### Intenta ejecutar el terminal con derechos de administrador! ###---")
        print(f"---### Nada será guardado si decides continuar! ###---")
        print()
        input_trigger()

def main():
    # Puedes llamar directamente a start_server_trigger() si ya no necesitas la prueba de acceso a archivos
    # fileAccessTest()
    start_server_trigger()

if __name__ == "__main__":
    main()