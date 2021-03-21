from setuptools import setup, find_packages

from pytfe import __version__


setup(
    name='pytfe',
    version=__version__,
    author='Nielson Santana',
    author_email='nielsonnas@gmail.com',
    license='MIT',
    entry_points={
        'console_scripts': ['pytfe=pytfe.app:main'],
    },
    install_requires=[],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    python_requires=">=3.6",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
    ],
)
