# Ansible modules for YunoHost

**These modules are still pretty much experimental. In particular, testing has only been done manually at the moment.**

- These modules allow controlling more finely install or modifications to [YunoHost](https://yunohost.org/) installations (for now, applications only).

- It could go nicely with the following Ansible role at [github.com/LydraFr/ansible-yunohost](https://github.com/LydraFr/ansible-yunohost).

- Only the app module (`ynh_app.py`) exists as a draft for now.

- See the beginning of the `ynh_app.py` file for documentation and usage.

- Place these python files inside the `library/` directory of your Ansible project.
