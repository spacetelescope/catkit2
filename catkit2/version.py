def get_version():
	'''Return the version of this package.

	Returns
	-------
	string
		The version of the catkit2 package.
	'''
	if get_version._version is None:
		from pkg_resources import get_distribution, DistributionNotFound

		try:
			get_version._version = get_distribution('catkit2').version
		except DistributionNotFound:
			# package is not installed
			pass

	return get_version._version

get_version._version = None
