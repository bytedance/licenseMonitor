# -*- coding: utf-8 -*-
import os
import re
import sys
import yaml
import datetime
import argparse

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license
from config import config

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()
CURRENT_TIME = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-L', '--LM_LICENSE_FILE_file',
                        required=True,
                        default='',
                        help='Required argument, specify licenseMonitor LM_LICENSE_FILE file.')
    parser.add_argument('-l', '--license_log_config_file',
                        default='',
                        help='Specify license log configuration file, must be yaml format.')
    parser.add_argument('-o', '--output_file',
                        default=str(CWD) + '/feature_record_on_license_log.' + str(CURRENT_TIME) + '.yaml',
                        help='Output file, default is "<CWD>/feature_record_on_license_log.<CURRENT_TIME>.yaml".')

    args = parser.parse_args()

    # Check args.LM_LICENSE_FILE_file.
    if not os.path.exists(args.LM_LICENSE_FILE_file):
        common.bprint('"' + str(args.LM_LICENSE_FILE_file) + ': No such file!', level='Error')
        sys.exit(1)

    # Check args.license_log_config_file
    if not args.license_log_config_file:
        args.license_log_config_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/others/license_log.yaml'

    if not os.path.exists(args.license_log_config_file):
        common.bprint('License log configuration file "' + str(args.license_log_config_file) + '" is missing.', level='Error')
        sys.exit(1)

    return args.LM_LICENSE_FILE_file, args.license_log_config_file, args.output_file


class CollectFeatureRecord():
    """
    1. Get license log information from license_log_config_file.
    2. Get license information with "lmstat" command.
    3. Collect feature record from license log.
    """
    def __init__(self, LM_LICENSE_FILE_file, license_log_config_file, output_file):
        self.license_log_dic = self.parse_license_log_config_file(license_log_config_file)
        self.output_file = output_file
        self.setenv(LM_LICENSE_FILE_file)

        print('>>> Getting license feature list ...')

        my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        self.license_dic = my_get_license_info.get_license_info()

    def parse_license_log_config_file(self, license_log_config_file):
        """
        Get license_log_dic from license_log_config_file (yaml file).
        """
        print('>>> Getting license log list ...')

        license_log_dic = {}

        try:
            with open(license_log_config_file, 'r') as LLCF:
                license_log_dic = yaml.load(LLCF, Loader=yaml.FullLoader)
        except Exception as error:
            common.bprint('Failed on opening "' + str(license_log_config_file) + '" for read: ' + str(error), level='Warning')

        return license_log_dic

    def setenv(self, LM_LICENSE_FILE_file):
        """
        Setup environment variables LM_LICENSE_FILE with settings on LM_LICENSE_FILE file.
        """
        print('>>> Setup env variable LM_LICENSE_FILE with "' + str(LM_LICENSE_FILE_file) + '"')

        if not os.path.exists(LM_LICENSE_FILE_file):
            common.bprint('"' + str(LM_LICENSE_FILE_file) + '": No such file.', level='Warning')
            os.environ['LM_LICENSE_FILE'] = ''
        else:
            LM_LICENSE_FILE_list = []

            with open(LM_LICENSE_FILE_file, 'r') as LF:
                for line in LF.readlines():
                    line = line.strip()

                    if re.match(r'^\s*#.*$', line) or re.match(r'^\s*$', line):
                        continue
                    else:
                        if line not in LM_LICENSE_FILE_list:
                            LM_LICENSE_FILE_list.append(line)

            LM_LICENSE_FILE_string = ':'.join(LM_LICENSE_FILE_list)
            os.environ['LM_LICENSE_FILE'] = LM_LICENSE_FILE_string

    def collect_feature_record_from_license_log(self, feature, license_server, license_log):
        """
        Search license feature checkout record on specified license_log.
        """
        record_list = []
        grep_command = 'grep \'OUT: "' + str(feature) + '"\' ' + str(license_log) + ' | tail -n 10'

        if os.path.exists(license_log):
            (return_code, stdout, stderr) = common.run_command(grep_command)
            stdout_list = str(stdout, 'utf-8').split('\n')
        else:
            host_name = license_server.split('@')[1]
            stdout_list = common.ssh_client(host_name=host_name, command=grep_command, timeout=1)

        for line in stdout_list:
            if re.match(r'^.*OUT: "' + str(feature) + r'"\s+(\S+)@(\S+)\s+.*$', line):
                my_match = re.match(r'^.*OUT: "' + str(feature) + r'"\s+(\S+)@(\S+)\s+.*$', line)
                user = my_match.group(1)
                host = my_match.group(2)
                record_list.append({'user': user, 'host': host})

        return record_list

    def collect_feature_record_info(self):
        """
        Collect license feature record information, and save feature_record_dic.
        feature_record_dic = {
            feature: {vendor_daemon: {license_server: [{'user'=user, 'host'=host},]}},
        """
        print('>>> Collecting license feature record info ...')

        feature_record_dic = {}

        if self.license_log_dic and self.license_dic:
            license_server_list = list(self.license_dic.keys())
            license_server_list.sort()

            for license_server in license_server_list:
                if ('vendor_daemon' in self.license_dic[license_server]) and (license_server in self.license_log_dic):
                    for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                        if 'feature' in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]:
                            for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                                print('    Searching record for license_server(' + str(license_server) + ') vendor_daemon(' + str(vendor_daemon) + ') feature(' + str(feature) + ')')

                                license_log = self.license_log_dic[license_server]
                                record_list = self.collect_feature_record_from_license_log(feature, license_server, license_log)

                                if record_list:
                                    feature_record_dic.setdefault(feature, {})

                                    if vendor_daemon not in feature_record_dic[feature]:
                                        feature_record_dic[feature][vendor_daemon] = {}

                                    feature_record_dic[feature][vendor_daemon][license_server] = record_list

        return feature_record_dic

    def save_feature_record_info(self, feature_record_dic):
        """
        Save feature_record_dic into self.output_file.
        """
        try:
            print('>>> Save output file "' + str(self.output_file) + '".')

            with open(self.output_file, 'w') as OF:
                yaml.dump(feature_record_dic, OF)

            os.chmod(self.output_file, 0o777)
        except Exception as error:
            common.bprint('Failed on writing "' + str(self.output_file) + '": ' + str(error), level='Error')

    def run(self):
        """
        Collect and save license feature record information.
        """
        feature_record_dic = self.collect_feature_record_info()

        if not feature_record_dic:
            common.bprint('No license feature record is detected on license log.', level='Error')
            sys.exit(1)
        else:
            self.save_feature_record_info(feature_record_dic)


################
# Main Process #
################
def main():
    (LM_LICENSE_FILE_file, license_log_config_file, output_file) = read_args()
    my_collect_feature_record = CollectFeatureRecord(LM_LICENSE_FILE_file, license_log_config_file, output_file)
    my_collect_feature_record.run()


if __name__ == '__main__':
    main()
