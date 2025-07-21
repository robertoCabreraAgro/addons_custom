import base64
import ssl
import subprocess
import tempfile

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from pytz import timezone

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

DEFAULT_TZ = timezone("America/Mexico_City")


def convert_key_cer_to_pem(key, password):
    # TODO compute it from a python way
    with tempfile.NamedTemporaryFile(
        "wb", suffix=".key", prefix="edi.mx.tmp."
    ) as key_file, tempfile.NamedTemporaryFile(
        "wb", suffix=".txt", prefix="edi.mx.tmp."
    ) as pwd_file, tempfile.NamedTemporaryFile(
        "rb", suffix=".key", prefix="edi.mx.tmp."
    ) as keypem_file:
        key_file.write(key)
        key_file.flush()
        pwd_file.write(password)
        pwd_file.flush()
        subprocess.call(
            (
                "openssl pkcs8 -in %s -inform der -outform pem -out %s -passin file:%s"
                % (key_file.name, keypem_file.name, pwd_file.name)
            ).split()
        )
        key_pem = keypem_file.read()
    return key_pem


def str_to_datetime(dt_str, timez=DEFAULT_TZ):
    return timez.localize(fields.Datetime.from_string(dt_str))


class Esignature(models.Model):
    _name = "l10n_mx_edi.esignature"
    _description = "MX E-signature"

    content = fields.Binary(
        string="Esignature",
        required=True,
        attachment=False,
        help="Esignature in der format",
    )
    key = fields.Binary(
        string="Esignature Key",
        required=True,
        attachment=False,
        help="Esignature Key in der format",
    )
    password = fields.Char(
        string="Esignature Password",
        required=True,
        help="Password for the Esignature Key",
    )
    holder = fields.Char(
        required=False,
        help="Holder for the certificate",
    )
    holder_vat = fields.Char(
        string='Holder"s VAT',
        required=False,
        help='Holder"s Vat for the certificate',
    )
    serial_number = fields.Char(
        string="Serial number",
        readonly=True,
        index=True,
        help="The serial number to add to electronic documents",
    )
    date_start = fields.Datetime(
        string="Available date",
        readonly=True,
        help="The date on which the certificate starts to be valid",
    )
    date_end = fields.Datetime(
        string="Expiration date",
        readonly=True,
        help="The date on which the certificate expires",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @tools.ormcache("content")
    def get_pem_cer(self, content):
        self.ensure_one()
        return ssl.DER_cert_to_PEM_cert(base64.decodebytes(content)).encode("UTF-8")

    @tools.ormcache("key", "password")
    def get_pem_key(self, key, password):
        self.ensure_one()
        return convert_key_cer_to_pem(base64.decodebytes(key), password.encode("UTF-8"))

    def get_cert_data(self):
        self.ensure_one()
        cer_pem_dirty = self.get_pem_cer(self.content)
        certificate = x509.load_pem_x509_certificate(
            cer_pem_dirty, backend=default_backend()
        )
        cer_pem = b"".join(
            [
                line
                for line in cer_pem_dirty.splitlines()
                if not line.startswith(b"-----")
            ]
        )
        return cer_pem, certificate

    def get_pk_data(self):
        self.ensure_one()
        password = self.password.encode("UTF-8")
        key_pem = convert_key_cer_to_pem(base64.decodebytes(self.key), password)
        try:
            private_key = serialization.load_pem_private_key(
                key_pem,
                password=password,
                backend=default_backend(),
            )
        except TypeError as e:
            if "Password was given but private key is not encrypted" in str(e):
                private_key = serialization.load_pem_private_key(
                    key_pem,
                    password=None,
                    backend=default_backend(),
                )
            else:
                raise ValidationError(self.env._("Invalid Password"))
        return key_pem, private_key

    def get_mx_current_datetime(self):
        return fields.Datetime.context_timestamp(
            self.with_context(tz="America/Mexico_City"), fields.Datetime.now()
        )

    def get_valid_esignature(self):
        mexican_dt = self.get_mx_current_datetime()
        for record in self:
            date_start = str_to_datetime(record.date_start)
            date_end = str_to_datetime(record.date_end)
            if date_start <= mexican_dt <= date_end:
                return record
        return None

    @api.constrains("content", "key", "password")
    def _check_credentials(self):
        mexican_dt = self.get_mx_current_datetime()
        for record in self:
            try:
                _cer_pem, certificate = record.get_cert_data()
                not_before = certificate.not_valid_before.replace(tzinfo=DEFAULT_TZ)
                not_after = certificate.not_valid_after.replace(tzinfo=DEFAULT_TZ)
                serial_number = certificate.serial_number

                subject = certificate.subject
                cn_attr = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                holder = cn_attr[0].value if cn_attr else None

                x500_attr = subject.get_attributes_for_oid(
                    NameOID.X500_UNIQUE_IDENTIFIER
                )
                holder_vat = x500_attr[0].value.split(" ")[0] if x500_attr else None

            except Exception:
                raise ValidationError(self.env._("The esignature content is invalid."))

            record.holder = holder
            record.holder_vat = holder_vat
            record.serial_number = ("%x" % serial_number)[1::2]
            record.date_start = not_before.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            record.date_end = not_after.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            if mexican_dt > not_after:
                raise ValidationError(
                    self.env._("The certificate is expired since %s", record.date_end)
                )

            try:
                record.get_pk_data()
            except Exception:
                raise ValidationError(
                    self.env._("The certificate key and/or password is/are invalid.")
                )
