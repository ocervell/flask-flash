from setuptools import setup

setup(name='Flask-Flash',
      version='1.4.1',
      description='Flask API framework (API + Client) to create simple APIs from database models.',
      author='Olivier Cervello',
      author_email='olivier.cervello@gmail.com',
      url='https://github.com/ocervell/flask_flash',
      install_requires=[
        'flask-restful',
        'SQLAlchemy',
        'Flask-SQLAlchemy',
        'Flask-Marshmallow',
        'marshmallow-sqlalchemy',
        # 'redis',
        'Flask-Script',
        'Flask-Migrate',
	'Flask-Caching',
        'Flask',
        'flask-httpauth',
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
