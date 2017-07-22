from flask_flash.extensions import db, ma

class UserModel(db.Model):
    first_name = db.Column(db.Text, primary_key=True)
    last_name = db.Column(db.Text)
    country = db.Column(db.Text, default=None)

class UserSchema(ma.ModelSchema):
    class Meta:
        model = UserModel
    first_name = ma.Field(required=True)
    last_name = ma.Field(required=True)
