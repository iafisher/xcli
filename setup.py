import os

from setuptools import find_packages, setup

dpath = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(dpath, "README.md"), "r") as f:
    long_description = f.read()


setup(
    name="xcli",
    version="0.2",
    description="Utilities for building command-line applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    author="Ian Fisher",
    author_email="iafisher@fastmail.com",
    packages=find_packages(exclude=["tests"]),
    project_urls={"Source": "https://github.com/iafisher/xcli"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
    ],
)
