# -*- coding: utf-8 -*-
################################
# File Name   : license_sample.py
# Author      : liyanqing.1987
# Created On  : 2023-04-23 17:30:35
# Description :
################################
import os
import re
import sys
import time
import shutil
import datetime
import argparse
from multiprocessing import Process

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license
from common import common_sqlite3

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.licenseMonitor/config'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config
else:
    from config import config

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-u', '--usage',
                        action='store_true',
                        default=False,
                        help='Sample license feature usage info.')
    parser.add_argument('-U', '--utilization',
                        action='store_true',
                        default=False,
                        help='Sample license feature utilization info.')

    args = parser.parse_args()

    if (not args.usage) and (not args.utilization):
        common.bprint('At least one argument of "usage/utilization" must be selected.', level='Error')
        sys.exit(1)

    return args.usage, args.utilization


class Sampling:
    """
    Sample and save license feature information.
    """
    def __init__(self, usage_sampling, utilization_sampling):
        self.usage_sampling = usage_sampling
        self.utilization_sampling = utilization_sampling

        # Get sample time.
        self.sample_second = int(time.time())
        self.sample_date = datetime.datetime.today().strftime('%Y%m%d')
        self.sample_time = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')

        # Get self.license_dic.
        print('>>> Sampling license usage information ...')

        LM_LICENSE_FILE_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/LM_LICENSE_FILE'

        if os.path.exists(LM_LICENSE_FILE_file):
            os.environ['LM_LICENSE_FILE'] = ''

            with open(LM_LICENSE_FILE_file, 'r') as LLF:
                for line in LLF.readlines():
                    line = line.strip()

                    if (not re.match(r'^\s*$', line)) and (not re.match(r'^\s*#.*$', line)):
                        if os.environ['LM_LICENSE_FILE']:
                            os.environ['LM_LICENSE_FILE'] = str(os.environ['LM_LICENSE_FILE']) + ':' + str(line)
                        else:
                            os.environ['LM_LICENSE_FILE'] = str(line)

        if not hasattr(config, 'lmstat_path'):
            config.lmstat_path = ''

        if not hasattr(config, 'lmstat_bsub_command'):
            config.lmstat_bsub_command = ''

        my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        self.license_dic = my_get_license_info.get_license_info()

    def create_db_path(self, db_path):
        """
        Create db_path if not exists.
        """
        if not os.path.exists(db_path):
            try:
                print('    Create directory "' + str(db_path) + '".')
                os.makedirs(db_path, mode=0o755)
            except Exception as error:
                common.bprint('Failed on creating database directory "' + str(db_path) + '".', level='Error')
                common.bprint(error, color='red', display_method=1, indent=9)

                if not re.search('File exists', str(error)):
                    sys.exit(1)

    def copy_file(self, source_file, target_dir):
        """
        Copy source_file into target_dir.
        """
        try:
            print('    Copy "' + str(source_file) + '" into directory "' + str(target_dir) + '".')
            shutil.copy(source_file, target_dir)
        except Exception as warning:
            common.bprint('Failed on copying "' + str(source_file) + '" into directory "' + str(target_dir) + '".', level='Warning')
            common.bprint(warning, color='yellow', display_method=1, indent=11)

    def detect_project_setting(self):
        """
        Detect config/project/* and save new update into config.db_path/project_setting.
        """
        print('>>> Detect project setting ...')

        project_list_file = os.path.realpath(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_list')
        project_submit_host_file = os.path.realpath(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_submit_host')
        project_execute_host_file = os.path.realpath(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_execute_host')
        project_user_file = os.path.realpath(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_user')

        # Get project_setting_dic.
        copy_mark = False
        project_setting_db_path = str(config.db_path) + '/project_setting'

        self.create_db_path(project_setting_db_path)

        project_setting_dic = common.parse_project_setting_db_path(project_setting_db_path)

        if not project_setting_dic:
            copy_mark = True
        else:
            create_time_list = list(os.listdir(project_setting_db_path))
            latest_create_time = create_time_list[-1]

            # Get project_list/project_submit_host/project_execute_host/project_user content on config directory.
            config_project_list = common.parse_project_list_file(project_list_file)
            config_project_submit_host_dic = common.parse_project_proportion_file(project_submit_host_file, config_project_list)
            config_project_execute_host_dic = common.parse_project_proportion_file(project_execute_host_file, config_project_list)
            config_project_user_dic = common.parse_project_proportion_file(project_user_file, config_project_list)

            # Compare latest db_path setting and current config setting.
            if (project_setting_dic[latest_create_time]['project_list'] != config_project_list) or (project_setting_dic[latest_create_time]['project_submit_host'] != config_project_submit_host_dic) or (project_setting_dic[latest_create_time]['project_execute_host'] != config_project_execute_host_dic) or (project_setting_dic[latest_create_time]['project_user'] != config_project_user_dic):
                copy_mark = True

        if copy_mark:
            current_time = datetime.datetime.today().strftime('%Y%m%d%H%M%S')
            current_project_setting_db_path = str(project_setting_db_path) + '/' + str(current_time)

            self.create_db_path(current_project_setting_db_path)
            self.copy_file(project_list_file, current_project_setting_db_path)
            self.copy_file(project_execute_host_file, current_project_setting_db_path)
            self.copy_file(project_submit_host_file, current_project_setting_db_path)
            self.copy_file(project_user_file, current_project_setting_db_path)

    def sample_usage_info(self):
        """
        Sample license feature usage info and save it into sqlite db.
        """
        print('>>> Sampling usage info ...')

        for license_server in self.license_dic.keys():
            for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                db_path = str(config.db_path) + '/license_server/' + str(license_server) + '/' + str(vendor_daemon)

                self.create_db_path(db_path)

                usage_db_file = str(db_path) + '/usage.db'
                (result, usage_db_conn) = common_sqlite3.connect_db_file(usage_db_file, mode='write')

                if result == 'passed':
                    usage_table_list = common_sqlite3.get_sql_table_list(usage_db_file, usage_db_conn)

                    key_list = ['id', 'sample_second', 'sample_time', 'server', 'vendor', 'feature', 'user', 'submit_host', 'execute_host', 'num', 'version', 'start_second', 'start_time']
                    key_type_list = ['INTEGER PRIMARY KEY AUTOINCREMENT', 'INTEGER', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'INTEGER', 'TEXT']

                    for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                        usage_table_name = feature

                        print('    Sampling usage info for "' + str(license_server) + '/' + str(vendor_daemon) + '/' + str(feature) + '" ...')

                        if usage_table_name not in usage_table_list:
                            # Generate database table title.
                            key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                            common_sqlite3.create_sql_table(usage_db_file, usage_db_conn, usage_table_name, key_string, commit=False)

                            # Insert sql table value.
                            for usage_dic in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']:
                                start_second = common_license.switch_start_time(usage_dic['start_time'], compare_second=self.sample_second)
                                value_list = ['NULL', self.sample_second, self.sample_time, license_server, vendor_daemon, feature, usage_dic['user'], usage_dic['submit_host'], usage_dic['execute_host'], usage_dic['license_num'], usage_dic['version'], start_second, usage_dic['start_time']]
                                value_string = common_sqlite3.gen_sql_table_value_string(value_list, autoincrement=True)
                                common_sqlite3.insert_into_sql_table(usage_db_file, usage_db_conn, usage_table_name, value_string, commit=False)
                        else:
                            # Clean up usage database, only keep 100000 items.
                            usage_table_count = common_sqlite3.get_sql_table_count(usage_db_file, usage_db_conn, usage_table_name)

                            if usage_table_count != 'N/A':
                                if int(usage_table_count) > 100000:
                                    row_id = 'sample_time'
                                    begin_line = 0
                                    end_line = int(usage_table_count) - 100000

                                    print('    Deleting database "' + str(usage_db_file) + '" table "' + str(usage_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                                    common_sqlite3.delete_sql_table_rows(usage_db_file, usage_db_conn, usage_table_name, row_id, begin_line, end_line)

                            for usage_dic in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']:
                                select_condition = "WHERE server='" + str(license_server) + "' AND vendor='" + str(vendor_daemon) + "' AND feature='" + str(feature) + "' AND user='" + str(usage_dic['user']) + "' AND submit_host='" + str(usage_dic['submit_host']) + "' AND execute_host='" + str(usage_dic['execute_host']) + "' AND num='" + str(usage_dic['license_num']) + "' AND version='" + str(usage_dic['version']) + "' AND start_time='" + str(usage_dic['start_time']) + "'"
                                usage_db_data_dic = common_sqlite3.get_sql_table_data(usage_db_file, usage_db_conn, usage_table_name, ['server', 'vendor', 'feature'], select_condition)

                                if usage_db_data_dic:
                                    # Replace sql table value.
                                    set_condition = "SET sample_second='" + str(self.sample_second) + "', sample_time='" + str(self.sample_time) + "'"
                                    where_condition = "WHERE server='" + str(license_server) + "' AND vendor='" + str(vendor_daemon) + "' AND feature='" + str(feature) + "' AND user='" + str(usage_dic['user']) + "' AND submit_host='" + str(usage_dic['submit_host']) + "' AND execute_host='" + str(usage_dic['execute_host']) + "' AND num='" + str(usage_dic['license_num']) + "' AND version='" + str(usage_dic['version']) + "' AND start_time='" + str(usage_dic['start_time']) + "'"
                                    common_sqlite3.update_sql_table_data(usage_db_file, usage_db_conn, usage_table_name, set_condition, where_condition, commit=False)
                                else:
                                    # Insert sql table value.
                                    start_second = common_license.switch_start_time(usage_dic['start_time'], compare_second=self.sample_second)
                                    value_list = ['NULL', self.sample_second, self.sample_time, license_server, vendor_daemon, feature, usage_dic['user'], usage_dic['submit_host'], usage_dic['execute_host'], usage_dic['license_num'], usage_dic['version'], start_second, usage_dic['start_time']]
                                    value_string = common_sqlite3.gen_sql_table_value_string(value_list, autoincrement=True)
                                    common_sqlite3.insert_into_sql_table(usage_db_file, usage_db_conn, usage_table_name, value_string, commit=False)

                    usage_db_conn.commit()
                    usage_db_conn.close()

    def sample_utilization_info(self):
        """
        Sample license feature utilization info and save it into sqlite db.
        """
        print('>>> Sampling utilization info ...')

        for license_server in self.license_dic.keys():
            for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                db_path = str(config.db_path) + '/license_server/' + str(license_server) + '/' + str(vendor_daemon)

                self.create_db_path(db_path)

                utilization_db_file = str(db_path) + '/utilization.db'
                (result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file, mode='write')

                if result == 'passed':
                    utilization_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)
                    feature_utilization_dic = self.get_feature_utilization_info(specified_license_server=license_server, specified_vendor_daemon=vendor_daemon)

                    key_list = ['sample_second', 'sample_time', 'issued', 'in_use', 'utilization']
                    key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'INTEGER', 'TEXT']

                    for (feature, feature_dic) in feature_utilization_dic.items():
                        utilization_table_name = feature

                        print('    Sampling utilization info for "' + str(license_server) + '/' + str(vendor_daemon) + '/' + str(feature) + '" ...')

                        # Clean up utilization database, only keep 100000 items.
                        if utilization_table_name in utilization_table_list:
                            utilization_table_count = common_sqlite3.get_sql_table_count(utilization_db_file, utilization_db_conn, utilization_table_name)

                            if utilization_table_count != 'N/A':
                                if int(utilization_table_count) > 100000:
                                    row_id = 'sample_time'
                                    begin_line = 0
                                    end_line = int(utilization_table_count) - 100000

                                    print('    Deleting database "' + str(utilization_db_file) + '" table "' + str(utilization_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                                    common_sqlite3.delete_sql_table_rows(utilization_db_file, utilization_db_conn, utilization_table_name, row_id, begin_line, end_line)

                        # Generate sql table.
                        if utilization_table_name not in utilization_table_list:
                            key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                            common_sqlite3.create_sql_table(utilization_db_file, utilization_db_conn, utilization_table_name, key_string, commit=False)

                        # Insert sql table value.
                        value_list = [self.sample_second, self.sample_time, feature_dic['issued'], feature_dic['in_use'], feature_dic['utilization']]
                        value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                        common_sqlite3.insert_into_sql_table(utilization_db_file, utilization_db_conn, utilization_table_name, value_string, commit=False)

                    utilization_db_conn.commit()
                    utilization_db_conn.close()

        self.count_utilization_day_info()

    def get_feature_utilization_info(self, specified_license_server, specified_vendor_daemon):
        """
        Get issued/in_use info from self.license_dic.
        Reture issued/in_use/utilization info with feature_utilization_dic.
        """
        # Get feature issed/in_use information.
        feature_utilization_dic = {}

        for license_server in self.license_dic.keys():
            if license_server == specified_license_server:
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon == specified_vendor_daemon:
                        for (feature, feature_dic) in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].items():
                            feature_utilization_dic.setdefault(feature, [])
                            feature_utilization_dic[feature].append({'issued': feature_dic['issued'], 'in_use': feature_dic['in_use']})

        # Get feature utilization information.
        for (feature, feature_dic_list) in feature_utilization_dic.items():
            feature_utilization_dic[feature] = {}
            issued_sum = 0
            in_use_sum = 0

            for feature_dic in feature_dic_list:
                issued_num = feature_dic['issued']
                in_use_num = int(feature_dic['in_use'])
                in_use_sum += in_use_num

                if issued_num == 'Uncounted':
                    issued_sum = 'Uncounted'

                    if in_use_num == 0:
                        issued_num = 1
                    else:
                        issued_num = in_use_num
                else:
                    if issued_sum != 'Uncounted':
                        issued_num = int(issued_num)
                        issued_sum += issued_num

            if issued_sum == 'Uncounted':
                if in_use_sum == 0:
                    utilization = 0
                else:
                    utilization = 100
            else:
                utilization = round(100*in_use_sum/issued_sum, 1)

            feature_utilization_dic[feature] = {'issued': issued_sum, 'in_use': in_use_sum, 'utilization': utilization}

        return feature_utilization_dic

    def count_utilization_day_info(self):
        """
        Count license feature utilization day info and save it into sqlite db.
        """
        print('')
        print('>>> Counting utilization (day average) info ...')

        for license_server in self.license_dic.keys():
            for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                utilization_day_db_file = str(config.db_path) + '/license_server/' + str(license_server) + '/' + str(vendor_daemon) + '/utilization_day.db'
                (result, utilization_day_db_conn) = common_sqlite3.connect_db_file(utilization_day_db_file, mode='write')

                if result == 'passed':
                    utilization_day_table_list = common_sqlite3.get_sql_table_list(utilization_day_db_file, utilization_day_db_conn)
                    utilization_day_dic = self.get_utilization_day_info(specified_license_server=license_server, specified_vendor_daemon=vendor_daemon)

                    key_list = ['sample_date', 'issued', 'in_use', 'utilization']
                    key_type_list = ['TEXT PRIMARY KEY', 'TEXT', 'INTEGER', 'TEXT']

                    for (utilization_day_table_name, utilization_day_table_dic) in utilization_day_dic.items():
                        print('    Counting utilization (day average) info for "' + str(license_server) + '/' + str(vendor_daemon) + '/' + str(utilization_day_table_name) + '" ...')

                        # Generate sql table.
                        if utilization_day_table_name not in utilization_day_table_list:
                            key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                            common_sqlite3.create_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, key_string, commit=False)

                            # Insert sql table value.
                            value_list = [self.sample_date, utilization_day_table_dic['issued'], utilization_day_table_dic['in_use'], utilization_day_table_dic['utilization']]
                            value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                            common_sqlite3.insert_into_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, value_string, commit=False)
                        else:
                            # Clean up utilization database, only keep 3650 items.
                            utilization_day_table_count = common_sqlite3.get_sql_table_count(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name)

                            if utilization_day_table_count != 'N/A':
                                if int(utilization_day_table_count) > 3650:
                                    row_id = 'sample_time'
                                    begin_line = 0
                                    end_line = int(utilization_day_table_count) - 3650

                                    print('    Deleting database "' + str(utilization_day_db_file) + '" table "' + str(utilization_day_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                                    common_sqlite3.delete_sql_table_rows(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, row_id, begin_line, end_line)

                            select_condition = "WHERE sample_date='" + str(self.sample_date) + "'"
                            utilization_day_db_data_dic = common_sqlite3.get_sql_table_data(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, ['issued', 'in_use', 'utilization'], select_condition)

                            if utilization_day_db_data_dic:
                                # Replace sql table value.
                                set_condition = "SET issued='" + str(utilization_day_table_dic['issued']) + "', in_use='" + str(utilization_day_table_dic['in_use']) + "', utilization='" + str(utilization_day_table_dic['utilization']) + "'"
                                where_condition = "WHERE sample_date='" + str(self.sample_date) + "'"
                                common_sqlite3.update_sql_table_data(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, set_condition, where_condition, commit=False)
                            else:
                                # Insert sql table value.
                                value_list = [self.sample_date, utilization_day_table_dic['issued'], utilization_day_table_dic['in_use'], utilization_day_table_dic['utilization']]
                                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                                common_sqlite3.insert_into_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, value_string, commit=False)

                    utilization_day_db_conn.commit()
                    utilization_day_db_conn.close()

    def get_utilization_day_info(self, specified_license_server, specified_vendor_daemon):
        """
        Get current day issued/in_use/utilization info from sqlite3 database.
        Reture issued_avg/in_use_avg/utilization_avg info with utilization_day_dic.
        """
        utilization_day_dic = {}
        begin_time = str(self.sample_date) + ' 00:00:00'
        begin_second = time.mktime(time.strptime(begin_time, '%Y%m%d %H:%M:%S'))
        end_time = str(self.sample_date) + ' 23:59:59'
        end_second = time.mktime(time.strptime(end_time, '%Y%m%d %H:%M:%S'))
        select_condition = "WHERE sample_second BETWEEN '" + str(begin_second) + "' AND '" + str(end_second) + "'"

        for license_server in self.license_dic.keys():
            if license_server == specified_license_server:
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon == specified_vendor_daemon:
                        utilization_db_file = str(config.db_path) + '/license_server/' + str(license_server) + '/' + str(vendor_daemon) + '/utilization.db'

                        if os.path.exists(utilization_db_file):
                            (result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file, mode='read')

                            if result == 'passed':
                                utilization_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)

                                for utilization_table_name in utilization_table_list:
                                    # Get current day issued/in_use/utilization from sqlite3 database.
                                    utilization_db_data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, utilization_table_name, ['issued', 'in_use', 'utilization'], select_condition)

                                    if utilization_db_data_dic:
                                        # Get issued_sum/in_use_sum/utilization_sum info.
                                        issued_sum = 0
                                        in_use_sum = 0
                                        utilization_sum = 0

                                        for (i, issued) in enumerate(utilization_db_data_dic['issued']):
                                            if (issued == 'Uncounted') or (issued_sum == 'Uncounted'):
                                                issued_sum = 'Uncounted'
                                            else:
                                                issued_sum += int(issued)

                                            in_use_sum += int(utilization_db_data_dic['in_use'][i])
                                            utilization_sum += float(utilization_db_data_dic['utilization'][i])

                                        # Get issued_avg/in_use_avg/utilization_avg info.
                                        if issued_sum == 'Uncounted':
                                            issued_avg = 'Uncounted'
                                        else:
                                            issued_avg = round(issued_sum/len(utilization_db_data_dic['issued']), 1)

                                        in_use_avg = round(in_use_sum/len(utilization_db_data_dic['issued']), 1)
                                        utilization_avg = round(utilization_sum/len(utilization_db_data_dic['issued']), 1)

                                        utilization_day_dic[utilization_table_name] = {'issued': issued_avg, 'in_use': in_use_avg, 'utilization': utilization_avg}

        return utilization_day_dic

    def sampling(self):
        if hasattr(config, 'db_path') and config.db_path:
            if self.usage_sampling:
                p = Process(target=self.sample_usage_info)
                p.start()

            if self.utilization_sampling:
                p = Process(target=self.sample_utilization_info)
                p.start()

            p.join()
        else:
            common.bprint('No "db_path" is specified on config/config.py.', level='Error')
            sys.exit(1)


################
# Main Process #
################
def main():
    (usage, utilization) = read_args()
    my_sampling = Sampling(usage, utilization)
    my_sampling.detect_project_setting()
    my_sampling.sampling()


if __name__ == '__main__':
    main()
