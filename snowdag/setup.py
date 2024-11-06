from setuptools import find_packages, setup

setup(
    name="snowdag",
    packages=find_packages(exclude=["snowdag_tests"]),
    install_requires=["dagster", "dagster-cloud"],
    extras_require={"dev": ["dagster-webserver", "pytest"]},
)
