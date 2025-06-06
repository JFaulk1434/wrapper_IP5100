from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ip5100-wrapper",
    version="1.0.1",
    author="Justin Faulk",
    author_email="jfaulk@proitav.us",
    description="A Python wrapper for controlling IP5100 ASpeed encoders and decoders via Telnet",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JFaulk1434/wrapper_IP5100",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Multimedia :: Video",
    ],
    python_requires=">=3.13",
    install_requires=[
        "telnetlib-313-and-up",
    ],
)
