===========================
Units of Measure Extended
===========================

This module extends Odoo's unit of measure system by providing additional 
units for power (kilowatts, horsepower) and fuel efficiency (km/l, mpg), 
along with a configuration interface that allows users to switch between 
metric and imperial systems.

The module adds configuration options in General Settings to choose between:

* **Length units**: Meters or Yards
* **Odometer units**: Kilometers or Miles  
* **Area units**: Square Meters or Square Feet
* **Power units**: Kilowatts (Kw) or Horsepower (HP)
* **Fuel efficiency units**: Km/L or Miles per Gallon (MPG)

These configurations affect how measurements are displayed and interpreted 
throughout the system, providing flexibility for international businesses 
operating with different measurement standards.

**Table of contents**

.. contents::
   :local:

Usage
=====

To use this module, you need to:

#. Go to Settings > General Settings
#. Scroll down to the **Products** section
#. Configure your preferred units of measure:

   * **Length**: Choose between Meters or Yards
   * **Odometer**: Choose between Kilometers or Miles
   * **Area**: Choose between Square Meters or Square Feet
   * **Power**: Choose between Kilowatts (Kw) or Horsepower (HP)
   * **Fuel Efficiency**: Choose between Km/L or Miles per Gallon (MPG)

#. Click **Save** to apply your changes

Once configured, the system will use your selected units throughout the 
application. These settings affect:

* Product measurements and specifications
* Fleet management calculations
* Manufacturing processes that involve power or efficiency metrics
* Reporting and analytics where these units are displayed

**Note**: Changes to unit configurations will take effect immediately and 
apply globally across all modules that use these measurement types.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/maringuadarrama/addons_custom/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/maringuadarrama/addons_custom/issues/new?body=module:%20uom_extended%0Aversion:%2019.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* AgroMarin

Contributors
~~~~~~~~~~~~

* Luis Marin <luis.marin@agromarin.mx>

Maintainers
~~~~~~~~~~~

This module is maintained by AgroMarin.

.. image:: https://www.agromarin.mx/logo.png
   :alt: AgroMarin
   :target: https://www.agromarin.mx

AgroMarin is a company specialized in agricultural ERP solutions based on Odoo.

You are welcome to contribute. To learn how please visit https://www.agromarin.mx.
