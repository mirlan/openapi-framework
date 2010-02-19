#!/usr/bin/python26
import os
import memcache
import json
import OpenAPIConfig
from datetime import datetime
from tornado import web
from tornado import escape
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class APIHandler(web.RequestHandler):
	enforceAPIKey = False
	apiKeyType = None # Must be specified by subclasses
	mc = memcache.Client(['127.0.0.1:11211'], debug=0)

	mongoDBConn = None
	def mongoDB(self):
		log.debug('mongoDB START')
		if not self.mongoDBConn:
			from pymongo import Connection
			self.mongoDBConn = Connection()
		return self.mongoDBConn

	
	def getAPIKeysCollection(self, apiKeyType=None):
		log.debug('getAPIKeysCollection START')
		if apiKeyType:
			log.debug('getAPIKeysCollection: %s' % apiKeyType)
			return self.mongoDB().apikeys[apiKeyType]
		else:
			log.debug('getAPIKeysCollection: %s' % self.apiKeyType)
			return self.mongoDB().apikeys[self.apiKeyType]
		log.debug('getAPIKeysCollection END')
	
	
	def methodClass(self):
		log.debug('methodClass: %s' % self.__class__.__name__)
		return self.__class__.__name__


	def methodName(self):
		methodName = os.path.basename(self.request.path).split(".")[0]
		# The get name is reserved but if you want to have a methodName of get 
		# 	name your method _get. It will get translated here.
		if methodName == 'get':
			methodName = '_get'
		elif methodName == 'post':
			methodName = '_post'
		log.debug('methodName: %s' % methodName)
		return methodName


	def format(self):
		try:
			return os.path.basename(self.request.path).split(".")[1]
		except:
			return ""


	def setHeaderFormat(self):
		if self.format() == "xml":
			self.set_header('Content-Type', 'text/xml')
		elif self.format() == "json":
			self.set_header('Content-Type', 'application/json')
		else:
			self.set_header('Content-Type', 'text/html')


	def callMethod(self):
		log.debug('callMethod START')
		self_method = getattr(self, self.methodName(), None)
		if callable(self_method):
			self.logMethodStart()
			log.debug('callMethod: %s START' % self_method.func_name)
			self_method(self.request.arguments)
			log.debug('callMethod: %s END' % self_method.func_name)
			self.logMethodStop()


	def logMethodStart(self):
		log.debug('logMethodStart START')
		timestamp = datetime.now()
		apikey = self.request.arguments.get('apikey', [None])[0]
		# APIKEY STAT
		if self.enforceAPIKey and apikey:
			self.getAPIKeysCollection().update(
				{ 'apikey': apikey }, 
				{ '$set': { 'timestamp': timestamp }, '$inc': { 'count': 1 } },
				upsert=False, safe=False, multi=False )

		# METHOD STATS
		self.mongoDB().usageStats.methodStats.update( 
			{ 'methodClass': self.methodClass(), 'methodName': self.methodName() },
			{ '$inc': { 'count': 1 }, '$set': { 'timestamp': timestamp } },
			safe=False )
		
		# REAL-TIME STAT
		usageStatDict = {
			'apikey': apikey,
			'methodClass': self.methodClass(),
			'methodName': self.methodName(),
			'timestamp': timestamp,
			'duration': None # Don't know what time if responded...yet
			}
		self.mongoDB().usageStats.currentUsageStats.insert(usageStatDict, safe=False)
		log.debug('logMethodStart END')


	def logMethodStop(self):
		log.debug('logMethodStop START')
		timestamp = datetime.now()
		apikey = self.request.arguments.get('apikey', [None])[0]

		# REAL-TIME STAT
		currentUsageStat = self.mongoDB().usageStats.currentUsageStats.find_one({ 
			'apikey': apikey, 
			'methodClass': self.methodClass(),
			'methodName': self.methodName(),
			'duration': None })
		delta = timestamp - currentUsageStat['timestamp']
		currentUsageStat['duration'] =  delta.seconds*1000 + delta.microseconds/1000
		self.mongoDB().usageStats.currentUsageStats.save(currentUsageStat, safe=False)
		log.debug('logMethodStop END')


	def throttleCheck(self, apikey):
		log.debug('throttleCheck START')
		shouldWeThrottle = True
		currentTimestamp = datetime.now()
		timestamps = self.mc.get( apikey )
		if timestamps is None:
			timestamps = []
		log.debug('throttleCheck: timestamps = %s' % timestamps)
		if len(timestamps) == OpenAPIConfig.THROTTLE_FREQUENCY-1:
			duration = currentTimestamp - timestamps.pop(0)
			log.debug('throttleCheck: duration = %s' % duration.seconds)
			if duration.seconds < OpenAPIConfig.THROTTLE_WINDOW:
				shouldWeThrottle = True
			else:
				shouldWeThrottle = False
		else:
			shouldWeThrottle = False
		timestamps.append( currentTimestamp )
		self.mc.set( apikey, timestamps, OpenAPIConfig.MEMCACHE_WINDOW )
		log.debug('throttleCheck END: %s' % shouldWeThrottle)
		return shouldWeThrottle
	
	
	#This method verifies API key
	#it either fail and throw appropriate HTTP status code and error message or just pass through 
	def verifyKey(self):
		log.debug('verifyKey START')
		#check if apikey parameter was provided
		apikey = self.request.arguments.get('apikey', [None])[0]
		if not apikey:
			raise web.HTTPError(401, self.format(), "APIKEY parameter is missing.")
		elif len(apikey) != 36:
			#TODO: fix UUID validation
			raise web.HTTPError(401, self.format(), "APIKEY parameter is invalid.")

		# check cache
		if self.mc.get( apikey ): # apikey is in memcache
			isValidKey = True
		else: # apikey not in cache
			apikeyCollection = self.getAPIKeysCollection(self.apiKeyType)
			apikeyDict = apikeyCollection.find_one( { 'apikey' : apikey } )
			if apikeyDict:
				isValidKey = True
			else:
				isValidKey = False
		
		if isValidKey is False:
			raise web.HTTPError(401, self.format(), "APIKEY given could not be found.")
			
		if self.throttleCheck( apikey ):
			raise web.HTTPError(401, self.format(), "API usage throttled for this APIKEY, usage should not exceed %s times in %s seconds." % \
				(OpenAPIConfig.THROTTLE_FREQUENCY, OpenAPIConfig.THROTTLE_WINDOW))
		log.debug('verifyKey END')
		

	def handleJSON(self, returnVal):
		log.debug('handleJSON START')
		return json.dumps(returnVal, ensure_ascii=False)
		log.debug('handleJSON END')


	def handleJSONCallback(self, returnVal):
		log.debug('handleJSONCallback START')
		if self.request.arguments.get('callback'):
			return '%s(%s);' % (self.request.arguments.get('callback')[0], self.handleJSON(returnVal))
		else:
			return self.handleJSON(returnVal)
		log.debug('handleJSONCallback END')


	def get(self):
		log.debug('get START')
		log.debug(__name__)
		if self.enforceAPIKey:
			self.verifyKey()
		try:
			self.setHeaderFormat()
			self.callMethod()
		except:
			raise #pass
		log.debug('get END')
		


	def post(self):
		log.debug('post START')
		if self.enforceAPIKey:
			self.verifyKey()
		try:
			self.setHeaderFormat()
			self.callMethod()
		except:
			raise #pass
		log.debug('post END')

