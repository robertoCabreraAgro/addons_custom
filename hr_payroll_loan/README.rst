Loans For Payroll
=================
Create loans to your employees and add an automatic deduction to their payslips.

.. image:: hr_payroll_loan/static/src/img/loans.png
   :width: 800pt


First, you need to create a loan for an employee, please add an Input type to the loan, it is a good idea to create an input type per concept you will work with.

.. image:: hr_payroll_loan/static/src/img/loans2.png
   :width: 800pt


To be allowed to select an input type you will need to check the option on the input type.

.. image:: hr_payroll_loan/static/src/img/loans3_1.png
   :width: 800pt

To be allowed to define an interest percent in the loan it is necessary to check the option "Allows interest payment" on the input type.

.. image:: hr_payroll_loan/static/src/img/loans3_2.png
   :width: 800pt

Select the loan's period and its payment term. The payment term is the number of times the employee will pay the loan, use -1 if will be paid indefined. Set no date to if the loan will be paid indefined.

.. image:: hr_payroll_loan/static/src/img/loans4.png
   :width: 800pt


Create a Salary rule to add the deduction to the payslip. Use python code calculation and use the method get_loan to get the loan and calculate the payslip line value. You can find an example code in the demo salary rule 'Life Ensurance Demo'.

.. image:: hr_payroll_loan/static/src/img/loans5.png
   :width: 800pt


After creating and adding the salary rule to the appropriate salary structure, you should include an input for the loan in the payslip under the 'Other inputs' section.

.. image:: hr_payroll_loan/static/src/img/loans6.png
   :width: 800pt

Then, you can calculate the payslip as usual, and the loan will be deducted. The system will retrieve the valid loans according to the loan configuration.

.. image:: hr_payroll_loan/static/src/img/loans7.png
   :width: 800pt


When you confirm the payslip, the system records the payslips where the employee paid the loan.

.. image:: hr_payroll_loan/static/src/img/loans8.png
   :width: 800pt


.. image:: hr_payroll_loan/static/src/img/loans9.png
   :width: 800pt



Installation
============

To install this module, you need to:

- Not special pre-installation is required, just install as a regular Odoo
  module:

  - Download this module from `Vauxoo/hr-advanced
    <https://git.vauxoo.com/vauxoo/hr-advanced>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

Configuration
=============

To configure this module, you need to:

- To use the feature in your own salary rules please review the code in the demo salary rule 'Life Ensurance Demo'


Bug Tracker
===========

Bugs are tracked on
`Gitlab Vauxoo Issues <https://git.vauxoo.com/vauxoo/hr-advanced/-/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback
`here <https://git.vauxoo.com/vauxoo/hr-advanced/-/issues/new?body=module:%20
hr_payroll_loan%0Aversion:%20
14.0.0.0.1%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_

Credits
=======

**Contributors**

* Luis Torres <luis_t@vauxoo.com> (Planner/Auditor)
* Alejandro Santillán <asantillan@vauxoo.com> (Developer)
* José Zubieta <josejoaquin@vauxoo.com> (Developer)

Maintainer
==========

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
   :width: 800pt
