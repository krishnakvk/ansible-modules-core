#!/usr/bin/python
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
#

DOCUMENTATION = """
---
module: ios_command
version_added: "2.1"
author: "Peter Sprygada (@privateip)"
short_description: Run commands on remote devices running Cisco IOS
description:
  - Sends arbitrary commands to an ios node and returns the results
    read from the device. This module includes an
    argument that will cause the module to wait for a specific condition
    before returning or timing out if the condition is not met.
  - This module does not support running commands in configuration mode.
    Please use M(ios_config) to configure IOS devices.
extends_documentation_fragment: ios
options:
  commands:
    description:
      - List of commands to send to the remote ios device over the
        configured provider. The resulting output from the command
        is returned. If the I(wait_for) argument is provided, the
        module is not returned until the condition is satisfied or
        the number of retries has expired.
    required: true
  wait_for:
    description:
      - List of conditions to evaluate against the output of the
        command. The task will wait for each condition to be true
        before moving forward. If the conditional is not true
        within the configured number of retries, the task fails.
        See examples.
    required: false
    default: null
    aliases: ['waitfor']
    version_added: "2.2"
  retries:
    description:
      - Specifies the number of retries a command should by tried
        before it is considered failed. The command is run on the
        target device every retry and evaluated against the
        I(wait_for) conditions.
    required: false
    default: 10
  interval:
    description:
      - Configures the interval in seconds to wait between retries
        of the command. If the command does not pass the specified
        conditions, the interval indicates how long to wait before
        trying the command again.
    required: false
    default: 1
"""

EXAMPLES = """
# Note: examples below use the following provider dict to handle
#       transport and authentication to the node.
vars:
  cli:
    host: "{{ inventory_hostname }}"
    username: cisco
    password: cisco
    transport: cli

tasks:
  - name: run show version on remote devices
    ios_command:
      commands: show version
      provider "{{ cli }}"

  - name: run show version and check to see if output contains IOS
    ios_command:
      commands: show version
      wait_for: result[0] contains IOS
      provider "{{ cli }}"

  - name: run multiple commands on remote nodes
     ios_command:
      commands:
        - show version
        - show interfaces
      provider "{{ cli }}"

  - name: run multiple commands and evaluate the output
    ios_command:
      commands:
        - show version
        - show interfaces
      wait_for:
        - result[0] contains IOS
        - result[1] contains Loopback0
      provider: "{{ cli }}"
"""

RETURN = """
stdout:
  description: The set of responses from the commands
  returned: always
  type: list
  sample: ['...', '...']

stdout_lines:
  description: The value of stdout split into a list
  returned: always
  type: list
  sample: [['...', '...'], ['...'], ['...']]

failed_conditions:
  description: The list of conditionals that have failed
  returned: failed
  type: list
  sample: ['...', '...']

warnings:
  description: The list of warnings (if any) generated by module based on arguments
  returned: always
  type: list
  sample: ['...', '...']
"""
from ansible.module_utils.basic import get_exception
from ansible.module_utils.netcmd import CommandRunner, FailedConditionsError
from ansible.module_utils.ios import NetworkModule, NetworkError

def to_lines(stdout):
    for item in stdout:
        if isinstance(item, basestring):
            item = str(item).split('\n')
        yield item

def main():
    spec = dict(
        commands=dict(type='list', required=True),
        wait_for=dict(type='list', aliases=['waitfor']),
        retries=dict(default=10, type='int'),
        interval=dict(default=1, type='int')
    )

    module = NetworkModule(argument_spec=spec,
                           connect_on_load=False,
                           supports_check_mode=True)

    commands = module.params['commands']
    conditionals = module.params['wait_for'] or list()

    warnings = list()

    runner = CommandRunner(module)

    for cmd in commands:
        if module.check_mode and not cmd.startswith('show'):
            warnings.append('only show commands are supported when using '
                            'check mode, not executing `%s`' % cmd)
        else:
            if cmd.startswith('conf'):
                module.fail_json(msg='ios_command does not support running '
                                     'config mode commands.  Please use '
                                     'ios_config instead')
            runner.add_command(cmd)

    for item in conditionals:
        runner.add_conditional(item)

    runner.retries = module.params['retries']
    runner.interval = module.params['interval']

    try:
        runner.run()
    except FailedConditionsError:
        exc = get_exception()
        module.fail_json(msg=str(exc), failed_conditions=exc.failed_conditions)
    except NetworkError:
        exc = get_exception()
        module.fail_json(msg=str(exc))

    result = dict(changed=False)

    result['stdout'] = list()
    for cmd in commands:
        try:
            output = runner.get_command(cmd)
        except ValueError:
            output = 'command not executed due to check_mode, see warnings'
        result['stdout'].append(output)


    result['warnings'] = warnings
    result['stdout_lines'] = list(to_lines(result['stdout']))

    module.exit_json(**result)


if __name__ == '__main__':
    main()

