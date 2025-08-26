==============
Discuss Alerts
==============

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-agromarin--addons-lightgray.png?logo=github
    :target: https://github.com/agromarin/agromarin-addons/tree/18.0/discuss_alerts
    :alt: agromarin/agromarin-addons

|badge1| |badge2| |badge3|

This module extends Odoo's Discuss (chat) functionality to enable automated alerts 
and notifications in discussion channels based on configurable criteria.

**Table of contents**

.. contents::
   :local:

Overview
========

The Discuss Alerts module allows you to configure discussion channels to automatically
post messages when certain conditions are met in your Odoo database. This is particularly
useful for monitoring critical business events and notifying relevant teams through
dedicated alert channels.

Features
========

* Convert any discussion channel into an alert channel
* Configure alerts based on any Odoo model (Sales Orders, Invoices, etc.)
* Define custom domains to filter which records trigger alerts
* Use mail templates for consistent alert formatting
* Track last execution time to avoid duplicate notifications
* Automated processing via scheduled actions (cron)

Configuration
=============

To configure an alert channel:

#. Go to **Discuss** app
#. Open or create a discussion channel
#. Enable the **Alert Channel** toggle
#. Navigate to the **Alert settings** tab (visible only to system administrators)
#. Configure the following fields:

   * **Model**: Select the Odoo model to monitor (e.g., Sale Order)
   * **Domain**: Define filter criteria for records that should trigger alerts
   * **Alert template**: Choose a mail template that will format the alert messages
   * **Message**: Preview and edit the template content directly

#. Save your changes

The system will automatically check for new records matching your criteria and post
formatted messages to the channel.

Usage
=====

Once configured, the alert system works automatically:

#. The scheduled action runs periodically (default: every hour)
#. It searches for active alert channels
#. For each channel, it evaluates the configured domain
#. New records created since the last execution are identified
#. Alert messages are posted to the channel using the selected template
#. The last execution time is updated

To manually trigger alert processing:

#. Go to **Settings** > **Technical** > **Scheduled Actions**
#. Find "Discuss Channel Alert Notification"
#. Click **Run Manually**

Known issues / Roadmap
======================

* Add support for update-based alerts (not just creation)
* Allow customizable cron intervals per channel
* Add support for user mentions in alert messages
* Implement alert throttling to prevent spam
* Add email digest option for offline users
* Support for conditional template selection

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/agromarin/agromarin-addons/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/agromarin/agromarin-addons/issues/new?body=module:%20discuss_alerts%0Aversion:%20saas~18.2%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* Agro Marin

Contributors
~~~~~~~~~~~~

* Agro Marin Development Team

Maintainers
~~~~~~~~~~~

This module is maintained by Agro Marin.

.. image:: https://www.agromarin.mx/logo.png
   :alt: Agro Marin
   :target: https://www.agromarin.mx

This module is part of the `agromarin-addons <https://github.com/agromarin/agromarin-addons/tree/18.0/discuss_alerts>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.