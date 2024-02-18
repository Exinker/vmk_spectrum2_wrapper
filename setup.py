from setuptools import setup, find_packages

from vmk_spectrum2_wrapper import DESCRIPTION, VERSION, NAME, AUTHOR_NAME, AUTHOR_EMAIL


setup(
	# info
    name=NAME,
	description=DESCRIPTION,
	license='MIT',
    keywords=['spectroscopy', 'emulation'],

	# version
    version=VERSION,

	# author details
    author=AUTHOR_NAME,
    author_email=AUTHOR_EMAIL,

	# setup directories
    packages=find_packages(),

	# setup data
    include_package_data=True,

	# requires
    install_requires=['numpy', 'vmk_spectrum2'],
    python_requires='>=3.10',

)
