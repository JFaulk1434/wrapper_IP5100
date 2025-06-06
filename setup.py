from setuptools import setup, find_packages

setup(
    name="ip5100-wrapper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "telnetlib-313-and-up",
    ],
    author="Justin Faulk",
    author_email="",  # Add your email if you want
    description="A Python wrapper for IP5100 ASpeed devices",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/JFaulk1434/wrapper_IP5100",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.13",
)
