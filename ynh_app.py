#!/usr/bin/python

# Copyright: (c) 2021, Hadrien <ketsapiwiq@protonmail.com>
# GNU Affero General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/agpl-3.0.txt)

from subprocess import Popen, PIPE
import json
from urllib.parse import urlencode
from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = """
---
module: ynh_app

short_description: Modify Yunohost app

description:
    - "This module calls yunohost CLI to modify apps install"

options:
    name:
        description:
            -  Name, local path or git URL of the app to install
        required: true
    label:
        description:
            - The label for the installed app
        required: false
    settings:
        description:
            - A dict of settings for the installed app, check app repo to know which ones to use
        required: false
    # force:
    #     description:
    #         - Do not ask confirmation if the app is not safe to use (low quality, experimental or 3rd party)
    #     required: false
    # upgraded:
    #     description:
    #         - Upgrade app if there is an upgrade available
    #     required: false
    domain:
        description:
            - The domain on which to install the app
        required: false
    state:
        description:
            - Whether 'present' or 'absent'
        required: true

author:
    - Hadrien (@ketsapiwiq)
"""

EXAMPLES = """
# Change app domain and settings
- name: Update the default domain
  ynh_app:
    name: wordpress
    domain: google.com
    settings:
        path: '/'
    label: Wordpress
"""

RETURN = """
# new_settings:
#     description: The new settings key-values
#     type: str
# reachable:
#     description: Whether the app is reachable at new URL
#     type: str
#     returned: always
# created:
#     description: Whether the app got created
#     type: bool
#     returned: always
uninstalled:
    description: Whether the app got uninstalled
    type: bool
    returned: sometimes
command:
    description: The command executed
    type: str
    returned: sometimes
state:
    description: A quick description of the app state
    type: str
    returned: always
# installed:
#     description: Whether the app got installed
#     type: bool
#     returned: sometimes
# changed_domain:
#     description: Whether the domain needed to be changed
#     type: bool
#     returned: always
"""


def get_app_info(name, verbose=False):
    try:
        if verbose:
            command = [
                "/usr/bin/yunohost",
                "app",
                "info",
                "--output-as",
                "json",
                "--full",
                name,
            ]
        else:
            command = ["/usr/bin/yunohost", "app", "info", "--output-as", "json", name]
        app_info_result = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = app_info_result.communicate()

        stdout = stdout.decode("UTF-8")
        stderr = stderr.decode("UTF-8")
        if app_info_result.returncode != 0:
            if "Could not find" in stderr:
                return False

            module.fail_json(
                msg="YunoHost returned an error for command: "
                + str(command)
                + "\nExit code:"
                + app_info_result.returncode
                + "\nError: "
                + str(stderr),
                **result
            )
        else:
            return json.loads(stdout)
    except OSError as e:
        module.fail_json(
            msg="Could not run CLI with command: "
            + str(command)
            + "\nError: "
            + str(e),
            **result
        )


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        id=dict(type="str", required=False),
        name=dict(type="str", required=False),
        label=dict(type="str", required=False),
        settings=dict(type="dict", required=False, default=dict()),
        domain=dict(type="str", required=False),
        # TODO: not implemented
        force=dict(type="bool", required=False, default=False),
        # TODO: not implemented
        # upgraded=dict(type='bool', required=False, default=False),
        state=dict(type="str", required=False, default="present"),
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(changed=False)

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # We parse arguments received and check for coherence
    # TODO: test and support installing a second app by playing with id and name e.g. grav__2

    # TODO: test coherence for this
    app_id = module.params["id"] or module.params["name"]
    app_name = module.params["name"] or module.params["id"]

    app_label = module.params["label"] or module.params["name"]
    app_domain = module.params["domain"]
    app_settings = module.params["settings"]
    app_args = urlencode({**dict(domain=app_domain), **app_settings})
    app_desired_state = module.params["state"]
    # app_upgraded = module.params['upgraded']
    # app_force = module.params['force']
    # TODO: add option to handle backup and/or purge?

    #  Check if app exists

    previous = get_app_info(app_name, True)
    app_was_present = bool(previous)

    result = dict(changed=False)

    # Apply changes in order
    if not app_was_present and app_desired_state == "absent":
        result["changed"] = False
        module.exit_json(**result)

    #  Uninstall if needed
    elif app_was_present and app_desired_state == "absent":

        result["uninstalled"] = True
        result["changed"] = True
        if module.check_mode:
            module.exit_json(**result)

        command = ["/usr/bin/yunohost", "app", "remove", app_id]
        change = Popen(command, stdout=PIPE, stderr=PIPE)
        result["command"] = command
        stdout, stderr = change.communicate()

        #   If app doesn't exist, create it with given params
    elif not app_was_present and app_desired_state == "present":

        result["installed"] = True
        result["changed"] = True
        result["app_args"] = app_args

        if module.check_mode:
            module.exit_json(**result)

        command = [
            "/usr/bin/yunohost",
            "app",
            "install",
            app_name,
            "--label",
            app_label,
            "--args",
            app_args,
            "--force",
        ]
        change = Popen(
            command,
            # domain=domain.tld&path=/path
            stdout=PIPE,
            stderr=PIPE,
        )
        result["command"] = command
        stdout, stderr = change.communicate()

    elif app_was_present and app_desired_state == "present":
        # This module doesn't support app modifications yet.
        result["changed"] = False
        result["app_args"] = app_args

        result["msg"] = "This module doesn't support app modifications yet."
        result["state"] = get_app_info(app_name)
        module.exit_json(**result)
        # TODO:
        # determine changes to do
        # FIXME: confusion between app url (github repo), app 'id' ('grav') and app name / unique id / 'settings.id' ('grav__2')
        #   0. Check if changes are coherent:  you can't change "url" (but it's not supposed to be possible, since it's also the unique ID, is it?)
        #   1. Need to install? Need to uninstall?
        #   1. Need to change label?
        #   2. Need to change some settings
        #   3. Need to change domain? Check if domain exists
        #   4. Need to upgrade?
        # 5. Build array of changed

        # 6. If check mode, return array of planned changed stuff and quit
        # If no change, quit now

        #   1. Change label if needed
        #   2. Change some settings if needed (and test reachability? Rollback if not?)
        #   3. Change domain if needed (and test reachability? Rollback if not?)
        #   4. Upgrade if needed

    else:
        module.fail_json(
            msg="Logic error: make sure 'state' is either present or absent"
        )

    result["state"] = get_app_info(app_name)

    result["stdout"] = stdout.decode("UTF-8")
    result["stderr"] = stderr.decode("UTF-8")
    result["rc"] = change.returncode
    if change.returncode != 0:
        module.fail_json(msg="Error when proceeding to change", **result)
    else:
        module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
