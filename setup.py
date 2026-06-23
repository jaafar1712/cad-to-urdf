from setuptools import setup, find_packages

setup(
    name='cad2urdf',
    version='0.1.0',
    description='Convert CAD assemblies (STEP) to ROS 2 URDF packages',
    packages=find_packages(),
    python_requires='>=3.10',
    entry_points={
        'console_scripts': [
            'cad2urdf=main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
)
