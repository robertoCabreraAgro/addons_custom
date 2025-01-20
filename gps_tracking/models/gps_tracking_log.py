# import datetime
import decimal
import logging
import struct
# from datetime import datetime
from datetime import datetime, timezone
import requests
from pyproj import Transformer

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


HOST = '0.0.0.0'  # Puede que '0.0.0.0' no funcione en algunos sistemas Linux; cambia a una cadena con la dirección IP, por ejemplo: '192.168.0.1'
PORT = 5055  # Cambia esto por el puerto que estás utilizando


class GpsTrackingLog(models.Model):
    _name = 'gps.tracking.log'
    _description = 'GPS Tracking Log'


    # imei = fields.Char(string='IMEI', required=True)
    device_id = fields.Many2one(
        'gps.tracking.device',
        string='Device',
        required=True,
        ondelete='cascade'
    )
    timestamp = fields.Datetime(string='Timestamp', required=True)
    priority = fields.Integer(string='Priority')
    altitude = fields.Float(string='Altitude')
    angle = fields.Float(string='Angle')
    satellites = fields.Integer(string='Satellites')
    speed = fields.Float(string='Speed')
    event_id = fields.Integer(string='Event ID')
    latitude = fields.Float(string='Latitude', digits=(16, 7))
    longitude = fields.Float(string='Longitude', digits=(16, 7))
    the_point = fields.GeoPoint(string='Position', srid=3857, compute='_compute_the_point', store=True)
    address = fields.Char(string='Address', compute='_compute_address', store=True)
    raw_data = fields.Text("Raw Data")
    # history_route = fields.GeoLine(string="History Route", compute='_compute_history_route', store=True)


    @api.depends('latitude', 'longitude')
    def _compute_the_point(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for rec in self:
            if rec.latitude and rec.longitude:
                _logger.info(f"Transformando latitud {rec.latitude} y longitud {rec.longitude} de SRID 4326 a SRID 3857.")
                x, y = transformer.transform(rec.longitude, rec.latitude)
                rec.the_point = f'POINT({x} {y})'
                _logger.info(f"Coordenadas transformadas: {x}, {y} (SRID 3857).")
            else:
                _logger.warning(f"Faltan latitud o longitud en el registro {rec.id}, no se puede convertir a SRID 3857.")
                rec.the_point = False


    @api.depends('latitude', 'longitude')
    def _compute_address(self):
        api_key = ''  # Sustituye por tu clave de API
        for rec in self:
            _logger.info(f"Ejecutando _compute_address para ID {rec.id} con latitude={rec.latitude}, longitude={rec.longitude}")
            if rec.latitude and rec.longitude:
                url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={rec.latitude},{rec.longitude}&key={api_key}"
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if data['results']:
                            rec.address = data['results'][0]['formatted_address']
                            _logger.info(f"Dirección obtenida para ID {rec.id}: {rec.address}")
                        else:
                            rec.address = "Address not found"
                            _logger.warning(f"Sin resultados para las coordenadas ID {rec.id}: {url}")
                    else:
                        _logger.error(f"Error al consultar la API de Google Maps para ID {rec.id}: {response.status_code}")
                        rec.address = "Error fetching address"
                except Exception as e:
                    _logger.exception(f"Excepción al consultar la API de Google Maps para ID {rec.id}: {e}")
                    rec.address = "Error fetching address"
            else:
                rec.address = "Coordinates not set"
                _logger.warning(f"Coordenadas no establecidas para ID {rec.id}")

    def input_trigger(self, payload="", imei=""):
        device_imei = "default_IMEI" if not imei else imei
        # imei_checker = self.env["gps.tracking.log"].sudo().imei_checker(hex_imei=payload)
        # if imei_checker:
        #     device_imei = self.env["gps.tracking.log"].sudo().ascii_imei_converter(payload)

        try:
            if self.codec_8e_checker(payload.replace(" ", "")) == False:
                _logger.warning("Paquete Codec8 inválido")
                self.input_trigger(payload)
            else:
                self.codec_parser_trigger(payload, device_imei, "USER")
        except Exception as e:
            _logger.error(f"Error occurred: {e} enter proper Codec8 packet or EXIT!!!")
            self.input_trigger(payload)

    def crc16_arc(self, data):
        data_part_length_crc = int(data[8:16], 16)
        data_part_for_crc = bytes.fromhex(data[16:16 + 2 * data_part_length_crc])
        crc16_arc_from_record = data[16 + len(data_part_for_crc.hex()):24 + len(data_part_for_crc.hex())]

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
            print(f"Record length: {len(data)} characters // {int(len(data) / 2)} bytes")
            return True
        else:
            print("CRC check Failed!")
            return False

    def codec_8e_checker(self, codec8_packet):
        if str(codec8_packet[16:16 + 2]).upper() != "8E" and str(codec8_packet[16:16 + 2]).upper() != "08":
            print()
            print(f"Invalid packet!")
            return False
        else:
            return self.crc16_arc(codec8_packet)

    def codec_parser_trigger(self, codec8_packet, device_imei, props):
        try:
            return self.codec_8e_parser(codec8_packet.replace(" ", ""), device_imei, props)
        except Exception as e:
            print(f"Error ocurrido: {e} ingresa un paquete Codec8 válido o escribe 'EXIT'!")
            # self.input_trigger()

    def imei_checker(self, hex_imei):  # Función para verificar el IMEI
        imei_length = int(hex_imei[:4], 16)
        if imei_length != len(hex_imei[4:]) / 2:
            return False
        else:
            pass

        ascii_imei = self.ascii_imei_converter(hex_imei)
        _logger.info(f"IMEI recibido = {ascii_imei}")
        if not ascii_imei.isnumeric() or len(ascii_imei) != 15:
            _logger.warning(f"No es un IMEI válido: no es numérico o tiene longitud incorrecta!")
            return False
        else:
            return True

    def ascii_imei_converter(self, hex_imei):
        return bytes.fromhex(hex_imei[4:]).decode()

    def codec_8e_parser(self, codec_8E_packet, device_imei, props):
        zero_bytes = codec_8E_packet[:8]
        print()
        print(f"zero bytes = {zero_bytes}")

        data_field_length = int(codec_8E_packet[8:8 + 8], 16)
        print(f"data field length = {data_field_length} bytes")
        codec_type = str(codec_8E_packet[16:16 + 2])
        print(f"codec type = {codec_type}")

        data_step = 4
        if codec_type == "08":
            data_step = 2
        else:
            pass

        number_of_records = int(codec_8E_packet[18:18 + 2], 16)
        print(f"number of records = {number_of_records}")

        avl_data_start = codec_8E_packet[20:]
        data_field_position = 0

        for record_number in range(1, number_of_records + 1):
            io_dict = {}
            io_dict["device_IMEI"] = device_imei
            print()
            print(f"data from record {record_number}")
            print(f"########################################")

            timestamp = avl_data_start[data_field_position:data_field_position + 16]
            io_dict["timestamp"] = self.device_time_stamper(timestamp)
            print(f"timestamp = {io_dict['timestamp']}")
            io_dict["_rec_delay_"] = self.record_delay_counter(timestamp)
            data_field_position += 16  # Timestamp es de 8 bytes (16 dígitos hex)

            priority = avl_data_start[data_field_position:data_field_position + 2]
            io_dict["priority"] = int(priority, 16)
            print(f"record priority = {io_dict['priority']}")
            data_field_position += 2  # Priority es de 1 byte (2 dígitos hex)

            longitude = avl_data_start[data_field_position:data_field_position + 8]
            io_dict["longitude"] = self.coordinate_formater(longitude)
            print(f"longitude = {io_dict['longitude']}")
            data_field_position += 8

            latitude = avl_data_start[data_field_position:data_field_position + 8]
            io_dict["latitude"] = self.coordinate_formater(latitude)
            print(f"latitude = {io_dict['latitude']}")
            data_field_position += 8

            altitude = avl_data_start[data_field_position:data_field_position + 4]
            io_dict["altitude"] = int(altitude, 16)
            print(f"altitude = {io_dict['altitude']}")
            data_field_position += 4

            angle = avl_data_start[data_field_position:data_field_position + 4]
            io_dict["angle"] = int(angle, 16)
            print(f"angle = {io_dict['angle']}")
            data_field_position += 4

            satellites = avl_data_start[data_field_position:data_field_position + 2]
            io_dict["satellites"] = int(satellites, 16)
            print(f"satellites = {io_dict['satellites']}")
            data_field_position += 2

            speed = avl_data_start[data_field_position:data_field_position + 4]
            io_dict["speed"] = int(speed, 16)
            print(f"speed = {io_dict['speed']}")
            data_field_position += 4

            event_io_id = avl_data_start[data_field_position:data_field_position + data_step]
            io_dict["eventID"] = int(event_io_id, 16)
            print(f"event ID = {io_dict['eventID']}")
            data_field_position += len(event_io_id)

            total_io_elements = avl_data_start[data_field_position:data_field_position + data_step]
            total_io_elements_parsed = int(total_io_elements, 16)
            print(f"total I/O elements in record {record_number} = {total_io_elements_parsed}")
            data_field_position += len(total_io_elements)

            # Procesar IO de 1 byte
            byte1_io_number = avl_data_start[data_field_position:data_field_position + data_step]
            byte1_io_number_parsed = int(byte1_io_number, 16)
            print(f"1 byte io count = {byte1_io_number_parsed}")
            data_field_position += len(byte1_io_number)

            if byte1_io_number_parsed > 0:
                i = 1
                while i <= byte1_io_number_parsed:
                    key = avl_data_start[data_field_position:data_field_position + data_step]
                    data_field_position += len(key)
                    value = avl_data_start[data_field_position:data_field_position + 2]

                    io_dict[int(key, 16)] = self.sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                    i += 1
            else:
                pass

                # Procesar IO de 2 bytes
            byte2_io_number = avl_data_start[data_field_position:data_field_position + data_step]
            byte2_io_number_parsed = int(byte2_io_number, 16)
            print(f"2 byte io count = {byte2_io_number_parsed}")
            data_field_position += len(byte2_io_number)

            if byte2_io_number_parsed > 0:
                i = 1
                while i <= byte2_io_number_parsed:
                    key = avl_data_start[data_field_position:data_field_position + data_step]
                    data_field_position += len(key)

                    value = avl_data_start[data_field_position:data_field_position + 4]
                    io_dict[int(key, 16)] = self.sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                    i += 1
            else:
                pass

            # Procesar IO de 4 bytes
            byte4_io_number = avl_data_start[data_field_position:data_field_position + data_step]
            byte4_io_number_parsed = int(byte4_io_number, 16)
            print(f"4 byte io count = {byte4_io_number_parsed}")
            data_field_position += len(byte4_io_number)

            if byte4_io_number_parsed > 0:
                i = 1
                while i <= byte4_io_number_parsed:
                    key = avl_data_start[data_field_position:data_field_position + data_step]
                    data_field_position += len(key)

                    value = avl_data_start[data_field_position:data_field_position + 8]
                    io_dict[int(key, 16)] = self.sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                    i += 1
            else:
                pass

            # Procesar IO de 8 bytes
            byte8_io_number = avl_data_start[data_field_position:data_field_position + data_step]
            byte8_io_number_parsed = int(byte8_io_number, 16)
            print(f"8 byte io count = {byte8_io_number_parsed}")
            data_field_position += len(byte8_io_number)

            if byte8_io_number_parsed > 0:
                i = 1
                while i <= byte8_io_number_parsed:
                    key = avl_data_start[data_field_position:data_field_position + data_step]
                    data_field_position += len(key)

                    value = avl_data_start[data_field_position:data_field_position + 16]
                    io_dict[int(key, 16)] = self.sorting_hat(int(key, 16), value)
                    data_field_position += len(value)
                    print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                    i += 1
            else:
                pass

            # Si es Codec8E, procesar IO de tamaño variable
            if codec_type.upper() == "8E":
                byteX_io_number = avl_data_start[data_field_position:data_field_position + 4]
                byteX_io_number_parsed = int(byteX_io_number, 16)
                print(f"X byte io count = {byteX_io_number_parsed}")
                data_field_position += len(byteX_io_number)

                if byteX_io_number_parsed > 0:
                    i = 1
                    while i <= byteX_io_number_parsed:
                        key = avl_data_start[data_field_position:data_field_position + 4]
                        data_field_position += len(key)

                        value_length = avl_data_start[data_field_position:data_field_position + 4]
                        data_field_position += 4
                        value = avl_data_start[data_field_position:data_field_position + (2 * (int(value_length, 16)))]
                        io_dict[int(key, 16)] = self.sorting_hat(int(key, 16), value)
                        data_field_position += len(value)
                        print(f"avl_ID: {int(key, 16)} : {io_dict[int(key, 16)]}")
                        i += 1
                else:
                    pass
            else:
                pass
            record_data = {
                "timestamp": io_dict["timestamp"],
                "priority": io_dict["priority"],
                "longitude": io_dict["longitude"],
                "latitude": io_dict["latitude"],
                "altitude": io_dict["altitude"],
                "angle": io_dict["angle"],
                "satellites": io_dict["satellites"],
                "speed": io_dict["speed"],
                "event_id": io_dict["eventID"],
                "raw_data": io_dict,
            }
            device = self.env['gps.tracking.device'].search([('imei', '=', device_imei)], limit=1)
            if not device:
                device = self.env['gps.tracking.device'].create({'imei': device_imei})
            record_data['device_id'] = device.id
            self.create(record_data)

    def coordinate_formater(self, hex_coordinate):
        coordinate = int(hex_coordinate, 16)
        if coordinate & (1 << 31):
            new_int = coordinate - 2 ** 32
            dec_coordinate = new_int / 1e7
        else:
            dec_coordinate = coordinate / 1e7
        return dec_coordinate

    def time_stamper(self):
        current_server_time = datetime.now()
        server_time_stamp = current_server_time.strftime('%H:%M:%S %d-%m-%Y')
        return server_time_stamp

    def device_time_stamper(self, timestamp):
        timestamp_ms = int(timestamp, 16) / 1000
        timestamp_utc = datetime.fromtimestamp(timestamp_ms, timezone.utc).replace(tzinfo=None)

        # timestamp_utc = datetime.datetime.utcfromtimestamp(timestamp_ms)
        # utc_offset = datetime.datetime.fromtimestamp(timestamp_ms) - datetime.datetime.utcfromtimestamp(timestamp_ms)
        # timestamp_local = timestamp_utc + utc_offset

        return timestamp_utc

    def record_delay_counter(self, timestamp):
        timestamp_ms = int(timestamp, 16) / 1000
        current_server_time = datetime.now().timestamp()
        return f"{int(current_server_time - timestamp_ms)} seconds"

    def parse_data_integer(self, data):
        return int(data, 16)

    def int_multiply_01(self, data):
        return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.1'))

    def int_multiply_001(self, data):
        return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.01'))

    def int_multiply_0001(self, data):
        return float(decimal.Decimal(int(data, 16)) * decimal.Decimal('0.001'))

    def signed_no_multiply(self, data):
        try:
            binary = bytes.fromhex(data.zfill(8))
            value = struct.unpack(">i", binary)[0]
            return value
        except Exception as e:
            print(f"Valor inesperado en la función '{data}', error: '{e}'. Dejaré el valor sin parsear!")
            return f"0x{data}"


    def sorting_hat(self, key, value):
        parse_functions_dictionary = {
            240: self.parse_data_integer,
            239: self.parse_data_integer,
            80: self.parse_data_integer,
            21: self.parse_data_integer,
            200: self.parse_data_integer,
            69: self.parse_data_integer,
            181: self.int_multiply_01,
            182: self.int_multiply_01,
            66: self.int_multiply_0001,
            24: self.parse_data_integer,
            205: self.parse_data_integer,
            206: self.parse_data_integer,
            67: self.int_multiply_0001,
            68: self.int_multiply_0001,
            241: self.parse_data_integer,
            299: self.parse_data_integer,
            16: self.parse_data_integer,
            1: self.parse_data_integer,
            9: self.parse_data_integer,
            179: self.parse_data_integer,
            12: self.int_multiply_0001,
            13: self.int_multiply_001,
            17: self.signed_no_multiply,
            18: self.signed_no_multiply,
            19: self.signed_no_multiply,
            11: self.parse_data_integer,
            10: self.parse_data_integer,
            2: self.parse_data_integer,
            3: self.parse_data_integer,
            6: self.int_multiply_0001,
            180: self.parse_data_integer
        }

        if key in parse_functions_dictionary:
            parse_function = parse_functions_dictionary[key]
            return parse_function(value)
        else:
            return f"0x{value}"
