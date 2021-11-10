import json

import os
import pytest
import unittest
from unittest.mock import patch
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes
import ynh_app


def set_module_args(args):
    """prepare arguments so that they will be picked up during module creation"""
    args = json.dumps({'ANSIBLE_MODULE_ARGS': args})
    basic._ANSIBLE_ARGS = to_bytes(args)


class AnsibleExitJson(Exception):
    """Exception class to be raised by module.exit_json and caught by the test case"""
    pass


class AnsibleFailJson(Exception):
    """Exception class to be raised by module.fail_json and caught by the test case"""
    pass


def exit_json(*args, **kwargs):
    """function to patch over exit_json; package return data into an exception"""
    if 'changed' not in kwargs:
        kwargs['changed'] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    """function to patch over fail_json; package return data into an exception"""
    kwargs['failed'] = True
    raise AnsibleFailJson(kwargs)


def os_ynh_present(self): return True


def yunohost(self, command, check_rc=False):
    """Mock run_command when app doesn't exist"""
    if command[1] == "app":
        # if command[2] == "list":
        #     return (0, "{'apps': []}", "")
        # if command[2] == "info":
        #     return (1, "", "Could not find app")
        elif command[2] == "install":
            return (0, '{"name": "app", "id": "app"}', "")
        if command[2] == "list":
            return (0, '{"apps": {"patate": {"domain": "yuno.patate.fr", "installed": true}', "")
        elif command[2] == "info":
            return (0, "{'name': 'test', 'description': 'test', 'state': 'installed', 'type': 'app', 'path': '/home/test/test'}", "")


class TestYnhApp(unittest.TestCase):

    def setUp(self):
        self.mock_module_helper = patch.multiple(basic.AnsibleModule,
                                                 exit_json=exit_json,
                                                 fail_json=fail_json,
                                                 yunohost=yunohost)
        self.mock_module_helper_os = patch.object(
            os.path, "exists", os_ynh_present)
        self.mock_module_helper.start()
        self.mock_module_helper_os.start()
        self.addCleanup(self.mock_module_helper.stop)
        self.addCleanup(self.mock_module_helper_os.stop)

    def test_module_fail_when_required_args_missing(self):
        with self.assertRaises(AnsibleFailJson):
            set_module_args({})
            ynh_app.main()

    def test_ensure_app_installed(self):
        set_module_args(
            {"name": "patate", "domain": "yuno.patate.fr"}
        )

        with patch.object(basic.AnsibleModule, '_get_info') as mock_nonexisting:

            with self.assertRaises(AnsibleExitJson) as result:
                ynh_app.main()
                # ensure result is changed
                self.assertFalse(result.exception.args[0]['changed'])

            # assert stdout='{"apps": {"patate": {"domain": "yuno.patate.fr", "installed": true}}}'

        mock_nonexisting.assert_called_once_with(
            "/usr/bin/yunohost app list")
        mock_nonexisting.assert_called_once_with(
            "/usr/bin/yunohost app install patate")

    def test_ensure_app_uninstalled(self):

        set_module_args(
            {"name": "patate", "domain": "yuno.patate.fr", "state": "absent"}
        )

        with patch.object(basic.AnsibleModule, 'run_command', run_command_existing) as mock_existing:
            mock_existing = run_command_existing(self, command)
            with self.assertRaises(AnsibleExitJson) as result:
                ynh_app.main()
            # ensure result is changed
            self.assertFalse(result.exception.args[0]['changed'])
            self.assertTrue(
                result == {"apps": {"patate": {"domain": "yuno.patate.fr", "installed": False}}})

        mock_existing.assert_called_once_with(
            "/usr/bin/yunohost app list")
        mock_existing.assert_called_once_with(
            "/usr/bin/yunohost app uninstall patate")

# if (sys.argv[1] == "user" and sys.argv[2] == "permission" and sys.argv[3] == "list"):
#     print(json.dumps({"permissions": {"dokuwiki.main": {"allowed": [
#         "visitors", "all_users"]}, "dokuwiki.admin": {"allowed": ["user"]}}}))
# # then check if command is "test/bin/yunohost app install patate --args domain=None --force --output-as json" and return mockup json answer
# elif (sys.argv[1] == "app" and sys.argv[2] == "install" and sys.argv[3] == "patate" and sys.argv[4] == "--args"):
#     print(json.dumps({"id": "patate", "app_name": "patate", "app_description": "patate", "app_icon": "patate", "app_url": "patate", "app_category": "patate", "app_version": "patate", "label": "patate", "app_permissions": {"dokuwiki.main": {"allowed": [
#         "visitors", "all_users"]}, "dokuwiki.admin": {"allowed": ["user"]}}}))
# else:
#     sys.exit("Could not find")
