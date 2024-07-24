from odoo import models, fields


class PowerUserPython(models.Model):
	_name = "power.user.python"
	_description = "Python scripts from Odoo interface"


	name = fields.Char("Name", required=True)
	query_text = fields.Text("Query Text")
	result_text = fields.Text("Result")
	sequence = fields.Integer(default=10)


	def execute_code(self):
		if self.query_text:
			localdict = {
				"self": self, 
				"cr": self._cr,
				"uid": self._uid,
				"context": self._context or {},
				"user":self.env.user,
				"result": None, #used to store the result of the test
			}
			exec(self.query_text, localdict)
			self.write({"result_text": localdict.get("result", "")})
		return True
