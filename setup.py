from setuptools import setup, find_packages


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="runner",
    version="0.1.0",
    long_description=readme(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    package_data={"": ["LICENSE"]},
    package_dir={"runner": "runner"},
    include_package_data=True,
    zip_safe=False,
    cmdclass={},
    project_urls={},
)
