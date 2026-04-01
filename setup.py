from setuptools import setup, find_packages

setup(
    name='indeed_ontario',
    version='1.0',
    packages=find_packages(),
    entry_points={'scrapy': ['settings = indeed_ontario.settings']},
)
