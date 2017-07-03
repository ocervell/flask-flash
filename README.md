# Flask-Flash
Flask API Framework to create database-driven CRUD APIs (and non-CRUD) with embedded API client.

Quickstart
-----------

In the following we will create a CRUD (Create, Read, Update, Delete) API
wrapping around our `User` model.

**Install Flask-Flash**

```pip install Flask-Flash```


**Create a CRUD API**

Create your app folder with the following structure:

`app/models.py` - Definition of database models and Marshmallow schemas.

```
from flask_flash.extensions import db, ma

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32))
    password = db.Column(db.String(32))

class UserSchema(ma.ModelSchema):
  	class Meta:
        model = User # link schema with model
    username = db.Field(required=True)
    password = db.Field(required=True)
```

`app/resources.py` - Definition of API endpoints.
```
from flask_flash import CRUD
from models import User, UserSchema

class User(CRUD):
    model = UserModel
    schema = UserSchema
```

`app/manage.py` - Flash app basic initialization (config and routes).

```
from flask_flash import Flash
from .resources import User

config = { 'default': BaseConfig }
routes = [ User ]
app = Flash(config, routes)

if __name__ == '__main__':
    app.manager.run()
```

**Run your API**

```
./manage.py runserver
Server running on localhost:5001
```
At this point you can test your API with cURL:

*API Check:*

`curl localhost:5001/api`

*Create user:*

`curl -X POST -d {'username': 'John', 'password': '@kj!4la'}`

*Get user 1:*

`curl localhost:5001/api/user/1`

Check the docs to see the advanced list of options for URL queries.

Flask-Flash API Client (Python)
-----------

### Basic usage
```
from flask_flash.client import BaseClient, CRUDEndpoint  
c = BaseClient('localhost:5001')
c.add(CRUDEndpoint, '/user', '/users')
c.users.create(username='John', password='@kj!4la')
c.users.get()  # get first 20 users
c.users.get(1) # get user 1
c.users.update(1, username='Johnny') # update username for user 1
```

### Advanced client usage

#### Query API
```
q = [
	  ['name', 'startswith', 'John']
]
c.users.get(match=q)
#[
#  {
#      'id': 1
#      'username': 'John'
#  }
#  {
#      'id': 2,
#     'username': 'Johnny'
# }
#]
```

#### Sorting / Ordering
```
c.users.get(order_by='username', sort='asc')
```

#### Pagination
You can disable pagination either on a per request basis or for every request.

Use this with precaution as it can cause the API to hang for big databases.
```
c.users.get(paginate=False)  # get all users
```
or (disable pagination for every requests)
```
c = BaseClient('localhost:5001', paginate=False)
```

You can allow more records per page using `per_page` argument, and query a specific page using `page` argument.
```
c.users.get(page=1, per_page=100) # get 100 first results
```

#### Extending the API Client
Instead of adding the endpoints using `add` like above, Flask-Flash API client can be modified to add your own endpoints by subclassing `BaseClient`.
```
class MyClient(BaseClient):
	@property
    def users(self):
    	return CRUDEndpoint(self, '/user/<id>', '/users')

c = MyClient('localhost:5001')
john = c.users.create(username='John', password='@%$kjn')
```

A `CRUDEndpoint` can have other methods than the default `get`, `create`, `update`, `delete`.

The next example shows how to subclass `CRUDEndpoint` to add a method to it:

```
class UserEndpoint(CRUDEndpoint):
  	def reverse_username(user_id):
      	user = self.get(user_id)
        return self.update(user_id, username=user['username'].reverse())

class MyClient(BaseClient):
	@property
    def users(self):
    	  return UserEndpoint(self, '/user/<id>', '/users')

c.users.reverse_username(john['id'])
# {
#	'id',
#	'username': 'nhoj'
# }
```
