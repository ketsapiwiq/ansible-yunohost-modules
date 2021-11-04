#!/usr/bin/python

# Copyright: (c) 2021, Hadrien <ketsapiwiq@protonmail.com>
# GNU Affero General Public License v3.0+ (see COPYING or
# https://www.gnu.org/licenses/agpl-3.0.txt)

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
    # FIXME: confusion between app url (github repo), app 'id' ('grav') and app name / unique id / 'settings.id' ('grav__2')

    id:
        description:
            -  ID of an already existing app
        required: false
    name:
        description:
            -  Name, local path or git URL of the app to install
        required: true
    label:
        description:
            - The label for the installed app
        required: false
    domain:
        description:
            - The domain on which to install the app
        required: false
    settings:
        description:
            - A dict of settings for the installed app, check app repo to know which ones to use (e.g. path)
        required: false
    # force:
    #     description:
    #         - Do not ask confirmation if the app is not safe to use (low quality, experimental or 3rd party)
    #     required: false
    upgrade:
        description:
            - Upgrade app if there is an upgrade available
        required: false
        default: false
    append:
        description:
            - If `yes`, add permissions specified in `permissions` to the app. If `no`, only permissions specified in `permissions` will be applied to the app, removing all other permissions.
        default: false
        required: false
    permissions:
        description:
            - A list of allowed groups and users for the app, with `all_users` and `visitors` being special groups.  If `append=no` is set (by default), it will remove any permission not in that list, including `all_users` and `visitors`.
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
installed:
    description: Whether the app got installed
    type: bool
    returned: sometimes
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
# changed_domain:
#     description: Whether the domain needed to be changed
#     type: bool
#     returned: always
"""

########################################################################
#  Helpers
########################################################################


def get_app_info(name, verbose=False):
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
        command = ["/usr/bin/yunohost", "app",
                   "info", "--output-as", "json", name]
    rc, stdout, stderr = module.run_command(command)

    if rc != 0:
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


def change_setting(setting_str, new_value):
    if (setting_str in previous.settings and new_value !=
            previous.settings[setting_str]) or setting_str not in previous.settings:
        result["changed"] = True
        # result['settings'].append(...)
        result["diff"].append(
            {
                "after": new_value,
                "after_header": "path",
                "before": previous.settings.path or None,
                "before_header": "path",
            }
        )
        command = ["/usr/bin/yunohost", "app", "update", new_value]
        # --output-as json?

        result["commands"].append(command)
        if not module.check_mode:
            app_change_setting[setting_str] = module.run_command(command, True)


# FIXME: list of allowed or dict of allowed/denied? (or two lists?)


def change_permission(action, permission):
    raise NotImplementedError()


def run_module():

    ########################################################################
    #  Setup
    ########################################################################

    # define available arguments/parameters a user can pass to the module
    # module.require_one_of("id", "name")
    module_args = dict(
        #         # FIXME: confusion between app url (github repo), app 'id' ('grav') and app name / unique id / 'settings.id' ('grav__2')
        id=dict(type="str", required=False),
        name=dict(type="str", required=False),
        label=dict(type="str", required=False),
        settings=dict(type="dict", required=False, default=dict()),
        domain=dict(type="str", required=False),
        append=dict(type="bool", required=False, default=False),
        permissions=dict(type="dict", required=False, default=False),
        # TODO: not implemented
        # force=dict(type="bool", required=False, default=False),
        upgrade=dict(type="bool", required=False, default=False),
        state=dict(type="str", required=False, default="present"),
    )

    # seed the result dict in the object
    # we primarily care about diff, changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(changed=False, diff=list())

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # We parse arguments received and check for coherence
    # TODO: test and support installing a second app by playing with id and
    # name e.g. grav__2

    # TODO: test coherence for id and name and make it a function
    app_id = module.params["id"] or module.params["name"]
    app_name = module.params["name"] or module.params["id"]
    app_label = module.params["label"]
    # TODO: check require app_domain if install == True
    app_domain = module.params["domain"]
    app_settings = module.params["settings"]
    app_desired_state = module.params["state"]
    app_public = module.params["public"]
    # TODO: should we implement a reset permissions? it exists in yunohost
    app_permissions = module.params["permissions"]
    app_upgrade = module.params["upgrade"]
    # app_force = module.params['force']
    # TODO: add option to handle backup and/or purge?

    app_args = urlencode({**dict(domain=app_domain), **app_settings})

    ########################################################################
    #  Check if app exists
    ########################################################################

    previous = get_app_info(app_name, True)
    app_was_present = bool(previous)

    result = dict(changed=False)

    result.commands = list()

    if not (app_desired_state == "absent" or app_desired_state == "present"):
        module.fail_on_missing_params("state")
    # First, try simple changes (e.g. has to be installed or uninstalled)

    ########################################################################
    #  Uninstall if needed
    ########################################################################

    if app_was_present and app_desired_state == "absent":

        result["uninstalled"] = True
        result["changed"] = True
        command = ["/usr/bin/yunohost", "app", "remove", module.params.id]
        # --output-as json?

        result["commands"].append(command)

        if module.check_mode:
            module.exit_json(**result)

        app_uninstall_result = module.run_command(command, True)

    ########################################################################
    #   If app doesn't exist, create it with given params
    ########################################################################

    elif not app_was_present and app_desired_state == "present":

        result["installed"] = True
        result["changed"] = True
        result["install_app_args"] = app_args
        # use result.diff?

        # TODO: check this label logic
        if label in module.params:
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
                # --output-as json ?
            ]
        else:
            command = [
                "/usr/bin/yunohost",
                "app",
                "install",
                app_name,
                "--args",
                app_args,
                "--force",
                "--output-as",
                "json",
            ]

        result["commands"].append(command)

        if not module.check_mode:
            # TODO: test domain+ path has correctly been set
            rc, stdout, stderr = module.run_command(command, True)
            # TODO: test app_id has correctly been set
            app_id = json.loads(stdout).id

    ########################################################################
    # If already installed, change app install
    ########################################################################

    elif app_was_present and app_desired_state == "present":

        if app_label != previous.label:
            result["changed"] = True
            result["diff"].append(
                {
                    "after": app_label,
                    "after_header": "label",
                    "before": previous.label,
                    "before_header": "label",
                }
            )
            command = [
                "/usr/bin/yunohost",
                "user",
                "permission",
                "update",
                app_id,
                "--label",
                app_name,
            ]

            result["commands"].append(command)
            if not module.check_mode:
                rc, stdout, stderr = module.run_command(command, True)

            ###################################################################
            #   Change domain if needed
            ###################################################################

            # FIXME: Isn't it with a custom command? or change_setting()?
            # if previous.settings.domain and (domain in module.params or domain in module.params['settings']):
            # new_domain = module.params['domain'] or module.params['settings']['domain']
            # if(new_domain != previous.settings.domain):
            #     result["changed"] = True
            #     result["diff"].append({
            #         "after": app_domain,
            #         "after_header": "domain",
            #         "before": previous.settings.domain,
            #         "before_header": "domain"
            #     })

            if domain in module.settings:
                # check_mode check is done inside the function
                change_setting("domain", app_domain)

        #######################################################################
        #   Change path if needed
        #######################################################################

        # FIXME: what if path doesn't exist? check diff between path and url
        #  FIXME: if path was not set but is being set

        # if path in module.settings:
        #     # FIXME: Does this regen the nginx conf properly?
        #     change_setting("path", module.settings['path'])

        #######################################################################
        # Upgrade if needed
        #######################################################################
        # Alternative cmd:
        # /usr/share/yunohost/helpers.d/utils
        # if(ynh_check_app_version_changed):
        #     ynh_upgrade_needed

        command = [
            "/usr/bin/yunohost",
            "tools",
            "update",
            "apps",
            "--output-as",
            "json",
        ]

        rc, stdout, stderr = module.run_command(command, True)

        app = next(
            (
                i
                for i, app in enumerate(json.loads(stdout).apps)
                if module.params["id"] == app.id
            ),
            False,
        )
        #  if any(app_id == app.id for app in json.loads(stdout).apps):
        if app:
            if module.params["upgrade"]:
                result["changed"] = True
                # TODO: check command
                command = ["/usr/bin/yunohost", "app", "update", app_id]
                commands.append(command)
                # TODO: get previous.version always?
                result["diff"].append(
                    {
                        "after": app.new_version,
                        "after_header": "version",
                        "before": app.current_version,
                        "before_header": "version",
                    }
                )
                if not module.check_mode:
                    module.run_command(command)
            else:
                result["upgradable"] = True

        #  Need to change label?
        # End of "if installed", settings and permissions tweaks happen in any
        # case the app should be present
    if app_desired_state == "present":

        #######################################################################
        #  Change settings if needed
        #######################################################################

        # FIXME: check if domain and settings.domain are not both set (settings.domain should be ineffective maybe?)
        # FIXME: don't change domain and path settings twice
        # TODO: actually only use settings and drop domain and path no?
        for setting in settings:
            # check_mode check is done inside the function
            change_setting(setting)

        # TODO: As diff?
        # result["settings"] = app_settings

        #######################################################################
        #   Change permissions if needed
        #######################################################################

        # yunohost user permission list dokuwiki --output-as json
        # {"permissions": {"dokuwiki.main": {"allowed": ["visitors", "all_users"]}, "dokuwiki.admin": {"allowed": ["user"]}}}

        # TODO: Check alias is done between app.main and app
        #         root@ynh:~# yunohost user permission add dokuwiki visitors all_users --output-as json
        # Warning: Group 'visitors' already has permission 'dokuwiki.main' enabled
        # Warning: Group 'all_users' already has permission 'dokuwiki.main' enabled
        # {"allowed": ["visitors", "all_users"], "corresponding_users": ["lucas", "leadelmaire", "elie"], "auth_header": true, "label": "Wikiwiki", "show_tile": true, "protected": false, "url": "/", "additional_urls": []}
        # ...
        # root@ynh:~# yunohost user permission remove dokuwiki visitors --output-as json
        # Warning: Group 'visitors' already has permission 'dokuwiki.main' disabled
        # Warning: Group 'all_users' already has permission 'dokuwiki.main' disabled
        # {"allowed": [], "corresponding_users": [], "auth_header": true, "label": "Wikiwiki", "show_tile": true, "protected": false, "url": "/", "additional_urls": []}

        command = [
            "yunohost",
            "user",
            "permission",
            "list",
            app_id,
            "--output-as",
            "json",
        ]
        rc, stdout, stderr = module.run_command(command, True)
        list_permissions = json.loads(stdout)

        # if public in module.params:
        #     change_permission('add', app_id, 'visitors')

        if permissions in module.params:
            if not module.params.append:
                for permission in list_permissions:
                    if permission not in module.params[permissions]:
                        change_permission("delete", permission)

            for permission in module.params[permissions]:
                if permission not in list_permissions:
                    change_permission("add", permission)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
