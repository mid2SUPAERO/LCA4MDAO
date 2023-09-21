from setuptools import setup

setup(
    name='LCA4MDAO',
    version='0.1',
    packages=['lca4mdao', 'lca4mdao.examples', 'lca4mdao.optimizer'],
    include_package_data=True,
    url='https://github.com/mid2SUPAERO/LCA4MDAO',
    license='MIT license',
    author='Thomas Bellier',
    author_email='thomas.bellier@isae-supaero.fr',
    description=' Introducing Life Cycle Assessment in MDAO framework in an python environment. ',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
