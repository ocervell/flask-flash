
Flask-Flash
-----------
**Flask-Flash** provides simple generation of database-driven RESTful APIs.

A **Flash API** can be generated with minimal configuration allowing for quick API development.

Resources following the **CRUD** ***(Create, Read, Update, Delete)*** model are made very easy.


Description
-----------
**Flask-Flash** makes some assumptions about what an API should have in order to be rock-solid and production-ready, but will give you the ability to customize it to your own needs.

It provides both an API and the Python client to query it:

#### Flash API
- Integrates well with an existing `flask.Flask` application object
- Automatic registration (and routing) of resources
- Automatic resource caching for `GET` requests (to reduce database load)
- Provides `flask_flash.Protected` mixin with:
	- Basic Authentication using `Flask-HTTPAuth`
	- Custom authentication forwarding
	- Custom permission control on every method
- Provides `flask_flash.CRUD` mixin with:
	- Implements HTTP methods: `HEAD`, `GET`, `PUT`, `POST`, `DELETE`
	- Automatic model serialization, deserialization and parameter validation using `Flask-Marshmallow`
	- Resource filtering and sorting, and pagination using `db.query` object


#### Flash API Client
- Authentication and token handling
- Easy resource querying, filtering, sorting, controlling pagination and caching
- Provides `flask_flash.CRUDEndpoint`  with basic CRUD methods: `count`, `create`, `get`, `update`, `delete`
- Configurable retries on common HTTP status codes
- Extensible

Quickstart
-----------

In the following we will create a CRUD (Create, Read, Update, Delete) API
around our `User` model.

The following example code is accessible from the `examples/app1` folder.

### Install Flask-Flash

```pip install Flask-Flash```


### Create a CRUD API

Create an `app` folder with the following structure:

`app/models.py` - *Definition of SQLAlchemy models and Marshmallow schemas.*

```
from flask_flash import db, ma

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32))
    password = db.Column(db.String(32))

class UserSchema(ma.ModelSchema):
    class Meta:
        model = UserModel # link schema with model
    username = ma.Field(required=True)
    password = ma.Field(required=True)
```

`app/resources.py` - *Definition of API resources.*
```
from flask_flash import CRUD
from models import UserModel, UserSchema

class User(CRUD):
    model = UserModel
    schema = UserSchema
```

`app/manage.py` - *Basic initialization of our `Flash` app*

```
#!/usr/bin/env python
from flask_flash import Flash
from resources import User

flash = Flash([User])

if __name__ == '__main__':
    flash.manager.run()
```

### Run your API

```
./manage.py runserver --threaded -d -r
Server running on localhost:5001
```
***API Check:***

`curl localhost:5001/api`

The above command should return a `HTTP 200 OK` and `{}` as content.

### Query your API

Here are the most common URL parameters to apply on `CRUD` resources:
 - **Filter** on db columns using `<key>=<value>` (*str*, *str*/*csv-list*\*) params.
 - **Filter** on db columns using `match` (*list*)
 - **Pagination** using `paginate` (*bool*), `per_page` (*int*) and `page` (*int*).
 - **Caching** on/off using `cache` (*bool*)
 - **Sorting** results using `order_by=<key>` and `sort` (*string*, 'asc' or 'desc')
 - **Limit** the number of results using `limit` (*int*)
 - **Include / Exclude** what field shows up in results by using `include` (*csv-list*) and `exclude` (*csv-list*)

\**csv-list*: Syntax for lists like `key=x1,x2,x3` are preferred over syntax `key=x1&key=x2&key=x3` or `key=[x1,x2,x3]` for simplicity of query.

***Create users:***

```
curl -X POST localhost:5001/api/users \
-H "Content-Type:application/json" \
-d [{'username': 'John', 'password': '@kj!4la'}, {'username': 'Xiang', 'password': 'lu1Z3k'}]
```
***Get user with*** `id == 1`:

`curl localhost:5001/api/user/1`

***Get users with*** `id == 1 OR id == 2 OR id == 3`:

`curl localhost:5001/api/users?id=1,2,3`

***Get all users with*** `password == @kj!4la`:
  ```
 curl localhost:5001/api/users? \
 	&password=@kj!4la \
    &paginate=false \    
 ```

 ***Get all users with*** `username >= John AND 1 <= id <= 5`.
 ***Include only*** `id` ***and*** `username` fields in response
 ```
 curl localhost:5001/api/users?\
 	&match=[[ username, >=, John ], [ id, between, [1, 5] ]] \
    &order_by=username \
    &sort=asc \
    &include=id,username,password \
    &paginate=false   
 ```

 ***Disable cache to get most recent results***
 ```
 curl localhost:5001/api/users?cache=false
 ```

Flask-Flash API Client (Python)
-----------

The positive side of having a client as part of the API framework means that
we are done with running most common db queries from our shell and can use a high level Python client instead.

Here is an example how to use the **Flask-Flash** client:

```
from flask_flash import BaseClient, CRUDEndpoint  
c = BaseClient('localhost:5001')
c.register(CRUDEndpoint, '/user', '/users')  # register endpoint
c.users.create(username='John', password='@kj!4la') # create user
c.users.get()  						 # get first 20 users
c.users.get(1) 						 # get user 1
c.users.update(1, username='Johnny') # update username for user 1
```

The `CRUDEndpoint` allows to use the following `CRUD` features:

### Queries
You can use `match` argument (only for `CRUD` resources) to use for `CRUDEndpoint.get` and `CRUDEndpoint.count` methods to
```
q = [
	  ['name', 'startswith', 'John'],
      ['id', 'between', [1, 5] ],
]
c.users.get(match=q)
```
Note: All the [sqlalchemy operators](https://github.com/zzzeek/sqlalchemy/blob/master/lib/sqlalchemy/sql/operators.py) are supported for `match` syntax.


### Sorting

Sorting is enabled by default on the `db.Model` primary key (if defined) in ascending order.

Sort by any key in the model using `order_by`, and organize by ascending or descending order by setting `sort` to `'asc'` or `'desc'`.
```
c.users.get(order_by='username', sort='asc')
```

### Pagination
Pagination is enabled by default.
The default number of records per page is 20.

Although it's generally not advised to disable pagination (requests might timeout), it can still be done in `Flask-Flash`, either for the client as a whole:
```
c = BaseClient('localhost:5001', paginate=False)
```
... or per request:
```
c.users.get(paginate=False)  # get all users
```

The number of records per page and the page to query are controlled using `per_page` and `page` argument.
```
c.users.get(page=1, per_page=100) # get the 100 first results
```

### Extending the API Client
Instead of adding the endpoints using `register` like above, Flask-Flash API client can be modified to add your own endpoints (and functions !).

This is done by subclassing `BaseClient`:
```
class MyClient(BaseClient):
    @property
    def users(self):
    	return CRUDEndpoint(self, '/user', '/users')

    @property
    def get_user_count(self):
    	return self.users.count(paginate=False)

c = MyClient('localhost:5001')
c.users.create(username='John', password='@%$kjn')
nusers = c.get_user_count(self)
```

Of course, every `CRUDEndpoint` can also have other methods than the default `get`, `create`, `update`, `delete`.

Their implementation is up to you, here is an example for a `delete_all` function:
```
class UserEndpoint(CRUDEndpoint):
    def delete_all():
      	users = self.get(paginate=False)
        ids = [u['id'] for u in users]
        return self.delete(ids)

class MyClient(BaseClient):
    @property
    def users(self):
    	  return UserEndpoint(self, '/user', '/users')
```
And in a script, call:
```
c = MyClient('localhost:5001')
c.users.delete_all()
```
