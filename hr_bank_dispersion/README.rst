.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
    :alt: License: LGPL-3

Bank Dispersion
===============

Added the base methods required to generate the bank dispersion for all banks.

To add support to a bank, is necessary create a method with the next name:

``_generate_BANK_NAME_dispersion``, where is the bank name assigned in the bank
account from the employee.

And this returns the txt content to set in the file.


Installation
============

To install this module, you need to:

- Not special pre-installation is required, just install as a regular Odoo
  module:

  - Download this module from `Vauxoo/hr-advanced
    <https://github.com/vauxoo/hr-advanced>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/Vauxoo/hr-advanced/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback
`here <https://github.com/Vauxoo/hr-advanced/issues/new?body=module:%20
hr_bank_dispersion%0Aversion:%20
16.0.1.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_

Credits
=======

**Contributors**

* Luis Torres <luis_t@vauxoo.com> (Developer)
* Alejandro Santillan <asantillan@vauxoo.com> (Developer)

Maintainer
==========

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
