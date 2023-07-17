import setuptools
import os


FILE_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(FILE_PATH, "README.md"), "r", encoding="utf8") as fh:
    long_description = fh.read()

requirements_path = os.path.join(FILE_PATH, "requirements/common.txt")
with open(requirements_path, encoding="utf8") as f:
    required = f.read().splitlines()

setuptools.setup(
    name="pwv",
    author="clarmy",
    version="0.0.1",
    author_email="clarmyleewt@gmail.com",
    description="A package to verify Pangu weather",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Clarmy/pangu-weather-verify",
    include_package_data=True,
    package_data={"": ["*.csv", "*.config", "*.nl", "*.json"]},
    packages=setuptools.find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]
    ),
    install_requires=required,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
        "Topic :: Scientific/Engineering :: Mathematics",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.8",
)
