"""Setup configuration for jupyter-claude-assistant."""

from setuptools import setup, find_packages
import os

# Read the README
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="jupyter-claude-assistant",
    version="1.0.0",
    description="AI-powered coding assistant for JupyterLab using Claude",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Jupyter Claude Assistant",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "anthropic>=0.20.0",
        "jupyter-server>=2.0.0",
        "jupyterlab>=4.0.0",
        "tornado>=6.0",
        "click>=8.0",
        "rich>=12.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio",
            "black",
            "mypy",
        ]
    },
    entry_points={
        "console_scripts": [
            "jca=cli.jca:main",
            "jupyter-claude=cli.jca:main",
        ],
        "jupyter_serverproxy_servers": [],
    },
    data_files=[
        (
            "etc/jupyter/jupyter_server_config.d",
            ["jupyter-claude-assistant.json"],
        )
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Jupyter",
        "Framework :: Jupyter :: JupyterLab",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="jupyter jupyterlab claude anthropic ai assistant notebook",
)
