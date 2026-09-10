def get_version():
	'''Return the version of this package.

	Returns
	-------
	string
		The version of the catkit2 package.
	'''
	if get_version._version is None:
		try:
			# Python 3.8+: importlib.metadata is in the standard library.
			from importlib.metadata import version, PackageNotFoundError
		except ImportError:
			# Python 3.7: importlib.metadata is not in the stdlib, use the
			# importlib_metadata backport.
			from importlib_metadata import version, PackageNotFoundError

		try:
			get_version._version = version('catkit2')
		except PackageNotFoundError:
			# package is not installed
			pass

	return get_version._version

get_version._version = None
