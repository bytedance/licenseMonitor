import os
import sys
import stat

CWD = os.getcwd()
PYTHON_PATH = os.path.dirname(os.path.abspath(sys.executable))


def check_python_version():
    """
    Check python version.
    python3 is required, anaconda3 is better.
    """
    print('>>> Check python version.')

    current_python = sys.version_info[:2]
    required_python = (3, 8)

    if current_python < required_python:
        sys.stderr.write("""
==========================
Unsupported Python version
==========================
lsfMonitor requires Python {}.{},
Current python is Python {}.{}.
""".format(*(required_python + current_python)))
        sys.exit(1)
    else:
        print('    Required python version : ' + str(required_python))
        print('    Current  python version : ' + str(current_python))


def gen_shell_tools():
    """
    Generate shell scripts under <LICENSE_MONITOR_INSTALL_PATH>/tools.
    """
    tool_list = ['bin/license_monitor', 'tools/config_product_feature_relationship', 'tools/get_product_feature_relationship']

    for tool_name in tool_list:
        tool = str(CWD) + '/' + str(tool_name)
        ld_library_path_setting = ''

        if 'LD_LIBRARY_PATH' in os.environ:
            ld_library_path_setting = 'export LD_LIBRARY_PATH=' + str(os.environ['LD_LIBRARY_PATH'])

        print('')
        print('>>> Generate script "' + str(tool) + '".')

        try:
            with open(tool, 'w') as SP:
                SP.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(PYTHON_PATH) + """:$PATH

# Set install path.
export LICENSE_MONITOR_INSTALL_PATH=""" + str(CWD) + """

# Set LD_LIBRARY_PATH.
""" + str(ld_library_path_setting) + """

# Execute """ + str(tool_name) + """.py.
python3 $LICENSE_MONITOR_INSTALL_PATH/""" + str(tool_name) + '.py $@')

            os.chmod(tool, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
            sys.exit(1)


def gen_config_file():
    """
    Generate config file <LICENSE_MONITOR_INSTALL_PATH>/config/config.py.
    """
    config_file = str(CWD) + '/config/config.py'

    print('')
    print('>>> Generate config file "' + str(config_file) + '".')

    if os.path.exists(config_file):
        print('*Warning*: config file "' + str(config_file) + '" already exists, will not update it.')
    else:
        try:
            with open(config_file, 'w') as CF:
                CF.write('''# Specify EDA license administrators. (only administrator can execute license_monitor)
administrators = ""

# Set configured LM_LICENSE_FILE for administrators. If False, will get LM_LICENSE_FILE from current terminal.
show_configured_for_admin = True

# Specify lmstat path, just like "***/bin".
lmstat_path = ""

# Specify lmstat bsub command, just like "bsub -q normal -Is".
lmstat_bsub_command = ""

# Specify LM_LICENSE_FILE setting.
LM_LICENSE_FILE = ""

# Specify EDA license product-feature relationship file, you can get the file with "tools/get_product_feature_relationship.py".
product_feature_relationship_file = ""

# The time interval to fresh license information automatically, unit is "second", default is 300 seconds.
fresh_interval = 300
''')

            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)


################
# Main Process #
################
def main():
    check_python_version()
    gen_shell_tools()
    gen_config_file()

    print('')
    print('Done, Please enjoy it.')


if __name__ == '__main__':
    main()
