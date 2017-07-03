from flask_flash.extensions import db, ma

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    country = db.Column(db.Text, default=None)

class UserSchema(ma.ModelSchema):
    class Meta:
        model = UserModel
    first_name = ma.Field(required=True)
    last_name = ma.Field(required=True)
