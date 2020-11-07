from flask_flash.extensions import db, ma

perms = db.Table('perms',
    db.Column('user_model.first_name', db.Integer, db.ForeignKey('permission_model.name')),
    db.Column('permission_model.name', db.Integer, db.ForeignKey('user_model.first_name'))
)

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    country = db.Column(db.Text, default=None)
    permissions = db.relationship('PermissionModel', secondary=perms, backref=db.backref('users'))

class PermissionModel(db.Model):
    name = db.Column(db.Text, primary_key=True)

class PermissionSchema(ma.ModelSchema):
    class Meta:
        model = PermissionModel
    name = ma.Field(required=True)
    users = ma.List(ma.HyperlinkRelated('api.user', external=True))

class UserSchema(ma.ModelSchema):
    class Meta:
        model = UserModel
    first_name = ma.Field(required=True)
    last_name = ma.Field(required=True)
    permissions = ma.List(ma.HyperlinkRelated('api.permission', external=True))
