# MEMCACHE_WINDOW is the time in which an API KEY is remembered in cache, after the time has elapsed the DB will be queried.
MEMCACHE_WINDOW = 600 # 10 minutes

# THROTTLING RATE, A user (APIKEY) can use the API THROTTLE_FREQUENCY times in THROTTLE_WINDOW seconds
THROTTLE_FREQUENCY = 10 # times
THROTTLE_WINDOW = 60 # secs (1 min)

# API_NAMES are the names of all your API used by the DC API framework.
API_NAMES = (
	('DC Employees', 'DC Employees'),
	('Geocoding', 'Geocoding'),
	('Open311 Read Only', 'Open311 Read Only'),
	('Open311 Write', 'Open311 Write'),
)