from setuptools import setup, find_packages

with open("README.md", encoding='utf-8') as f:
    long_description = f.read()

version = None
with open('./src/jmcomic/__init__.py', encoding='utf-8') as f:
    for line in f:
        if '__version__' in line:
            version = line[line.index("'") + 1: line.rindex("'")]
            break

if version is None:
    print('Set version first!')
    exit(1)

setup(
    name='jmcomic',
    version=version,
    description='Python API For JMComic (禁漫天堂)',
    long_description_content_type="text/markdown",
    long_description=long_description,
    url='https://github.com/hect0x7/JMComic-Crawler-Python',
    author='hect0x7',
    author_email='93357912+hect0x7@users.noreply.github.com',
    packages=find_packages("src"),
    package_dir={"": "src"},
    python_requires=">=3.7",
    install_requires=[
        'curl_cffi',
        'commonX',
        'PyYAML',
        'Pillow',
        'pycryptodome',
    ],
    keywords=['python', 'jmcomic', '18comic', '禁漫天堂', 'NSFW'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    entry_points={
        'console_scripts': [
            'jmcomic = jmcomic.cl:main'
        ]
    }
)
