# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018-2019 Canonical Ltd
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

from typing import Optional
from unittest import mock

import fixtures
from testtools.matchers import Equals

from . import LifecycleCommandsBaseTestCase
from snapcraft import project
from snapcraft.internal import steps
from snapcraft.internal.build_providers.errors import ProviderExecError
from tests import fixture_setup
from tests.unit.build_providers import ProviderImpl


class BuildEnvironmentParsingTest(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()

        # Use "clean" step for testing provider handling.
        self.step = "clean"

        # Don't actually run clean - we only want to test the command
        # line interface flag parsing.
        self.useFixture(fixtures.MockPatch("snapcraft.internal.lifecycle.clean"))

        # tests.unit.TestCase sets SNAPCRAFT_BUILD_ENVIRONMENT to host.
        # These build provider tests will want to set this explicitly.
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", None)
        )

        self.mock_get_provider_for = self.useFixture(
            fixtures.MockPatch(
                "snapcraft.internal.build_providers.get_provider_for",
                return_value=ProviderImpl,
            )
        ).mock

        # Tests need to dictate this (or not).
        self.useFixture(
            fixtures.MockPatch(
                "snapcraft.internal.common.is_process_container", return_value=False
            )
        )

        self.useFixture(fixture_setup.FakeMultipass())

        snapcraft_yaml = fixture_setup.SnapcraftYaml(self.path, base="core")
        snapcraft_yaml.update_part("part1", dict(plugin="nil"))
        self.useFixture(snapcraft_yaml)


class AssortedBuildEnvironmentParsingTests(BuildEnvironmentParsingTest):
    def test_host_container(self):
        self.useFixture(
            fixtures.MockPatch(
                "snapcraft.internal.common.is_process_container", return_value=True
            )
        )
        result = self.run_command([self.step])

        # Mock get_provider_for not called when using "host".
        self.mock_get_provider_for.assert_not_called()
        self.assertThat(result.exit_code, Equals(0))

    def test_use_lxd(self):
        result = self.run_command([self.step, "--use-lxd"])

        self.mock_get_provider_for.assert_called_once_with("lxd")
        self.assertThat(result.exit_code, Equals(0))

    def test_destructive_mode(self):
        result = self.run_command([self.step, "--destructive-mode"])

        # Mock get_provider_for not called when using "host".
        self.mock_get_provider_for.assert_not_called()
        self.assertThat(result.exit_code, Equals(0))

    def test_host_build_env(self):
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "host")
        )

        result = self.run_command([self.step])

        self.mock_get_provider_for.assert_not_called()
        self.assertThat(result.exit_code, Equals(0))

    def test_invalid_clean_provider_build_env(self):
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "invalid")
        )

        result = self.run_command([self.step])

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_clean_provider_build_arg(self):
        result = self.run_command([self.step, "--provider", "invalid"])

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_combo_lxd_destructive(self):
        result = self.run_command([self.step, "--use-lxd", "--destructive-mode"])

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_combo_use_lxd_mismatch(self):
        result = self.run_command([self.step, "--use-lxd", "--provider", "host"])

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_combo_destructive_mode_mismatch(self):
        result = self.run_command(
            [self.step, "--destructive-mode", "--provider", "lxd"]
        )

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_host_without_destructive_mode(self):
        result = self.run_command([self.step, "--provider", "host"])

        self.assertThat(result.exit_code, Equals(2))

    def test_invalid_mismatch(self):
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )

        result = self.run_command([self.step, "--provider", "host"])

        self.assertThat(result.exit_code, Equals(2))


class ValidBuildEnvironmentParsingTests(BuildEnvironmentParsingTest):
    scenarios = [
        ("default", dict(env=None, arg=None, result="multipass")),
        ("host_env", dict(env="host", arg=None, result="host")),
        ("host_arg", dict(env=None, arg="host", result="host")),
        ("host_both", dict(env="host", arg="host", result="host")),
        ("lxd_env", dict(env="lxd", arg=None, result="lxd")),
        ("lxd_arg", dict(env=None, arg="lxd", result="lxd")),
        ("lxd_both", dict(env="lxd", arg="lxd", result="lxd")),
        ("multipass_env", dict(env="multipass", arg=None, result="multipass")),
        ("multipass_arg", dict(env=None, arg="multipass", result="multipass")),
        ("multipass_both", dict(env="multipass", arg="multipass", result="multipass")),
    ]

    def test_valid_clean_providers(self):
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", self.env)
        )

        if self.result == "host":
            result = self.run_command(
                [self.step, "--provider", self.arg, "--destructive-mode"]
            )

            self.mock_get_provider_for.assert_not_called()
        else:
            result = self.run_command([self.step, "--provider", self.arg])

            self.mock_get_provider_for.assert_called_once_with(self.result)

        self.assertThat(result.exit_code, Equals(0))


class BuildProviderYamlValidationTest(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )

        patcher = mock.patch(
            "snapcraft.internal.build_providers.get_provider_for",
            return_value=ProviderImpl,
        )
        self.provider = patcher.start()
        self.addCleanup(patcher.stop)

        self.useFixture(fixture_setup.FakeMultipass())

    def test_validation_passes(self):
        snapcraft_yaml = fixture_setup.SnapcraftYaml(self.path, base="core")
        snapcraft_yaml.update_part("part1", dict(plugin="nil"))
        self.useFixture(snapcraft_yaml)

        result = self.run_command(["pull"])

        self.assertThat(result.exit_code, Equals(0))

    def test_validation_fails(self):
        snapcraft_yaml = fixture_setup.SnapcraftYaml(
            self.path, name="name with spaces", base="core"
        )
        snapcraft_yaml.update_part("part1", dict(plugin="nil"))
        self.useFixture(snapcraft_yaml)

        self.assertRaises(
            project.errors.YamlValidationError, self.run_command, ["pull"]
        )


class BuildProviderDebugCommandTestCase(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )
        self.useFixture(fixture_setup.FakeMultipass())

        shell_mock = mock.Mock()

        class Provider(ProviderImpl):
            def execute_step(self, step: steps.Step) -> None:
                raise ProviderExecError(
                    provider_name="fake", command=["snapcraft", "pull"], exit_code=1
                )

            def shell(self):
                shell_mock()

        patcher = mock.patch(
            "snapcraft.internal.build_providers.get_provider_for", return_value=Provider
        )
        self.provider = patcher.start()
        self.addCleanup(patcher.stop)

        self.shell_mock = shell_mock

        self.make_snapcraft_yaml("pull", base="core")

    def test_step_with_debug_using_build_provider_fails(self):
        result = self.run_command(["--debug", "pull"])

        self.assertThat(result.exit_code, Equals(0))
        self.shell_mock.assert_called_once_with()

    def test_step_with_debug_after_pull_using_build_provider_fails(self):
        result = self.run_command(["pull", "--debug"])

        self.assertThat(result.exit_code, Equals(0))
        self.shell_mock.assert_called_once_with()

    def test_step_without_debug_using_build_provider_fails_and_does_not_shell(self):
        self.assertRaises(ProviderExecError, self.run_command, ["pull"])

        self.shell_mock.assert_not_called()


class BuildProviderShellCommandTestCase(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )
        self.useFixture(fixture_setup.FakeMultipass())

        shell_mock = mock.Mock()
        pack_project_mock = mock.Mock()
        execute_step_mock = mock.Mock()

        class Provider(ProviderImpl):
            def pack_project(self, *, output: Optional[str] = None) -> None:
                pack_project_mock(output)

            def execute_step(self, step: steps.Step) -> None:
                execute_step_mock(step)

            def shell(self):
                shell_mock()

        patcher = mock.patch(
            "snapcraft.internal.build_providers.get_provider_for", return_value=Provider
        )
        self.provider = patcher.start()
        self.addCleanup(patcher.stop)

        self.shell_mock = shell_mock
        self.pack_project_mock = pack_project_mock
        self.execute_step_mock = execute_step_mock

        self.make_snapcraft_yaml("pull", base="core")

    def test_step_with_shell_after(self):
        result = self.run_command(["pull", "--shell-after"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_called_once_with(steps.PULL)
        self.shell_mock.assert_called_once_with()

    def test_snap_with_shell_after(self):
        result = self.run_command(["snap", "--output", "fake.snap", "--shell-after"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_called_once_with("fake.snap")
        self.execute_step_mock.assert_not_called()
        self.shell_mock.assert_called_once_with()

    def test_step_without_shell_after_does_not_enter_shell(self):
        result = self.run_command(["pull"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_called_once_with(steps.PULL)
        self.shell_mock.assert_not_called()

    def test_error_with_shell_after_error_and_debug(self):
        self.shell_mock.side_effect = EnvironmentError("error")

        self.assertRaises(
            EnvironmentError, self.run_command, ["pull", "--shell-after", "--debug"]
        )

        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_called_once_with(steps.PULL)
        self.shell_mock.assert_called_once_with()

    def test_pull_step_with_shell(self):
        result = self.run_command(["pull", "--shell"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_not_called()
        self.shell_mock.assert_called_once_with()

    def test_step_with_shell(self):
        result = self.run_command(["stage", "--shell"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_called_once_with(steps.BUILD)
        self.shell_mock.assert_called_once_with()

    def test_snap_with_shell(self):
        result = self.run_command(["snap", "--shell"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_not_called()
        self.execute_step_mock.assert_called_once_with(steps.PRIME)
        self.shell_mock.assert_called_once_with()

    def test_snap_without_shell(self):
        result = self.run_command(["snap"])

        self.assertThat(result.exit_code, Equals(0))
        self.pack_project_mock.assert_called_once_with(None)
        self.execute_step_mock.assert_not_called()
        self.shell_mock.assert_not_called()


class BuildProviderTryCommandTestCase(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )
        self.useFixture(fixture_setup.FakeMultipass())

        mount_prime_mock = mock.Mock()

        class Provider(ProviderImpl):
            def _mount_prime_directory(self) -> None:
                mount_prime_mock()

        patcher = mock.patch(
            "snapcraft.internal.build_providers.get_provider_for", return_value=Provider
        )
        self.provider = patcher.start()
        self.addCleanup(patcher.stop)

        self.mount_prime_mock = mount_prime_mock

        self.make_snapcraft_yaml("pull", base="core")

    def test_try(self):
        result = self.run_command(["try"])

        self.assertThat(result.exit_code, Equals(0))
        self.mount_prime_mock.assert_called_once_with()


class BuildProviderCleanCommandTestCase(LifecycleCommandsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "multipass")
        )
        self.useFixture(fixture_setup.FakeMultipass())

        clean_project_mock = mock.Mock()
        clean_mock = mock.Mock()

        class Provider(ProviderImpl):
            def execute_step(self, step: steps.Step) -> None:
                raise ProviderExecError(
                    provider_name="fake", command=["snapcraft", "pull"], exit_code=1
                )

            def clean_project(self):
                clean_project_mock()

            def clean(self, part_names):
                clean_mock(part_names=part_names)

        patcher = mock.patch(
            "snapcraft.internal.build_providers.get_provider_for", return_value=Provider
        )
        self.provider = patcher.start()
        self.addCleanup(patcher.stop)

        self.clean_project_mock = clean_project_mock
        self.clean_mock = clean_mock

        self.make_snapcraft_yaml("pull", base="core")

    @mock.patch("snapcraft.internal.lifecycle.clean")
    def test_clean(self, lifecycle_clean_mock):
        result = self.run_command(["clean"])

        self.assertThat(result.exit_code, Equals(0))
        lifecycle_clean_mock.assert_called_once_with(mock.ANY, tuple(), steps.PRIME)
        self.clean_project_mock.assert_called_once_with()
        self.clean_mock.assert_not_called()

    def test_clean_a_single_part(self):
        result = self.run_command(["clean", "part1"])

        self.assertThat(result.exit_code, Equals(0))
        self.clean_project_mock.assert_not_called()
        self.clean_mock.assert_called_once_with(part_names=("part1",))

    def test_clean_multiple_parts(self):
        result = self.run_command(["clean", "part1", "part2", "part3"])

        self.assertThat(result.exit_code, Equals(0))
        self.clean_project_mock.assert_not_called()
        self.clean_mock.assert_called_once_with(part_names=("part1", "part2", "part3"))

    def test_unprime_with_build_environment_errors(self):
        result = self.run_command(["clean", "--unprime"])

        self.assertThat(result.exit_code, Equals(2))
        self.clean_project_mock.assert_not_called()
        self.clean_mock.assert_not_called()

    @mock.patch("snapcraft.cli.lifecycle.get_project")
    @mock.patch("snapcraft.internal.lifecycle.clean")
    def test_unprime_in_managed_host(self, lifecycle_clean_mock, get_project_mock):
        self.useFixture(
            fixtures.EnvironmentVariable("SNAPCRAFT_BUILD_ENVIRONMENT", "managed-host")
        )
        project_mock = mock.Mock()
        project_mock.info.base.return_value = "core"
        get_project_mock.return_value = project_mock

        result = self.run_command(["clean", "--unprime"])

        self.assertThat(result.exit_code, Equals(0))
        lifecycle_clean_mock.assert_called_once_with(project_mock, tuple(), steps.PRIME)
        self.clean_project_mock.assert_not_called()
        self.clean_mock.assert_not_called()
