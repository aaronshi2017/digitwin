from setuptools import setup, find_packages

setup(
    name="digitwin",
    version="0.1.0",
    description="Digital Twin AI network congestion simulation",
    packages=find_packages(),
    install_requires=[
        "docker>=6.0",
        "ns3-pybind>=0.0.1"
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "digitwin= digitwin.congestion_ai:run_simulation",
        ],
    },
)
