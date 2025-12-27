from setuptools import setup, find_packages

setup(
    name="claude-cli",
    version="0.2.0",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=[
        "click",
        "requests",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "claude=src.cli:cli",
        ],
    },
)