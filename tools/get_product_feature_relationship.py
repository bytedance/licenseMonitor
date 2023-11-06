# -*- coding: utf-8 -*-
################################
# File Name   : get_product_feature_relationship.py
# Author      : liyanqing
# Created On  : 2021-11-30 17:25:47
# Description :
################################
import os
import re
import sys
import argparse
import yaml

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-v', '--vendors',
                        nargs='+',
                        default=[],
                        help='Required argument, specify vendor list, must be the same order of license_files.')
    parser.add_argument('-l', '--license_files',
                        required=True,
                        nargs='+',
                        default=[],
                        help='Required argument, specify license files.')
    parser.add_argument('-o', '--output_file',
                        default='',
                        help='Output file, yaml format.')

    args = parser.parse_args()

    # Check license file exists or not.
    for license_file in args.license_files:
        if not os.path.exists(license_file):
            common.print_error('*Error*: "' + str(license_file) + '": No such license file.')
            sys.exit(1)

    # Set default venodr setting.
    if not args.vendors:
        for license_file in args.license_files:
            args.vendors.append(os.path.basename(license_file))

    # Check vendor valid or not.
    valid_vendor_list = ['cdslmd', 'snpslmd', 'mgcld']

    for vendor in args.vendors:
        if vendor not in valid_vendor_list:
            common.print_error('*Error*: "' + str(vendor) + '": invalid vendor.')
            sys.exit(1)

    # Set default output file setting.
    if not args.output_file:
        if len(args.license_files) == 1:
            args.output_file = str(CWD) + '/' + str(os.path.basename(args.license_files[0])) + '.yaml'
        else:
            common.print_error('*Error*: No output file is specified.')
            sys.exit(1)

    # Check output directory exists or not.
    args.output_file = os.path.abspath(args.output_file)
    output_file_dir = os.path.dirname(args.output_file)

    if not os.path.exists(output_file_dir):
        common.print_error('*Error*: "' + str(output_file_dir) + '": No such output file directory.')
        sys.exit(1)

    # Check output file exists or not.
    if os.path.exists(args.output_file):
        common.print_error('*Error*: "' + str(args.output_file) + '": output file exists, please remove it first.')
        sys.exit(1)

    return (args.license_files, args.vendors, args.output_file)


class GetProductFeatureRelationship():
    def __init__(self):
        self.license_dic = {}

    def parse_cdslmd_license_file(self, license_file):
        """
        Parse cdslmd license file, get product_id/product_name/feature information.
        """
        product_id_compile = re.compile(r'^\s*#\s*Product\s+Id\s*:\s*(\S+?),.*$')
        product_name_compile = re.compile(r'^\s*#\s*Product\s+Name\s*:\s*(.+?)\s*$')
        feature_compile = re.compile(r'^\s*#\s*Feature\s*:\s*(.+?)\s+.*$')
        product_dic = {}
        product_dic_list = []

        with open(license_file, 'r') as LF:
            for line in LF.readlines():
                if product_id_compile.match(line):
                    if product_dic:
                        product_dic_list.append(product_dic)
                        product_dic = {}

                    my_match = product_id_compile.match(line)
                    product_id = my_match.group(1)
                    product_dic.setdefault('product_id', product_id)
                elif product_name_compile.match(line):
                    my_match = product_name_compile.match(line)
                    product_name = my_match.group(1)
                    product_dic.setdefault('product_name', product_name)
                elif feature_compile.match(line):
                    my_match = feature_compile.match(line)
                    feature = my_match.group(1)
                    product_dic.setdefault('feature', [])
                    product_dic['feature'].append(feature)

        if product_dic:
            product_dic_list.append(product_dic)

        return (product_dic_list)

    def parse_snpslmd_license_file(self, license_file):
        """
        Parse snpslmd license file, get product_id/product_name/feature information.
        """
        product_compile = re.compile(r'^\s*#\S*\s*Product\s*:.*$')
        separate_compile = re.compile(r'^\s*#\S*\s*----.*$')
        product_id_name_compile = re.compile(r'^\s*#\S*\s*(\S+?):\S+\s+(.+?)\s+0000.*$')
        feature_compile = re.compile(r'^\s*(FEATURE|PACKAGE|INCREMENT)\s+(\S+)\s+.*$')
        feature_id_compile = re.compile(r'^\s*[^#].*SN=RK:(.+?):.*$')
        feature = ''
        product_mark = 0
        product_dic_list = []

        with open(license_file, 'r') as LF:
            for line in LF.readlines():
                if (product_mark == 0) and product_compile.match(line):
                    product_mark = 1
                elif (product_mark == 1) and separate_compile.match(line):
                    product_mark = 2
                elif (product_mark == 2) and product_id_name_compile.match(line):
                    my_match = product_id_name_compile.match(line)
                    product_id = my_match.group(1)
                    product_name = my_match.group(2)
                    product_dic = {'product_id': product_id, 'product_name': product_name, 'feature': []}
                    product_dic_list.append(product_dic)
                elif (product_mark == 2) and separate_compile.match(line):
                    product_mark = 0
                elif (product_mark == 0) and feature_compile.match(line):
                    my_match = feature_compile.match(line)
                    feature = my_match.group(2)
                elif (product_mark == 0) and feature_id_compile.match(line):
                    my_match = feature_id_compile.match(line)
                    current_product_id = my_match.group(1)
                    find_mark = False

                    for (i, product_dic) in enumerate(product_dic_list):
                        if current_product_id == product_dic['product_id']:
                            if feature not in product_dic['feature']:
                                product_dic_list[i]['feature'].append(feature)

                            find_mark = True
                            break

                    if not find_mark:
                        common.print_warning('*Warning*: Not find product_id "' + str(current_product_id) + '" for feature "' + str(feature) + '".')

        return (product_dic_list)

    def parse_mgcld_license_file(self, license_file):
        """
        Parse mgcld license file, get product_id/product_name/feature information.
        """
        product_id_name_compile = re.compile(r'^\s*#\s*(\d+)\s+(.+?)\s+(\d+)\s*$')
        feature_compile1 = re.compile(r'^\s*#\s*(\S+)\s+(20\S+)\s+(\d+/\d+\d+)\s+(\d+/\d+/\d+)\s+(\d+)\s*$')
        feature_compile2 = re.compile(r'^\s*#\s*(\S+)\s+(20\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s*$')
        product_dic = {}
        product_dic_list = []

        with open(license_file, 'r', errors='ignore') as LF:
            for line in LF.readlines():
                if product_id_name_compile.match(line):
                    if product_dic:
                        product_dic_list.append(product_dic)
                        product_dic = {}

                    my_match = product_id_name_compile.match(line)
                    product_id = my_match.group(1)
                    product_name = my_match.group(2)
                    product_dic = {'product_id': product_id, 'product_name': product_name, 'feature': []}
                elif feature_compile1.match(line) or feature_compile2.match(line):
                    if feature_compile1.match(line):
                        my_match = feature_compile1.match(line)
                    elif feature_compile2.match(line):
                        my_match = feature_compile2.match(line)

                    feature = my_match.group(1)
                    product_dic.setdefault('feature', [])
                    product_dic['feature'].append(feature)

        return (product_dic_list)

    def switch_product_dic_list(self, product_dic_list):
        """
        Switch product_dic_list to feature_dic, to get feature-product relationship with dictory.
        """
        feature_dic = {}

        for product_dic in product_dic_list:
            product_name = product_dic['product_name']
            feature_list = product_dic['feature']

            for feature in feature_list:
                feature_dic.setdefault(feature, [])

                if product_name not in feature_dic[feature]:
                    feature_dic[feature].append(product_name)

        return (feature_dic)

    def parse_license_file(self, vendor, license_file):
        """
        Parse license file to get product-feature relationship.
        """
        # Parse license file.
        print('>>> Parse ' + str(vendor) + ' license file "' + str(license_file) + '".')

        feature_dic = {}

        if vendor == 'cdslmd':
            product_dic_list = self.parse_cdslmd_license_file(license_file)
            feature_dic = self.switch_product_dic_list(product_dic_list)
            self.license_dic.setdefault('cdslmd', feature_dic)
        elif vendor == 'snpslmd':
            product_dic_list = self.parse_snpslmd_license_file(license_file)
            feature_dic = self.switch_product_dic_list(product_dic_list)
            self.license_dic.setdefault('snpslmd', feature_dic)
        elif vendor == 'mgcld':
            product_dic_list = self.parse_mgcld_license_file(license_file)
            feature_dic = self.switch_product_dic_list(product_dic_list)
            self.license_dic.setdefault('mgcld', feature_dic)

        # Verify self.license_dic feature completeness.
        license_file_dic = common_license.parse_license_file(license_file)
        self.verify_product_dic(feature_dic, license_file_dic)

    def verify_product_dic(self, feature_dic, license_file_dic):
        # Get feature list from license_file_dic.
        license_file_feature_list = []

        for license_file_feature_dic in license_file_dic['feature']:
            if license_file_feature_dic['feature'] not in license_file_feature_list:
                license_file_feature_list.append(license_file_feature_dic['feature'])

        # Verify product_feature_list and liense_file_feature_list.
        for feature in license_file_feature_list:
            if feature not in feature_dic.keys():
                common.print_warning('*Warning*: No product_id/product_name information for feature "' + str(feature) + '".')

    def write_output_file(self, output_file, license_dic={}):
        """
        Write license_dic into output_file with yaml format.
        """
        # Set default license_dic.
        if not license_dic:
            license_dic = self.license_dic

        # Write output_file.
        print('')
        print('>>> Write output file "' + str(output_file) + '".')

        with open(output_file, 'w', encoding='utf-8') as OF:
            yaml.dump(license_dic, OF)


################
# Main Process #
################
def main():
    (license_file_list, vendor_list, output_file) = read_args()
    my_get_product_feature_relationship = GetProductFeatureRelationship()

    for (i, license_file) in enumerate(license_file_list):
        vendor = vendor_list[i]
        my_get_product_feature_relationship.parse_license_file(vendor, license_file)

    my_get_product_feature_relationship.write_output_file(output_file)


if __name__ == '__main__':
    main()
