# Copyright (c) 2014, Facebook, Inc.  All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
#
"""Module providing tasks that help with dbus integration"""
from __future__ import absolute_import

from sparts.sparts import option
from sparts.vtask import VTask, SkipTask

try:
    # from sparts.fb303.dbus import FB303DbusService
    # from sparts.tasks.fb303 import FB303HandlerTask
    HAVE_FB303 = True
except ImportError:
    HAVE_FB303 = False

from gi.repository import Gio, GLib
from concurrent.futures import Future
import time

# early init of GLib threading support
GLib.threads_init()


# class VServiceDBusObject(dbus.service.Object):
#     """DBus interface implementation that exports common VService methods"""
#     def __init__(self, dbus_service):
#         self.dbus_service = dbus_service
#         self.service = self.dbus_service.service
#         self.logger = self.dbus_service.logger
#         self.path = '/'.join(['', self.service.name, 'sparts'])
#         dbus.service.Object.__init__(self, self.dbus_service.bus, self.path)

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='s', out_signature='v')
#     def getOption(self, name):
#         return self.service.getOption(name)

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='sv', out_signature='')
#     def setOption(self, name, value):
#         if value == '__None__':
#             value = None
#         self.service.setOption(name, value)

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='a{sv}')
#     def getOptions(self):
#         result = {}
#         for k, v in self.service.getOptions().iteritems():
#             # dbus doesn't support serializing None as a variant
#             if v is None:
#                 v = '__None__'
#             result[k] = v
#         return result

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='as')
#     def listOptions(self):
#         return self.service.getOptions().keys()

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='')
#     def shutdown(self):
#         self.service.shutdown()

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='')
#     def restart(self):
#         self.service.reinitialize()

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='as')
#     def listTasks(self):
#         return [t.name for t in self.service.tasks]

#     @dbus.service.method(dbus_interface='org.sparts.Service',
#                          in_signature='', out_signature='x')
#     def uptime(self):
#         return int(time.time() - self.service.start_time)


class DBusMainLoopTask(VTask):
    """Configure and run the DBus Main Loop in a sparts task"""
    THREADS_INITED = False
    mainloop = None

    def initTask(self):
        super(DBusMainLoopTask, self).initTask()
        needed = getattr(self.service, 'REQUIRE_DBUS', False)
        for t in self.service.tasks:
            if isinstance(t, DBusTask):
                needed = True

        if not needed:
            raise SkipTask("No DBusTasks found or enabled")

        # glib.threads_init()
        # gobject.threads_init()
        # dbus.mainloop.glib.threads_init()
        self.mainloop = GLib.MainLoop.new(None, False)

    def _runloop(self):
        self.logger.debug('loop run()')
        self.mainloop.run()

    def stop(self):
        super(DBusMainLoopTask, self).stop()

        if self.mainloop is None:
            return

        self.mainloop.quit()

        # OK!  Apparently, there is some wonky destructor event handling that
        # seems to work better than just calling .quit() in order to properly
        # return full control of signal handling, threads, etc to the actual
        # main process.
        self.mainloop = None

class DBusTask(VTask):
    """Base Class for Tasks that depend on the DBus Main Loop"""
    DEPS = [DBusMainLoopTask]
    LOOPLESS = True

    def initTask(self):
        super(DBusTask, self).initTask()
        self.mainloop_task = self.service.requireTask(DBusMainLoopTask)

    @property
    def mainloop(self):
        return self.mainloop_task.mainloop


class DBusServiceError(Exception):
    """Wrapper for DBus related errors"""
    pass


class DBusServiceTask(DBusTask):
    """Glue Task for exporting this VService over dbus"""
    OPT_PREFIX = 'dbus'
    BUS_NAME = None
    # BUS_CLASS = VServiceDBusObject
    USE_SYSTEM_BUS = False

    bus_name = option(default=lambda cls: cls.BUS_NAME, metavar='NAME',
                      help='Bus Name.  Should be something like '
                           '"com.sparts.AwesomeService"')
    replace = option(action='store_true', type=bool,
        default=False, help='Replace, and enable replacing of this service')
    queue = option(action='store_true', type=bool,
        default=False, help='If not --{task}-replace, will wait to take '
                            'this bus name')
    system_bus = option(action='store_true', type=bool,
                        default=lambda cls: cls.USE_SYSTEM_BUS,
                        help='Use system bus')

    dbus_service = None

    def initTask(self):
        super(DBusServiceTask, self).initTask()

        assert self.bus_name is not None, \
            "You must pass a --{task}-bus-name"

    def _getBusType(self):
        self.logger.debug('bus type: %s',
                          'system' if self.system_bus else 'session')
        if self.system_bus:
            return Gio.BusType.SYSTEM
        return Gio.BusType.SESSION

    def nameLost(self, connection, name):
        """Override"""
        self.logger.debug('name lost() %r %s', connection, name)
        raise DBusServiceError('Failed to acquire name %s' % self.bus_name)

    def nameAcquired(self, connection, name):
        """Override"""
        self.logger.debug('name acquired() %r %s', connection, name)

    def busAcquired(self, connection, name):
        """Override"""
        self.logger.debug('bus acquired: %r addr: %s', connection, name)

    def _asyncStartCb(self, res):
        bus_type = self._getBusType()
        self.logger.debug('bus_own_name() start')
        Gio.bus_own_name(bus_type, self.bus_name,
                         Gio.BusNameOwnerFlags.NONE,
                         self.busAcquired,
                         self.nameAcquired,
                         self.nameLost)
        self.logger.debug('bus_own_name() finished')
        res.set_result(True)

    def scheduleStart(self):
        self.logger.debug('schedule start()')
        ft = Future()
        GLib.idle_add(self._asyncStartCb, ft)
        ft.result()
        self.logger.debug('task started()')

    def start(self):
        self.scheduleStart();
        self.addHandlers()
        super(DBusServiceTask, self).start()

    def addHandlers(self):
        return
        self.sparts_dbus = self.BUS_CLASS(self)
        if HAVE_FB303:
            task = self.service.getTask(FB303HandlerTask)
            if task is not None:
                self.fb303_dbus = FB303DbusService(
                    self.dbus_service, task, self.service.name)

    def stop(self):
        if self.dbus_service is not None:
            self.dbus_service = None

        #self.bus.close()
        super(DBusServiceTask, self).stop()
