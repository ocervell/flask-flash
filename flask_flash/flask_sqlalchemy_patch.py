"""
flask_sqlalchemy_patch.py
~
Maintainer: Olivier Cervello.
Description:
    This Flask-SQLAlchemy patch adds the ability to add 'Base' db models using
    the Flask-SQLAlchemy `db` object:
Example use:
```
    from sqlalchemy.ext.declarative import declarative_base
    from flask_flash import db
    Base = declarative_base()
    class MyModel(Base):
        pass
    db.register_base(MyModel)
```
"""
import flask_sqlalchemy

class SQLAlchemy(flask_sqlalchemy.SQLAlchemy):
    def __init__(self, app=None, use_native_unicode=True, session_options=None,
                 metadata=None, query_class=flask_sqlalchemy.BaseQuery, model_class=flask_sqlalchemy.Model):
        self.use_native_unicode = use_native_unicode
        self.Query = query_class
        self.session = self.create_scoped_session(session_options)
        self.Model = self.make_declarative_base(model_class, metadata)
        self._engine_lock = flask_sqlalchemy.Lock()
        self.app = app
        flask_sqlalchemy._include_sqlalchemy(self, query_class)
        self.external_bases = []

        if app is not None:
            self.init_app(app)

    def get_tables_for_bind(self, bind=None):
        """Returns a list of all tables relevant for a bind."""
        result = []
        for Base in self.bases:
            for table in flask_sqlalchemy.itervalues(Base.metadata.tables):
                if table.info.get('bind_key') == bind:
                    result.append(table)

        return result

    def get_binds(self, app=None):
        """Returns a dictionary with a table->engine mapping.
        This is suitable for use of sessionmaker(binds=db.get_binds(app)).
        """
        app = self.get_app(app)
        binds = [None] + list(app.config.get('SQLALCHEMY_BINDS') or ())
        retval = {}
        for bind in binds:
            engine = self.get_engine(app, bind)
            tables = self.get_tables_for_bind(bind)
            retval.update(dict((table, engine) for table in tables))
        return retval

    @property
    def bases(self):
        return [self.Model] + self.external_bases

    def register_base(self, Base):
        """Register an external raw SQLAlchemy declarative base.
        Allows usage of the base with our session management and
        adds convenience query property using self.Query by default.
        """
        self.external_bases.append(Base)
        for c in Base._decl_class_registry.values():
            if isinstance(c, type):
                if not hasattr(c, 'query') and not hasattr(c, 'query_class'):
                    c.query_class = self.Query
                if not hasattr(c, 'query'):
                    c.query = flask_sqlalchemy._QueryProperty(self)

                    # for name in dir(c):
                    #     attr = getattr(c, name)
                    #     if type(attr) == orm.attributes.InstrumentedAttribute:
                    #         if hasattr(attr.prop, 'query_class'):
                    #             attr.prop.query_class = self.Query

                    # if hasattr(c , 'rel_dynamic'):
                    #     c.rel_dynamic.prop.query_class = self.Query
