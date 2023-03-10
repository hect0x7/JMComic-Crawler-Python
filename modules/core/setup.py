from setuptools import setup, find_packages

setup(
    name='jmcomic',
    version='0.3.0',
    description='python-jmcomic-api',
    author='Straw',
    packages=find_packages(),
    install_requires=[
        "Pillow>=9.2.0",
        "setuptools>=47.1.0",
        "beautifulsoup4>=4.11.1",
        "requests>=2.28.1",
        "lxml>=4.9.2",
        "PyYAML>=6.0",
        "common>=0.3.0",
    ]
)
