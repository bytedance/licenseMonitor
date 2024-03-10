# -*- coding: utf-8 -*-
import os
import re
import sys
import yaml
import getpass
import argparse
import datetime

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()
CURRENT_TIME = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-l', '--LM_LICENSE_FILE_file',
                        required=True,
                        default='',
                        help='Required argument, specify licenseMonitor LM_LICENSE_FILE file.')
    parser.add_argument('-o', '--output_file',
                        default=str(CWD) + '/license_log.' + str(CURRENT_TIME) + '.yaml',
                        help='Output file, default is "<CWD>/license_log.<CURRENT_TIME>.yaml".')

    args = parser.parse_args()

    if not os.path.exists(args.LM_LICENSE_FILE_file):
        common.bprint('"' + str(args.LM_LICENSE_FILE_file) + ': No such file!', level='Error')
        sys.exit(1)

    return args.LM_LICENSE_FILE_file, args.output_file


class GetLicenseLog():
    """
    Get license log, save into output_file with dictory database.
    license_log_dic = {
        <license_server>: <license_log_path>,
    }
    """
    def __init__(self, LM_LICENSE_FILE_file, output_file):
        self.LM_LICENSE_FILE_list = self.parse_LM_LICENSE_FILE_file(LM_LICENSE_FILE_file)
        self.output_file = output_file

    def parse_LM_LICENSE_FILE_file(self, LM_LICENSE_FILE_file):
        """
        Setup environment variables LM_LICENSE_FILE with settings on LM_LICENSE_FILE file.
        """
        LM_LICENSE_FILE_list = []

        with open(LM_LICENSE_FILE_file, 'r') as LF:
            for line in LF.readlines():
                line = line.strip()

                if re.match(r'^\s*#.*$', line) or re.match(r'^\s*$', line):
                    continue
                else:
                    if line not in LM_LICENSE_FILE_list:
                        LM_LICENSE_FILE_list.append(line)

        return LM_LICENSE_FILE_list

    def get_license_server_list(self):
        """
        Get all license server (without "<port>@") with self.LM_LICENSE_FILE_list.
        """
        license_server_list = []

        for LM_LICENSE_FILE in self.LM_LICENSE_FILE_list:
            if re.match(r'^\d+@(\S+)$', LM_LICENSE_FILE):
                my_match = re.match(r'^\d+@(\S+)$', LM_LICENSE_FILE)
                license_server = my_match.group(1)

                if license_server not in license_server_list:
                    license_server_list.append(license_server)

        return license_server_list

    def get_license_log(self, license_server):
        """
        Parse netstat/ps information, get port <-> license_log relationship.
        """
        server_log_dic = {}

        # Get license_server & license_log.
        pid_port_dic = {}
        command = 'netstat -anp | grep lmgrd ; ps aux | grep lmgrd'
        stdout_list = common.ssh_client(host_name=license_server, user_name=str(getpass.getuser()), command=command, timeout=1)

        for line in stdout_list:
            if re.match(r'^\s*\S+\s+\d+\s+\d+\s+\S+:(\d+)\s+.*ESTABLISHED\s+(\d+)/lmgrd\s*$', line):
                my_match = re.match(r'^\s*\S+\s+\d+\s+\d+\s+\S+:(\d+)\s+.*ESTABLISHED\s+(\d+)/lmgrd\s*$', line)
                port = my_match.group(1)
                pid = my_match.group(2)
                pid_port_dic[pid] = port
            elif re.match(r'^\S+\s+(\d+)\s+.*lmgrd\s+.*-l\s+(\S+).*$', line):
                my_match = re.match(r'^\S+\s+(\d+)\s+.*lmgrd\s+.*-l\s+(\S+).*$', line)
                pid = my_match.group(1)
                license_log_path = my_match.group(2)

                if pid in pid_port_dic:
                    port = pid_port_dic[pid]
                    server_log_dic[port] = license_log_path

                    print('    Port(' + str(port) + ') find license log "' + str(license_log_path) + '".')

        return server_log_dic

    def run(self):
        """
        Main function.
        """
        license_log_dic = {}
        license_server_list = self.get_license_server_list()

        # Get license log path.
        for license_server in license_server_list:
            print('>>> Processing license server "' + str(license_server) + '" ...')

            server_log_dic = self.get_license_log(license_server)

            if server_log_dic:
                for (port, license_log_path) in server_log_dic.items():
                    license_log_dic.setdefault(str(port) + '@' + str(license_server), license_log_path)

        # Save license log path.
        if license_log_dic:
            try:
                print('>>> Save output file "' + str(self.output_file) + '".')

                with open(self.output_file, 'w') as OF:
                    yaml.dump(license_log_dic, OF)

                os.chmod(self.output_file, 0o777)
            except Exception as error:
                common.bprint('Failed on writing "' + str(self.output_file) + '": ' + str(error), level='Error')


################
# Main Process #
################
def main():
    (LM_LICENSE_FILE_file, output_file) = read_args()
    my_get_license_log = GetLicenseLog(LM_LICENSE_FILE_file, output_file)
    my_get_license_log.run()


if __name__ == '__main__':
    main()
