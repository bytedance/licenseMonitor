# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import time
import copy
import yaml
import getpass
import datetime
import argparse

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QAction, qApp, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QMessageBox, QLineEdit, QComboBox, QHeaderView, QDateEdit, QFileDialog, QMenu
from PyQt5.QtGui import QIcon, QBrush, QFont
from PyQt5.QtCore import Qt, QThread, QDate

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_pyqt5
from common import common_license
from common import common_sqlite3
from config import config

os.environ['PYTHONUNBUFFERED'] = '1'
USER = getpass.getuser()

# Solve some unexpected warning message.
if 'XDG_RUNTIME_DIR' not in os.environ:
    os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-' + str(USER)

    if not os.path.exists(os.environ['XDG_RUNTIME_DIR']):
        os.makedirs(os.environ['XDG_RUNTIME_DIR'])

    os.chmod(os.environ['XDG_RUNTIME_DIR'], stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-f", "--feature",
                        default='',
                        help='Specify license feature which you want to see on "FEATURE/EXPIRES/USAGE/UTILIZATION/COST" tab.')
    parser.add_argument("-u", "--user",
                        default='',
                        help='Specify the user on "USAGE" tab.')
    parser.add_argument("-t", "--tab",
                        default='FEATURE',
                        choices=['SERVER', 'FEATURE', 'EXPIRES', 'USAGE', 'UTILIZATION', 'COST'],
                        help='Specify current tab, default is "FEATURE" tab.')

    args = parser.parse_args()

    # Set default tab for args.feature.
    if args.feature and (not args.tab):
        args.tab = 'FEATURE'

    # Set default tab for args.user.
    if args.user and (not args.tab):
        args.tab = 'USAGE'

    return (args.feature, args.user, args.tab)


class MainWindow(QMainWindow):
    """
    Main window of licenseMonitor.
    """
    def __init__(self, specified_feature, specified_user, specified_tab):
        super().__init__()
        self.license_dic = {}

        # Enable detail information on UTILIZATION tab.
        self.enable_utilization_detail = False

        # Enable "product" instead of "feature".
        self.enable_utilization_product = False
        self.enable_cost_product = False

        # Basic setting.
        self.db_dic = self.get_db_info()
        self.license_dic_second = 0

        # Get administrator list.
        if hasattr(config, 'administrators') and config.administrators:
            self.administrator_list = config.administrators.split()
        else:
            common.print_warning('*Warning*: No "administrators" is specified on config file, some functions are limited.')
            self.administrator_list = []

        # Notice no-admin user.
        if ('all' not in self.administrator_list) and ('ALL' not in self.administrator_list) and (USER not in self.administrator_list):
            common.print_warning('*Warning*: You are not administrator, cannot access some function!')

        # Get project related information.
        project_list_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_list'
        self.project_list = common_license.parse_project_list_file(project_list_file)

        # Get self.project_setting_dic.
        project_setting_dic = {}
        self.project_setting_dic = {}
        self.project_setting_create_second_list = []
        project_setting_db_path = str(config.db_path) + '/project_setting'

        if os.path.exists(project_setting_db_path):
            project_setting_dic = common_license.parse_project_setting_db_path(project_setting_db_path)
        else:
            common.print_warning('*Warning*: "' + str(project_setting_db_path) + '": No such directory.')

        for create_time in project_setting_dic.keys():
            create_second = int(time.mktime(time.strptime(str(create_time), '%Y%m%d%H%M%S')))
            self.project_setting_dic.setdefault(create_second, project_setting_dic[create_time])
            self.project_setting_create_second_list.append(create_second)

        # Get feature/product filter list.
        self.utilization_white_feature_list = self.parse_feature_product_filter_file('utilization', 'white', 'feature')
        self.utilization_black_feature_list = self.parse_feature_product_filter_file('utilization', 'black', 'feature')
        self.utilization_white_product_list = self.parse_feature_product_filter_file('utilization', 'white', 'product')
        self.utilization_black_product_list = self.parse_feature_product_filter_file('utilization', 'black', 'product')
        self.cost_white_feature_list = self.parse_feature_product_filter_file('cost', 'white', 'feature')
        self.cost_black_feature_list = self.parse_feature_product_filter_file('cost', 'black', 'feature')
        self.cost_white_product_list = self.parse_feature_product_filter_file('cost', 'white', 'product')
        self.cost_black_product_list = self.parse_feature_product_filter_file('cost', 'black', 'product')

        # Enable "others" project on COST tab.
        if hasattr(config, 'enable_cost_others_project'):
            self.enable_cost_others_project = config.enable_cost_others_project
        else:
            self.enable_cost_others_project = True

        if self.enable_cost_others_project:
            self.project_list.append('others')

        # Generate GUI.
        self.init_ui()

        # Pre-set feature.
        if specified_feature:
            self.feature_tab_feature_line.setText(specified_feature)
            self.expires_tab_feature_line.setText(specified_feature)
            self.usage_tab_feature_line.setText(specified_feature)

            if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
                self.utilization_tab_feature_line.setText(specified_feature)
                self.cost_tab_feature_line.setText(specified_feature)

        # Pre-set user.
        if specified_user:
            self.usage_tab_user_line.setText(specified_user)

        # For pre-set feature or pre-set user, update tab.
        if specified_feature or specified_user:
            self.get_license_dic(force=True)

            if specified_feature:
                self.filter_feature_tab_license_feature(get_license_info=False)
                self.filter_expires_tab_license_feature(get_license_info=False)
                self.filter_usage_tab_license_feature(get_license_info=False)

                if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
                    self.filter_utilization_tab()
                    self.filter_cost_tab()

            if specified_user and (not specified_feature):
                self.filter_usage_tab_license_feature(get_license_info=False)

        # For pre-set tab.
        self.switch_tab(specified_tab)

    def get_license_dic(self, force=False):
        # Not update license_dic repeatedly in config.fresh_interval seconds.
        current_second = int(time.time())

        if not force:
            if hasattr(config, 'fresh_interval') and config.fresh_interval:
                if current_second - self.license_dic_second <= int(config.fresh_interval):
                    return

        self.license_dic_second = current_second

        # Print loading license informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading license info, please wait a moment ...')

        # Print loading license informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading license info, please wait a moment ...')
        my_show_message.start()

        # Get self.license_dic.
        LM_LICENSE_FILE_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/LM_LICENSE_FILE'

        if os.path.exists(LM_LICENSE_FILE_file) and (('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list)):
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
        elif config.lmstat_path and not os.path.exists(config.lmstat_path):
            common.print_warning('*Warning*: "' + str(config.lmstat_path) + '": no such lmstat file!')
            config.lmstat_path = ''

        if not hasattr(config, 'lmstat_bsub_command'):
            config.lmstat_bsub_command = ''

        my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        self.license_dic = my_get_license_info.get_license_info()

        # Print loading license informaiton message with GUI. (END)
        my_show_message.terminate()

        if not self.license_dic:
            common.print_warning('*Warning*: Not find any valid license information.')

    def get_license_server_list(self, license_dic={}):
        """
        Get all license_server on specified license_dic.
        """
        license_server_list = []

        if not license_dic:
            license_dic = self.license_dic

        for license_server in license_dic.keys():
            if license_server not in license_server_list:
                license_server_list.append(license_server)

        return (license_server_list)

    def get_vendor_daemon_list(self, license_dic={}, specified_license_server_list=['ALL', ]):
        """
        Get vendor_daemon on specified license_dic with specified license_server_list.
        """
        vendor_daemon_list = []

        if not license_dic:
            license_dic = self.license_dic

        for license_server in license_dic.keys():
            if ('ALL' in specified_license_server_list) or (license_server in specified_license_server_list):
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        return (vendor_daemon_list)

    def get_db_info(self):
        """
        Get curve/utilization/usage database information.
        """
        db_dic = {}

        if hasattr(config, 'db_path') and config.db_path and os.path.exists(config.db_path):
            license_server_db_path = str(config.db_path) + '/license_server'

            if not os.path.exists(license_server_db_path):
                common.print_warning('*Warning*: "' + str(license_server_db_path) + '": No such directory.')
            else:
                for license_server in os.listdir(license_server_db_path):
                    license_server_path = str(license_server_db_path) + '/' + str(license_server)

                    if re.match(r'^\d+@\S+$', license_server) and os.path.isdir(license_server_path):
                        db_dic.setdefault(license_server, {})

                        for vendor_daemon in os.listdir(license_server_path):
                            vendor_daemon_path = str(license_server_path) + '/' + str(vendor_daemon)
                            curve_db_path = str(vendor_daemon_path) + '/utilization.db'
                            usage_db_path = str(vendor_daemon_path) + '/usage.db'

                            if self.enable_utilization_detail:
                                utilization_db_path = str(vendor_daemon_path) + '/utilization.db'
                            else:
                                utilization_db_path = str(vendor_daemon_path) + '/utilization_day.db'

                            if os.path.isdir(vendor_daemon_path):
                                db_dic[license_server].setdefault(vendor_daemon, {})

                                if os.path.exists(curve_db_path):
                                    db_dic[license_server][vendor_daemon].setdefault('curve', curve_db_path)

                                if os.path.exists(usage_db_path):
                                    db_dic[license_server][vendor_daemon].setdefault('usage', usage_db_path)

                                if os.path.exists(utilization_db_path):
                                    db_dic[license_server][vendor_daemon].setdefault('utilization', utilization_db_path)

        return db_dic

    def parse_feature_product_filter_file(self, tab_name, filter_type, item_name):
        """
        Parse feature/product white/black filter file for UTILIZATION/COST tab, return feature/product list.
        """
        filter_list = []
        filter_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/' + str(tab_name) + '/' + str(tab_name) + '_' + str(filter_type) + '_' + str(item_name)

        if os.path.exists(filter_file):
            with open(filter_file, 'r') as FF:
                for line in FF.readlines():
                    if re.match(r'^\s*(#.*)?$', line):
                        continue
                    else:
                        filter_list.append(line.strip())

        return filter_list

    def init_ui(self):
        """
        Main process, draw the main graphic frame.
        """
        # Add menubar.
        self.gen_menubar()

        # Define main Tab widget
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        # Define four sub-tabs (JOB/JOBS/HOSTS/QUEUES)
        self.server_tab = QWidget()
        self.feature_tab = QWidget()
        self.expires_tab = QWidget()
        self.usage_tab = QWidget()

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            self.curve_tab = QWidget()
            self.utilization_tab = QWidget()
            self.cost_tab = QWidget()

        # Add the sub-tabs into main Tab widget
        self.main_tab.addTab(self.server_tab, 'SERVER')
        self.main_tab.addTab(self.feature_tab, 'FEATURE')
        self.main_tab.addTab(self.expires_tab, 'EXPIRES')
        self.main_tab.addTab(self.usage_tab, 'USAGE')

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            self.main_tab.addTab(self.curve_tab, 'CURVE')
            self.main_tab.addTab(self.utilization_tab, 'UTILIZATION')
            self.main_tab.addTab(self.cost_tab, 'COST')

        # Get License information.
        self.get_license_dic()

        # Generate the sub-tabs
        self.gen_server_tab()
        self.gen_feature_tab()
        self.gen_expires_tab()
        self.gen_usage_tab()

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            self.gen_curve_tab()
            self.gen_utilization_tab()
            self.gen_cost_tab()

        # Show main window
        self.setWindowTitle('licenseMonitor')
        self.resize(1200, 580)
        self.setWindowTitle('licenseMonitor')
        self.setWindowIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/monitor.ico'))
        common_pyqt5.center_window(self)

    def switch_tab(self, specified_tab):
        """
        Switch to the specified Tab.
        """
        tab_dic = {
                   'SERVER': self.server_tab,
                   'FEATURE': self.feature_tab,
                   'EXPIRES': self.expires_tab,
                   'USAGE': self.usage_tab,
                  }

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            tab_dic['CURVE'] = self.curve_tab,
            tab_dic['UTILIZATION'] = self.utilization_tab,
            tab_dic['COST'] = self.cost_tab,

        self.main_tab.setCurrentWidget(tab_dic[specified_tab])

    def gen_menubar(self):
        """
        Generate menubar.
        """
        menubar = self.menuBar()

        # File
        export_server_table_action = QAction('Export server table', self)
        export_server_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_server_table_action.triggered.connect(self.export_server_table)

        export_feature_table_action = QAction('Export feature table', self)
        export_feature_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_feature_table_action.triggered.connect(self.export_feature_table)

        export_expires_table_action = QAction('Export expires table', self)
        export_expires_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_expires_table_action.triggered.connect(self.export_expires_table)

        export_usage_table_action = QAction('Export usage table', self)
        export_usage_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_usage_table_action.triggered.connect(self.export_usage_table)

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            export_curve_table_action = QAction('Export curve table', self)
            export_curve_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
            export_curve_table_action.triggered.connect(self.export_curve_table)

            export_utilization_table_action = QAction('Export utilization table', self)
            export_utilization_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
            export_utilization_table_action.triggered.connect(self.export_utilization_table)

            export_cost_table_action = QAction('Export cost table', self)
            export_cost_table_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
            export_cost_table_action.triggered.connect(self.export_cost_table)

        exit_action = QAction('Exit', self)
        exit_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/exit.png'))
        exit_action.triggered.connect(qApp.quit)

        file_menu = menubar.addMenu('File')
        file_menu.addAction(export_server_table_action)
        file_menu.addAction(export_feature_table_action)
        file_menu.addAction(export_expires_table_action)
        file_menu.addAction(export_usage_table_action)

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            file_menu.addAction(export_curve_table_action)
            file_menu.addAction(export_utilization_table_action)
            file_menu.addAction(export_cost_table_action)

        file_menu.addAction(exit_action)

        # Setup
        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            enable_utilization_detail_action = QAction('Enable Utilization Detail', self, checkable=True)
            enable_utilization_detail_action.triggered.connect(self.func_enable_utilization_detail)

            enable_utilization_product_action = QAction('Enable Utilization Product', self, checkable=True)
            enable_utilization_product_action.triggered.connect(self.func_enable_utilization_product)

            enable_cost_product_action = QAction('Enable Cost Product', self, checkable=True)
            enable_cost_product_action.triggered.connect(self.func_enable_cost_product)

            enable_cost_others_project_action = QAction('Enable Cost Others Project', self, checkable=True)
            enable_cost_others_project_action.triggered.connect(self.func_enable_cost_others_project)

            if self.enable_cost_others_project:
                enable_cost_others_project_action.setChecked(True)

        setup_menu = menubar.addMenu('Setup')

        if ('all' in self.administrator_list) or ('ALL' in self.administrator_list) or (USER in self.administrator_list):
            setup_menu.addAction(enable_utilization_detail_action)
            setup_menu.addAction(enable_utilization_product_action)
            setup_menu.addAction(enable_cost_product_action)
            setup_menu.addAction(enable_cost_others_project_action)

        # Help
        version_action = QAction('Version', self)
        version_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/version.png'))
        version_action.triggered.connect(self.show_version)

        about_action = QAction('About licenseMonitor', self)
        about_action.setIcon(QIcon(str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/data/pictures/about.png'))
        about_action.triggered.connect(self.show_about)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(version_action)
        help_menu.addAction(about_action)

    def func_enable_utilization_detail(self, state):
        """
        Show detail information for utilization curve on UTILIZATION tab.
        """
        if state:
            self.enable_utilization_detail = True
            self.db_dic = self.get_db_info()
            self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addDays(-7))
        else:
            self.enable_utilization_detail = False
            self.db_dic = self.get_db_info()
            self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

    def func_enable_utilization_product(self, state):
        """
        Switch "feature" to "product" on UTILIZATION tab if enable_utilization_product_action is selected.
        """
        if state:
            self.enable_utilization_product = True
        else:
            self.enable_utilization_product = False

    def switch_product_on_utilization_dic(self, utilization_dic):
        """
        Switch "feature" to "product" on utilization_dic.
        """
        product_utilization_dic = {}
        specified_license_product = self.utilization_tab_product_line.text().strip()
        product_feature_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/product_feature/product_feature.yaml'

        if os.path.exists(product_feature_file):
            with open(product_feature_file, 'r') as PFF:
                product_feature_dic = yaml.load(PFF, Loader=yaml.FullLoader)

                for vendor_daemon in product_feature_dic.keys():
                    for feature in product_feature_dic[vendor_daemon].keys():
                        for product in product_feature_dic[vendor_daemon][feature]:
                            if (feature in utilization_dic) and (vendor_daemon in utilization_dic[feature]):
                                if (not specified_license_product) or (specified_license_product == product):
                                    product_utilization_dic.setdefault(product, {})
                                    product_utilization_dic[product].setdefault(vendor_daemon, {})

                                    sample_date_dic = utilization_dic[feature][vendor_daemon]

                                    if not product_utilization_dic[product][vendor_daemon]:
                                        product_utilization_dic[product][vendor_daemon] = sample_date_dic
                                    else:
                                        for sample_date in sample_date_dic.keys():
                                            if sample_date not in product_utilization_dic[product][vendor_daemon].keys():
                                                product_utilization_dic[product][vendor_daemon].setdefault(sample_date, sample_date_dic[sample_date])
                                            elif product_utilization_dic[product][vendor_daemon][sample_date]['utilization'] < sample_date_dic[sample_date]['utilization']:
                                                product_utilization_dic[product][vendor_daemon][sample_date]['utilization'] = sample_date_dic[sample_date]['utilization']

        # Filter with white/black product list.
        filtered_product_utilization_dic = copy.deepcopy(product_utilization_dic)

        if self.utilization_white_product_list:
            filtered_product_utilization_dic = {}

            for white_product in self.utilization_white_product_list:
                for product in product_utilization_dic.keys():
                    if re.match(white_product, product):
                        filtered_product_utilization_dic[product] = product_utilization_dic[product]
        elif self.utilization_black_product_list:
            for black_product in self.utilization_black_product_list:
                for product in product_utilization_dic.keys():
                    if re.match(black_product, product):
                        del filtered_product_utilization_dic[product]

        return filtered_product_utilization_dic

    def func_enable_cost_product(self, state):
        """
        Switch "feature" to "product" on COST tab if enable_cost_product_action is selected.
        """
        if state:
            self.enable_cost_product = True
        else:
            self.enable_cost_product = False

    def switch_product_on_cost_dic(self, cost_dic):
        """
        Switch "feature" to "product" on cost_dic.
        """
        product_cost_dic = {}
        specified_license_product = self.cost_tab_product_line.text().strip()
        product_feature_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/product_feature/product_feature.yaml'

        if os.path.exists(product_feature_file):
            with open(product_feature_file, 'r') as PFF:
                product_feature_dic = yaml.load(PFF, Loader=yaml.FullLoader)

                for vendor_daemon in product_feature_dic.keys():
                    for feature in product_feature_dic[vendor_daemon].keys():
                        for product in product_feature_dic[vendor_daemon][feature]:
                            if (feature in cost_dic) and (vendor_daemon in cost_dic[feature]):
                                if (not specified_license_product) or (specified_license_product == product):
                                    product_cost_dic.setdefault(product, {})
                                    product_cost_dic[product].setdefault(vendor_daemon, {})
                                    project_dic = cost_dic[feature][vendor_daemon]

                                    if not product_cost_dic[product][vendor_daemon]:
                                        product_cost_dic[product][vendor_daemon] = project_dic
                                    else:
                                        for project in project_dic.keys():
                                            if project not in product_cost_dic[product][vendor_daemon].keys():
                                                product_cost_dic[product][vendor_daemon].setdefault(project, project_dic[project])
                                            else:
                                                product_cost_dic[product][vendor_daemon][project] += project_dic[project]

        # Filter with white/black product list.
        filtered_product_cost_dic = copy.deepcopy(product_cost_dic)

        if self.cost_white_product_list:
            filtered_product_cost_dic = {}

            for white_product in self.cost_white_product_list:
                for product in product_cost_dic.keys():
                    if re.match(white_product, product):
                        filtered_product_cost_dic[product] = product_cost_dic[product]
        elif self.cost_black_product_list:
            for black_product in self.cost_black_product_list:
                for product in product_cost_dic.keys():
                    if re.match(black_product, product):
                        del filtered_product_cost_dic[product]

        return filtered_product_cost_dic

    def func_enable_cost_others_project(self, state):
        """
        Class no-project license usage to "others" project with self.enable_cost_others_project.
        """
        if state:
            self.enable_cost_others_project = True

            if 'others' not in self.project_list:
                self.project_list.append('others')
        else:
            self.enable_cost_others_project = False

            if 'others' in self.project_list:
                self.project_list.remove('others')

    def show_version(self):
        """
        Show licenseMonitor version information.
        """
        version = 'V1.3'
        QMessageBox.about(self, 'licenseMonitor', 'Version: ' + str(version) + '        ')

    def show_about(self):
        """
        Show licenseMonitor about information.
        """
        about_message = """
Thanks for downloading licenseMonitor.

licenseMonitor is an open source software for EDA software license information data-collection, data-analysis and data-display.
"""

        QMessageBox.about(self, 'licenseMonitor', about_message)

# For SERVER TAB (start) #
    def gen_server_tab(self):
        """
        Generate SERVER tab, show license server/vendor information.
        """
        self.server_tab_table = QTableWidget(self.server_tab)

        # Grid
        server_tab_grid = QGridLayout()
        server_tab_grid.addWidget(self.server_tab_table, 0, 0)
        self.server_tab.setLayout(server_tab_grid)

        # Generate self.server_tab_table
        self.gen_server_tab_table()

    def gen_server_tab_table(self):
        self.server_tab_table.setShowGrid(True)
        self.server_tab_table.setSortingEnabled(True)
        self.server_tab_table.setColumnCount(0)
        self.server_tab_table_title_list = ['Server', 'Server_Status', 'Server_Version', 'License_Files', 'Vendor', 'Vendor_Status', 'Vendor_Version']
        self.server_tab_table.setColumnCount(len(self.server_tab_table_title_list))
        self.server_tab_table.setHorizontalHeaderLabels(self.server_tab_table_title_list)

        # Set column width
        self.server_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.server_tab_table.setColumnWidth(1, 110)
        self.server_tab_table.setColumnWidth(2, 110)
        self.server_tab_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.server_tab_table.setColumnWidth(4, 90)
        self.server_tab_table.setColumnWidth(5, 120)
        self.server_tab_table.setColumnWidth(6, 120)

        # Get and update license_dic
        license_dic = copy.deepcopy(self.license_dic)

        for license_server in license_dic.keys():
            if not license_dic[license_server]['vendor_daemon']:
                license_dic[license_server]['vendor_daemon'].setdefault('', {'vendor_daemon_status': '', 'vendor_daemon_version': ''})

        # Set self.server_tab_table.setRowCount
        row = 0

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                row += 1

        self.server_tab_table.setRowCount(row)

        # Set item
        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                column = 0
                row += 1

                # For Server
                item = QTableWidgetItem()
                item.setText(license_server)

                if license_dic[license_server]['license_server_status'] != 'UP':
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For Server_Status
                column += 1
                item = QTableWidgetItem()
                item.setText(license_dic[license_server]['license_server_status'])

                if license_dic[license_server]['license_server_status'] != 'UP':
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For Server_Version
                column += 1
                item = QTableWidgetItem()
                item.setText(license_dic[license_server]['license_server_version'])

                if license_dic[license_server]['license_server_status'] != 'UP':
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For license_files
                column += 1
                item = QTableWidgetItem()
                item.setText(license_dic[license_server]['license_files'])

                if license_dic[license_server]['license_server_status'] != 'UP':
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For Vendor
                column += 1
                item = QTableWidgetItem()
                item.setText(vendor_daemon)

                if (license_dic[license_server]['license_server_status'] != 'UP') or (license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'] != 'UP'):
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For Vendor_Status
                column += 1
                item = QTableWidgetItem()
                item.setText(license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'])

                if (license_dic[license_server]['license_server_status'] != 'UP') or (license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'] != 'UP'):
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)

                # For Vendor_Version
                column += 1
                item = QTableWidgetItem()
                item.setText(license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_version'])

                if (license_dic[license_server]['license_server_status'] != 'UP') or (license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'] != 'UP'):
                    item.setBackground(QBrush(Qt.red))

                self.server_tab_table.setItem(row, column, item)
# For SERVER TAB (end) #

# For FEATURE TAB (start) #
    def gen_feature_tab(self):
        """
        Generate FEATURE tab, show license feature usage information.
        """
        self.feature_tab_frame = QFrame(self.feature_tab)
        self.feature_tab_frame.setFrameShadow(QFrame.Raised)
        self.feature_tab_frame.setFrameShape(QFrame.Box)

        self.feature_tab_table = QTableWidget(self.feature_tab)
        self.feature_tab_table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Grid
        feature_tab_grid = QGridLayout()

        feature_tab_grid.addWidget(self.feature_tab_frame, 0, 0)
        feature_tab_grid.addWidget(self.feature_tab_table, 1, 0)

        feature_tab_grid.setRowStretch(0, 1)
        feature_tab_grid.setRowStretch(1, 10)

        self.feature_tab.setLayout(feature_tab_grid)

        # Generate self.feature_tab_frame and self.feature_tab_table
        self.gen_feature_tab_frame()
        self.gen_feature_tab_table(self.license_dic)
        self.feature_tab_table.customContextMenuRequested.connect(self.generate_feature_menu)
        self.feature_tab_table.itemClicked.connect(self.feature_tab_table_check_click)

    def generate_feature_menu(self, pos):
        menu = QMenu()
        row = self.feature_tab_table.currentIndex().row()
        server = self.feature_tab_table.item(row, 0).text().strip()
        vendor = self.feature_tab_table.item(row, 1).text().strip()
        feature = self.feature_tab_table.item(row, 2).text().strip()
        user = ''

        action = QAction('View License Log')
        action.triggered.connect(lambda: self.gen_license_log_window(server=server, vendor=vendor, feature=feature, user=user))
        menu.addAction(action)

        menu.exec_(self.feature_tab_table.mapToGlobal(pos))

    def gen_license_log_window(self, server='', vendor='', feature='', user=''):
        # Generate license log window
        lic_files = ''

        if server in self.license_dic:
            if 'license_files' in self.license_dic[server]:
                lic_files = self.license_dic[server]['license_files']

        self.license_log_tab = LicenseLogWindow(server=server, vendor=vendor, feature=feature, user=user, lic_files=lic_files)
        self.license_log_tab.show()

    def gen_feature_tab_frame(self):
        # Show
        feature_tab_show_label = QLabel('Show', self.feature_tab_frame)
        feature_tab_show_label.setStyleSheet('font-weight: bold;')
        feature_tab_show_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_tab_show_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_show_combo()
        self.feature_tab_show_combo.activated.connect(self.filter_feature_tab_license_feature)

        # License Server
        feature_tab_server_label = QLabel('Server', self.feature_tab_frame)
        feature_tab_server_label.setStyleSheet('font-weight: bold;')
        feature_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_tab_server_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_server_combo()
        self.feature_tab_server_combo.activated.connect(self.feature_tab_server_combo_changed)

        # Vendor Daemon
        feature_tab_vendor_label = QLabel('Vendor', self.feature_tab_frame)
        feature_tab_vendor_label.setStyleSheet('font-weight: bold;')
        feature_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_tab_vendor_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_vendor_combo()
        self.feature_tab_vendor_combo.activated.connect(self.feature_tab_vendor_combo_changed)

        # License Feature
        feature_tab_feature_label = QLabel('Feature', self.feature_tab_frame)
        feature_tab_feature_label.setStyleSheet('font-weight: bold;')
        feature_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_tab_feature_line = QLineEdit()
        self.feature_tab_feature_line.returnPressed.connect(self.filter_feature_tab_license_feature)

        # Filter Button
        feature_tab_check_button = QPushButton('Check', self.feature_tab_frame)
        feature_tab_check_button.clicked.connect(self.filter_feature_tab_license_feature)

        # Grid
        feature_tab_frame_grid = QGridLayout()

        feature_tab_frame_grid.addWidget(feature_tab_show_label, 0, 0)
        feature_tab_frame_grid.addWidget(self.feature_tab_show_combo, 0, 1)
        feature_tab_frame_grid.addWidget(feature_tab_server_label, 0, 2)
        feature_tab_frame_grid.addWidget(self.feature_tab_server_combo, 0, 3)
        feature_tab_frame_grid.addWidget(feature_tab_vendor_label, 0, 4)
        feature_tab_frame_grid.addWidget(self.feature_tab_vendor_combo, 0, 5)
        feature_tab_frame_grid.addWidget(feature_tab_feature_label, 0, 6)
        feature_tab_frame_grid.addWidget(self.feature_tab_feature_line, 0, 7)
        feature_tab_frame_grid.addWidget(feature_tab_check_button, 0, 8)

        feature_tab_frame_grid.setColumnStretch(0, 1)
        feature_tab_frame_grid.setColumnStretch(1, 1)
        feature_tab_frame_grid.setColumnStretch(2, 1)
        feature_tab_frame_grid.setColumnStretch(3, 1)
        feature_tab_frame_grid.setColumnStretch(4, 1)
        feature_tab_frame_grid.setColumnStretch(5, 1)
        feature_tab_frame_grid.setColumnStretch(6, 1)
        feature_tab_frame_grid.setColumnStretch(7, 1)
        feature_tab_frame_grid.setColumnStretch(8, 1)

        self.feature_tab_frame.setLayout(feature_tab_frame_grid)

    def set_feature_tab_show_combo(self):
        self.feature_tab_show_combo.clear()
        self.feature_tab_show_combo.addItem('ALL')
        self.feature_tab_show_combo.addItem('IN_USE')
        self.feature_tab_show_combo.addItem('NOT_USED')

    def set_feature_tab_server_combo(self):
        self.feature_tab_server_combo.clear()
        self.feature_tab_server_combo.addItem('ALL')

        for license_server in self.license_dic.keys():
            self.feature_tab_server_combo.addItem(license_server)

    def set_feature_tab_vendor_combo(self):
        self.feature_tab_vendor_combo.clear()

        # Get vendor_daemon list.
        vendor_daemon_list = ['ALL', ]
        selected_license_server = self.feature_tab_server_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        # Fill self.feature_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.feature_tab_vendor_combo.addItem(vendor_daemon)

    def feature_tab_server_combo_changed(self):
        self.set_feature_tab_vendor_combo()
        self.filter_feature_tab_license_feature()

    def feature_tab_vendor_combo_changed(self):
        if self.feature_tab_vendor_combo.count() > 2:
            self.filter_feature_tab_license_feature()

    def filter_feature_tab_license_feature(self, get_license_info=True):
        # Re-generate self.feature_tab_table.
        if get_license_info:
            self.get_license_dic()

        if self.license_dic:
            selected_license_server = self.feature_tab_server_combo.currentText().strip()
            selected_vendor_daemon = self.feature_tab_vendor_combo.currentText().strip()
            specified_license_feature_list = self.feature_tab_feature_line.text().strip().split()
            show_mode = self.feature_tab_show_combo.currentText().strip()

            filter_license_dic = common_license.FilterLicenseDic()
            filtered_license_dic = filter_license_dic.run(license_dic=self.license_dic, server_list=[selected_license_server, ], vendor_list=[selected_vendor_daemon, ], feature_list=specified_license_feature_list, show_mode=show_mode)

            # Update self.feature_tab_table
            self.gen_feature_tab_table(filtered_license_dic)

    def feature_tab_table_check_click(self, item=None):
        if item is not None:
            if item.column() == 4:
                in_use_num = self.feature_tab_table.item(item.row(), item.column()).text().strip()

                if in_use_num != '0':
                    # Reset self.usage_tab_server_combo on USAGE tab.
                    current_license_server = self.feature_tab_table.item(item.row(), 0).text().strip()
                    license_server_list = self.get_license_server_list()
                    license_server_list.remove(current_license_server)
                    license_server_list.insert(0, 'ALL')
                    license_server_list.insert(0, current_license_server)

                    self.set_usage_tab_server_combo(license_server_list)

                    # Reset self.usage_tab_vendor_combo on USAGE tab.
                    current_vendor_daemon = self.feature_tab_table.item(item.row(), 1).text().strip()
                    vendor_daemon_list = self.get_vendor_daemon_list()
                    vendor_daemon_list.remove(current_vendor_daemon)
                    vendor_daemon_list.insert(0, 'ALL')
                    vendor_daemon_list.insert(0, current_vendor_daemon)

                    self.set_usage_tab_vendor_combo(vendor_daemon_list)

                    # Reset self.usage_tab_feature_line on USAGE tab.
                    current_feature = self.feature_tab_table.item(item.row(), 2).text().strip()
                    self.usage_tab_feature_line.setText(current_feature)

                    # Clear self.usage_tab_user_line on USAGE tab.
                    self.usage_tab_user_line.setText('')

                    # Switch to USGAE tab, filter USAGE tab license feature.
                    self.main_tab.setCurrentWidget(self.usage_tab)
                    self.filter_usage_tab_license_feature()

    def gen_feature_tab_table(self, license_dic):
        # Get license feature num.
        license_feature_num = 0

        if license_dic:
            for license_server in license_dic.keys():
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                        license_feature_num += 1

        # Fill self.feature_tab_table column.
        self.feature_tab_table.setShowGrid(True)
        self.feature_tab_table.setSortingEnabled(True)
        self.feature_tab_table.setColumnCount(0)
        self.feature_tab_table.setColumnCount(5)
        self.feature_tab_table_title_list = ['Server', 'Vendor', 'Feature', 'Total_License', 'In_Use_License']
        self.feature_tab_table.setHorizontalHeaderLabels(self.feature_tab_table_title_list)

        self.feature_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.feature_tab_table.setColumnWidth(1, 120)
        self.feature_tab_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.feature_tab_table.setColumnWidth(3, 160)
        self.feature_tab_table.setColumnWidth(4, 160)

        # Fill self.feature_tab_table row.
        self.feature_tab_table.setRowCount(0)
        self.feature_tab_table.setRowCount(license_feature_num)

        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    row += 1

                    # For Server.
                    item = QTableWidgetItem()
                    item.setText(license_server)
                    self.feature_tab_table.setItem(row, 0, item)

                    # For Vendor.
                    item = QTableWidgetItem()
                    item.setText(vendor_daemon)
                    self.feature_tab_table.setItem(row, 1, item)

                    # For Feature.
                    item = QTableWidgetItem()
                    item.setText(license_feature)
                    self.feature_tab_table.setItem(row, 2, item)

                    # For Total_License.
                    item = QTableWidgetItem()

                    if self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['issued'] == 'Uncounted':
                        item.setData(Qt.DisplayRole, self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['issued'])
                    else:
                        item.setData(Qt.DisplayRole, int(self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['issued']))

                    self.feature_tab_table.setItem(row, 3, item)

                    # For In_Use_License.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, int(self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['in_use']))

                    if item.text() != '0':
                        item.setFont(QFont('song', 9, QFont.Bold))

                    self.feature_tab_table.setItem(row, 4, item)
# For FEATURE TAB (end) #

# For EXPIRES TAB (start) #
    def gen_expires_tab(self):
        """
        Generate EXPIRES tab, show license feature expires information.
        """
        self.expires_tab_frame = QFrame(self.expires_tab)
        self.expires_tab_frame.setFrameShadow(QFrame.Raised)
        self.expires_tab_frame.setFrameShape(QFrame.Box)

        self.expires_tab_table = QTableWidget(self.expires_tab)

        # Grid
        expires_tab_grid = QGridLayout()

        expires_tab_grid.addWidget(self.expires_tab_frame, 0, 0)
        expires_tab_grid.addWidget(self.expires_tab_table, 1, 0)

        expires_tab_grid.setRowStretch(0, 1)
        expires_tab_grid.setRowStretch(1, 10)

        self.expires_tab.setLayout(expires_tab_grid)

        # Generate self.expires_tab_frame and self.expires_tab_table.
        self.gen_expires_tab_frame()
        self.gen_expires_tab_table(self.license_dic)

    def gen_expires_tab_frame(self):
        # Show
        expires_tab_show_label = QLabel('Show', self.expires_tab_frame)
        expires_tab_show_label.setStyleSheet('font-weight: bold;')
        expires_tab_show_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.expires_tab_show_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_show_combo()
        self.expires_tab_show_combo.activated.connect(self.filter_expires_tab_license_feature)

        # License Server
        expires_tab_server_label = QLabel('Server', self.expires_tab_frame)
        expires_tab_server_label.setStyleSheet('font-weight: bold;')
        expires_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.expires_tab_server_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_server_combo()
        self.expires_tab_server_combo.activated.connect(self.expires_tab_server_combo_changed)

        # License vendor daemon
        expires_tab_vendor_label = QLabel('Vendor', self.expires_tab_frame)
        expires_tab_vendor_label.setStyleSheet('font-weight: bold;')
        expires_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.expires_tab_vendor_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_vendor_combo()
        self.expires_tab_vendor_combo.activated.connect(self.expires_tab_vendor_combo_changed)

        # License Feature
        expires_tab_feature_label = QLabel('Feature', self.expires_tab_frame)
        expires_tab_feature_label.setStyleSheet('font-weight: bold;')
        expires_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.expires_tab_feature_line = QLineEdit()
        self.expires_tab_feature_line.returnPressed.connect(self.filter_expires_tab_license_feature)

        # Filter Button
        expires_tab_check_button = QPushButton('Check', self.expires_tab_frame)
        expires_tab_check_button.clicked.connect(self.filter_expires_tab_license_feature)

        # Grid
        expires_tab_frame_grid = QGridLayout()

        expires_tab_frame_grid.addWidget(expires_tab_show_label, 0, 0)
        expires_tab_frame_grid.addWidget(self.expires_tab_show_combo, 0, 1)
        expires_tab_frame_grid.addWidget(expires_tab_server_label, 0, 2)
        expires_tab_frame_grid.addWidget(self.expires_tab_server_combo, 0, 3)
        expires_tab_frame_grid.addWidget(expires_tab_vendor_label, 0, 4)
        expires_tab_frame_grid.addWidget(self.expires_tab_vendor_combo, 0, 5)
        expires_tab_frame_grid.addWidget(expires_tab_feature_label, 0, 6)
        expires_tab_frame_grid.addWidget(self.expires_tab_feature_line, 0, 7)
        expires_tab_frame_grid.addWidget(expires_tab_check_button, 0, 8)

        expires_tab_frame_grid.setColumnStretch(0, 1)
        expires_tab_frame_grid.setColumnStretch(1, 1)
        expires_tab_frame_grid.setColumnStretch(2, 1)
        expires_tab_frame_grid.setColumnStretch(3, 1)
        expires_tab_frame_grid.setColumnStretch(4, 1)
        expires_tab_frame_grid.setColumnStretch(5, 1)
        expires_tab_frame_grid.setColumnStretch(6, 1)
        expires_tab_frame_grid.setColumnStretch(7, 1)
        expires_tab_frame_grid.setColumnStretch(8, 1)

        self.expires_tab_frame.setLayout(expires_tab_frame_grid)

    def set_expires_tab_show_combo(self):
        self.expires_tab_show_combo.clear()
        self.expires_tab_show_combo.addItem('ALL')
        self.expires_tab_show_combo.addItem('Expired')
        self.expires_tab_show_combo.addItem('Nearly_Expired')
        self.expires_tab_show_combo.addItem('Unexpired')

    def set_expires_tab_server_combo(self):
        self.expires_tab_server_combo.clear()
        self.expires_tab_server_combo.addItem('ALL')

        for license_server in self.license_dic.keys():
            self.expires_tab_server_combo.addItem(license_server)

    def set_expires_tab_vendor_combo(self):
        self.expires_tab_vendor_combo.clear()

        # Get vendor_daemon list.
        vendor_daemon_list = ['ALL', ]
        selected_license_server = self.expires_tab_server_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        # Fill self.expires_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.expires_tab_vendor_combo.addItem(vendor_daemon)

    def expires_tab_server_combo_changed(self):
        self.set_expires_tab_vendor_combo()
        self.filter_expires_tab_license_feature()

    def expires_tab_vendor_combo_changed(self):
        if self.expires_tab_vendor_combo.count() > 2:
            self.filter_expires_tab_license_feature()

    def filter_expires_tab_license_feature(self, get_license_info=True):
        # Re-generate self.expires_tab_table.
        if get_license_info:
            self.get_license_dic()

        if self.license_dic:
            selected_show_mode = self.expires_tab_show_combo.currentText().strip()
            selected_license_server = self.expires_tab_server_combo.currentText().strip()
            selected_vendor_daemon = self.expires_tab_vendor_combo.currentText().strip()
            specified_license_feature_list = self.expires_tab_feature_line.text().strip().split()

            filter_license_dic = common_license.FilterLicenseDic()
            filtered_license_dic = filter_license_dic.run(license_dic=self.license_dic, server_list=[selected_license_server, ], vendor_list=[selected_vendor_daemon, ], feature_list=specified_license_feature_list, show_mode=selected_show_mode)

            # Update self.expires_tab_table
            self.gen_expires_tab_table(filtered_license_dic)

    def gen_expires_tab_table(self, license_dic):
        # Get license expires num.
        license_feature_num = 0

        if license_dic:
            for license_server in license_dic.keys():
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].keys():
                        for expires_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][license_feature]:
                            license_feature_num += 1

        # Fill self.expires_tab_table column.
        self.expires_tab_table.setShowGrid(True)
        self.expires_tab_table.setSortingEnabled(True)
        self.expires_tab_table.setColumnCount(0)
        self.expires_tab_table.setColumnCount(6)
        self.expires_tab_table_title_list = ['Server', 'Vendor', 'Feature', 'Version', 'License_Num', 'Expires']
        self.expires_tab_table.setHorizontalHeaderLabels(self.expires_tab_table_title_list)

        self.expires_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.expires_tab_table.setColumnWidth(1, 100)
        self.expires_tab_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.expires_tab_table.setColumnWidth(3, 100)
        self.expires_tab_table.setColumnWidth(4, 120)
        self.expires_tab_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        # Fill self.expires_tab_table row.
        self.expires_tab_table.setRowCount(0)
        self.expires_tab_table.setRowCount(license_feature_num)

        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].keys():
                    for expires_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][license_feature]:
                        row += 1

                        # For Server.
                        item = QTableWidgetItem()
                        item.setText(license_server)
                        self.expires_tab_table.setItem(row, 0, item)

                        # For Vendor.
                        item = QTableWidgetItem()
                        item.setText(expires_dic['vendor'])
                        self.expires_tab_table.setItem(row, 1, item)

                        # For Feature.
                        item = QTableWidgetItem()
                        item.setText(license_feature)
                        self.expires_tab_table.setItem(row, 2, item)

                        # For Version.
                        item = QTableWidgetItem()
                        item.setText(expires_dic['version'])
                        self.expires_tab_table.setItem(row, 3, item)

                        # For Feature Number.
                        item = QTableWidgetItem()
                        item.setData(Qt.DisplayRole, int(expires_dic['license']))
                        self.expires_tab_table.setItem(row, 4, item)

                        # For Expires Date.
                        item = QTableWidgetItem()
                        expires_date = common_license.switch_expires_date(expires_dic['expires'])
                        item.setText(expires_date)

                        expires_mark = common_license.check_expire_date(expires_dic['expires'])

                        if expires_mark == 0:
                            pass
                        elif expires_mark == -1:
                            item.setForeground(QBrush(Qt.gray))
                        else:
                            item.setForeground(QBrush(Qt.red))

                        self.expires_tab_table.setItem(row, 5, item)

    def generate_usage_menu(self, pos):
        menu = QMenu()
        row = self.usage_tab_table.currentIndex().row()
        server = self.usage_tab_table.item(row, 0).text().strip()
        vendor = self.usage_tab_table.item(row, 1).text().strip()
        feature = self.usage_tab_table.item(row, 2).text().strip()
        user = self.usage_tab_table.item(row, 3).text().strip()

        action = QAction('View License Log')
        action.triggered.connect(lambda: self.gen_license_log_window(server=server, vendor=vendor, feature=feature, user=user))
        menu.addAction(action)

        menu.exec_(self.usage_tab_table.mapToGlobal(pos))

# For EXPIRES TAB (end) #

# For USAGE TAB (start) #
    def gen_usage_tab(self):
        """
        Generate USAGE tab, show license feature usage information for running tasks.
        """
        self.usage_tab_frame = QFrame(self.usage_tab)
        self.usage_tab_frame.setFrameShadow(QFrame.Raised)
        self.usage_tab_frame.setFrameShape(QFrame.Box)

        self.usage_tab_table = QTableWidget(self.usage_tab)

        # Grid
        usage_tab_grid = QGridLayout()

        usage_tab_grid.addWidget(self.usage_tab_frame, 0, 0)
        usage_tab_grid.addWidget(self.usage_tab_table, 1, 0)

        usage_tab_grid.setRowStretch(0, 1)
        usage_tab_grid.setRowStretch(1, 10)

        self.usage_tab.setLayout(usage_tab_grid)

        # Generate self.usage_tab_frame and self.usage_tab_table.
        self.gen_usage_tab_frame()
        self.gen_usage_tab_table(self.license_dic)
        self.usage_tab_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.usage_tab_table.customContextMenuRequested.connect(self.generate_usage_menu)

    def gen_usage_tab_frame(self):
        # License Server
        usage_tab_server_label = QLabel('Server', self.usage_tab_frame)
        usage_tab_server_label.setStyleSheet('font-weight: bold;')
        usage_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_server_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_server_combo()
        self.usage_tab_server_combo.activated.connect(self.usage_tab_server_combo_changed)

        # License vendor daemon
        usage_tab_vendor_label = QLabel('Vendor', self.usage_tab_frame)
        usage_tab_vendor_label.setStyleSheet('font-weight: bold;')
        usage_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_vendor_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_vendor_combo()
        self.usage_tab_vendor_combo.activated.connect(self.usage_tab_vendor_combo_changed)

        # License Feature
        usage_tab_feature_label = QLabel('Feature', self.usage_tab_frame)
        usage_tab_feature_label.setStyleSheet('font-weight: bold;')
        usage_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_feature_line = QLineEdit()
        self.usage_tab_feature_line.returnPressed.connect(self.filter_usage_tab_license_feature)

        # Submit Host
        usage_tab_submit_host_label = QLabel('Submit_Host', self.usage_tab_frame)
        usage_tab_submit_host_label.setStyleSheet('font-weight: bold;')
        usage_tab_submit_host_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_submit_host_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_submit_host_combo()
        self.usage_tab_submit_host_combo.activated.connect(self.filter_usage_tab_license_feature)

        # Execute Host
        usage_tab_execute_host_label = QLabel('Execute_Host', self.usage_tab_frame)
        usage_tab_execute_host_label.setStyleSheet('font-weight: bold;')
        usage_tab_execute_host_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_execute_host_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_execute_host_combo()
        self.usage_tab_execute_host_combo.activated.connect(self.filter_usage_tab_license_feature)

        # User
        usage_tab_user_label = QLabel('User', self.usage_tab_frame)
        usage_tab_user_label.setStyleSheet('font-weight: bold;')
        usage_tab_user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.usage_tab_user_line = QLineEdit()
        self.usage_tab_user_line.returnPressed.connect(self.filter_usage_tab_license_feature)

        # Fileter
        usage_tab_check_button = QPushButton('Check', self.usage_tab_frame)
        usage_tab_check_button.clicked.connect(self.filter_usage_tab_license_feature)

        # Grid
        usage_tab_frame_grid = QGridLayout()

        usage_tab_frame_grid.addWidget(usage_tab_server_label, 0, 0)
        usage_tab_frame_grid.addWidget(self.usage_tab_server_combo, 0, 1)
        usage_tab_frame_grid.addWidget(usage_tab_vendor_label, 0, 2)
        usage_tab_frame_grid.addWidget(self.usage_tab_vendor_combo, 0, 3)
        usage_tab_frame_grid.addWidget(usage_tab_feature_label, 0, 4)
        usage_tab_frame_grid.addWidget(self.usage_tab_feature_line, 0, 5)
        usage_tab_frame_grid.addWidget(usage_tab_check_button, 0, 6)
        usage_tab_frame_grid.addWidget(usage_tab_submit_host_label, 1, 0)
        usage_tab_frame_grid.addWidget(self.usage_tab_submit_host_combo, 1, 1)
        usage_tab_frame_grid.addWidget(usage_tab_execute_host_label, 1, 2)
        usage_tab_frame_grid.addWidget(self.usage_tab_execute_host_combo, 1, 3)
        usage_tab_frame_grid.addWidget(usage_tab_user_label, 1, 4)
        usage_tab_frame_grid.addWidget(self.usage_tab_user_line, 1, 5)

        usage_tab_frame_grid.setColumnStretch(0, 1)
        usage_tab_frame_grid.setColumnStretch(1, 1)
        usage_tab_frame_grid.setColumnStretch(2, 1)
        usage_tab_frame_grid.setColumnStretch(3, 1)
        usage_tab_frame_grid.setColumnStretch(4, 1)
        usage_tab_frame_grid.setColumnStretch(5, 1)
        usage_tab_frame_grid.setColumnStretch(6, 1)

        self.usage_tab_frame.setLayout(usage_tab_frame_grid)

    def set_usage_tab_server_combo(self, license_server_list=[]):
        self.usage_tab_server_combo.clear()

        if not license_server_list:
            license_server_list.append('ALL')

            for license_server in self.license_dic.keys():
                license_server_list.append(license_server)

        for license_server in license_server_list:
            self.usage_tab_server_combo.addItem(license_server)

    def usage_tab_server_combo_changed(self):
        if self.usage_tab_server_combo.count() > 2:
            self.set_usage_tab_vendor_combo()
            self.set_usage_tab_submit_host_combo()
            self.set_usage_tab_execute_host_combo()
            self.filter_usage_tab_license_feature()

    def set_usage_tab_vendor_combo(self, vendor_daemon_list=[]):
        self.usage_tab_vendor_combo.clear()

        if not vendor_daemon_list:
            vendor_daemon_list = ['ALL', ]
            selected_license_server = self.usage_tab_server_combo.currentText().strip()

            for license_server in self.license_dic.keys():
                if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                    for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                        if vendor_daemon not in vendor_daemon_list:
                            vendor_daemon_list.append(vendor_daemon)

        # Fill self.usage_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.usage_tab_vendor_combo.addItem(vendor_daemon)

    def usage_tab_vendor_combo_changed(self):
        if self.usage_tab_vendor_combo.count() > 2:
            self.set_usage_tab_submit_host_combo()
            self.set_usage_tab_execute_host_combo()
            self.filter_usage_tab_license_feature()

    def set_usage_tab_submit_host_combo(self):
        self.usage_tab_submit_host_combo.clear()
        submit_host_list = ['ALL', ]
        selected_license_server = self.usage_tab_server_combo.currentText().strip()
        selected_vendor_daemon = self.usage_tab_vendor_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if (selected_vendor_daemon == 'ALL') or (selected_vendor_daemon == vendor_daemon):
                        for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                            for usage_dic in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']:
                                submit_host = usage_dic['submit_host']

                                if submit_host not in submit_host_list:
                                    submit_host_list.append(submit_host)

        # Fill self.usage_tab_vendor_combo.
        for submit_host in submit_host_list:
            self.usage_tab_submit_host_combo.addItem(submit_host)

    def set_usage_tab_execute_host_combo(self):
        self.usage_tab_execute_host_combo.clear()
        execute_host_list = ['ALL', ]
        selected_license_server = self.usage_tab_server_combo.currentText().strip()
        selected_vendor_daemon = self.usage_tab_vendor_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if (selected_vendor_daemon == 'ALL') or (selected_vendor_daemon == vendor_daemon):
                        for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                            for usage_dic in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']:
                                execute_host = usage_dic['execute_host']

                                if execute_host not in execute_host_list:
                                    execute_host_list.append(execute_host)

        # Fill self.usage_tab_vendor_combo.
        for execute_host in execute_host_list:
            self.usage_tab_execute_host_combo.addItem(execute_host)

    def filter_usage_tab_license_feature(self, get_license_info=True):
        # Re-generate self.usage_tab_table.
        if get_license_info:
            self.get_license_dic()

        if self.license_dic:
            selected_license_server = self.usage_tab_server_combo.currentText().strip()
            selected_vendor_daemon = self.usage_tab_vendor_combo.currentText().strip()
            specified_license_feature_list = self.usage_tab_feature_line.text().strip().split()
            selected_submit_host = self.usage_tab_submit_host_combo.currentText().strip()
            selected_execute_host = self.usage_tab_execute_host_combo.currentText().strip()
            specified_user_list = self.usage_tab_user_line.text().strip().split()

            filter_license_dic = common_license.FilterLicenseDic()
            filtered_license_dic = filter_license_dic.run(license_dic=self.license_dic, server_list=[selected_license_server, ], vendor_list=[selected_vendor_daemon, ], feature_list=specified_license_feature_list, submit_host_list=[selected_submit_host, ], execute_host_list=[selected_execute_host, ], user_list=specified_user_list, show_mode='IN_USE')

            # Update self.usage_tab_table
            self.gen_usage_tab_table(license_dic=filtered_license_dic)

    def gen_usage_tab_table(self, license_dic):
        # Get license usage num.
        license_usage_num = 0

        if license_dic:
            for license_server in license_dic.keys():
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                        for usage_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['in_use_info']:
                            license_usage_num += 1

        # Fill self.usage_tab_table column.
        self.usage_tab_table.setShowGrid(True)
        self.usage_tab_table.setSortingEnabled(True)
        self.usage_tab_table.setColumnCount(0)
        self.usage_tab_table.setColumnCount(9)
        self.usage_tab_table_title_list = ['Server', 'Vendor', 'Feature', 'User', 'Submit_Host', 'Execute_Host', 'Num', 'Version', 'Start_Time']
        self.usage_tab_table.setHorizontalHeaderLabels(self.usage_tab_table_title_list)

        self.usage_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.usage_tab_table.setColumnWidth(1, 85)
        self.usage_tab_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.usage_tab_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.usage_tab_table.setColumnWidth(4, 110)
        self.usage_tab_table.setColumnWidth(5, 110)
        self.usage_tab_table.setColumnWidth(6, 50)
        self.usage_tab_table.setColumnWidth(7, 85)
        self.usage_tab_table.setColumnWidth(8, 135)

        # Fill self.usage_tab_table row.
        self.usage_tab_table.setRowCount(0)
        self.usage_tab_table.setRowCount(license_usage_num)

        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for license_feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    for usage_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][license_feature]['in_use_info']:
                        row += 1

                        # For Server.
                        item = QTableWidgetItem()
                        item.setText(license_server)
                        self.usage_tab_table.setItem(row, 0, item)

                        # For Vendor.
                        item = QTableWidgetItem()
                        item.setText(vendor_daemon)
                        self.usage_tab_table.setItem(row, 1, item)

                        # For Feature.
                        item = QTableWidgetItem()
                        item.setText(license_feature)
                        self.usage_tab_table.setItem(row, 2, item)

                        # For User.
                        item = QTableWidgetItem()
                        item.setText(usage_dic['user'])
                        self.usage_tab_table.setItem(row, 3, item)

                        # For Submit_Host.
                        item = QTableWidgetItem()
                        item.setText(usage_dic['submit_host'])
                        self.usage_tab_table.setItem(row, 4, item)

                        # For Execute_Host.
                        item = QTableWidgetItem()
                        item.setText(usage_dic['execute_host'])
                        self.usage_tab_table.setItem(row, 5, item)

                        # For License_Num.
                        item = QTableWidgetItem()
                        item.setData(Qt.DisplayRole, int(usage_dic['license_num']))
                        self.usage_tab_table.setItem(row, 6, item)

                        # For License_Version.
                        item = QTableWidgetItem()
                        item.setText(usage_dic['version'])
                        self.usage_tab_table.setItem(row, 7, item)

                        # For Start_Time.
                        item = QTableWidgetItem()
                        start_time = common_license.switch_start_time(usage_dic['start_time'], format='%Y-%m-%d %H:%M')
                        item.setText(start_time)

                        if common_license.check_long_runtime(usage_dic['start_time']):
                            item.setForeground(QBrush(Qt.red))

                        self.usage_tab_table.setItem(row, 8, item)
# For USAGE TAB (end) #

# For CURVE TAB (start) #
    def gen_curve_tab(self):
        """
        Generate CURVE tab, show license feature curve information.
        """
        self.curve_tab_frame0 = QFrame(self.curve_tab)
        self.curve_tab_frame0.setFrameShadow(QFrame.Raised)
        self.curve_tab_frame0.setFrameShape(QFrame.Box)

        self.curve_tab_table = QTableWidget(self.curve_tab)
        self.curve_tab_table.itemClicked.connect(self.curve_tab_table_click)

        self.curve_tab_frame1 = QFrame(self.curve_tab)
        self.curve_tab_frame1.setFrameShadow(QFrame.Raised)
        self.curve_tab_frame1.setFrameShape(QFrame.Box)

        # Grid
        curve_tab_grid = QGridLayout()

        curve_tab_grid.addWidget(self.curve_tab_frame0, 0, 0, 1, 2)
        curve_tab_grid.addWidget(self.curve_tab_table, 1, 0)
        curve_tab_grid.addWidget(self.curve_tab_frame1, 1, 1)

        curve_tab_grid.setRowStretch(0, 1)
        curve_tab_grid.setRowStretch(1, 10)

        curve_tab_grid.setColumnStretch(0, 2)
        curve_tab_grid.setColumnStretch(1, 3)

        self.curve_tab.setLayout(curve_tab_grid)

        # Generate self.curve_tab_frame0, self.curve_tab_table and self.curve_tab_frame1.
        self.gen_curve_tab_frame0()
        self.gen_curve_tab_table()
        self.gen_curve_tab_frame1()
        self.update_curve_tab_frame1()

    def gen_curve_tab_frame0(self):
        # License Server
        curve_tab_server_label = QLabel('Server', self.curve_tab_frame0)
        curve_tab_server_label.setStyleSheet('font-weight: bold;')
        curve_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.curve_tab_server_combo = QComboBox(self.curve_tab_frame0)
        self.set_curve_tab_server_combo()
        self.curve_tab_server_combo.activated.connect(self.curve_tab_server_combo_changed)

        # License vendor daemon
        curve_tab_vendor_label = QLabel('Vendor', self.curve_tab_frame0)
        curve_tab_vendor_label.setStyleSheet('font-weight: bold;')
        curve_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.curve_tab_vendor_combo = QComboBox(self.curve_tab_frame0)
        self.set_curve_tab_vendor_combo()

        # License Feature
        curve_tab_feature_label = QLabel('Feature', self.curve_tab_frame0)
        curve_tab_feature_label.setStyleSheet('font-weight: bold;')
        curve_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.curve_tab_feature_line = QLineEdit()
        self.curve_tab_feature_line.returnPressed.connect(self.filter_curve_tab)

        # Check button
        curve_tab_check_button = QPushButton('Check', self.curve_tab_frame0)
        curve_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        curve_tab_check_button.clicked.connect(self.filter_curve_tab)

        # Begin_Data
        curve_tab_begin_date_label = QLabel('Begin_Date', self.curve_tab_frame0)
        curve_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        curve_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.curve_tab_begin_date_edit = QDateEdit(self.curve_tab_frame0)
        self.curve_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.curve_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.curve_tab_begin_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.curve_tab_begin_date_edit.setCalendarPopup(True)
        self.curve_tab_begin_date_edit.setDate(QDate.currentDate().addDays(-7))

        # End_Data
        curve_tab_end_date_label = QLabel('End_Date', self.curve_tab_frame0)
        curve_tab_end_date_label.setStyleSheet("font-weight: bold;")
        curve_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.curve_tab_end_date_edit = QDateEdit(self.curve_tab_frame0)
        self.curve_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.curve_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.curve_tab_end_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.curve_tab_end_date_edit.setCalendarPopup(True)
        self.curve_tab_end_date_edit.setDate(QDate.currentDate())

        # Empty label
        curve_tab_empty_label = QLabel('', self.curve_tab_frame0)

        # Export button
        curve_tab_export_button = QPushButton('Export', self.curve_tab_frame0)
        curve_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        curve_tab_export_button.clicked.connect(self.export_curve_table)

        # self.curve_tab_frame0 - Grid
        curve_tab_frame0_grid = QGridLayout()

        curve_tab_frame0_grid.addWidget(curve_tab_server_label, 0, 0)
        curve_tab_frame0_grid.addWidget(self.curve_tab_server_combo, 0, 1)
        curve_tab_frame0_grid.addWidget(curve_tab_vendor_label, 0, 2)
        curve_tab_frame0_grid.addWidget(self.curve_tab_vendor_combo, 0, 3)
        curve_tab_frame0_grid.addWidget(curve_tab_feature_label, 0, 4)
        curve_tab_frame0_grid.addWidget(self.curve_tab_feature_line, 0, 5)
        curve_tab_frame0_grid.addWidget(curve_tab_check_button, 0, 6)
        curve_tab_frame0_grid.addWidget(curve_tab_begin_date_label, 1, 0)
        curve_tab_frame0_grid.addWidget(self.curve_tab_begin_date_edit, 1, 1)
        curve_tab_frame0_grid.addWidget(curve_tab_end_date_label, 1, 2)
        curve_tab_frame0_grid.addWidget(self.curve_tab_end_date_edit, 1, 3)
        curve_tab_frame0_grid.addWidget(curve_tab_empty_label, 1, 4, 1, 2)
        curve_tab_frame0_grid.addWidget(curve_tab_export_button, 1, 6)

        curve_tab_frame0_grid.setColumnStretch(0, 1)
        curve_tab_frame0_grid.setColumnStretch(1, 1)
        curve_tab_frame0_grid.setColumnStretch(2, 1)
        curve_tab_frame0_grid.setColumnStretch(3, 1)
        curve_tab_frame0_grid.setColumnStretch(4, 1)
        curve_tab_frame0_grid.setColumnStretch(5, 1)
        curve_tab_frame0_grid.setColumnStretch(6, 1)

        self.curve_tab_frame0.setLayout(curve_tab_frame0_grid)

    def set_curve_tab_server_combo(self):
        """
        Set (initialize) self.curve_tab_server_combo.
        """
        self.curve_tab_server_combo.clear()

        license_server_list = ['ALL', ]

        for license_server in self.license_dic.keys():
            license_server_list.append(license_server)

        for license_server in license_server_list:
            self.curve_tab_server_combo.addItem(license_server)

    def curve_tab_server_combo_changed(self):
        """
        If self.curve_tab_server_combo is selected, update self.curve_tab_vendor_combo, then filter license feature on CURVE tab.
        """
        self.set_curve_tab_vendor_combo()

    def set_curve_tab_vendor_combo(self):
        """
        Set (initialize) self.curve_tab_vendor_combo.
        """
        self.curve_tab_vendor_combo.clear()

        vendor_daemon_list = ['ALL', ]
        selected_license_server = self.curve_tab_server_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        for vendor_daemon in vendor_daemon_list:
            self.curve_tab_vendor_combo.addItem(vendor_daemon)

    def filter_curve_tab(self):
        """
        Update self.curve_tab_table and self.curve_tab_frame1.
        """
        curve_dic = self.get_curve_info()

        self.gen_curve_tab_table(curve_dic)
        self.update_curve_tab_frame1(curve_dic)

    def get_curve_info(self):
        """
        Get curve information from config.db_path/license_server/<license_server>/<vendor_deamon>/utilization.db.
        """
        # Print loading curve informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading curve info, please wait a moment ...')

        # Print loading curve informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading curve info, please wait a moment ...')
        my_show_message.start()

        curve_dic = {}
        fuzzy_curve_dic = {}

        key_list = ['sample_time', 'issued', 'in_use']
        begin_date = self.curve_tab_begin_date_edit.date().toString(Qt.ISODate)
        begin_time = str(begin_date) + ' 00:00:00'
        begin_second = time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))
        end_date = self.curve_tab_end_date_edit.date().toString(Qt.ISODate)
        end_time = str(end_date) + ' 23:59:59'
        end_second = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
        select_condition = 'WHERE sample_second>=' + str(begin_second) + ' AND sample_second<=' + str(end_second)

        selected_license_server = self.curve_tab_server_combo.currentText().strip()
        selected_vendor_daemon = self.curve_tab_vendor_combo.currentText().strip()
        specified_license_feature = self.curve_tab_feature_line.text().strip()

        # Filter with license_server/vendor_daemon/feature.
        for license_server in self.db_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.db_dic[license_server].keys():
                    if (selected_vendor_daemon == 'ALL') or (selected_vendor_daemon == vendor_daemon):
                        if 'curve' in self.db_dic[license_server][vendor_daemon].keys():
                            curve_db_file = self.db_dic[license_server][vendor_daemon]['curve']
                            (curve_db_file_connect_result, curve_db_conn) = common_sqlite3.connect_db_file(curve_db_file)

                            if curve_db_file_connect_result == 'failed':
                                common.print_warning('*Warning*: Failed on connecting curve database file "' + str(curve_db_file) + '".')
                            else:
                                curve_db_table_list = common_sqlite3.get_sql_table_list(curve_db_file, curve_db_conn)

                                for feature in curve_db_table_list:
                                    # Check fuzzy_mode.
                                    fuzzy_mode = False

                                    if (feature != specified_license_feature) and re.search(re.escape(specified_license_feature.lower()), feature.lower()):
                                        fuzzy_mode = True

                                    # feature match or fuzzy_mode.
                                    if (not specified_license_feature) or (feature == specified_license_feature) or fuzzy_mode:
                                        data_dic = common_sqlite3.get_sql_table_data(curve_db_file, curve_db_conn, feature, key_list, select_condition)

                                        if data_dic:
                                            if fuzzy_mode:
                                                fuzzy_curve_dic.setdefault(feature, {})
                                                fuzzy_curve_dic[feature].setdefault(vendor_daemon, {})
                                            else:
                                                curve_dic.setdefault(feature, {})
                                                curve_dic[feature].setdefault(vendor_daemon, {})

                                            for (i, sample_time) in enumerate(data_dic['sample_time']):
                                                issued_num = data_dic['issued'][i]
                                                in_use_num = data_dic['in_use'][i]

                                                if fuzzy_mode:
                                                    fuzzy_curve_dic[feature][vendor_daemon].setdefault(sample_time, {'issued': 0.0, 'in_use': 0.0})
                                                else:
                                                    curve_dic[feature][vendor_daemon].setdefault(sample_time, {'issued': 0.0, 'in_use': 0.0})

                                                if issued_num == 'Uncounted':
                                                    if fuzzy_mode:
                                                        fuzzy_curve_dic[feature][vendor_daemon][sample_time]['issued'] = 'Uncounted'
                                                    else:
                                                        curve_dic[feature][vendor_daemon][sample_time]['issued'] = 'Uncounted'
                                                else:
                                                    if fuzzy_mode:
                                                        if fuzzy_curve_dic[feature][vendor_daemon][sample_time]['issued'] != 'Uncounted':
                                                            fuzzy_curve_dic[feature][vendor_daemon][sample_time]['issued'] += float(issued_num)
                                                    else:
                                                        if curve_dic[feature][vendor_daemon][sample_time]['issued'] != 'Uncounted':
                                                            curve_dic[feature][vendor_daemon][sample_time]['issued'] += float(issued_num)

                                                if fuzzy_mode:
                                                    fuzzy_curve_dic[feature][vendor_daemon][sample_time]['in_use'] += float(in_use_num)
                                                else:
                                                    curve_dic[feature][vendor_daemon][sample_time]['in_use'] += float(in_use_num)

                                curve_db_conn.close()

        # Filter with feature on fuzzy mode.
        if (not curve_dic) and fuzzy_curve_dic:
            curve_dic = fuzzy_curve_dic

        my_show_message.terminate()

        if not curve_dic:
            common.print_warning('*Warning*: No curve data is find.')

        return curve_dic

    def gen_curve_tab_table(self, curve_dic={}):
        """
        Generate self.curve_tab_table.
        """
        self.curve_tab_table.setShowGrid(True)
        self.curve_tab_table.setSortingEnabled(True)
        self.curve_tab_table.setColumnCount(0)
        self.curve_tab_table.setColumnCount(5)
        self.curve_tab_table_title_list = ['Feature', 'Vendor', 'Total', 'In_Use', 'Peak']
        self.curve_tab_table.setHorizontalHeaderLabels(self.curve_tab_table_title_list)

        self.curve_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.curve_tab_table.setColumnWidth(1, 80)
        self.curve_tab_table.setColumnWidth(2, 90)
        self.curve_tab_table.setColumnWidth(3, 60)
        self.curve_tab_table.setColumnWidth(4, 60)

        # Set self.curve_tab_table row length.
        row_length = 0

        for feature in curve_dic.keys():
            for vendor_daemon in curve_dic[feature].keys():
                row_length += 1

        self.curve_tab_table.setRowCount(0)
        self.curve_tab_table.setRowCount(row_length)

        # Fill self.curve_tab_table items.
        if curve_dic:
            i = -1

            for feature in curve_dic.keys():
                for vendor_daemon in curve_dic[feature].keys():
                    issued_list = []
                    in_use_list = []

                    for sample_time in curve_dic[feature][vendor_daemon].keys():
                        issued_num = curve_dic[feature][vendor_daemon][sample_time]['issued']
                        in_use_num = curve_dic[feature][vendor_daemon][sample_time]['in_use']

                        issued_list.append(issued_num)
                        in_use_list.append(in_use_num)

                    if 'Uncounted' in issued_list:
                        avg_issued = 'Uncounted'
                    else:
                        avg_issued = round(sum(issued_list)/len(issued_list), 1)

                    avg_in_use = round(sum(in_use_list)/len(in_use_list), 1)
                    peak_in_use = max(in_use_list)

                    i += 1

                    # Fill "Feature" item.
                    item = QTableWidgetItem(feature)
                    self.curve_tab_table.setItem(i, 0, item)

                    # Fill "Vendor" item.
                    item = QTableWidgetItem(vendor_daemon)
                    self.curve_tab_table.setItem(i, 1, item)

                    # Fill "Total" item.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, avg_issued)
                    self.curve_tab_table.setItem(i, 2, item)

                    # Fill "In_Use" item.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, avg_in_use)
                    self.curve_tab_table.setItem(i, 3, item)

                    # Fill "Peak" item.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, peak_in_use)
                    self.curve_tab_table.setItem(i, 4, item)

    def curve_tab_table_click(self, item=None):
        """
        If click feature name on self.curve_tab_table, jump to FEATURE tab and show feature related information.
        """
        if item:
            if item.column() == 0:
                current_row = self.curve_tab_table.currentRow()
                feature = self.curve_tab_table.item(current_row, 0).text().strip()

                self.feature_tab_feature_line.setText(feature)
                self.filter_feature_tab_license_feature(get_license_info=False)
                self.main_tab.setCurrentWidget(self.feature_tab)

    def gen_curve_tab_frame1(self):
        """
        Generate self.curve_tab_frame1.
        """
        # self.curve_tab_frame1
        self.curve_tab_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.curve_tab_toolbar = common_pyqt5.NavigationToolbar2QT(self.curve_tab_canvas, self)

        # self.curve_tab_frame1 - Grid
        curve_tab_frame1_grid = QGridLayout()
        curve_tab_frame1_grid.addWidget(self.curve_tab_toolbar, 0, 0)
        curve_tab_frame1_grid.addWidget(self.curve_tab_canvas, 1, 0)
        self.curve_tab_frame1.setLayout(curve_tab_frame1_grid)

    def update_curve_tab_frame1(self, curve_dic={}):
        """
        Generate self.curve_tab_frame1.
        """
        # Generate fig.
        fig = self.curve_tab_canvas.figure
        fig.clear()
        self.curve_tab_canvas.draw()

        specified_license_feature = self.curve_tab_feature_line.text().strip()

        if not specified_license_feature:
            common.print_warning('*Warning*: No feature is specified, will not generate curve.')
            return
        elif specified_license_feature not in curve_dic:
            common.print_warning('*Warning*: No valid feature is specified, will not generate curve.')
            return

        # Print loading cost informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Process curve info, please wait a moment ...')

        # Print loading cost informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Process curve info, please wait a moment ...')
        my_show_message.start()

        # Get sample_time_list.
        sample_time_list = []

        for feature in curve_dic.keys():
            for vendor_daemon in curve_dic[feature].keys():
                sample_time_list.extend(list(curve_dic[feature][vendor_daemon].keys()))

        sample_time_list = list(set(sample_time_list))
        sample_time_list.sort()

        # Get issued/in_use list.
        issued_list = []
        in_use_list = []

        for sample_time in sample_time_list:
            for feature in curve_dic.keys():
                for vendor_daemon in curve_dic[feature].keys():
                    if sample_time in curve_dic[feature][vendor_daemon].keys():
                        issued_num = curve_dic[feature][vendor_daemon][sample_time]['issued']
                        in_use_num = curve_dic[feature][vendor_daemon][sample_time]['in_use']

                        if issued_num == 'Uncounted':
                            issued_num = 0

                        issued_list.append(issued_num)
                        in_use_list.append(in_use_num)

        my_show_message.terminate()

        if sample_time_list and issued_list and in_use_list:
            # Update sample_time format.
            for (i, sample_time) in enumerate(sample_time_list):
                sample_time_list[i] = datetime.datetime.strptime(sample_time, '%Y%m%d_%H%M%S')

            # Draw curve.
            self.draw_curve_tab_curve(fig, sample_time_list, issued_list, in_use_list)

    def draw_curve_tab_curve(self, fig, sample_time_list, issued_list, in_use_list):
        """
        Draw average issued/in_use curve for specified feature(s).
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        avg_in_use = round((sum(in_use_list)/len(in_use_list)), 1)
        axes.set_title('Average Used : ' + str(avg_in_use))
        axes.set_xlabel('Sample Time')
        axes.set_ylabel('Num')
        axes.plot(sample_time_list, issued_list, 'bo-', label='TOTAL', linewidth=0.1, markersize=0.1)
        axes.plot(sample_time_list, in_use_list, 'go-', label='IN_USE', linewidth=0.1, markersize=0.1)
        axes.fill_between(sample_time_list, 0, in_use_list, color='green', alpha=0.5)
        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.curve_tab_canvas.draw()
# For CURVE TAB (end) #

# For UTILIZATION TAB (start) #
    def gen_utilization_tab(self):
        """
        Generate UTILIZATION tab, show license feature utilization information.
        """
        self.utilization_tab_frame0 = QFrame(self.utilization_tab)
        self.utilization_tab_frame0.setFrameShadow(QFrame.Raised)
        self.utilization_tab_frame0.setFrameShape(QFrame.Box)

        self.utilization_tab_table = QTableWidget(self.utilization_tab)
        self.utilization_tab_table.itemClicked.connect(self.utilization_tab_table_click)

        self.utilization_tab_frame1 = QFrame(self.utilization_tab)
        self.utilization_tab_frame1.setFrameShadow(QFrame.Raised)
        self.utilization_tab_frame1.setFrameShape(QFrame.Box)

        # Grid
        utilization_tab_grid = QGridLayout()

        utilization_tab_grid.addWidget(self.utilization_tab_frame0, 0, 0, 1, 2)
        utilization_tab_grid.addWidget(self.utilization_tab_table, 1, 0)
        utilization_tab_grid.addWidget(self.utilization_tab_frame1, 1, 1)

        utilization_tab_grid.setRowStretch(0, 1)
        utilization_tab_grid.setRowStretch(1, 10)

        utilization_tab_grid.setColumnStretch(0, 3)
        utilization_tab_grid.setColumnStretch(1, 7)

        self.utilization_tab.setLayout(utilization_tab_grid)

        # Generate self.utilization_tab_frame0, self.utilization_tab_table and self.utilization_tab_frame1.
        self.gen_utilization_tab_frame0()
        self.gen_utilization_tab_table()
        self.gen_utilization_tab_frame1()
        self.update_utilization_tab_frame1()

    def gen_utilization_tab_frame0(self):
        # License Server
        utilization_tab_server_label = QLabel('Server', self.utilization_tab_frame0)
        utilization_tab_server_label.setStyleSheet('font-weight: bold;')
        utilization_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_server_combo = QComboBox(self.utilization_tab_frame0)
        self.set_utilization_tab_server_combo()
        self.utilization_tab_server_combo.activated.connect(self.utilization_tab_server_combo_changed)

        # License vendor daemon
        utilization_tab_vendor_label = QLabel('Vendor', self.utilization_tab_frame0)
        utilization_tab_vendor_label.setStyleSheet('font-weight: bold;')
        utilization_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_vendor_combo = QComboBox(self.utilization_tab_frame0)
        self.set_utilization_tab_vendor_combo()

        # License Feature
        utilization_tab_feature_label = QLabel('Feature', self.utilization_tab_frame0)
        utilization_tab_feature_label.setStyleSheet('font-weight: bold;')
        utilization_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_feature_line = QLineEdit()
        self.utilization_tab_feature_line.returnPressed.connect(self.filter_utilization_tab)

        # Check button
        utilization_tab_check_button = QPushButton('Check', self.utilization_tab_frame0)
        utilization_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        utilization_tab_check_button.clicked.connect(self.filter_utilization_tab)

        # Begin_Data
        utilization_tab_begin_date_label = QLabel('Begin_Date', self.utilization_tab_frame0)
        utilization_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        utilization_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_begin_date_edit = QDateEdit(self.utilization_tab_frame0)
        self.utilization_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.utilization_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.utilization_tab_begin_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.utilization_tab_begin_date_edit.setCalendarPopup(True)
        self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

        # End_Data
        utilization_tab_end_date_label = QLabel('End_Date', self.utilization_tab_frame0)
        utilization_tab_end_date_label.setStyleSheet("font-weight: bold;")
        utilization_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_end_date_edit = QDateEdit(self.utilization_tab_frame0)
        self.utilization_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.utilization_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.utilization_tab_end_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.utilization_tab_end_date_edit.setCalendarPopup(True)
        self.utilization_tab_end_date_edit.setDate(QDate.currentDate())

        # License Product
        utilization_tab_product_label = QLabel('Product', self.utilization_tab_frame0)
        utilization_tab_product_label.setStyleSheet('font-weight: bold;')
        utilization_tab_product_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_product_line = QLineEdit()
        self.utilization_tab_product_line.returnPressed.connect(self.filter_utilization_tab)

        # Export button
        utilization_tab_export_button = QPushButton('Export', self.utilization_tab_frame0)
        utilization_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        utilization_tab_export_button.clicked.connect(self.export_utilization_table)

        # self.utilization_tab_frame0 - Grid
        utilization_tab_frame0_grid = QGridLayout()

        utilization_tab_frame0_grid.addWidget(utilization_tab_server_label, 0, 0)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_server_combo, 0, 1)
        utilization_tab_frame0_grid.addWidget(utilization_tab_vendor_label, 0, 2)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_vendor_combo, 0, 3)
        utilization_tab_frame0_grid.addWidget(utilization_tab_feature_label, 0, 4)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_feature_line, 0, 5)
        utilization_tab_frame0_grid.addWidget(utilization_tab_check_button, 0, 6)
        utilization_tab_frame0_grid.addWidget(utilization_tab_begin_date_label, 1, 0)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_begin_date_edit, 1, 1)
        utilization_tab_frame0_grid.addWidget(utilization_tab_end_date_label, 1, 2)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_end_date_edit, 1, 3)
        utilization_tab_frame0_grid.addWidget(utilization_tab_product_label, 1, 4)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_product_line, 1, 5)
        utilization_tab_frame0_grid.addWidget(utilization_tab_export_button, 1, 6)

        utilization_tab_frame0_grid.setColumnStretch(0, 1)
        utilization_tab_frame0_grid.setColumnStretch(1, 1)
        utilization_tab_frame0_grid.setColumnStretch(2, 1)
        utilization_tab_frame0_grid.setColumnStretch(3, 1)
        utilization_tab_frame0_grid.setColumnStretch(4, 1)
        utilization_tab_frame0_grid.setColumnStretch(5, 1)
        utilization_tab_frame0_grid.setColumnStretch(6, 1)

        self.utilization_tab_frame0.setLayout(utilization_tab_frame0_grid)

    def set_utilization_tab_server_combo(self):
        """
        Set (initialize) self.utilization_tab_server_combo.
        """
        self.utilization_tab_server_combo.clear()

        license_server_list = ['ALL', ]

        for license_server in self.license_dic.keys():
            license_server_list.append(license_server)

        for license_server in license_server_list:
            self.utilization_tab_server_combo.addItem(license_server)

    def utilization_tab_server_combo_changed(self):
        """
        If self.utilization_tab_server_combo is selected, update self.utilization_tab_vendor_combo, then filter license feature on UTILIAZTION tab.
        """
        self.set_utilization_tab_vendor_combo()

    def set_utilization_tab_vendor_combo(self):
        """
        Set (initialize) self.utilization_tab_vendor_combo.
        """
        self.utilization_tab_vendor_combo.clear()

        vendor_daemon_list = ['ALL', ]
        selected_license_server = self.utilization_tab_server_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        for vendor_daemon in vendor_daemon_list:
            self.utilization_tab_vendor_combo.addItem(vendor_daemon)

    def filter_utilization_tab(self):
        """
        Update self.utilization_tab_table and self.utilization_tab_frame1.
        """
        utilization_dic = self.get_utilization_info()

        if utilization_dic:
            if self.enable_utilization_product:
                utilization_dic = self.switch_product_on_utilization_dic(utilization_dic)

            self.gen_utilization_tab_table(utilization_dic)
            self.update_utilization_tab_frame1(utilization_dic)

    def get_utilization_info(self):
        """
        Get utilization information from config.db_path/license_server/<license_server>/<vendor_deamon>/utilization(_day).db.
        """
        # Print loading utilization informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading utilization info, please wait a moment ...')

        # Print loading utilization informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading utilization info, please wait a moment ...')
        my_show_message.start()

        utilization_dic = {}
        fuzzy_utilization_dic = {}

        if self.enable_utilization_detail:
            key_list = ['sample_time', 'issued', 'in_use']
            begin_date = self.utilization_tab_begin_date_edit.date().toString(Qt.ISODate)
            begin_time = str(begin_date) + ' 00:00:00'
            begin_second = time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))
            end_date = self.utilization_tab_end_date_edit.date().toString(Qt.ISODate)
            end_time = str(end_date) + ' 23:59:59'
            end_second = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
            select_condition = 'WHERE sample_second>=' + str(begin_second) + ' AND sample_second<=' + str(end_second)
        else:
            key_list = ['sample_date', 'issued', 'in_use']
            begin_date = self.utilization_tab_begin_date_edit.date().toString(Qt.ISODate)
            begin_date = re.sub('-', '', begin_date)
            end_date = self.utilization_tab_end_date_edit.date().toString(Qt.ISODate)
            end_date = re.sub('-', '', end_date)
            select_condition = 'WHERE sample_date>=' + str(begin_date) + ' AND sample_date<=' + str(end_date)

        selected_license_server = self.utilization_tab_server_combo.currentText().strip()
        selected_vendor_daemon = self.utilization_tab_vendor_combo.currentText().strip()
        specified_license_feature_list = self.utilization_tab_feature_line.text().strip().split()

        # Filter with license_server/vendor_daemon/feature.
        for license_server in self.db_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.db_dic[license_server].keys():
                    if (selected_vendor_daemon == 'ALL') or (selected_vendor_daemon == vendor_daemon):
                        if 'utilization' in self.db_dic[license_server][vendor_daemon].keys():
                            utilization_db_file = self.db_dic[license_server][vendor_daemon]['utilization']
                            (utilization_db_file_connect_result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file)

                            if utilization_db_file_connect_result == 'failed':
                                common.print_warning('*Warning*: Failed on connecting utilization database file "' + str(utilization_db_file) + '".')
                            else:
                                utilization_db_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)

                                for feature in utilization_db_table_list:
                                    # Check fuzzy_mode.
                                    fuzzy_mode = False

                                    for specified_license_feature in specified_license_feature_list:
                                        if (feature != specified_license_feature) and re.search(re.escape(specified_license_feature.lower()), feature.lower()):
                                            fuzzy_mode = True
                                            break

                                    # feature match or fuzzy_mode.
                                    if (not specified_license_feature_list) or (feature in specified_license_feature_list) or fuzzy_mode:
                                        data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, feature, key_list, select_condition)

                                        if data_dic:
                                            if fuzzy_mode:
                                                fuzzy_utilization_dic.setdefault(feature, {})
                                                fuzzy_utilization_dic[feature].setdefault(vendor_daemon, {})
                                            else:
                                                utilization_dic.setdefault(feature, {})
                                                utilization_dic[feature].setdefault(vendor_daemon, {})

                                            if self.enable_utilization_detail:
                                                key = 'sample_time'
                                            else:
                                                key = 'sample_date'

                                            for (i, sample_date) in enumerate(data_dic[key]):
                                                issued_num = data_dic['issued'][i]
                                                in_use_num = data_dic['in_use'][i]

                                                if fuzzy_mode:
                                                    fuzzy_utilization_dic[feature][vendor_daemon].setdefault(sample_date, {'issued': 0.0, 'in_use': 0.0})
                                                else:
                                                    utilization_dic[feature][vendor_daemon].setdefault(sample_date, {'issued': 0.0, 'in_use': 0.0})

                                                if issued_num == 'Uncounted':
                                                    if fuzzy_mode:
                                                        fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] = 'Uncounted'
                                                    else:
                                                        utilization_dic[feature][vendor_daemon][sample_date]['issued'] = 'Uncounted'
                                                else:
                                                    if fuzzy_mode:
                                                        if fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] != 'Uncounted':
                                                            fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] += float(issued_num)
                                                    else:
                                                        if utilization_dic[feature][vendor_daemon][sample_date]['issued'] != 'Uncounted':
                                                            utilization_dic[feature][vendor_daemon][sample_date]['issued'] += float(issued_num)

                                                if fuzzy_mode:
                                                    fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['in_use'] += float(in_use_num)
                                                else:
                                                    utilization_dic[feature][vendor_daemon][sample_date]['in_use'] += float(in_use_num)

                                utilization_db_conn.close()

        # Filter with feature on fuzzy mode.
        if (not utilization_dic) and fuzzy_utilization_dic:
            utilization_dic = fuzzy_utilization_dic

        # Filter with white/black feature list.
        filtered_utilization_dic = copy.deepcopy(utilization_dic)

        if self.utilization_white_feature_list:
            filtered_utilization_dic = {}

            for white_feature in self.utilization_white_feature_list:
                for feature in utilization_dic.keys():
                    if re.match(white_feature, feature):
                        filtered_utilization_dic[feature] = utilization_dic[feature]
        elif self.utilization_black_feature_list:
            for black_feature in self.utilization_black_feature_list:
                for feature in utilization_dic.keys():
                    if re.match(black_feature, feature):
                        del filtered_utilization_dic[feature]

        # Count utilizaton information.
        for feature in filtered_utilization_dic.keys():
            for vendor_daemon in filtered_utilization_dic[feature].keys():
                for sample_date in filtered_utilization_dic[feature][vendor_daemon].keys():
                    issued_num = filtered_utilization_dic[feature][vendor_daemon][sample_date]['issued']
                    in_use_num = filtered_utilization_dic[feature][vendor_daemon][sample_date]['in_use']
                    utilization = 0.0

                    if issued_num == 'Uncounted':
                        if in_use_num > 0:
                            utilization = 100.0
                        else:
                            utilization = 0.0
                    else:
                        utilization = round(100 * in_use_num / issued_num, 1)

                    filtered_utilization_dic[feature][vendor_daemon][sample_date]['utilization'] = utilization

        my_show_message.terminate()

        if not filtered_utilization_dic:
            common.print_warning('*Warning*: No utilization data is find.')

        return filtered_utilization_dic

    def gen_utilization_tab_table(self, utilization_dic={}):
        """
        Generate self.utilization_tab_table.
        """
        if self.enable_utilization_product:
            self.utilization_tab_table_title_list = ['Product', 'Vendor', 'Ut (%)']
        else:
            self.utilization_tab_table_title_list = ['Feature', 'Vendor', 'Ut (%)']

        self.utilization_tab_table.setShowGrid(True)
        self.utilization_tab_table.setSortingEnabled(True)
        self.utilization_tab_table.setColumnCount(0)
        self.utilization_tab_table.setColumnCount(3)
        self.utilization_tab_table.setHorizontalHeaderLabels(self.utilization_tab_table_title_list)

        self.utilization_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.utilization_tab_table.setColumnWidth(1, 80)
        self.utilization_tab_table.setColumnWidth(2, 60)

        # Set self.utilization_tab_table row length.
        row_length = 0

        for feature in utilization_dic.keys():
            for vendor_daemon in utilization_dic[feature].keys():
                row_length += 1

        self.utilization_tab_table.setRowCount(0)
        self.utilization_tab_table.setRowCount(row_length)

        # Fill self.utilization_tab_table items.
        if utilization_dic:
            i = -1

            for feature in utilization_dic.keys():
                for vendor_daemon in utilization_dic[feature].keys():
                    if self.enable_utilization_product:
                        utilization_list = []

                        for sample_date in utilization_dic[feature][vendor_daemon].keys():
                            utilization_list.append(utilization_dic[feature][vendor_daemon][sample_date]['utilization'])

                        avg_utilization = round(sum(utilization_list) / len(utilization_list), 1)
                    else:
                        issued_list = []
                        in_use_list = []

                        for sample_date in utilization_dic[feature][vendor_daemon].keys():
                            issued_list.append(utilization_dic[feature][vendor_daemon][sample_date]['issued'])
                            in_use_list.append(utilization_dic[feature][vendor_daemon][sample_date]['in_use'])

                        if 'Uncounted' in issued_list:
                            if sum(in_use_list) > 0:
                                avg_utilization = 100.0
                            else:
                                avg_utilization = 0.0
                        else:
                            avg_utilization = round(100 * sum(in_use_list) / sum(issued_list), 1)

                    i += 1

                    # Fill "feature" item.
                    item = QTableWidgetItem(feature)
                    self.utilization_tab_table.setItem(i, 0, item)

                    # Fill "vendor" item.
                    item = QTableWidgetItem(vendor_daemon)
                    self.utilization_tab_table.setItem(i, 1, item)

                    # Fill "utilization" item.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, avg_utilization)

                    if avg_utilization >= 80:
                        item.setForeground(Qt.red)
                    elif int(avg_utilization) == 0:
                        item.setForeground(Qt.gray)

                    self.utilization_tab_table.setItem(i, 2, item)

    def utilization_tab_table_click(self, item=None):
        """
        If click feature name on self.utilization_tab_table, jump to FEATURE tab and show feature related information.
        """
        if item:
            if (item.column() == 0) and (not self.enable_utilization_product):
                current_row = self.utilization_tab_table.currentRow()
                feature = self.utilization_tab_table.item(current_row, 0).text().strip()

                self.feature_tab_feature_line.setText(feature)
                self.filter_feature_tab_license_feature(get_license_info=False)
                self.main_tab.setCurrentWidget(self.feature_tab)

    def gen_utilization_tab_frame1(self):
        """
        Generate self.utilization_tab_frame1.
        """
        # self.utilization_tab_frame1
        self.utilization_tab_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.utilization_tab_toolbar = common_pyqt5.NavigationToolbar2QT(self.utilization_tab_canvas, self)

        # self.utilization_tab_frame1 - Grid
        utilization_tab_frame1_grid = QGridLayout()
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_toolbar, 0, 0)
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_canvas, 1, 0)
        self.utilization_tab_frame1.setLayout(utilization_tab_frame1_grid)

    def update_utilization_tab_frame1(self, utilization_dic={}):
        """
        Generate self.utilization_tab_frame1.
        """
        # Generate fig.
        fig = self.utilization_tab_canvas.figure
        fig.clear()
        self.utilization_tab_canvas.draw()

        # Print loading cost informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Process utilization info, please wait a moment ...')

        # Print loading cost informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Process utilization info, please wait a moment ...')
        my_show_message.start()

        # Get sample_date_list.
        sample_date_list = []

        for feature in utilization_dic.keys():
            for vendor_daemon in utilization_dic[feature].keys():
                sample_date_list.extend(list(utilization_dic[feature][vendor_daemon].keys()))

        sample_date_list = list(set(sample_date_list))
        sample_date_list.sort()

        # Get utilization_list.
        utilization_list = []

        for sample_date in sample_date_list:
            sample_date_utilization_list = []

            for feature in utilization_dic.keys():
                for vendor_daemon in utilization_dic[feature].keys():
                    if sample_date in utilization_dic[feature][vendor_daemon].keys():
                        sample_date_utilization_list.append(utilization_dic[feature][vendor_daemon][sample_date]['utilization'])

            avg_sample_date_utilzation = round(sum(sample_date_utilization_list) / len(sample_date_utilization_list), 1)
            utilization_list.append(avg_sample_date_utilzation)

        my_show_message.terminate()

        if sample_date_list and utilization_list:
            # Update sample_date format.
            for (i, sample_date) in enumerate(sample_date_list):
                if self.enable_utilization_detail:
                    sample_date_list[i] = datetime.datetime.strptime(sample_date, '%Y%m%d_%H%M%S')
                else:
                    sample_date_list[i] = datetime.datetime.strptime(sample_date, '%Y%m%d')

            # Get avg_utilization.
            avg_utilization = round(sum(utilization_list) / len(utilization_list), 1)

            # Draw utilization curve.
            self.draw_utilization_tab_curve(fig, avg_utilization, sample_date_list, utilization_list)

    def draw_utilization_tab_curve(self, fig, avg_utilization, sample_date_list, utilization_list):
        """
        Draw average utilization curve for specified feature(s).
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        axes.set_title('Average Utilization : ' + str(avg_utilization) + '%')

        if self.enable_utilization_detail:
            axes.set_xlabel('Sample Time')
        else:
            axes.set_xlabel('Sample Date')

        axes.set_ylabel('Utilization (%)')
        axes.plot(sample_date_list, utilization_list, 'ro-', label='UT', linewidth=0.1, markersize=0.1)
        axes.fill_between(sample_date_list, 0, utilization_list, color='red', alpha=0.5)
        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.utilization_tab_canvas.draw()
# For UTILIZATION TAB (end) #

# For COST TAB (start) #
    def gen_cost_tab(self):
        """
        Generate COST tab, show license feature cost information.
        """
        self.cost_tab_frame0 = QFrame(self.cost_tab)
        self.cost_tab_frame0.setFrameShadow(QFrame.Raised)
        self.cost_tab_frame0.setFrameShape(QFrame.Box)

        self.cost_tab_table = QTableWidget(self.cost_tab)
        self.cost_tab_table.itemClicked.connect(self.cost_tab_table_click)

        # Grid
        cost_tab_grid = QGridLayout()

        cost_tab_grid.addWidget(self.cost_tab_frame0, 0, 0)
        cost_tab_grid.addWidget(self.cost_tab_table, 1, 0)

        cost_tab_grid.setRowStretch(0, 1)
        cost_tab_grid.setRowStretch(1, 10)

        self.cost_tab.setLayout(cost_tab_grid)

        # Generate self.cost_tab_frame0, self.cost_tab_table and self.cost_tab_frame1.
        self.gen_cost_tab_frame0()
        self.gen_cost_tab_table()

    def gen_cost_tab_frame0(self):
        # License Server
        cost_tab_server_label = QLabel('Server', self.cost_tab_frame0)
        cost_tab_server_label.setStyleSheet('font-weight: bold;')
        cost_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_server_combo = QComboBox(self.cost_tab_frame0)
        self.set_cost_tab_server_combo()
        self.cost_tab_server_combo.activated.connect(self.cost_tab_server_combo_changed)

        # License vendor daemon
        cost_tab_vendor_label = QLabel('Vendor', self.cost_tab_frame0)
        cost_tab_vendor_label.setStyleSheet('font-weight: bold;')
        cost_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_vendor_combo = QComboBox(self.cost_tab_frame0)
        self.set_cost_tab_vendor_combo()
        self.cost_tab_vendor_combo.activated.connect(self.cost_tab_vendor_combo_changed)

        # License Feature
        cost_tab_feature_label = QLabel('Feature', self.cost_tab_frame0)
        cost_tab_feature_label.setStyleSheet('font-weight: bold;')
        cost_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_feature_line = QLineEdit()
        self.cost_tab_feature_line.returnPressed.connect(self.filter_cost_tab)

        # Check button
        cost_tab_check_button = QPushButton('Check', self.cost_tab_frame0)
        cost_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        cost_tab_check_button.clicked.connect(self.filter_cost_tab)

        # Begin_Data
        cost_tab_begin_date_label = QLabel('Begin_Date', self.cost_tab_frame0)
        cost_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        cost_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_begin_date_edit = QDateEdit(self.cost_tab_frame0)
        self.cost_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.cost_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.cost_tab_begin_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.cost_tab_begin_date_edit.setCalendarPopup(True)
        self.cost_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

        # End_Data
        cost_tab_end_date_label = QLabel('End_Date', self.cost_tab_frame0)
        cost_tab_end_date_label.setStyleSheet("font-weight: bold;")
        cost_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_end_date_edit = QDateEdit(self.cost_tab_frame0)
        self.cost_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.cost_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.cost_tab_end_date_edit.setMaximumDate(QDate.currentDate().addDays(0))
        self.cost_tab_end_date_edit.setCalendarPopup(True)
        self.cost_tab_end_date_edit.setDate(QDate.currentDate())

        # License Product
        cost_tab_product_label = QLabel('Product', self.cost_tab_frame0)
        cost_tab_product_label.setStyleSheet('font-weight: bold;')
        cost_tab_product_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cost_tab_product_line = QLineEdit()
        self.cost_tab_product_line.returnPressed.connect(self.filter_cost_tab)

        # Export button
        cost_tab_export_button = QPushButton('Export', self.cost_tab_frame0)
        cost_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        cost_tab_export_button.clicked.connect(self.export_cost_table)

        # self.cost_tab_frame0 - Grid
        cost_tab_frame0_grid = QGridLayout()

        cost_tab_frame0_grid.addWidget(cost_tab_server_label, 0, 0)
        cost_tab_frame0_grid.addWidget(self.cost_tab_server_combo, 0, 1)
        cost_tab_frame0_grid.addWidget(cost_tab_vendor_label, 0, 2)
        cost_tab_frame0_grid.addWidget(self.cost_tab_vendor_combo, 0, 3)
        cost_tab_frame0_grid.addWidget(cost_tab_feature_label, 0, 4)
        cost_tab_frame0_grid.addWidget(self.cost_tab_feature_line, 0, 5)
        cost_tab_frame0_grid.addWidget(cost_tab_check_button, 0, 6)
        cost_tab_frame0_grid.addWidget(cost_tab_begin_date_label, 1, 0)
        cost_tab_frame0_grid.addWidget(self.cost_tab_begin_date_edit, 1, 1)
        cost_tab_frame0_grid.addWidget(cost_tab_end_date_label, 1, 2)
        cost_tab_frame0_grid.addWidget(self.cost_tab_end_date_edit, 1, 3)
        cost_tab_frame0_grid.addWidget(cost_tab_product_label, 1, 4)
        cost_tab_frame0_grid.addWidget(self.cost_tab_product_line, 1, 5)
        cost_tab_frame0_grid.addWidget(cost_tab_export_button, 1, 6)

        cost_tab_frame0_grid.setColumnStretch(0, 1)
        cost_tab_frame0_grid.setColumnStretch(1, 1)
        cost_tab_frame0_grid.setColumnStretch(2, 1)
        cost_tab_frame0_grid.setColumnStretch(3, 1)
        cost_tab_frame0_grid.setColumnStretch(4, 1)
        cost_tab_frame0_grid.setColumnStretch(5, 1)
        cost_tab_frame0_grid.setColumnStretch(6, 1)

        self.cost_tab_frame0.setLayout(cost_tab_frame0_grid)

    def set_cost_tab_server_combo(self):
        """
        Set (initialize) self.cost_tab_server_combo.
        """
        self.cost_tab_server_combo.clear()

        license_server_list = ['ALL', ]

        for license_server in self.license_dic.keys():
            license_server_list.append(license_server)

        for license_server in license_server_list:
            self.cost_tab_server_combo.addItem(license_server)

    def cost_tab_server_combo_changed(self):
        """
        If self.cost_tab_server_combo is selected, update self.cost_tab_vendor_combo, then filter license feature on cost_tab.
        """
        self.set_cost_tab_vendor_combo()
        self.filter_cost_tab()

    def set_cost_tab_vendor_combo(self):
        """
        Set (initialize) self.cost_tab_vendor_combo.
        """
        self.cost_tab_vendor_combo.clear()

        vendor_daemon_list = ['ALL', ]
        selected_license_server = self.cost_tab_server_combo.currentText().strip()

        for license_server in self.license_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        for vendor_daemon in vendor_daemon_list:
            self.cost_tab_vendor_combo.addItem(vendor_daemon)

    def cost_tab_vendor_combo_changed(self):
        """
        If self.cost_tab_vendor_combo is selected, filter license feature on cost_tab.
        """
        if self.cost_tab_vendor_combo.count() > 2:
            self.filter_cost_tab()

    def filter_cost_tab(self):
        """
        Update self.cost_tab_table.
        """
        cost_dic = self.get_cost_info()

        self.gen_cost_tab_table(cost_dic)

    def get_cost_info(self):
        """
        Get EDA license feature cost information from config.db_path/license_server/<license_server>/<vendor_deamon>/usage.db.
        """
        # Print loading cost informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading cost info, please wait a moment ...')

        # Print loading cost informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading cost info, please wait a moment ...')
        my_show_message.start()

        cost_dic = {}
        fuzzy_cost_dic = {}

        begin_date = self.cost_tab_begin_date_edit.date().toString(Qt.ISODate)
        begin_date = str(begin_date) + ' 00:00:00'
        begin_second = int(datetime.datetime.strptime(begin_date, "%Y-%m-%d %H:%M:%S").timestamp())
        end_date = self.cost_tab_end_date_edit.date().toString(Qt.ISODate)
        end_date = str(end_date) + ' 23:59:59'
        end_second = int(datetime.datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").timestamp())
        select_condition = 'WHERE sample_second>' + str(begin_second) + ' AND start_second<' + str(end_second)

        selected_license_server = self.cost_tab_server_combo.currentText().strip()
        selected_vendor_daemon = self.cost_tab_vendor_combo.currentText().strip()
        specified_license_feature_list = self.cost_tab_feature_line.text().strip().split()

        # Filter with license_server/vendor_daemon/feature.
        for license_server in self.db_dic.keys():
            if (selected_license_server == 'ALL') or (selected_license_server == license_server):
                for vendor_daemon in self.db_dic[license_server].keys():
                    if (selected_vendor_daemon == 'ALL') or (selected_vendor_daemon == vendor_daemon):
                        # Get full feature information from utilization database.
                        if 'utilization' in self.db_dic[license_server][vendor_daemon].keys():
                            utilization_db_file = self.db_dic[license_server][vendor_daemon]['utilization']
                            (utilization_db_file_connect_result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file)

                            if utilization_db_file_connect_result == 'failed':
                                common.print_warning('*Warning*: Failed on connecting utilization database file "' + str(utilization_db_file) + '".')
                            else:
                                utilization_db_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)

                                for feature in utilization_db_table_list:
                                    if feature != 'sqlite_sequence':
                                        # Check fuzzy_mode.
                                        fuzzy_mode = False

                                        for specified_license_feature in specified_license_feature_list:
                                            if (feature != specified_license_feature) and re.search(re.escape(specified_license_feature.lower()), feature.lower()):
                                                fuzzy_mode = True
                                                break

                                        # feature match or fuzzy_mode.
                                        if (not specified_license_feature_list) or (feature in specified_license_feature_list) or fuzzy_mode:
                                            if fuzzy_mode:
                                                fuzzy_cost_dic.setdefault(feature, {})
                                                fuzzy_cost_dic[feature].setdefault(vendor_daemon, {})

                                                for project in self.project_list:
                                                    fuzzy_cost_dic[feature][vendor_daemon].setdefault(project, 0)
                                            else:
                                                cost_dic.setdefault(feature, {})
                                                cost_dic[feature].setdefault(vendor_daemon, {})

                                                for project in self.project_list:
                                                    cost_dic[feature][vendor_daemon].setdefault(project, 0)

                        # Get used feature information from utilization database.
                        if 'usage' in self.db_dic[license_server][vendor_daemon].keys():
                            usage_db_file = self.db_dic[license_server][vendor_daemon]['usage']
                            (usage_db_file_connect_result, usage_db_conn) = common_sqlite3.connect_db_file(usage_db_file)

                            if usage_db_file_connect_result == 'failed':
                                common.print_warning('*Warning*: Failed on connecting usage database file "' + str(usage_db_file) + '".')
                            else:
                                usage_db_table_list = common_sqlite3.get_sql_table_list(usage_db_file, usage_db_conn)

                                for feature in usage_db_table_list:
                                    if feature != 'sqlite_sequence':
                                        # Check fuzzy_mode.
                                        fuzzy_mode = False

                                        for specified_license_feature in specified_license_feature_list:
                                            if (feature != specified_license_feature) and re.search(re.escape(specified_license_feature.lower()), feature.lower()):
                                                fuzzy_mode = True
                                                break

                                        # feature match or fuzzy_mode.
                                        if (not specified_license_feature_list) or (feature in specified_license_feature_list) or fuzzy_mode:
                                            data_dic = common_sqlite3.get_sql_table_data(usage_db_file, usage_db_conn, feature, ['sample_second', 'user', 'submit_host', 'execute_host', 'num', 'start_second'], select_condition)

                                            if data_dic:
                                                if fuzzy_mode:
                                                    fuzzy_cost_dic.setdefault(feature, {})
                                                    fuzzy_cost_dic[feature].setdefault(vendor_daemon, {})

                                                    for project in self.project_list:
                                                        fuzzy_cost_dic[feature][vendor_daemon].setdefault(project, 0)
                                                else:
                                                    cost_dic.setdefault(feature, {})
                                                    cost_dic[feature].setdefault(vendor_daemon, {})

                                                    for project in self.project_list:
                                                        cost_dic[feature][vendor_daemon].setdefault(project, 0)

                                                for (i, sample_second) in enumerate(data_dic['sample_second']):
                                                    num = int(data_dic['num'][i])
                                                    start_second = int(data_dic['start_second'][i])

                                                    # Get total runtime for the feature usage record.
                                                    if start_second >= begin_second:
                                                        if sample_second >= end_second:
                                                            runtime_second = num * (end_second - start_second)
                                                        else:
                                                            runtime_second = num * (sample_second - start_second)
                                                    else:
                                                        if sample_second >= end_second:
                                                            runtime_second = num * (end_second - begin_second)
                                                        else:
                                                            runtime_second = num * (sample_second - begin_second)

                                                    # Get project runtime information for the feature usage record.
                                                    project_dic = self.get_project_info(submit_host=data_dic['submit_host'][i], execute_host=data_dic['execute_host'][i], user=data_dic['user'][i], start_second=start_second)

                                                    if project_dic:
                                                        for project in project_dic.keys():
                                                            if project in self.project_list:
                                                                if fuzzy_mode:
                                                                    fuzzy_cost_dic[feature][vendor_daemon][project] += project_dic[project] * runtime_second
                                                                else:
                                                                    cost_dic[feature][vendor_daemon][project] += project_dic[project] * runtime_second
                                                            else:
                                                                if self.enable_cost_others_project:
                                                                    # If not find any product information, collect runtime into 'others' group.
                                                                    if fuzzy_mode:
                                                                        fuzzy_cost_dic[feature][vendor_daemon]['others'] += runtime_second
                                                                    else:
                                                                        cost_dic[feature][vendor_daemon]['others'] += runtime_second
                                                    else:
                                                        if self.enable_cost_others_project:
                                                            # If not find any product information, collect runtime into 'others' group.
                                                            if fuzzy_mode:
                                                                fuzzy_cost_dic[feature][vendor_daemon]['others'] += runtime_second
                                                            else:
                                                                cost_dic[feature][vendor_daemon]['others'] += runtime_second

                                usage_db_conn.close()

        # Filter with feature on fuzzy mode.
        if (not cost_dic) and fuzzy_cost_dic:
            cost_dic = fuzzy_cost_dic

        # Filter with white/black feature list.
        filtered_cost_dic = copy.deepcopy(cost_dic)

        if self.cost_white_feature_list:
            filtered_cost_dic = {}

            for white_feature in self.cost_white_feature_list:
                for feature in cost_dic.keys():
                    if re.match(white_feature, feature):
                        filtered_cost_dic[feature] = cost_dic[feature]
        elif self.cost_black_feature_list:
            for black_feature in self.cost_black_feature_list:
                for feature in cost_dic.keys():
                    if re.match(black_feature, feature):
                        del filtered_cost_dic[feature]

        my_show_message.terminate()

        if not filtered_cost_dic:
            common.print_warning('*Warning*: No cost data is find.')

        return filtered_cost_dic

    def get_project_info(self, submit_host, execute_host, user, start_second):
        """
        Get project information based on submit_host/execute_host/user.
        """
        project_dic = {}
        factor_dic = {'submit_host': submit_host, 'execute_host': execute_host, 'user': user}

        if hasattr(config, 'project_primary_factors') and config.project_primary_factors:
            project_primary_factor_list = config.project_primary_factors.split()

            for (i, create_second) in enumerate(self.project_setting_create_second_list):
                if ((i == 0) and (start_second <= create_second)) or ((i == len(self.project_setting_create_second_list)-1) and (start_second >= create_second)) or ((i < len(self.project_setting_create_second_list)-1) and (start_second >= create_second) and (start_second <= self.project_setting_create_second_list[i+1])):
                    for project_primary_factor in project_primary_factor_list:
                        if project_primary_factor not in factor_dic.keys():
                            common.print_error('*Error*: "' + str(project_primary_factor) + '": invalid project_primary_factors setting on config file.')
                            sys.exit(1)
                        else:
                            factor_value = factor_dic[project_primary_factor]
                            project_proportion_dic = {}

                            if factor_value in self.project_setting_dic[create_second]['project_' + str(project_primary_factor)].keys():
                                project_proportion_dic = self.project_setting_dic[create_second]['project_' + str(project_primary_factor)][factor_value]

                            if project_proportion_dic:
                                project_dic = project_proportion_dic
                                break
                            else:
                                continue

        return project_dic

    def gen_cost_tab_table(self, cost_dic={}):
        """
        Generate self.cost_tab_table.
        """
        if self.enable_cost_product:
            self.cost_tab_table_title_list = ['Product', 'Vendor', 'RunTime (H)']
            cost_dic = self.switch_product_on_cost_dic(cost_dic)
        else:
            self.cost_tab_table_title_list = ['Feature', 'Vendor', 'RunTime (H)']

        self.cost_tab_table_title_list.extend(self.project_list)

        self.cost_tab_table.setShowGrid(True)
        self.cost_tab_table.setSortingEnabled(True)
        self.cost_tab_table.setColumnCount(0)
        self.cost_tab_table.setColumnCount(len(self.cost_tab_table_title_list))
        self.cost_tab_table.setHorizontalHeaderLabels(self.cost_tab_table_title_list)
        self.cost_tab_table.setColumnWidth(1, 80)
        self.cost_tab_table.setColumnWidth(2, 100)

        # Set self.cost_tab_table row length.
        row_length = 0

        for feature in cost_dic.keys():
            for vendor_daemon in cost_dic[feature].keys():
                row_length += 1

        self.cost_tab_table.setRowCount(0)
        self.cost_tab_table.setRowCount(row_length)

        # Fill self.cost_tab_table items.
        if cost_dic:
            i = -1

            for feature in cost_dic.keys():
                for vendor_daemon in cost_dic[feature].keys():
                    i += 1

                    # Get total_runtime information.
                    total_runtime = 0

                    for project in cost_dic[feature][vendor_daemon].keys():
                        project_runtime = cost_dic[feature][vendor_daemon][project]
                        total_runtime += project_runtime

                    # Fill "Feature" item.
                    item = QTableWidgetItem(feature)
                    self.cost_tab_table.setItem(i, 0, item)

                    # Fill "Vendor" item.
                    item = QTableWidgetItem(vendor_daemon)
                    self.cost_tab_table.setItem(i, 1, item)

                    # Fill "RunTime" item.
                    item = QTableWidgetItem()
                    total_runtime_hour = int(total_runtime/3600)

                    if (total_runtime != 0) and (total_runtime_hour == 0):
                        total_runtime_hour = 0.1

                    item.setData(Qt.DisplayRole, total_runtime_hour)

                    if total_runtime == 0:
                        item.setForeground(Qt.gray)

                    self.cost_tab_table.setItem(i, 2, item)

                    # Fill "project*" item.
                    j = 2

                    for project in self.project_list:
                        if project in cost_dic[feature][vendor_daemon].keys():
                            project_runtime = cost_dic[feature][vendor_daemon][project]

                            if total_runtime == 0:
                                project_rate = 0
                            else:
                                project_rate = round(100*project_runtime/total_runtime, 2)

                            if re.match(r'^(\d+)\.0+$', str(project_rate)):
                                my_match = re.match(r'^(\d+)\.0+$', str(project_rate))
                                project_rate = int(my_match.group(1))

                            item = QTableWidgetItem()
                            item.setData(Qt.DisplayRole, str(project_rate) + '%')

                            if total_runtime == 0:
                                item.setForeground(Qt.gray)
                            elif (project == 'others') and (project_rate != 0):
                                item.setForeground(Qt.red)

                            j += 1
                            self.cost_tab_table.setItem(i, j, item)

    def cost_tab_table_click(self, item=None):
        """
        If click feature name on self.cost_tab_table, jump to FEATURE tab and show feature related information.
        """
        if item:
            if (item.column() == 0) and (not self.enable_cost_product):
                current_row = self.cost_tab_table.currentRow()
                feature = self.cost_tab_table.item(current_row, 0).text().strip()

                self.feature_tab_feature_line.setText(feature)
                self.filter_feature_tab_license_feature(get_license_info=False)
                self.main_tab.setCurrentWidget(self.feature_tab)
# For COST TAB (end) #

# Export table (start) #
    def export_server_table(self):
        self.export_table('server', self.server_tab_table, self.server_tab_table_title_list)

    def export_feature_table(self):
        self.export_table('feature', self.feature_tab_table, self.feature_tab_table_title_list)

    def export_expires_table(self):
        self.export_table('expires', self.expires_tab_table, self.expires_tab_table_title_list)

    def export_usage_table(self):
        self.export_table('usage', self.usage_tab_table, self.usage_tab_table_title_list)

    def export_curve_table(self):
        self.export_table('curve', self.curve_tab_table, self.curve_tab_table_title_list)

    def export_utilization_table(self):
        self.export_table('utilization', self.utilization_tab_table, self.utilization_tab_table_title_list)

    def export_cost_table(self):
        self.export_table('cost', self.cost_tab_table, self.cost_tab_table_title_list)

    def export_table(self, table_type, table_item, title_list):
        """
        Export specified table info into an Excel.
        """
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_time_string = re.sub('-', '', current_time)
        current_time_string = re.sub(':', '', current_time_string)
        current_time_string = re.sub(' ', '_', current_time_string)
        default_output_file = './licenseMonitor_' + str(table_type) + '_' + str(current_time_string) + '.xlsx'
        (output_file, output_file_type) = QFileDialog.getSaveFileName(self, 'Export ' + str(table_type) + ' table', default_output_file, 'Excel (*.xlsx)')

        if output_file:
            # Get table content.
            table_info_list = []
            table_info_list.append(title_list)

            for row in range(table_item.rowCount()):
                row_list = []

                for column in range(table_item.columnCount()):
                    if table_item.item(row, column):
                        row_list.append(table_item.item(row, column).text())
                    else:
                        row_list.append('')

                table_info_list.append(row_list)

            # Write excel
            print('* [' + str(current_time) + '] Writing ' + str(table_type) + ' table into "' + str(output_file) + '" ...')

            common.write_excel(excel_file=output_file, contents_list=table_info_list, specified_sheet_name=table_type)
# Export table (end) #

    def close_event(self, QCloseEvent):
        """
        When window close, post-process.
        """
        print('Bye')


class LicenseLogWindow(QMainWindow):
    def __init__(self, server='', vendor='', feature='', user='', lic_files=''):
        super().__init__()

        self.server = server
        self.vendor = vendor
        self.feature = feature
        self.user = user
        self.lic_files = lic_files

        # Generate GUI.
        self.init_ui()

    def init_ui(self):
        # Set License Log Window title
        self.setWindowTitle('Licence Log')

        # Set size & position
        self.license_log_widget = QWidget()
        self.setCentralWidget(self.license_log_widget)
        self.resize(800, 525)
        common_pyqt5.center_window(self)

        self.license_log_frame = QFrame(self.license_log_widget)
        self.license_log_frame.setFrameShadow(QFrame.Raised)
        self.license_log_frame.setFrameShape(QFrame.Box)

        self.license_log_table = QTableWidget(self.license_log_widget)

        self.license_log_grid = QGridLayout()

        self.license_log_grid.addWidget(self.license_log_frame, 0, 0)
        self.license_log_grid.addWidget(self.license_log_table, 1, 0)
        self.license_log_grid.setRowStretch(0, 1)
        self.license_log_grid.setRowStretch(1, 10)

        self.license_log_widget.setLayout(self.license_log_grid)

        self.gen_license_log_frame()
        self.gen_license_log_table()

    def gen_license_log_frame(self):
        # License Server
        self.server_label0 = QLabel('Server', self.license_log_frame)
        self.server_label0.setStyleSheet('font-weight: bold;')
        self.server_label0.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.server_label1 = QLabel(self.server, self.license_log_frame)
        self.server_label1.setAlignment(Qt.AlignVCenter)

        # License vendor/daemon
        self.vendor_label0 = QLabel('Vendor', self.license_log_frame)
        self.vendor_label0.setStyleSheet('font-weight: bold;')
        self.vendor_label0.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.vendor_label1 = QLabel(self.vendor, self.license_log_frame)
        self.vendor_label1.setAlignment(Qt.AlignVCenter)

        # License Feature
        self.feature_label = QLabel('Feature', self.license_log_frame)
        self.feature_label.setStyleSheet('font-weight: bold;')
        self.feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_line = QLineEdit()
        self.feature_line.setText(self.feature)
        self.feature_line.returnPressed.connect(self.gen_license_log_table)

        # License User
        self.user_label = QLabel('User', self.license_log_frame)
        self.user_label.setStyleSheet('font-weight: bold;')
        self.user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.user_line = QLineEdit()
        self.user_line.setText(self.user)
        self.user_line.returnPressed.connect(self.gen_license_log_table)

        # License Status
        self.status_label = QLabel('Status', self.license_log_frame)
        self.status_label.setStyleSheet('font-weight: bold;')
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.status_combo = QComboBox(self.license_log_frame)
        self.set_status_combo()
        self.status_combo.activated.connect(self.gen_license_log_table)

        # License Log Check
        self.check_button = QPushButton('Check', self.license_log_frame)
        self.check_button.clicked.connect(self.gen_license_log_table)

        self.license_log_frame_grid = QGridLayout()
        self.license_log_frame_grid.addWidget(self.server_label0, 0, 0)
        self.license_log_frame_grid.addWidget(self.server_label1, 0, 1)
        self.license_log_frame_grid.addWidget(self.vendor_label0, 0, 2)
        self.license_log_frame_grid.addWidget(self.vendor_label1, 0, 3)
        self.license_log_frame_grid.addWidget(self.check_button, 0, 5)
        self.license_log_frame_grid.addWidget(self.feature_label, 2, 0)
        self.license_log_frame_grid.addWidget(self.feature_line, 2, 1)
        self.license_log_frame_grid.addWidget(self.user_label, 2, 2)
        self.license_log_frame_grid.addWidget(self.user_line, 2, 3)
        self.license_log_frame_grid.addWidget(self.status_label, 2, 4)
        self.license_log_frame_grid.addWidget(self.status_combo, 2, 5)

        self.license_log_frame_grid.setColumnStretch(0, 1)
        self.license_log_frame_grid.setColumnStretch(1, 1)
        self.license_log_frame_grid.setColumnStretch(2, 1)
        self.license_log_frame_grid.setColumnStretch(3, 1)
        self.license_log_frame_grid.setColumnStretch(4, 1)
        self.license_log_frame_grid.setColumnStretch(5, 1)
        self.license_log_frame_grid.setColumnStretch(6, 1)

        self.license_log_frame.setLayout(self.license_log_frame_grid)

    def get_license_log_info(self, feature='', user='', status='ALL'):
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading license log, please wait a moment ...')

        my_show_message = ShowMessage('Info', 'Loading license log, please wait a moment ...')
        my_show_message.start()

        if hasattr(config, 'max_record_num') and config.max_record_num and re.match(r'^\d+$', str(config.max_record_num)):
            max_record_num = int(config.max_record_num)
        else:
            max_record_num = 1000

        license_log_class = LicenseLog(server=self.server, vendor=self.vendor, feature=feature, user=user, status=status, lic_files=self.lic_files, max_record_num=max_record_num)
        license_log_info_list = license_log_class.license_log_info_list

        my_show_message.terminate()

        return license_log_info_list

    def gen_license_log_table(self):
        self.license_log_table.setShowGrid(True)
        self.license_log_table.setSortingEnabled(True)
        self.license_log_table.setColumnCount(6)
        self.license_log_table.setHorizontalHeaderLabels(['Log Time', 'Status', 'Feature', 'User', 'Execute_Host', 'Info'])

        self.license_log_table.setColumnWidth(0, 80)
        self.license_log_table.setColumnWidth(1, 120)
        self.license_log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.license_log_table.setColumnWidth(3, 120)
        self.license_log_table.setColumnWidth(4, 120)
        self.license_log_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        # Get license log info
        feature = self.feature_line.text().strip()
        user = self.user_line.text().strip()
        status = self.status_combo.currentText().strip()
        license_log_info_list = self.get_license_log_info(feature=feature, user=user, status=status)

        # Get license log num.
        license_log_num = len(license_log_info_list)

        # Fill license_log_table.
        self.license_log_table.setRowCount(0)
        self.license_log_table.setRowCount(license_log_num)
        self.license_log_table. setSortingEnabled(False)

        row = -1

        for record in license_log_info_list:
            row += 1

            item = QTableWidgetItem()
            item.setText(record.log_time)
            self.license_log_table.setItem(row, 0, item)

            item = QTableWidgetItem()
            item.setText(record.status)
            self.license_log_table.setItem(row, 1, item)

            item = QTableWidgetItem()
            item.setText(record.feature)
            self.license_log_table.setItem(row, 2, item)

            item = QTableWidgetItem()
            item.setText(record.user)
            self.license_log_table.setItem(row, 3, item)

            item = QTableWidgetItem()
            item.setText(record.exec_host)
            self.license_log_table.setItem(row, 4, item)

            info = record.info if record.info else ''

            item = QTableWidgetItem()
            item.setText(info)
            self.license_log_table.setItem(row, 5, item)

    def set_status_combo(self):
        """
        Set self.status_combo
        """
        self.status_combo.clear()

        for status in ['ALL', 'OUT', 'IN', 'DENIED', 'QUEUED', 'UNSUPPORTED']:
            self.status_combo.addItem(status)


class LicenseRecord:
    def __init__(self, log_time, status, feature, user, exec_host, info):
        self.log_time = log_time
        self.status = status
        self.feature = feature
        self.user = user
        self.exec_host = exec_host
        self.info = info


class LicenseLog:
    """
    Get feature/user information from license log file.
    """
    def __init__(self, server='', vendor='', feature='', user='', status='', lic_files='', max_record_num=1000):
        self.server = server
        self.vendor = vendor
        self.feature = feature
        self.user = user
        self.status = status
        self.lic_files = lic_files
        self.max_record_num = max_record_num

        # Main data structrue for LicenseLog, save all license log information.
        self.license_log_info_list = []

        # Get self.license_log_info_list.
        if self.feature:
            self.get_license_log_info()

    def get_license_log_info(self):
        """
        Get self.license_log_info_list.
        """
        # Get real license log path.
        license_log = ''
        license_server_host = self.server.split('@')[1]

        if (not license_log) and self.lic_files:
            lic_log_rec = re.compile(r'^.*lmgrd.*\s+-c\s+(.*)\s+-l\s+(\S+)\s*.*$')
            command = 'ps -aux | grep lmgrd '

            stdout_list = common.ssh_client(host_name=license_server_host, user_name=str(getpass.getuser()), command=command, timeout=1)

            for line in stdout_list:
                if my_match := lic_log_rec.match(line):
                    license_file_info = my_match.group(1)

                    if self.lic_files.find(license_file_info) != -1:
                        license_log = my_match.group(2)

        # Get expected information from license log.
        if not license_log:
            common.print_warning('*Warning*: Could not find ' + str(self.vendor) + ' license log file in ' + str(self.server) + ' ...')
        else:
            if os.path.exists(license_log):
                grep_cmd = 'grep \'"%s"\' %s ' % (self.feature, license_log)
                (return_code, stdout, stderr) = common.run_command(grep_cmd)
                stdout_list = str(stdout, 'unicode_escape').split('\n')
            else:
                grep_cmd = 'grep \'"%s"\' %s | tail -n %s' % (self.feature, license_log, str(self.max_record_num))
                stdout_list = common.ssh_client(host_name=license_server_host, user_name=str(getpass.getuser()), command=grep_cmd, timeout=20)

            self.parse_license_log_info(license_log, stdout_list)

    def parse_license_log_info(self, license_log, stdout_list):
        """
        Parse license log, get expected info, save into self.license_log_info_list.
        """
        if not stdout_list:
            common.print_warning('*Warning*: Could not find any infomation when reading license log file ' + str(license_log) + '...')
            return

        if self.status == 'ALL':
            log_rec = re.compile(r'^\s*([0-9:]+)\s*\(\S+\)\s+\b(DENIED|IN|OUT|UNSUPPORTED|QUEUED)+\b:\s+\"(.*%s.*)\".*\s+(.*%s.*)(?=@)@(\S+).\s*(.*)\s*$' % (self.feature, self.user))
        else:
            log_rec = re.compile(r'^\s*([0-9:]+)\s*\(\S+\)\s+\b(%s)+\b:\s+\"(.*%s.*)\".*\s+(.*%s.*)(?=@)@(\S+).\s*(.*)\s*$' % (self.status, self.feature, self.user))

        info_num = len(stdout_list)

        for i in range(info_num):
            if i >= self.max_record_num:
                break

            line = stdout_list[info_num - 1 - i]

            if my_match := log_rec.match(line):
                log_time = my_match.group(1)
                status = my_match.group(2)
                feature = my_match.group(3)
                user = my_match.group(4)
                exec_host = my_match.group(5)
                info = my_match.group(6).strip()

                if info.find(']') != -1:
                    info = info.split(']')[1]

                license_record = LicenseRecord(log_time, status, feature, user, exec_host, info)
                self.license_log_info_list.append(license_record)


class ShowMessage(QThread):
    """
    Show message with tool message.
    """
    def __init__(self, title, message):
        super(ShowMessage, self).__init__()
        self.title = title
        self.message = message

    def run(self):
        command = 'python3 ' + str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/tools/message.py --title "' + str(self.title) + '" --message "' + str(self.message) + '"'
        os.system(command)

    def terminate(self):
        time.sleep(0.01)
        QThread.terminate(self)


#################
# Main Function #
#################
def main():
    (specified_feature, specified_user, specified_tab) = read_args()
    app = QApplication(sys.argv)
    mw = MainWindow(specified_feature, specified_user, specified_tab)
    mw.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
