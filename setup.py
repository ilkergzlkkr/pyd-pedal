# pypedal setup
from setuptools import setup, find_packages

requirements = []
with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

dev_requirements = []
with open("dev.requirements.txt", "r") as f:
    dev_requirements = f.read().splitlines()

tests_requirements = []
with open("tests.requirements.txt", "r") as f:
    tests_requirements = f.read().splitlines()

setup(
    name="pyd-pedal",
    version="1.0.0",
    description="A python wrapper for the Pedalboard audio processing library",
    author="ilkergzlkkr",
    packages=find_packages(include=["pypedal*"]),
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "tests": tests_requirements,
    },
    python_requires=">=3.8.5",
    entry_points={
        "console_scripts": [
            "pypedal=pypedal.pedal.equalizer:app",
        ],
    },
)
