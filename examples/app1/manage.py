#!/usr/bin/env python
from flask_flash import Flash
from resources import User

flash = Flash(resources=[User])

if __name__ == '__main__':
    flash.manager.run()
