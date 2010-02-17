import os
import uuid
import OpenAPIConfig
from OpenAPI import APIHandler
from django import forms
from datetime import datetime


class RegisterForm(forms.Form):

	apiKeyType = forms.ChoiceField(choices=OpenAPIConfig.API_NAMES, required=True)
	name = forms.CharField(label="Your name", required=True)
	email = forms.EmailField(label="E-Mail", required=True)
	app = forms.CharField(label="Application name", required=True)
	url = forms.URLField(label="Application URL", required=True)


class RegisterKey(APIHandler):
	enforceAPIKey = False

	def methodName(self):
		methodName = os.path.basename(self.request.path).split(".")[0]
		# The get name is reserved but if you want to have a methodName of get 
		# 	name your method _get. It will get translated here.
		if methodName == 'key':
			if self.request.method == 'GET':
				methodName = '_get'
			elif self.request.method == 'POST':
				methodName = '_post'
			return methodName
		else:
			return super(APIHandler, self).methodName()

	def _get(self, args):
		form = RegisterForm()
		self.render("templates/RegisterKey.html", form=form, key=False)

	def _post(self, args):
		formArgs = {}
		for k,v in args.items(): formArgs[k] = v[0]
		form = RegisterForm(data=formArgs)
		if form.is_valid():
			# do whatever is required for registration
			newKey = str(uuid.uuid4()) 
			self.getAPIKeysCollection(formArgs['apiKeyType']).save( {
				'apikey': newKey,
				'name': formArgs['name'],
				'email': formArgs['email'],
				'app': formArgs['app'],
				'url': formArgs['url'],
				'issuedate': datetime.now(),
				'timestamp': None,
				'count': 0
			} )
			self.render("templates/RegisterKey.html", form=form, key=newKey)
		else:
			form = RegisterForm()
			self.render("templates/RegisterKey.html", form=form, key=False)

