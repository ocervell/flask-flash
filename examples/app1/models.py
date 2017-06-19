from flask_simple_api import db, ma

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    country = db.Column(db.Text)

class UserSchema(ma.ModelSchema):
    class Meta:
        model = User
    first_name = ma.Field(required=True)
    last_name = ma.Field(required=True)
    country = ma.Field(required=True)
