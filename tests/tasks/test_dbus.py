# Copyright (c) 2015, Facebook, Inc.  All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
#
from sparts.tests.base import MultiTaskTestCase, Skip
try:
    from gi.repository import Gio
    from sparts.tasks.dbus import DBusServiceTask, \
        DBusMainLoopTask, DBusServiceError
except ImportError:
    raise Skip("dbus support is required to run this test")

from sparts.sparts import option
from random import getrandbits
from concurrent.futures import Future


class BaseTestDBusTask(DBusServiceTask):

    def __init__(self, *args, **kwargs):
        super(BaseTestDBusTask, self).__init__(*args, **kwargs)
        self.name_acquire = Future()

    def nameAcquired(self, connection, name):
        self.name_acquire.set_result(True)

    def nameLost(self, connection, name):
        self.name_acquire.set_result(False)


class TestDBusTask(BaseTestDBusTask):
    BUS_NAME = 'com.github.facebook.test-{}'.format(getrandbits(32))


class TestDBusSystemTask(BaseTestDBusTask):
    BUS_NAME = 'com.github.facebook.systemtest'
    USE_SYSTEM_BUS = True


class TestDBus(MultiTaskTestCase):
    TASKS = [TestDBusTask, DBusMainLoopTask]

    def test_session_bus(self):
        t = self.service.getTask(TestDBusTask)
        self.assertTrue(t.name_acquire.result())


class TestSystemDBus(MultiTaskTestCase):
    TASKS = [TestDBusSystemTask, DBusMainLoopTask]

    def test_system_bus(self):
        t = self.service.getTask(TestDBusSystemTask)
        self.assertFalse(t.name_acquire.result())
