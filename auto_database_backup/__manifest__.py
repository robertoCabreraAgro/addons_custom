{
    "name": "Automatic Database Backup To Local Server, Remote Server,"
    "Google Drive, Dropbox, Onedrive, Nextcloud and Amazon S3 Odoo18",
    "version": "saas~18.2.2.0.0",
    "live_test_url": "https://youtu.be/Q2yMZyYjuTI",
    "category": "Extra Tools",
    "summary": "Odoo Database Backup, Automatic Backup, Database Backup, Automatic Backup,Database auto-backup, odoo backup"
    "google drive, dropbox, nextcloud, amazon S3, onedrive or "
    "remote server, Odoo18, Backup, Database, Odoo Apps",
    "description": "Odoo Database Backup, Database Backup, Automatic Backup, automatic database backup, odoo18, odoo apps,backup, automatic backup,odoo17 automatic database backup,backup google drive,backup dropbox, backup nextcloud, backup amazon S3, backup onedrive",
    "author": "Cybrosys Techno Solutions",
    "company": "Cybrosys Techno Solutions",
    "maintainer": "Cybrosys Techno Solutions",
    "website": "https://www.cybrosys.com",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/mail_template_data.xml",
        "views/db_backup_configure_views.xml",
        "wizard/dropbox_auth_code_views.xml",
    ],
    "external_dependencies": {
        "python": [
            "dropbox",
            "pyncclient",
            "boto3",
            "nextcloud-api-wrapper",
            "paramiko",
        ]
    },
    "images": ["static/description/banner.gif"],
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}
