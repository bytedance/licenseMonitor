# -*- coding: utf-8 -*-
################################
# File Name   : update_product_feature_relationship.py
# Author      : liyanqing.1987
# Created On  : 2023-12-15 10:54:38
# Description :
################################
import os
import re
import sys
import yaml
import copy
import argparse
import datetime

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license
from config import config
from tools import get_product_feature_relationship

os.environ['PYTHONUNBUFFERED'] = '1'
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
    parser.add_argument('-p', '--product_feature_relationship_file',
                        default='',
                        help='Specify original product feature relationship file.')
    parser.add_argument('-f', '--product_format',
                        default='<product_name>',
                        help='Specify product format, default is "<product_name>", only support "<product_id>" and "<product_name>" two variables.')
    parser.add_argument('-i', '--incremental_mode',
                        action='store_true',
                        default=False,
                        help='Enable incremental mode, default will replace old product feature relationship settings.')
    parser.add_argument('-o', '--output_file',
                        default='./product_feature.' + str(CURRENT_TIME) + '.yaml',
                        help='Output file, default is "./product_feature.<CURRENT_TIME>.yaml".')

    args = parser.parse_args()

    return args.LM_LICENSE_FILE_file, args.product_feature_relationship_file, args.product_format, args.incremental_mode, args.output_file


class UpdateProductFeatureRelationship():
    """
    Update origianl product feature relationship file with new product feature relationship.
    * Get LM_LICENSE_FILE from LM_LICENSE_FILE_file.
    * Get license files information for vendors "cdslmd/snpslmd/mgcld".
    * Parse license files and get product feature relationship.
    * Update original product feature relationship file with new product feature relationship.
    """
    def __init__(self, LM_LICENSE_FILE_file, orig_product_feature_relationship_file, product_format, incremental_mode, output_file):
        self.orig_product_feature_relationship_file = orig_product_feature_relationship_file
        self.product_format = product_format
        self.incremental_mode = incremental_mode
        self.output_file = output_file

        self.setenv(LM_LICENSE_FILE_file)

    def setenv(self, LM_LICENSE_FILE_file):
        """
        Setup environment variables LM_LICENSE_FILE with settings on LM_LICENSE_FILE file.
        """
        print('>>> Setup Environment variable LM_LICENSE_FILE with "' + str(LM_LICENSE_FILE_file) + '"')

        if not os.path.exists(LM_LICENSE_FILE_file):
            common.print_warning('*Warning*: "' + str(LM_LICENSE_FILE_file) + '": No such file.')
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

    def get_license_file_info(self):
        """
        Get vendor_daemon license files information.
        """
        print('>>> Get vendor daemon license files information')

        license_file_dic = {}
        my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        license_dic = my_get_license_info.get_license_info()
        valid_vendor_daemon_list = ['cdslmd', 'snpslmd', 'mgcld']

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon']:
                if vendor_daemon in valid_vendor_daemon_list:
                    license_file_dic.setdefault(vendor_daemon, [])
                    license_file_list = license_dic[license_server]['license_files'].split(':')

                    for license_file in license_file_list:
                        if license_file not in license_file_dic[vendor_daemon]:
                            license_file_dic[vendor_daemon].append(license_file)

        return license_file_dic

    def get_orig_product_feature_relationship(self):
        """
        Get orig_product_feature_relationship_dic from self.orig_product_feature_relationship_file.
        """
        orig_product_feature_relationship_dic = {}

        if os.path.exists(self.orig_product_feature_relationship_file):
            with open(self.orig_product_feature_relationship_file, 'r') as OPFRF:
                orig_product_feature_relationship_dic = yaml.load(OPFRF, Loader=yaml.FullLoader)

        return orig_product_feature_relationship_dic

    def run(self):
        """
        Update self.orig_product_feature_relationship_file with new product feature relationship from latest license files.
        Write final product feature relationship into self.output_file.
        """
        if os.environ['LM_LICENSE_FILE']:
            license_file_dic = self.get_license_file_info()

            if license_file_dic:
                vendor_list = []
                license_file_list = []

                for vendor_daemon in license_file_dic.keys():
                    for license_file in license_file_dic[vendor_daemon]:
                        if os.path.exists(license_file):
                            vendor_list.append(vendor_daemon)
                            license_file_list.append(license_file)

                my_get_product_feature_relationship = get_product_feature_relationship.GetProductFeatureRelationship(vendor_list, license_file_list, self.product_format, self.output_file)
                my_get_product_feature_relationship.run()
                product_feature_relationship_dic = my_get_product_feature_relationship.product_feature_relationship_dic

                if product_feature_relationship_dic:
                    orig_product_feature_relationship_dic = self.get_orig_product_feature_relationship()
                    new_product_feature_relationship_dic = copy.deepcopy(orig_product_feature_relationship_dic)

                    if not self.incremental_mode:
                        for vendor_daemon in product_feature_relationship_dic.keys():
                            new_product_feature_relationship_dic[vendor_daemon] = product_feature_relationship_dic[vendor_daemon]
                    else:
                        for vendor_daemon in product_feature_relationship_dic.keys():
                            if vendor_daemon not in new_product_feature_relationship_dic:
                                new_product_feature_relationship_dic[vendor_daemon] = product_feature_relationship_dic[vendor_daemon]
                            else:
                                for feature in product_feature_relationship_dic[vendor_daemon].keys():
                                    if feature not in new_product_feature_relationship_dic[vendor_daemon]:
                                        new_product_feature_relationship_dic[vendor_daemon][feature] = product_feature_relationship_dic[vendor_daemon][feature]
                                    else:
                                        for product in product_feature_relationship_dic[vendor_daemon][feature]:
                                            if product not in new_product_feature_relationship_dic[vendor_daemon][feature]:
                                                new_product_feature_relationship_dic[vendor_daemon][feature].append(product)

                    # Sort product list.
                    for vendor_daemon in new_product_feature_relationship_dic.keys():
                        for feature in new_product_feature_relationship_dic[vendor_daemon].keys():
                            new_product_feature_relationship_dic[vendor_daemon][feature].sort()

                    # Write output file.
                    if new_product_feature_relationship_dic:
                        my_get_product_feature_relationship.write_output_file(relationship_dic=new_product_feature_relationship_dic, output_file=self.output_file)


################
# Main Process #
################
def main():
    (LM_LICENSE_FILE_file, product_feature_relationship_file, product_format, incremental_mode, output_file) = read_args()
    my_update_product_feature_relationship = UpdateProductFeatureRelationship(LM_LICENSE_FILE_file, product_feature_relationship_file, product_format, incremental_mode, output_file)
    my_update_product_feature_relationship.run()


if __name__ == '__main__':
    main()
