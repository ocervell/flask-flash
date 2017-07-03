# Flask-Flash
Flask API Framework to create database-driven CRUD APIs (and non-CRUD) with embedded API client.

Quickstart
-----------

In the following we will create a CRUD (Create, Read, Update, Delete) API
wrapping around our `User` model.
The example is accessible in the `examples/app1` folder.

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

`app/manage.py` - Basic initialization of our `Flash` app (config and routes).

```
#!/usr/bin/env python
from flask_flash import Flash
from resources import User

flash = Flash(resources=[User])

if __name__ == '__main__':
    flash.manager.run()

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

`curl -X POST -H "Content-Type:application/json" -d {'username': 'John', 'password': '@kj!4la'}`

*Get user 1:*

`curl localhost:5001/api/user/1`

*Get first 20 users:*

`curl localhost:5001/api/users`

Check the docs to see the advanced list of options for URL queries.

Flask-Flash API Client (Python)
-----------

### Basic usage
The positive side of having a client as part of the API framework means that
we are done with running db queries from our shell and can use a higher level
Python client instead.

```
from flask_flash.client import BaseClient, CRUDEndpoint  
c = BaseClient('localhost:5001')
c.add(CRUDEndpoint, '/user', '/users')
c.users.create(username='John', password='@kj!4la')
c.users.get()  # get first 20 users
c.users.get(1) # get user 1
c.users.update(1, username='Johnny') # update username for user 1
```

Alternatively, for local-mode only, you can use the `Flask-Script` shell.
This time the endpoints are automatically registered to the client and the client
is automatically imported as `c`.

`./manage.py runserver`

```
c.users.get()
```

### Advanced client usage

#### Instanciating a remote client


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
