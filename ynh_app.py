#!/usr/bin/python

# Copyright: (c) 2021, Hadrien <ketsapiwiq@protonmail.com>
# GNU Affero General Public License v3.0+ (see COPYING or
# https://www.gnu.org/licenses/agpl-3.0.txt)

import os
import re
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
            -  Catalog name or Git URL of an app to install or unique ID of an already existing app (e.g. `grav__2`)
        required: true
    label:
        description:
            - The label for the app
        required: false
    domain:
        description:
            - The domain on which the app should be available
        required: false
    settings:
        description:
            - A list of key-pair settings values, check app manifest to know which ones to use (e.g. `path`)
        required: false
    force:
        description:
            - If `yes`, do not fail if the app is not safe to use (remote Git, low quality, experimental or 3rd party)
        required: false
    upgraded:
        description:
            - If `yes`, upgrade app if an upgrade is available
        required: false
    append:
        description:
            - If `yes`, add permissions specified in `permissions` to the app. If `no`, only permissions specified in `permissions` will be applied to the app, removing all other permissions.
        required: false
    permissions:
        description:
            - A list of allowed groups and users for the app, with `all_users` and `visitors` being special groups.  If `append=no` is set (by default), it will remove any permission not in that list, including `all_users` and `visitors`.
        required: false
    state:
        description:
            - Whether 'present' or 'absent'
        required: false

author:
    - Hadrien (@ketsapiwiq)
"""

EXAMPLES = """
- name: Update the default domain and path
  ynh_app:
    name: wordpress
    domain: my.yunohost.org
    settings:
        path: '/blog'
    label: Wordpress

- name: Uninstall app
ynh_app:
    name: dokuwiki
    state: absent

- name: Change domain and path
  ynh_app:
        name: dokuwiki
        domain: yuno.example.org
        path: /wiki

- name: Change label, domain and path
  ynh_app:
    name: dokuwiki
    settings:
        domain: example.org
    label: Spaghetti
    path: /doku

- name: Change permissions
  ynh_app:
    name: dokuwiki
    append: no
    permissions:
      - all_users

- name: Change permissions
  ynh_app:
    name: dokuwiki
    append: yes
    permissions:
      - visitors

- name: Add second instance
  ynh_app:
    id: dokuwiki__2
    name: dokuwiki
    label: DokuWiki 2
    domain: yuno.example.org
    settings:
        path: /wiki2

- name: Add third instance
  ynh_app:
    id: dokuwiki__3
    label: DokuWiki 3
    domain: yuno.example.org
    path: /wiki3
    append: no
    permissions:
      - lucas

- name: Remove second instance
  ynh_app:
    name: dokuwiki__2
    state: absent
"""

RETURN = """
installed:
    description: Whether the app got installed
    type: bool
    returned: changed
upgraded:
    description: Whether the app got upgraded
    type: bool
    returned: changed
uninstalled:
    description: Whether the app got uninstalled
    type: bool
    returned: changed
url:
    description: URL of the app
    type: str
    returned: always
commands:
    description: The list of change-inducing executed commands
    type: list
    returned: always
id:
    description: The ID of the app, useful when app got installed and it's a multi-instance install (e.g. `id=grav__2`)
    type: str
    returned: always
"""


def run_module():

    ########################################################################
    #  Helpers
    ########################################################################

    def _get_app_info(name, verbose=False):
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
                + str(rc)
                + "\nError: "
                + str(stderr),
                **result
            )
        else:
            return json.loads(stdout)

    def _change_setting(setting_str, new_value):
        if (setting_str in previous["settings"] and new_value !=
                previous["settings"][setting_str]) or setting_str not in previous["settings"]:
            result["changed"] = True
            result["diff"].append(
                {
                    "after": new_value+"\n",
                    "after_header": "setting "+setting_str+"\n",
                    "before": previous["settings"]["path"] or None,
                    "before_header": "setting "+setting_str+"\n",
                }
            )
            command = ["/usr/bin/yunohost", "app",
                       "setting", app_id, setting_str, "-v", new_value]
            # --output-as json?
            # TODO: append true or false for settings also? Else we should be able to delete settings with -d maybe?

            result["commands"].append(' '.join(command))
            if not module.check_mode:
                rc, stdout, stderr = module.run_command(
                    command, True)

    # TODO: list of denied as well? per permission? (not only main)

    def _change_permission(action, permission):
        result["changed"] = True
        if action != "add" and action != "remove":
            module.fail_json(
                msg="Unknown permission action: " + str(action), **result)

        command = ["/usr/bin/yunohost", "user",
                   "permission", action, app_id+".main", permission, "--output-as", "json"]

        result["commands"].append(' '.join(command))
        if not module.check_mode:
            rc, stdout, stderr = module.run_command(
                command, True)

    ########################################################################
    #  Setup
    ########################################################################

    # define available arguments/parameters a user can pass to the module
    # module.require_one_of("id", "name")
    module_args = dict(
        id=dict(type="str", required=False),
        name=dict(type="str", required=False),
        label=dict(type="str", required=False),
        settings=dict(type="dict", required=False, default={}),
        domain=dict(type="str", required=False),
        path=dict(type="str", required=False),
        append=dict(type="bool", required=False, default=False),
        permissions=dict(type="list", required=False,
                         elements="str", default=[]),
        # TODO: not implemented
        # force=dict(type="bool", required=False, default=False),
        upgraded=dict(type="bool", required=False, default=False),
        state=dict(type="str", required=False, default="present"),
    )

    # seed the result dict in the object
    # we primarily care about diff and changed
    # changed is if this module effectively modified the target
    # result = dict(changed=False)
    result = dict(changed=False, commands=[], diff=[])

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=True)

    # We parse arguments received and check for coherence

    # TODO: make it a function? check all cases
    app_id = module.params["id"]
    app_name = module.params["name"]

    if app_id:
        # if app_id ends with " __[0-9]+", extract the first part
        # if re.match(r"^.* __[0-9]+$", app_id):
        app_id_prefix = re.sub(r"__[0-9]+$", "", app_id)
        result["id"] = app_id

        # check if app_name and app_id are both set
        if app_name:
            if app_id_prefix != app_name:
                module.fail_json(
                    msg="Incoherent id and name, you should either set only id or name, or if you set both (e.g. to install a second instance of the same app), id should be of the form: `name__number`",
                    **result
                )
        else:
            app_name = app_id_prefix
            result["name"] = app_name
    elif not app_name:
        # TODO: handle this with "requireatleastone" ansible check
        module.fail_json(
            msg="You should either set id or name",
            **result
        )
    else:
        # app_id is not set and
        # app_name could be a url or a name
        # so we can't simply do app_id = app_name
        # check if app_name is a url
        if re.match(r"^https?://", app_name):
            # this is an url, we can extract the name from it because app_id = [app_name]_ynh
            # TODO: we can use functions from yunohost/src/app.py instead to extract name from URL in a more reliable way
            m = re.match(r"([A-z0-9_-])+_ynh", app_name)
            if m:
                app_id = m.group(1)
                result["id"] = app_id
            else:
                module.fail_json(
                    msg="Could not extract name from URL",
                    **result
                )
        else:
            app_id = app_name
            result["id"] = app_id

    app_label = module.params["label"]
    # priority being given to the upper-level params domain and path over when they're settings children
    app_domain = module.params["domain"] or module.params["settings"].get(
        "domain")
    if app_domain and "domain" in module.params["settings"] and module.params["settings"]["domain"] != app_domain:
        module.fail_json(
            msg="You can't set both domain and settings.domain, please use only one of them"
        )
    app_path = module.params["path"] or module.params["settings"].get("path")

    if app_path and "path" in module.params["settings"] and module.params["settings"]["path"] != app_path:
        # raise MutuallyExclusiveError(
        #     "You can't set both path and settings.path, please use only one of them"
        # )
        # module.fail_on_mutually_exclusive(
        #     [
        #         ("domain", "path"),
        #         ("domain", "settings.domain"),
        #         ("path", "settings.path"),
        #     ]
        # )
        module.fail_json(
            msg="You can't set both 'path' and 'settings.path' at the same time",
        )

    app_settings = module.params["settings"]
    app_desired_state = module.params["state"]
    if app_desired_state not in ["absent", "present"] and app_desired_state != None:
        module.fail_json(
            msg="Invalid state: " + app_desired_state,
            **result
        )
    # app_public = module.params["public"]
    # TODO: should we implement a reset permissions? (= implement actions) it exists in yunohost (= all_users)
    app_permissions = module.params["permissions"]
    app_upgrade = module.params["upgraded"]
    # app_force = module.params['force'] # by default
    # TODO: add option to handle backup and/or purge?

    app_args = urlencode({**dict(domain=app_domain), **app_settings})

    ########################################################################
    #  Check if Yunohost is installed
    ########################################################################

    if not os.path.exists("/usr/bin/yunohost"):
        module.fail_json(
            msg="Yunohost is not installed on the host."
        )

    ########################################################################
    #  Check if app exists
    ########################################################################

    previous = _get_app_info(app_id, True)
    app_was_present = bool(previous)
    if app_was_present:

        app_name = previous["manifest"]["id"]
        if not app_label:
            app_label = previous["name"]

    ########################################################################
    # Check if we need to install a second instance
    ########################################################################

    # module params to make the app install a second instance: specify id with ([a-z])__[0-9]+ and make it deduct if app doesn't exist that you have to install an app with name if specified or name="([a-z])"

    # Then, try simple changes (e.g. has to be installed or uninstalled)

    ########################################################################
    #  Uninstall if needed
    ########################################################################

    if not app_was_present and app_desired_state == "absent":
        result["changed"] = False
        result["msg"] = "App '" + app_id + "' is already absent"
        module.exit_json(**result)

    if app_was_present and app_desired_state == "absent":

        result["uninstalled"] = True
        result["changed"] = True
        command = ["/usr/bin/yunohost", "app", "remove", app_id]
        # --output-as json?

        result["commands"].append(' '.join(command))

        if module.check_mode:
            module.exit_json(**result)

        app_uninstall_result = module.run_command(command, True)

    ########################################################################
    #   If app doesn't exist, install it with given params
    ########################################################################

    elif not app_was_present and app_desired_state == "present":

        result["installed"] = True
        result["changed"] = True
        # should play ok with multi instance
        result["id"] = app_id

        # should we parse app install output to get app_id in case of multi install ?
        #   app_id = json.loads(stdout)['id']
        # _get_app_info(name=app_name)

        # Domain is mandatory for installing apps

        if not app_domain:
            module.fail_on_missing_params(["domain"])

        command = [
            "/usr/bin/yunohost",
            "app",
            "install",
            app_name,
            "--args",
            app_args,
            "--force",
        ]
        if app_label:
            command.append("--label")
            command.append(app_label)

        result["commands"].append(' '.join(command))

        if not module.check_mode:
            rc, stdout, stderr = module.run_command(command, True)

        # FIXME: do a _get_app_info(name=app_id) to get label (and fiddle with app_id?)
        after_install = _get_app_info(name=app_id)
        # gotta use None in case it's check_mode
        if module.check_mode:
            # We could get the label from the manifest but it's a bit overkill
            app_label = app_name.capitalize()
        else:
            app_label = after_install["name"]

    ########################################################################
    # If already installed, change app install
    ########################################################################

    elif app_was_present and app_desired_state == "present":

        ###################################################################
        #   Change label if needed
        ###################################################################

        if app_label and app_label != previous['label']:
            result["changed"] = True
            result["diff"].append(
                {
                    "after": app_label+"\n",
                    "after_header": "label",
                    "before": previous['label']+"\n",
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
                app_label,
            ]

            result["commands"].append(' '.join(command))
            if not module.check_mode:
                rc, stdout, stderr = module.run_command(command, True)

        ###################################################################
        #   Change domain and path if needed
        ###################################################################

        url_changed = False

        if app_domain:
            if previous["settings"]["domain"] and app_domain != previous["settings"]["domain"]:
                url_changed = True
                result["diff"].append({
                    "after": app_domain+"\n",
                    "after_header": "domain",
                    "before": previous["settings"]["domain"]+"\n",
                    "before_header": "domain"
                })
        else:
            app_domain = previous["settings"]["domain"]

        if app_path:
            if previous["settings"]["path"] and app_path != previous["settings"]["path"]:
                url_changed = True
                result["diff"].append({
                    "before_header": "path",
                    "after": app_path+"\n",
                    "after_header": "path",
                    "before": previous["settings"]["path"]+"\n",
                })
        else:
            app_path = previous["settings"]["path"]

        if url_changed:
            result["changed"] = True
            command = [
                "/usr/bin/yunohost",
                "app",
                "change-url",
                app_id,
                "--domain",
                app_domain,
                "--output-as",
                "json"
            ]
            if app_path:
                command.append("--path")
                command.append(app_path)

            result["commands"].append(' '.join(command))

            if not module.check_mode:
                rc, stdout, stderr = module.run_command(command, True)

        result["url"] = str(app_domain)+str(app_path)

        #######################################################################
        # Upgrade if needed
        #######################################################################

        # Alternative cmd:
        # /usr/share/yunohost/helpers.d/utils
        # if(ynh_check_app_version_changed):
        #     ynh_upgrade_needed

        # Should we always check for `upgradable`?
        if app_upgrade:

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
                    for i, app in enumerate(json.loads(stdout)['apps'])
                    if module.params["id"] == app.id
                ),
                False,
            )
            if app:
                result["changed"] = True
                result["upgraded"] = True
                command = ["/usr/bin/yunohost", "app", "update", app_id]
                commands.append(command.join(' '))
                result["diff"].append(
                    {
                        "after": app.new_version+"\n",
                        "after_header": "version",
                        "before": app.current_version+"\n",
                        "before_header": "version",
                    }
                )
                if not module.check_mode:
                    module.run_command(command)

        # End of "if installed", settings and permissions tweaks happen in any
        # case the app should be present
    if app_desired_state == "present":

        # We can now return label that was set in all cases
        result["label"] = app_label

        #######################################################################
        #  Change settings if needed
        #######################################################################

        for setting_key, setting_value in app_settings.items():
            # check_mode check is done inside the function
            # Ignore domain and path values in order to avoid setting them through the _change_setting function
            if setting_key != 'domain' and setting_key != 'path':
                _change_setting(setting_key, setting_value)

        #######################################################################
        #   Change permissions if needed
        #######################################################################

        # yunohost user permission list dokuwiki --output-as json
        # {"permissions": {"dokuwiki.main": {"allowed": ["visitors", "all_users"]}, "dokuwiki.admin": {"allowed": ["user"]}}}

        # TODO: Check alias is needed between app.main and app
        #         root@ynh:~# yunohost user permission add dokuwiki visitors all_users --output-as json
        # Warning: Group 'visitors' already has permission 'dokuwiki.main' enabled
        # Warning: Group 'all_users' already has permission 'dokuwiki.main' enabled
        # {"allowed": ["visitors", "all_users"], "corresponding_users": ["lucas", "leadelmaire", "elie"], "auth_header": true, "label": "Wikiwiki", "show_tile": true, "protected": false, "url": "/", "additional_urls": []}
        # ...
        # root@ynh:~# yunohost user permission remove dokuwiki visitors --output-as json
        # Warning: Group 'visitors' already has permission 'dokuwiki.main' disabled
        # Warning: Group 'all_users' already has permission 'dokuwiki.main' disabled
        # {"allowed": [], "corresponding_users": [], "auth_header": true, "label": "Wikiwiki", "show_tile": true, "protected": false, "url": "/", "additional_urls": []}

        # if public in module.params:
        #     _change_permission('add', app_id, 'visitors')

        # FIXME: not needed because included in app full info
        if app_permissions:
            command = [
                "/usr/bin/yunohost",
                "user",
                "permission",
                "list",
                # app_id + ".main",
                app_id,
                "--output-as",
                "json",
            ]

            rc, stdout, stderr = module.run_command(command, True)
            old_permissions = json.loads(
                stdout)["permissions"][app_id+".main"]["allowed"]

            if not module.params["append"]:
                for old_permission in old_permissions:
                    if old_permission not in app_permissions:
                        _change_permission("remove", old_permission)

            for new_permission in app_permissions:
                if new_permission not in old_permissions:
                    _change_permission("add", new_permission)

            if not module.params["append"]:
                final_permissions = app_permissions
            else:
                final_permissions = old_permissions + app_permissions

            result["diff"].append(
                {
                    "before_header": "allowed for "+app_id+".main",
                    "after_header": "allowed for "+app_id+".main",
                    "before": "\n".join(old_permissions)+"\n",
                    "after": "\n".join(final_permissions)+"\n",
                }
            )

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
