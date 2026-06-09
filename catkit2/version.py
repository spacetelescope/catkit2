def get_version():
	'''Return the version of this package.

	Returns
	-------
	string
		The version of the catkit2 package.
	'''
	if get_version._version is None:
		try:
			import importlib.metadata as importlib_metadata
		except ImportError:
			import importlib_metadata

		try:
			get_version._version = importlib_metadata.version('catkit2')
		except importlib_metadata.PackageNotFoundError:
			# package is not installed
			pass

	return get_version._version

get_version._version = None
