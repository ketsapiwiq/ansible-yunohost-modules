# Ansible modules for YunoHost

**These modules are still pretty much experimental. In particular, testing has only been done manually at the moment.**

- These modules allow controlling more finely install or modifications to [YunoHost](https://yunohost.org/) installations (for now, applications only).

- It could go nicely with the following Ansible role at [github.com/LydraFr/ansible-yunohost](https://github.com/LydraFr/ansible-yunohost).

- Only the app module (`ynh_app.py`) exists as a draft for now.

- See the beginning of the `ynh_app.py` file for documentation and usage.

- Place these python files inside the `library/` directory of your Ansible project.

## Examples

```yml
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
        domain: yuno.doxx.fr
        path: /wiki

- name: Change label, domain and path
  ynh_app:
    name: dokuwiki
    settings:
        domain: doxx.fr
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
    domain: yuno.doxx.fr
    settings:
        path: /wiki2

- name: Add third instance
  ynh_app:
    id: dokuwiki__3
    label: DokuWiki 3
    domain: yuno.doxx.fr
    path: /wiki3
    append: no
    permissions:
      - lucas

- name: Remove second instance
  ynh_app:
    name: dokuwiki__2
    state: absent
```
