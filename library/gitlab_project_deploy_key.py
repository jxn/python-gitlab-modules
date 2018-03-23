#!/usr/bin/python
# (c) 2018, Jackson Murtha, https://jxn.is
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: gitlab_project_deploy_key
short_description: enables an existing deploy key on Gitlab projects
description:
   - Operate on deploy keys by using the 'name' attribute
   - If state is 'present' the deploy key will be added to the project
   - If state is 'absent' the deploy key will be removed from the project
   - The project and deploy key should already exists when executing this module.
version_added: "2.6"
author: "Jackson Murtha (@jxn)"
requirements:
    - python-gitlab python module
options:
    server_url:
        description:
            - Url of Gitlab server, with protocol (http or https).
        required: true
    validate_certs:
        description:
            - When using https if SSL certificate needs to be verified.
        required: false
        default: true
        aliases:
            - verify_ssl
    login_user:
        description:
            - Gitlab user name.
        required: false
        default: null
    login_password:
        description:
            - Gitlab password for login_user
        required: false
        default: null
    login_token:
        description:
            - Gitlab token for logging in.
        required: false
        default: null
    project:
        description:
            - The namespace + project on which disable or enable the deploy key, in the form "namespace/project".
        required: true
        default: null
    profile:
        description:
            - configuration profile
        required: false
        default: null
    state:
        description:
            - enable or disable deploy keys.
        required: false
        default: "present"
        choices: ["present", "absent"]
    can_push:
        description:
            - Enable push permissions for the deploy key
        required: false
        default: false

'''

EXAMPLES = '''

- name: Enable existing key
  local_action:
    module: gitlab_project_deploy_key
    name: example-key-name
    profile: config_group_name
    project: my_group/my_project
    state: present
    validate_certs: false
- name: Enable existing key
  local_action:
    module: gitlab_project_deploy_key
    login_token: WxMnOO_py890Ev
    name: mykey-name
    project: my_group/my_project
    server_url: http://gitlab.yourdomain.com
    state: present
    can_push: true
'''

RETURN = '''# '''

try:
    import gitlab
    HAS_GITLAB_PACKAGE = True
except:
    HAS_GITLAB_PACKAGE = False

from ansible.module_utils.basic import *
from ansible.module_utils.pycompat24 import get_exception


class GitLabDeployKey(object):
    def __init__(self, module, git):
        self._module = module
        self._gitlab = git
        self.projectObject = None
        self.deployKeyObject = None

    def enableProjectDeployKey(self, key_can_push):
        """Enable deploy key for project"""
        project = self.projectObject

        try:
            project.keys.enable(self.deployKeyObject.id)
            self.deployKeyObject.can_push = key_can_push
            # Update will work when This is released: https://github.com/python-gitlab/python-gitlab/commit/9a30266d197c45b00bafd4cea2aa4ca30637046b
            self.deployKeyObject.save()
        except Exception:
            e = get_exception()
            self._module.fail_json(msg="Failed to enable deploy key: %s " % e)
        return 0, "deploy key enabled."

    def getDeployKey(self, key_name):
        deploy_keys = self._gitlab.deploykeys.list()
        if len(deploy_keys) >= 1:
            for key in deploy_keys:
                if (key.title == key_name):
                    self.deployKeyObject = self.projectObject.keys.get(key.id)
                    return True
        return False

    def getProject(self, project):
        """Fetches the project object from Gitlab API."""
        self.projectObject = self._gitlab.projects.get(project)
        return True

    def deleteDeployKey(self):
        """Delete deploy key"""

def main():
    module = AnsibleModule(
        argument_spec=dict(
            server_url=dict(required=False),
            validate_certs=dict(required=False, default=True, type='bool', aliases=['verify_ssl']),
            login_user=dict(required=False, no_log=True),
            login_password=dict(required=False, no_log=True),
            profile=dict(required=False),
            login_token=dict(required=False, no_log=True),
            project=dict(required=True),
            name=dict(required=True),
            state=dict(default="present", choices=["present", 'absent']),
            can_push=dict(default=False, required=False, type='bool'),
        ),
        supports_check_mode=True
    )

    if not HAS_GITLAB_PACKAGE:
        module.fail_json(msg="Missing required gitlab module (check docs or install with: pip install python-gitlab")

    server_url = module.params['server_url']
    verify_ssl = module.params['validate_certs']
    login_user = module.params['login_user']
    login_password = module.params['login_password']
    login_token = module.params['login_token']
    login_profile = module.params['profile']
    project = module.params['project']
    deploy_key_name = module.params['name']
    state = module.params['state']
    use_credentials = None
    use_token = None
    use_config = None
    can_push = module.params['can_push']

    # Validate some credentials configuration parameters.
    if login_user is not None and login_password is not None:
        use_credentials = True
    elif login_token is not None:
        use_credentials = False
    elif login_profile is not None:
        use_config = True
    else:
        module.fail_json(msg="No login credentials are given. Use login_user with login_password, or login_token")

    if login_token and login_user:
        module.fail_json(msg="You can either use 'login_token' or 'login_user' and 'login_password'")

    try:
        if use_credentials:
            git = gitlab.Gitlab(server_url, email=login_user, password=login_password, ssl_verify=verify_ssl)
            git.auth()
        elif use_token:
            git = gitlab.Gitlab(server_url, private_token=login_token, ssl_verify=verify_ssl)
            git.auth()
        else:
            git = gitlab.Gitlab.from_config(login_profile)
            git.auth()
    except Exception:
        e = get_exception()
        module.fail_json(msg="Failed to connect to Gitlab server: %s " % e)

    deploy_key = GitLabDeployKey(module, git)
    project_exists  = deploy_key.getProject(project=project)

    if not project_exists:
        module.fail_json(msg="The project or the group does not exists. This deploy key cannot be enabled.")

    deploy_key_exists = deploy_key.getDeployKey(key_name=deploy_key_name)

    if not deploy_key_exists:
        module.fail_json(msg="The deploy key with this name does not exist. This deploy key cannot be enabled.")

    (rc, out) = deploy_key.enableProjectDeployKey(key_can_push=can_push)

    module.exit_json(msg="success", result=out)

if __name__ == '__main__':
    main()

