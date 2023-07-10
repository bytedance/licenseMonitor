# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import time
import copy
import getpass
import datetime
import argparse

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QAction, qApp, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QMessageBox, QLineEdit, QComboBox, QHeaderView, QDateEdit, QFileDialog
from PyQt5.QtGui import QBrush, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, QDate

from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

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
                        help='Specify license feature which you want to see on "LICENSE/EXPIRES/USAGE/UTILIZATION/COST" tab.')
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


class FigureCanvas(FigureCanvasQTAgg):
    """
    Generate a new figure canvas.
    """
    def __init__(self):
        self.figure = Figure()
        super().__init__(self.figure)


class MainWindow(QMainWindow):
    """
    Main window of licenseMonitor.
    """
    def __init__(self, specified_feature, specified_user, specified_tab):
        super().__init__()
        self.license_dic = {}
        self.db_dic = self.get_db_info()
        self.license_dic_second = 0

        # Get project related information.
        self.project_list = self.parse_project_list_file()
        self.project_list.append('others')
        self.project_submit_host_dic = self.parse_project_proportion_file(config.project_submit_host_file)
        self.project_execute_host_dic = self.parse_project_proportion_file(config.project_execute_host_file)
        self.project_user_dic = self.parse_project_proportion_file(config.project_user_file)
        self.project_proportion_dic = {'submit_host': self.project_submit_host_dic, 'execute_host': self.project_execute_host_dic, 'user': self.project_user_dic}

        # Generate GUI.
        self.init_ui()

        # Pre-set feature.
        if specified_feature:
            self.feature_tab_feature_line.setText(specified_feature)
            self.expires_tab_feature_line.setText(specified_feature)
            self.usage_tab_feature_line.setText(specified_feature)
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
                self.filter_utilization_tab_license_feature()
                self.gen_cost_tab_table()

            if specified_user and (not specified_feature):
                self.filter_usage_tab_license_feature(get_license_info=False)

        # For pre-set tab.
        self.switch_tab(specified_tab)

    def get_license_dic(self, force=False):
        # Not update license_dic repeatedly in config.fresh_interval seconds.
        current_second = int(time.time())

        if not force:
            if current_second - self.license_dic_second <= int(config.fresh_interval):
                return

        self.license_dic_second = current_second

        # Print loading license informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading license information, please wait a moment ...')

        # Print loading license informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading license information, please wait a moment ...')
        my_show_message.start()

        # Get self.license_dic.
        administrator_list = config.administrators.split()

        if config.LM_LICENSE_FILE and os.path.exists(config.LM_LICENSE_FILE) and config.show_configured_for_admin and (USER in administrator_list):
            os.environ['LM_LICENSE_FILE'] = ''

            with open(config.LM_LICENSE_FILE, 'r') as LLF:
                for line in LLF.readlines():
                    line = line.strip()

                    if (not re.match(r'^\s*$', line)) and (not re.match(r'^\s*#.*$', line)):
                        os.environ['LM_LICENSE_FILE'] = str(os.environ['LM_LICENSE_FILE']) + ':' + str(line)

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
        db_dic = {}

        for license_server in os.listdir(config.db_path):
            license_server_path = str(config.db_path) + '/' + str(license_server)

            if re.match(r'^\d+@\S+$', license_server) and os.path.isdir(license_server_path):
                db_dic.setdefault(license_server, {})

                for vendor_daemon in os.listdir(license_server_path):
                    vendor_daemon_path = str(license_server_path) + '/' + str(vendor_daemon)
                    usage_db_path = str(vendor_daemon_path) + '/usage.db'
                    utilization_day_db_path = str(vendor_daemon_path) + '/utilization_day.db'

                    if os.path.isdir(vendor_daemon_path):
                        db_dic[license_server].setdefault(vendor_daemon, {})

                        if os.path.exists(usage_db_path):
                            db_dic[license_server][vendor_daemon].setdefault('usage', usage_db_path)

                        if os.path.exists(utilization_day_db_path):
                            db_dic[license_server][vendor_daemon].setdefault('utilization', utilization_day_db_path)

        return db_dic

    def parse_project_list_file(self):
        """
        Parse project_list_file and return List "project_list".
        """
        project_list = []

        if config.project_list_file and os.path.exists(config.project_list_file):
            with open(config.project_list_file, 'r') as PLF:
                for line in PLF.readlines():
                    line = line.strip()

                    if re.match(r'^\s*#.*$', line) or re.match(r'^\s*$', line):
                        continue
                    else:
                        if line not in project_list:
                            project_list.append(line)

        return project_list

    def parse_project_proportion_file(self, project_proportion_file):
        """
        Parse config.project_*_file and return dictory "project_proportion_dic".
        """
        project_proportion_dic = {}

        if project_proportion_file and os.path.exists(project_proportion_file):
            with open(project_proportion_file, 'r') as PPF:
                for line in PPF.readlines():
                    line = line.strip()

                    if re.match(r'^\s*#.*$', line) or re.match(r'^\s*$', line):
                        continue
                    elif re.match(r'^(\S+)\s*:\s*(\S+)$', line):
                        my_match = re.match(r'^(\S+)\s*:\s*(\S+)$', line)
                        item = my_match.group(1)
                        project = my_match.group(2)

                        if item in project_proportion_dic.keys():
                            common.print_warning('*Warning*: "' + str(item) + '": repeated item on "' + str(project_proportion_file) + '", ignore.')
                            continue
                        else:
                            project_proportion_dic[item] = {project: 1}
                    elif re.match(r'^(\S+)\s*:\s*(.+)$', line):
                        my_match = re.match(r'^(\S+)\s*:\s*(.+)$', line)
                        item = my_match.group(1)
                        project_string = my_match.group(2)
                        tmp_dic = {}

                        for project_setting in project_string.split():
                            if re.match(r'^(\S+)\((0.\d+)\)$', project_setting):
                                my_match = re.match(r'^(\S+)\((0.\d+)\)$', project_setting)
                                project = my_match.group(1)
                                project_proportion = my_match.group(2)

                                if project in tmp_dic.keys():
                                    tmp_dic = {}
                                    break
                                else:
                                    tmp_dic[project] = float(project_proportion)
                            else:
                                tmp_dic = {}
                                break

                        if not tmp_dic:
                            common.print_warning('*Warning*: invalid line on "' + str(project_proportion_file) + '", ignore.')
                            common.print_warning('           ' + str(line))
                            continue
                        else:
                            sum_proportion = sum(list(tmp_dic.values()))

                            if sum_proportion == 1.0:
                                project_proportion_dic[item] = tmp_dic
                            else:
                                common.print_warning('*Warning*: invalid line on "' + str(project_proportion_file) + '", ignore.')
                                common.print_warning('           ' + str(line))
                                continue
                    else:
                        common.print_warning('*Warning*: invalid line on "' + str(project_proportion_file) + '", ignore.')
                        common.print_warning('           ' + str(line))
                        continue

        return project_proportion_dic

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
        self.utilization_tab = QWidget()
        self.cost_tab = QWidget()

        # Add the sub-tabs into main Tab widget
        self.main_tab.addTab(self.server_tab, 'SERVER')
        self.main_tab.addTab(self.feature_tab, 'FEATURE')
        self.main_tab.addTab(self.expires_tab, 'EXPIRES')
        self.main_tab.addTab(self.usage_tab, 'USAGE')
        self.main_tab.addTab(self.utilization_tab, 'UTILIZATION')
        self.main_tab.addTab(self.cost_tab, 'COST')

        # Get License information.
        self.get_license_dic()

        # Generate the sub-tabs
        self.gen_server_tab()
        self.gen_feature_tab()
        self.gen_expires_tab()
        self.gen_usage_tab()
        self.gen_utilization_tab()
        self.gen_cost_tab()

        # Show main window
        self.setWindowTitle('licenseMonitor')
        self.resize(1200, 580)
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
                   'UTILIZATION': self.utilization_tab,
                   'COST': self.cost_tab,
                  }

        self.main_tab.setCurrentWidget(tab_dic[specified_tab])

    def gen_menubar(self):
        """
        Generate menubar.
        """
        menubar = self.menuBar()

        # File
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(qApp.quit)

        file_menu = menubar.addMenu('File')
        file_menu.addAction(exit_action)

        # Setup
        fresh_action = QAction('Fresh', self)
        fresh_action.triggered.connect(self.fresh)
        self.periodic_fresh_timer = QTimer(self)
        periodic_fresh_action = QAction('Periodic Fresh (1 min)', self, checkable=True)
        periodic_fresh_action.triggered.connect(self.periodic_fresh)

        setup_menu = menubar.addMenu('Setup')
        setup_menu.addAction(fresh_action)
        setup_menu.addAction(periodic_fresh_action)

        # Help
        version_action = QAction('Version', self)
        version_action.triggered.connect(self.show_version)

        about_action = QAction('About licenseMonitor', self)
        about_action.triggered.connect(self.show_about)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(version_action)
        help_menu.addAction(about_action)

    def fresh(self):
        """
        Re-build the GUI with latest license status.
        """
        self.get_license_dic(force=True)
        self.gen_server_tab_table()
        self.filter_feature_tab_license_feature(get_license_info=False)
        self.filter_expires_tab_license_feature(get_license_info=False)
        self.filter_usage_tab_license_feature(get_license_info=False)
        self.filter_utilization_tab_license_feature()
        self.gen_cost_tab_table()

    def periodic_fresh(self, state):
        """
        Fresh the GUI every 60 seconds.
        """
        if state:
            self.periodic_fresh_timer.timeout.connect(self.fresh)
            self.periodic_fresh_timer.start(60000)
        else:
            self.periodic_fresh_timer.stop()

    def show_version(self):
        """
        Show licenseMonitor version information.
        """
        version = 'V1.1'
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

# Common sub-functions (begin) #
    def gui_warning(self, warning_message):
        """
        Show the specified warning message on both of command line and GUI window.
        """
        common.print_warning(warning_message)
        QMessageBox.warning(self, 'licenseMonitor Warning', warning_message)
# Common sub-functions (end) #

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
        server_tab_table_title_list = ['Server', 'Server_Status', 'Server_Version', 'License_Files', 'Vendor', 'Vendor_Status', 'Vendor_Version']
        self.server_tab_table.setColumnCount(len(server_tab_table_title_list))
        self.server_tab_table.setHorizontalHeaderLabels(server_tab_table_title_list)

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
        self.feature_tab_table.itemClicked.connect(self.feature_tab_table_check_click)

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
        self.feature_tab_table.setHorizontalHeaderLabels(['Server', 'Vendor', 'Feature', 'Total_License', 'In_Use_License'])

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
        self.expires_tab_table.setHorizontalHeaderLabels(['Server', 'Vendor', 'Feature', 'Version', 'License_Num', 'Expires'])

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
        self.usage_tab_table.setHorizontalHeaderLabels(['Server', 'Vendor', 'Feature', 'User', 'Submit_Host', 'Execute_Host', 'Num', 'Version', 'Start_Time'])

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

# For UTILIZATION TAB (start) #
    def gen_utilization_tab(self):
        """
        Generate UTILIAZTION tab, show license feature utilization information.
        """
        self.utilization_tab_frame0 = QFrame(self.utilization_tab)
        self.utilization_tab_frame0.setFrameShadow(QFrame.Raised)
        self.utilization_tab_frame0.setFrameShape(QFrame.Box)

        self.utilization_tab_table = QTableWidget(self.utilization_tab)

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
        utilization_dic = self.get_utilization_info()
        self.gen_utilization_tab_table(utilization_dic)
        self.gen_utilization_tab_frame1()
        self.update_utilization_tab_frame1(utilization_dic)

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
        self.utilization_tab_vendor_combo.activated.connect(self.utilization_tab_vendor_combo_changed)

        # License Feature
        utilization_tab_feature_label = QLabel('Feature', self.utilization_tab_frame0)
        utilization_tab_feature_label.setStyleSheet('font-weight: bold;')
        utilization_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_feature_line = QLineEdit()
        self.utilization_tab_feature_line.returnPressed.connect(self.filter_utilization_tab_license_feature)

        # Check button
        utilization_tab_check_button = QPushButton('Check', self.utilization_tab_frame0)
        utilization_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        utilization_tab_check_button.clicked.connect(self.filter_utilization_tab_license_feature)

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

        # Empty label
        utilization_tab_empty_label = QLabel('', self.utilization_tab_frame0)

        # Export button
        utilization_tab_export_button = QPushButton('Export', self.utilization_tab_frame0)
        utilization_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        utilization_tab_export_button.clicked.connect(self.export_utilization_info)

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
        utilization_tab_frame0_grid.addWidget(utilization_tab_empty_label, 1, 4, 1, 2)
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
        If self.utilization_tab_server_combo is selected, update self.utilization_tab_vendor_combo, then filter license feature on utilization_tab.
        """
        self.set_utilization_tab_vendor_combo()
        self.filter_utilization_tab_license_feature()

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

    def utilization_tab_vendor_combo_changed(self):
        """
        If self.utilization_tab_vendor_combo is selected, filter license feature on utilization_tab.
        """
        if self.utilization_tab_vendor_combo.count() > 2:
            self.filter_utilization_tab_license_feature()

    def filter_utilization_tab_license_feature(self):
        """
        Update self.utilization_tab_table and self.utilization_tab_frame1.
        """
        utilization_dic = self.get_utilization_info()

        self.gen_utilization_tab_table(utilization_dic)
        self.update_utilization_tab_frame1(utilization_dic)

    def get_utilization_info(self):
        """
        Get utilization information from config.db_path/license_server/vendor_deamon/utilization_day.db.
        """
        # Print loading utilization informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading utilization information, please wait a moment ...')

        # Print loading utilization informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading utilization information, please wait a moment ...')
        my_show_message.start()

        utilization_dic = {}
        fuzzy_utilization_dic = {}

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
                                        data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, feature, ['sample_date', 'issued', 'in_use', 'utilization'], select_condition)

                                        if not data_dic:
                                            common.print_warning('*Warning*: utilization information is empty for "' + str(license_server) + '/' + str(vendor_daemon) + '/' + str(feature) + '".')
                                        else:
                                            if fuzzy_mode:
                                                fuzzy_utilization_dic.setdefault(feature, {})
                                                fuzzy_utilization_dic[feature].setdefault(vendor_daemon, {})
                                            else:
                                                utilization_dic.setdefault(feature, {})
                                                utilization_dic[feature].setdefault(vendor_daemon, {})

                                            for (i, sample_date) in enumerate(data_dic['sample_date']):
                                                issued = data_dic['issued'][i]
                                                in_use = data_dic['in_use'][i]
                                                utilization = data_dic['utilization'][i]

                                                if fuzzy_mode:
                                                    fuzzy_utilization_dic[feature][vendor_daemon].setdefault(sample_date, {'issued': 0.0, 'in_use': 0.0, 'utilization': []})
                                                else:
                                                    utilization_dic[feature][vendor_daemon].setdefault(sample_date, {'issued': 0.0, 'in_use': 0.0, 'utilization': []})

                                                if issued == 'Uncounted':
                                                    if fuzzy_mode:
                                                        fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] = 'Uncounted'
                                                    else:
                                                        utilization_dic[feature][vendor_daemon][sample_date]['issued'] = 'Uncounted'
                                                else:
                                                    if fuzzy_mode:
                                                        if fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] != 'Uncounted':
                                                            fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['issued'] = float(issued)
                                                    else:
                                                        if utilization_dic[feature][vendor_daemon][sample_date]['issued'] != 'Uncounted':
                                                            utilization_dic[feature][vendor_daemon][sample_date]['issued'] = float(issued)

                                                if fuzzy_mode:
                                                    fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['in_use'] = float(in_use)
                                                    fuzzy_utilization_dic[feature][vendor_daemon][sample_date]['utilization'].append(float(utilization))
                                                else:
                                                    utilization_dic[feature][vendor_daemon][sample_date]['in_use'] = float(in_use)
                                                    utilization_dic[feature][vendor_daemon][sample_date]['utilization'].append(float(utilization))

                                utilization_db_conn.close()

        # Filter with feature on fuzzy mode.
        if (not utilization_dic) and fuzzy_utilization_dic:
            utilization_dic = fuzzy_utilization_dic

        my_show_message.terminate()

        return utilization_dic

    def export_utilization_info(self):
        """
        Export self.utilization_tab_table into an Excel.
        """
        (utilization_info_file, file_type) = QFileDialog.getSaveFileName(self, 'Export utilization info', './lm_utilization.xlsx', 'Excel (*.xlsx)')

        if utilization_info_file:
            # Get self.utilization_tab_label content.
            utilization_tab_table_list = []
            utilization_tab_table_list.append(self.utilization_tab_table_title_list)

            for row in range(self.utilization_tab_table.rowCount()):
                row_list = []
                for column in range(self.utilization_tab_table.columnCount()):
                    row_list.append(self.utilization_tab_table.item(row, column).text())

                utilization_tab_table_list.append(row_list)

            # Write excel
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print('* [' + str(current_time) + '] Writing utilization info file "' + str(utilization_info_file) + '" ...')

            common.write_excel(excel_file=utilization_info_file, contents_list=utilization_tab_table_list, specified_sheet_name='utilization_info')

    def gen_utilization_tab_table(self, utilization_dic={}):
        """
        Generate self.utilization_tab_table.
        """
        if not utilization_dic:
            utilization_dic = self.get_utilization_info()

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
        i = -1

        for feature in utilization_dic.keys():
            for vendor_daemon in utilization_dic[feature].keys():
                utilization_list = []

                for sample_date in utilization_dic[feature][vendor_daemon].keys():
                    utilization_list.extend(utilization_dic[feature][vendor_daemon][sample_date]['utilization'])

                avg_utilization = round(sum(utilization_list)/len(utilization_list), 1)

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

    def gen_utilization_tab_frame1(self):
        """
        Generate self.utilization_tab_frame1.
        """
        # self.utilization_tab_frame1
        self.utilization_tab_canvas = FigureCanvas()
        self.utilization_tab_toolbar = NavigationToolbar2QT(self.utilization_tab_canvas, self)

        # self.utilization_tab_frame1 - Grid
        utilization_tab_frame1_grid = QGridLayout()
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_toolbar, 0, 0)
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_canvas, 0, 0)
        self.utilization_tab_frame1.setLayout(utilization_tab_frame1_grid)

    def update_utilization_tab_frame1(self, utilization_dic={}):
        """
        Generate self.utilization_tab_frame1.
        """
        if not utilization_dic:
            utilization_dic = self.get_utilization_info()

        # Generate fig.
        fig = self.utilization_tab_canvas.figure
        fig.clear()
        self.utilization_tab_canvas.draw()

        # Get date_list.
        date_list = []

        for feature in utilization_dic.keys():
            for vendor_daemon in utilization_dic[feature].keys():
                for sample_date in utilization_dic[feature][vendor_daemon].keys():
                    if sample_date not in date_list:
                        date_list.append(sample_date)

        date_list.sort()

        # Get utilization_list.
        utilization_list = []
        full_utilization_list = []

        for date in date_list:
            tmp_utilization_list = []

            for feature in utilization_dic.keys():
                for vendor_daemon in utilization_dic[feature].keys():
                    for sample_date in utilization_dic[feature][vendor_daemon].keys():
                        if sample_date == date:
                            tmp_utilization_list.extend(utilization_dic[feature][vendor_daemon][sample_date]['utilization'])
                            full_utilization_list.extend(utilization_dic[feature][vendor_daemon][sample_date]['utilization'])

            date_avg_utilization = round(sum(tmp_utilization_list)/len(tmp_utilization_list), 1)
            utilization_list.append(date_avg_utilization)

        # Update sample_date format.
        for (i, sample_date) in enumerate(date_list):
            sample_date = datetime.datetime.strptime(sample_date, '%Y%m%d')
            date_list[i] = sample_date

        # Get avg_utilization.
        avg_utilization = 0

        if full_utilization_list:
            avg_utilization = round(sum(full_utilization_list)/len(full_utilization_list), 1)

        # Draw utilization curve.
        self.draw_utilization_tab_curve(fig, avg_utilization, date_list, utilization_list)

    def draw_utilization_tab_curve(self, fig, avg_utilization, date_list, utilization_list):
        """
        Draw average utilization curve for specified feature(s).
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        axes.set_title('Average Utilization : ' + str(avg_utilization) + '%')
        axes.set_xlabel('Date')
        axes.set_ylabel('Utilization')
        axes.plot(date_list, utilization_list, 'ro-')
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
        self.cost_tab_feature_line.returnPressed.connect(self.gen_cost_tab_table)

        # Check button
        cost_tab_check_button = QPushButton('Check', self.cost_tab_frame0)
        cost_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        cost_tab_check_button.clicked.connect(self.gen_cost_tab_table)

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

        # Empty label
        cost_tab_empty_label = QLabel('', self.cost_tab_frame0)

        # Export button
        cost_tab_export_button = QPushButton('Export', self.cost_tab_frame0)
        cost_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        cost_tab_export_button.clicked.connect(self.export_cost_info)

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
        cost_tab_frame0_grid.addWidget(cost_tab_empty_label, 1, 4, 1, 2)
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
        self.gen_cost_tab_table()

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
            self.gen_cost_tab_table()

    def get_cost_info(self):
        """
        Get EDA license feature cost information from config.db_path/license_server/vendor_deamon/usage.db.
        """
        # Print loading cost informaiton message.
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('* [' + str(current_time) + '] Loading cost information, please wait a moment ...')

        # Print loading cost informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading cost information, please wait a moment ...')
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
                                                    project_dic = self.get_project_info(submit_host=data_dic['submit_host'][i], execute_host=data_dic['execute_host'][i], user=data_dic['user'][i])

                                                    if project_dic:
                                                        for project in project_dic.keys():
                                                            if fuzzy_mode:
                                                                fuzzy_cost_dic[feature][vendor_daemon][project] += project_dic[project] * runtime_second
                                                            else:
                                                                cost_dic[feature][vendor_daemon][project] += project_dic[project] * runtime_second
                                                    else:
                                                        # If not find any product information, collect runtime into 'others' group.
                                                        if fuzzy_mode:
                                                            fuzzy_cost_dic[feature][vendor_daemon]['others'] += runtime_second
                                                        else:
                                                            cost_dic[feature][vendor_daemon]['others'] += runtime_second

                                usage_db_conn.close()

        # Filter with feature on fuzzy mode.
        if (not cost_dic) and fuzzy_cost_dic:
            cost_dic = fuzzy_cost_dic

        my_show_message.terminate()

        return cost_dic

    def get_project_info(self, submit_host, execute_host, user):
        """
        Get project information based on submit_host/execute_host/user.
        """
        project_dic = {}
        factor_dic = {'submit_host': submit_host, 'execute_host': execute_host, 'user': user}

        if config.project_primary_factors:
            project_primary_factor_list = config.project_primary_factors.split()

            for project_primary_factor in project_primary_factor_list:
                if project_primary_factor not in factor_dic.keys():
                    common.print_error('*Error*: "' + str(project_primary_factor) + '": invalid project_primary_factors setting on config file.')
                    sys.exit(1)
                else:
                    factor_value = factor_dic[project_primary_factor]
                    project_proportion_dic = {}

                    if factor_value in self.project_proportion_dic[project_primary_factor].keys():
                        project_proportion_dic = self.project_proportion_dic[project_primary_factor][factor_value]

                    if project_proportion_dic:
                        project_dic = project_proportion_dic
                        break
                    else:
                        continue

        return project_dic

    def export_cost_info(self):
        """
        Export self.cost_tab_table into an Excel.
        """
        (cost_info_file, file_type) = QFileDialog.getSaveFileName(self, 'Export cost info', './lm_cost.xlsx', 'Excel (*.xlsx)')

        if cost_info_file:
            # Get self.cost_tab_label content.
            cost_tab_table_list = []
            cost_tab_table_list.append(self.cost_tab_table_title_list)

            for row in range(self.cost_tab_table.rowCount()):
                row_list = []

                for column in range(self.cost_tab_table.columnCount()):
                    row_list.append(self.cost_tab_table.item(row, column).text())

                cost_tab_table_list.append(row_list)

            # Write excel
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print('* [' + str(current_time) + '] Writing cost info file "' + str(cost_info_file) + '" ...')

            common.write_excel(excel_file=cost_info_file, contents_list=cost_tab_table_list, specified_sheet_name='cost_info')

    def gen_cost_tab_table(self):
        """
        Generate self.cost_tab_table.
        """
        cost_dic = self.get_cost_info()
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
# For COST TAB (end) #

    def close_event(self, QCloseEvent):
        """
        When window close, post-process.
        """
        print('Bye')


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
