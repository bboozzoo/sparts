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

from concurrent.futures import Future
from sparts.sparts import option
from random import getrandbits


class TestDBusTask(DBusServiceTask):
    BUS_NAME = 'com.github.facebook.test-{}'.format(getrandbits(32))


class TestDBusSystemTask(DBusServiceTask):
    BUS_NAME = 'com.github.facebook.systemtest'
    USE_SYSTEM_BUS = True

    def start(self):
        try:
            super(TestDBusSystemTask, self).start()
        except DBusServiceError as err:
            self.acquire_name_error = str(err)


class TestDBus(MultiTaskTestCase):
    TASKS = [TestDBusTask, DBusMainLoopTask]

    def setUp(self):


    def test_session_bus(self):


class TestSystemDBus(MultiTaskTestCase):
    TASKS = [TestDBusSystemTask, DBusMainLoopTask]

    def setUp(self):


    def test_system_bus(self):

        self.assertTrue(err.startswith('Failed to acquire name'))
