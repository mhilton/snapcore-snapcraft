# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2016-2019 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from testtools.matchers import FileExists, MatchesRegex

from tests import integration


class PushTestCase(integration.StoreTestCase):
    def test_push_with_login(self):
        # Make a snap
        self.addCleanup(self.logout)
        self.login()

        # Change to a random name and version.
        name = self.get_unique_name()
        version = self.get_unique_version()
        self.copy_project_to_cwd("basic")
        self.update_name_and_version(name, version)

        self.run_snapcraft("snap")

        # Register the snap
        self.register(name)
        # Upload the snap
        snap_file_path = "{}_{}_{}.snap".format(name, version, "all")
        self.assertThat(os.path.join(snap_file_path), FileExists())

        output = self.run_snapcraft(["push", snap_file_path])
        expected = r".*Ready to release!.*".format(name)
        self.assertThat(output, MatchesRegex(expected, flags=re.DOTALL))

    def test_push_and_release(self):
        # Make a snap
        self.addCleanup(self.logout)
        self.login()

        # Change to a random name and version when not on the fake store.
        if not self.is_store_fake():
            name = self.get_unique_name()
            version = self.get_unique_version()
        # If not, keep the name that is faked in our fake account.
        else:
            name = "basic"
            version = "1.0"

        self.copy_project_to_cwd("basic")
        self.update_name_and_version(name, version)

        self.run_snapcraft("snap")

        # Register the snap
        self.register(name)

        # Upload the snap
        snap_file_path = "{}_{}_{}.snap".format(name, version, "all")
        self.assertThat(os.path.join(snap_file_path), FileExists())

        output = self.run_snapcraft(["push", snap_file_path, "--release", "edge"])
        expected = r".*edge *{version}.*".format(version=version)
        self.assertThat(output, MatchesRegex(expected, flags=re.DOTALL))

    def test_push_with_deprecated_upload(self):
        # Make a snap
        self.addCleanup(self.logout)
        self.login()

        # Change to a random name and version.
        name = self.get_unique_name()
        version = self.get_unique_version()
        self.copy_project_to_cwd("basic")
        self.update_name_and_version(name, version)

        self.run_snapcraft("snap")

        # Register the snap
        self.register(name)
        # Upload the snap
        snap_file_path = "{}_{}_{}.snap".format(name, version, "all")
        self.assertThat(os.path.join(snap_file_path), FileExists())

        output = self.run_snapcraft(["upload", snap_file_path])
        expected = r".*Ready to release!.*".format(name)
        self.assertThat(output, MatchesRegex(expected, flags=re.DOTALL))
