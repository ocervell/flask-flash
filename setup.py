from setuptools import setup

setup(name='Flask-Flash',
      version='1.6.0',
      description='Flask API framework (API + Client) to create simple APIs from database models.',
      author='Olivier Cervello',
      author_email='olivier.cervello@gmail.com',
      url='https://github.com/ocervell/flask_flash',
      install_requires=[
        'SQLAlchemy',
        'marshmallow',
        'marshmallow-sqlalchemy',
        'Flask',
        'Flask-Restful',
        'Flask-SQLAlchemy',
        'Flask-Marshmallow',
        'Flask-Script',
        'Flask-Migrate',
	    'Flask-Caching',
        'Flask-HTTPAuth',
        'requests',
        'numpy',
        'pyyaml',
        'faker',
        'inflect'
      ],
      packages=[
        'flask_flash',
        'flask_flash/client',
      ],
      zip_safe=False)
