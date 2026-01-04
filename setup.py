from setuptools import setup
import os

def read_long_description():
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    return ""

setup(
    name="unofficial-claude-cli",
    version="0.7.3",
    
    author="TheTank10",
    
    description="A CLI and API for interacting with Claude",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    
    url="https://github.com/TheTank10/claude-cli",
    project_urls={
        "Bug Reports": "https://github.com/TheTank10/claude-cli/issues",
        "Source": "https://github.com/TheTank10/claude-cli",
    },
    
    license="MIT",

    packages=["claude_cli", "claude_cli.api", "claude_cli.cli"],
    package_dir={"claude_cli": "src"},
    
    install_requires=[
        "click>=8.0",
        "requests>=2.28.0",
        "rich>=13.0",
    ],
    
    entry_points={
        "console_scripts": [
            "claude=claude_cli.cli:cli",
        ],
    },

    python_requires=">=3.10",
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Chat",
    ],
    
    keywords="claude ai cli api chatbot",
)