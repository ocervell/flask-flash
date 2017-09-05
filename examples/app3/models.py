from flask_flash.extensions import db, ma
from sqlalchemy import Column, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import expression

Base = declarative_base()

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

class TrackerModel(Base):
    __tablename__ = 'tracker'
    id = Column(Integer, primary_key=True)
    track = Column(Boolean, default=True, server_default=expression.true())

db.register_base(TrackerModel)

class TrackerSchema(ma.ModelSchema):
    class Meta:
        model = TrackerModel
