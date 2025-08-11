# -*- coding: utf-8 -*-
import os
import re
import sys
import argparse

CWD = os.getcwd()
os.environ['PYTHONUNBUFFERED'] = '1'

sys.path.insert(0, os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.licenseMonitor/config'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config
else:
    from config import config


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-m', '--module_files_dirs',
                        required=True,
                        nargs='+',
                        help='Required argument, specify the directories where save module configuration files.')
    parser.add_argument('-f', '--LM_LICENSE_FILE_file',
                        default=str(CWD) + '/LM_LICENSE_FILE',
                        help='Specify output file, default is "' + str(CWD) + '/LM_LICENSE_FILE".')

    args = parser.parse_args()

    for module_files_dir in args.module_files_dirs:
        if not os.path.exists(module_files_dir):
            common.bprint('"' + str(args.module_files_dir) + '": No such directory.', level='Error')
            sys.exit(1)

    return args.module_files_dirs, args.LM_LICENSE_FILE_file


def get_LM_LICENSE_FILE_setting(module_files_dir_list):
    """
    Parse all fild on module files directory, get license server format string, and save them into LM_LICENSE_FILE_list.
    """
    LM_LICENSE_FILE_list = []

    for module_files_dir in module_files_dir_list:
        for root, dirs, files in os.walk(module_files_dir):
            for file in files:
                module_file = str(root) + '/' + str(file)

                with open(module_file, 'r') as MF:
                    print('>>> Parse "' + str(module_file) + '"')
                    mark = False

                    for line in MF.readlines():
                        if not mark:
                            if re.match(r'^\s*#%Module.*$', line):
                                mark = True
                            else:
                                break
                        else:
                            for license_server in re.findall(r'\d+@\S+', line):
                                print('    Find ' + str(license_server))
                                if license_server not in LM_LICENSE_FILE_list:
                                    LM_LICENSE_FILE_list.append(license_server)

    # Remove excluded license servers.
    if config.excluded_license_servers:
        print('')
        print('>>> Remove excluded license servers ...')
        excluded_license_server_list = config.excluded_license_servers.split()

        for excluded_license_server in excluded_license_server_list:
            if excluded_license_server in LM_LICENSE_FILE_list:
                print('    Remove "' + str(excluded_license_server) + '"')
                LM_LICENSE_FILE_list.remove(excluded_license_server)

    if not LM_LICENSE_FILE_list:
        common.bprint('Not get any valid LM_LICENSE_FILE setting.', level='Warning')
    else:
        print('')
        print('>>> Checking license server status ...')

        # Remove DOWN license servers.
        os.environ['LM_LICENSE_FILE'] = ':'.join(LM_LICENSE_FILE_list)
        my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        license_dic = my_get_license_info.get_license_info()
        LM_LICENSE_FILE_list = []

        for license_server in license_dic.keys():
            if license_dic[license_server]['license_server_status'] == 'UP':
                mark = False

                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    if license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'] == 'UP':
                        mark = True
                        break
                    else:
                        common.bprint('Vendor daemon status is "' + str(license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status']) + '" for "' + str(license_server) + '/' + str(vendor_daemon) + '".', level='Warning')

                if mark:
                    LM_LICENSE_FILE_list.append(license_server)
            else:
                common.bprint('License server status is "' + str(license_dic[license_server]['license_server_status']) + '" for "' + str(license_server) + '", ignore it.', level='Warning')

    LM_LICENSE_FILE_list.sort()

    return LM_LICENSE_FILE_list


def write_LM_LICENSE_FILE(LM_LICENSE_FILE_list, LM_LICENSE_FILE_file):
    """
    Write LM_LICENSE_FILE_list content into LM_LICENSE_FILE_file.
    """
    if LM_LICENSE_FILE_list:
        with open(LM_LICENSE_FILE_file, 'w') as LF:
            print('')
            print('>>> Write "' + str(LM_LICENSE_FILE_file) + '"')

            for LM_LICENSE_FILE_setting in LM_LICENSE_FILE_list:
                print('    ' + str(LM_LICENSE_FILE_setting))
                LF.write(str(LM_LICENSE_FILE_setting) + '\n')

        os.chmod(LM_LICENSE_FILE_file, 0o777)

        print('')
        print('* LM_LICENSE_FILE is saved on "' + str(LM_LICENSE_FILE_file) + '".')


################
# Main Process #
################
def main():
    (module_files_dir_list, LM_LICENSE_FILE_file) = read_args()
    LM_LICENSE_FILE_list = get_LM_LICENSE_FILE_setting(module_files_dir_list)
    write_LM_LICENSE_FILE(LM_LICENSE_FILE_list, LM_LICENSE_FILE_file)


if __name__ == '__main__':
    main()
