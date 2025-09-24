# -*- coding: utf-8 -*-
{
    "name": "Base EDI Framework",
    "version": "19.0.1.0.0",
    "category": "Accounting/EDI",
    "summary": "Unified EDI framework for electronic document interchange",
    "description": """
Base EDI Framework
==================

This module provides a unified framework for Electronic Document Interchange (EDI)
operations across different countries and formats. It extends Odoo's existing
account_edi and certificate modules to provide:

Features:
---------
* Enhanced certificate management for digital signatures
* Unified EDI document lifecycle management
* Provider abstraction for web services
* Validation framework
* Workflow automation engine
* Country-agnostic base classes

This module serves as the foundation for country-specific EDI implementations
such as:
- l10n_mx_edi_base (Mexican CFDI)
- l10n_br_edi_base (Brazilian NF-e)
- l10n_ar_edi_base (Argentinian electronic invoice)

Technical Details:
------------------
The module leverages:
- certificate: For digital signature management
- account_edi: For EDI document framework
- Standard Odoo patterns for extensibility
    """,
    "author": "AgroMarin",
    "website": "https://www.agromarin.com",
    "depends": [
        "account_edi",
        "certificate",
        "account",
        "base_setup",
    ],
    "data": [
        "security/base_edi_security.xml",
        "security/ir.model.access.csv",
        "views/edi_document_views.xml",
        "views/edi_provider_views.xml",
        "views/edi_workflow_views.xml",
        "views/certificate_views.xml",
        "views/res_config_settings_views.xml",
        "data/edi_format_data.xml",
    ],
    "demo": [
        "demo/demo_certificates.xml",
        "demo/demo_providers.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
}
