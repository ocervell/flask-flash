from setuptools import setup

setup(name='Flask-Flash',
      version='0.1',
      description='Flask API framework (API + Client) to create simple APIs from database models.',
      author='Olivier Cervello',
      author_email='olivier.cervello@gmail.com',
      url='https://github.com/ocervell/flask_flash',
      install_requires=[
        'flask-restful',
        'SQLAlchemy',
        'Flask-SQLAlchemy',
        'marshmallow',
        'marshmallow-sqlalchemy',
        'redis',
        'Flask-Script',
        'Flask-Migrate',
        'Flask',
        'requests',
        'numpy'
      ],
      packages=[
        'flask_flash',
        'flask_flash/client',
      ],
      zip_safe=False)
