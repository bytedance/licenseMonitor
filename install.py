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
    tool_list = ['bin/license_monitor', 'bin/license_sample', 'tools/config_product_feature_relationship', 'tools/get_product_feature_relationship', 'tools/patch']

    for tool_name in tool_list:
        tool = str(CWD) + '/' + str(tool_name)
        ld_library_path_setting = 'export LD_LIBRARY_PATH=$LICENSE_MONITOR_INSTALL_PATH/lib:'

        if 'LD_LIBRARY_PATH' in os.environ:
            ld_library_path_setting = str(ld_library_path_setting) + str(os.environ['LD_LIBRARY_PATH'])

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
    Generate config files.
    """
    config_file = str(CWD) + '/config/config.py'
    lmstat_path = str(CWD) + '/tools/lmstat'
    db_path = str(CWD) + '/db'
    lm_license_file = str(CWD) + '/config/LM_LICENSE_FILE'
    product_feature_file = str(CWD) + '/config/product_feature.yaml'
    project_list_file = str(CWD) + '/config/project_list'
    project_submit_host_file = str(CWD) + '/config/project_submit_host'
    project_execute_host_file = str(CWD) + '/config/project_execute_host'
    project_user_file = str(CWD) + '/config/project_user'

    # Generate config_file.
    print('')
    print('>>> Generate config file "' + str(config_file) + '".')

    if os.path.exists(config_file):
        print('*Warning*: config file "' + str(config_file) + '" already exists, will not update it.')
    else:
        try:
            with open(config_file, 'w') as CF:
                CF.write('''# Specify EDA license administrators.
administrators = ""

# Specify lmstat path, example "/eda/synopsys/scl/2021.03/linux64/bin/lmstat".
lmstat_path = "''' + str(lmstat_path) + '''"

# Specify lmstat bsub command, example "bsub -q normal -Is".
lmstat_bsub_command = "bsub -q normal -Is"

# Specify the database directory where to save sample data.
db_path = "''' + str(db_path) + '''"

# Specify LM_LICENSE_FILE file path (with license servers setting).
LM_LICENSE_FILE = "''' + str(lm_license_file) + '''"

# Specify EDA license product & feature relationship file, you can get the file with "tools/get_product_feature_relationship".
product_feature_file = "''' + str(product_feature_file) + '''"

# Specify project(s) file.
project_list_file = "''' + str(project_list_file) + '''"

# Specify project & submit_host relationship file.
project_submit_host_file = "''' + str(project_submit_host_file) + '''"

# Specify project & execute_host relationship file.
project_execute_host_file = "''' + str(project_execute_host_file) + '''"

# Specify project & user relationship file.
project_user_file = "''' + str(project_user_file) + '''"

# Specify which are the primary factors when getting project information.
# It could be one or serveral items between "user/execute_host/submit_host".
project_primary_factors = "user  execute_host  submit_host"

# Set configured LM_LICENSE_FILE for administrators.
# If False, will get LM_LICENSE_FILE from current terminal.
show_configured_for_admin = True

# The time interval to fresh license information automatically, unit is "second", default is 300 seconds.
fresh_interval = 300
''')

            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate lm_license_file.
    print('')
    print('>>> Generate LM_LICENSE_FILE configuration file "' + str(lm_license_file) + '".')

    if os.path.exists(lm_license_file):
        print('*Warning*: config file "' + str(lm_license_file) + '" already exists, will not update it.')
    else:
        try:
            with open(lm_license_file, 'w') as LLF:
                LLF.write('''# Example:
# 5280@lic_server1
# 27020@lic_server2
# 1717@lic_server3

''')

            os.chmod(lm_license_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(lm_license_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate product_feature_file.
    print('')
    print('>>> Generate product-feature relationship file "' + str(product_feature_file) + '".')

    if os.path.exists(product_feature_file):
        print('*Warning*: config file "' + str(product_feature_file) + '" already exists, will not update it.')
    else:
        try:
            with open(product_feature_file, 'w') as PFF:
                PFF.write('''# Please generate this file with script ''' + str(CWD) + '''/tools/get_product_feature_relationship.
''')

            os.chmod(product_feature_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(product_feature_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate project_list file.
    print('')
    print('>>> Generate project list file "' + str(project_list_file) + '".')

    if os.path.exists(project_list_file):
        print('*Warning*: config file "' + str(project_list_file) + '" already exists, will not update it.')
    else:
        try:
            with open(project_list_file, 'w') as PLF:
                PLF.write('''# Example:
# project1
# project2

''')

            os.chmod(project_list_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(project_list_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate project_submit_host_file.
    print('')
    print('>>> Generate project-submit_host relationship file "' + str(project_submit_host_file) + '".')

    if os.path.exists(project_submit_host_file):
        print('*Warning*: config file "' + str(project_submit_host_file) + '" already exists, will not update it.')
    else:
        try:
            with open(project_submit_host_file, 'w') as PSHF:
                PSHF.write('''# Example:
# host1 : project1(0.3) project2(0.7)
# host2 : project3

''')

            os.chmod(project_submit_host_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(project_submit_host_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate project_execute_host_file.
    print('')
    print('>>> Generate project-execute_host relationship file "' + str(project_execute_host_file) + '".')

    if os.path.exists(project_execute_host_file):
        print('*Warning*: config file "' + str(project_execute_host_file) + '" already exists, will not update it.')
    else:
        try:
            with open(project_execute_host_file, 'w') as PEHF:
                PEHF.write('''# Example:
# host1 : project1(0.3) project2(0.7)
# host2 : project3

''')

            os.chmod(project_execute_host_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(project_execute_host_file) + '" for write: ' + str(error))
            sys.exit(1)

    # Generate project_user_file.
    print('')
    print('>>> Generate project-user relationship file "' + str(project_user_file) + '".')

    if os.path.exists(project_user_file):
        print('*Warning*: config file "' + str(project_user_file) + '" already exists, will not update it.')
    else:
        try:
            with open(project_user_file, 'w') as PUF:
                PUF.write('''# Example:
# user1 : project1(0.3) project2(0.7)
# user2 : project3

''')

            os.chmod(project_user_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(project_user_file) + '" for write: ' + str(error))
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
