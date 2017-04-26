import unittest
import coloredlogs
import logging
import coloredlogs
import traceback

PATH_SPLIT = ' '

import logging
logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO')

class LogRouter:
    def __init__(self):
        self.modules = {}

    def getModule(self, path):
        return self.modules[path]

    def addModule(self, module):
        try:
            self.modules[module.getPath()] = module
            logger.debug('Added module %s to LogRouter' % module.getPath())
        except Exception as err:
            logger.warning('Tried to add invalid route.')
            traceback.print_exc()

    def register(self, path):
        module = Module(self, path)
        self.addModule(module)
        return module

    def req(self, line):
        try:
            mod_path, path, payload = line.split(PATH_SPLIT, maxsplit=2)
            module = self.getModule(mod_path)
            return module.call(path, payload)
        except:
            logger.warning('Invalid path %s' % path)
            return None

class Module:
    def __init__(self, router, path):
        self.router = router
        self._path = path
        self.routes = {}

    # @property
    def getPath(self):
        return self._path

    def getRoute(self, path):
        return self.routes[path]

    def addRoute(self, route):
        try:
            self.routes[route.getPath()] = route
            logger.debug('Added route %s to LogRouter' % route.getPath())
        except:
            logger.warning('Tried to add invalid route.')

    def call(self, path, payload):
        route = self.getRoute(path)
        return route.call(payload)

    # Route decorator
    def route(self, path):
        def decorator(ctrl):
            route = Route(path, ctrl)
            self.addRoute(route)

        return decorator

class Route:
    def __init__(self, path, ctrl):
        self.path = path
        self.ctrl = ctrl

        if not (self.path and self.ctrl):
            raise Exception('Name, path and controller must be specified for Route')

    def getPath(self):
        return self.path

    def call(self, payload):
        try:
            return self.ctrl(path=self.path, payload=payload)
        except Exception as err:
            traceback.print_exc()

router = LogRouter()
