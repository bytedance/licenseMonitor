# -*- coding: utf-8 -*-

import os
import sys
import stat
import time
import copy
import getpass
import datetime
import argparse

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QAction, qApp, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QMessageBox, QLineEdit, QComboBox, QHeaderView
from PyQt5.QtGui import QBrush, QFont
from PyQt5.QtCore import Qt, QTimer, QThread

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_license
from common import common_pyqt5
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
                        help='Specify license feature which you want to see on "LICENSE/EXPIRES/USAGE" tab.')
    parser.add_argument("-u", "--user",
                        default='',
                        help='Specify the user on "USAGE" tab.')
    parser.add_argument("-t", "--tab",
                        default='FEATURE',
                        choices=['SERVER', 'FEATURE', 'EXPIRES', 'USAGE'],
                        help='Specify current tab, default is "FEATURE" tab.')

    args = parser.parse_args()

    # Set default tab for args.feature.
    if args.feature:
        if not args.tab:
            args.tab = 'FEATURE'

    # Set default tab for args.user.
    if args.user:
        if not args.tab:
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
        self.license_dic_second = 0

        self.init_ui()

        # For pre-set feature.
        if specified_feature:
            # Update feature tab
            self.feature_tab_feature_line.setText(specified_feature)
            self.filter_feature_tab_license_feature()

            # Update expires tab
            self.expires_tab_feature_line.setText(specified_feature)
            self.filter_expires_tab_license_feature()

            # Update usage tab
            self.usage_tab_feature_line.setText(specified_feature)
            self.filter_usage_tab_license_feature()

        # For pre-set user.
        if specified_user:
            self.usage_tab_user_line.setText(specified_user)
            self.filter_usage_tab_license_feature()

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

        print('* [' + str(current_time) + '] Loading License information, please wait a moment ...')

        # Print loading license informaiton message with GUI.
        my_show_message = ShowMessage('Info', 'Loading license information, please wait a moment ...')
        my_show_message.start()

        # Get self.license_dic.
        if config.lmstat_path:
            os.environ['PATH'] = str(config.lmstat_path) + ':' + str(os.environ['PATH'])

        administrator_list = config.administrators.split()

        if config.LM_LICENSE_FILE and config.show_configured_for_admin and (USER in administrator_list):
            os.environ['LM_LICENSE_FILE'] = config.LM_LICENSE_FILE

        my_get_license_info = common_license.GetLicenseInfo(bsub_command=config.lmstat_bsub_command)
        self.license_dic = my_get_license_info.get_license_info()

        # Print loading license informaiton message with GUI. (END)
        my_show_message.terminate()

        if not self.license_dic:
            print('*Warning*: Not find any valid license information.')

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
            if (license_server in specified_license_server_list) or ('ALL' in specified_license_server_list):
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)

        return (vendor_daemon_list)

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

        # Add the sub-tabs into main Tab widget
        self.main_tab.addTab(self.server_tab, 'SERVER')
        self.main_tab.addTab(self.feature_tab, 'FEATURE')
        self.main_tab.addTab(self.expires_tab, 'EXPIRES')
        self.main_tab.addTab(self.usage_tab, 'USAGE')

        # Get License information.
        self.get_license_dic()

        # Generate the sub-tabs
        self.gen_server_tab()
        self.gen_feature_tab()
        self.gen_expires_tab()
        self.gen_usage_tab()

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
        self.gen_feature_tab_table(self.license_dic)
        self.gen_expires_tab_table(self.license_dic)
        self.gen_usage_tab_table(self.license_dic)

        self.filter_feature_tab_license_feature()
        self.filter_expires_tab_license_feature()
        self.filter_usage_tab_license_feature()

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
        version = 'V1.0 (2023.1.4)'
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
        feature_tab_show_label = QLabel('    Show', self.feature_tab_frame)
        feature_tab_show_label.setStyleSheet('font-weight: bold;')

        self.feature_tab_show_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_show_combo()
        self.feature_tab_show_combo.activated.connect(self.filter_feature_tab_license_feature)

        # License Server
        feature_tab_server_label = QLabel('    Server', self.feature_tab_frame)
        feature_tab_server_label.setStyleSheet('font-weight: bold;')

        self.feature_tab_server_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_server_combo()
        self.feature_tab_server_combo.activated.connect(self.update_feature_tab_vendor_combo)

        # Vendor Daemon
        feature_tab_vendor_label = QLabel('    Vendor', self.feature_tab_frame)
        feature_tab_vendor_label.setStyleSheet('font-weight: bold;')

        self.feature_tab_vendor_combo = QComboBox(self.feature_tab_frame)
        self.set_feature_tab_vendor_combo()
        self.feature_tab_vendor_combo.activated.connect(self.check_feature_tab_vendor_combo)

        # License Feature
        feature_tab_feature_labe = QLabel('    Feature', self.feature_tab_frame)
        feature_tab_feature_labe.setStyleSheet('font-weight: bold;')

        self.feature_tab_feature_line = QLineEdit()
        self.feature_tab_feature_line.returnPressed.connect(self.filter_feature_tab_license_feature)

        # Filter Button
        feature_tab_filter_button = QPushButton('Filter', self.feature_tab_frame)
        feature_tab_filter_button.clicked.connect(self.filter_feature_tab_license_feature)

        # Grid
        feature_tab_frame_grid = QGridLayout()

        feature_tab_frame_grid.addWidget(feature_tab_show_label, 0, 0)
        feature_tab_frame_grid.addWidget(self.feature_tab_show_combo, 0, 1)
        feature_tab_frame_grid.addWidget(feature_tab_server_label, 0, 2)
        feature_tab_frame_grid.addWidget(self.feature_tab_server_combo, 0, 3)
        feature_tab_frame_grid.addWidget(feature_tab_vendor_label, 0, 4)
        feature_tab_frame_grid.addWidget(self.feature_tab_vendor_combo, 0, 5)
        feature_tab_frame_grid.addWidget(feature_tab_feature_labe, 0, 6)
        feature_tab_frame_grid.addWidget(self.feature_tab_feature_line, 0, 7)
        feature_tab_frame_grid.addWidget(feature_tab_filter_button, 0, 8)

        feature_tab_frame_grid.setColumnStretch(1, 1)
        feature_tab_frame_grid.setColumnStretch(3, 1)
        feature_tab_frame_grid.setColumnStretch(5, 1)
        feature_tab_frame_grid.setColumnStretch(7, 1)

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

        if selected_license_server == 'ALL':
            for license_server in self.license_dic.keys():
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)
        else:
            for vendor_daemon in self.license_dic[selected_license_server]['vendor_daemon'].keys():
                if vendor_daemon not in vendor_daemon_list:
                    vendor_daemon_list.append(vendor_daemon)

        # Fill self.feature_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.feature_tab_vendor_combo.addItem(vendor_daemon)

    def update_feature_tab_vendor_combo(self):
        self.set_feature_tab_vendor_combo()
        self.filter_feature_tab_license_feature()

    def check_feature_tab_vendor_combo(self):
        if self.feature_tab_vendor_combo.count() > 2:
            self.filter_feature_tab_license_feature()

    def filter_feature_tab_license_feature(self):
        # Re-generate self.license_dic.
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
        expires_tab_show_label = QLabel('    Show', self.expires_tab_frame)
        expires_tab_show_label.setStyleSheet('font-weight: bold;')

        self.expires_tab_show_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_show_combo()
        self.expires_tab_show_combo.activated.connect(self.filter_expires_tab_license_feature)

        # License Server
        expires_tab_server_label = QLabel('    Server', self.expires_tab_frame)
        expires_tab_server_label.setStyleSheet('font-weight: bold;')

        self.expires_tab_server_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_server_combo()
        self.expires_tab_server_combo.activated.connect(self.update_expires_tab_vendor_combo)

        # License vendor daemon
        expires_tab_vendor_label = QLabel('    Vendor', self.expires_tab_frame)
        expires_tab_vendor_label.setStyleSheet('font-weight: bold;')

        self.expires_tab_vendor_combo = QComboBox(self.expires_tab_frame)
        self.set_expires_tab_vendor_combo()
        self.expires_tab_vendor_combo.activated.connect(self.check_expires_tab_vendor_combo)

        # License Feature
        expires_tab_feature_labe = QLabel('    Feature', self.expires_tab_frame)
        expires_tab_feature_labe.setStyleSheet('font-weight: bold;')

        self.expires_tab_feature_line = QLineEdit()
        self.expires_tab_feature_line.returnPressed.connect(self.filter_expires_tab_license_feature)

        # Filter Button
        expires_tab_filter_button = QPushButton('Filter', self.expires_tab_frame)
        expires_tab_filter_button.clicked.connect(self.filter_expires_tab_license_feature)

        # Grid
        expires_tab_frame_grid = QGridLayout()

        expires_tab_frame_grid.addWidget(expires_tab_show_label, 0, 0)
        expires_tab_frame_grid.addWidget(self.expires_tab_show_combo, 0, 1)
        expires_tab_frame_grid.addWidget(expires_tab_server_label, 0, 2)
        expires_tab_frame_grid.addWidget(self.expires_tab_server_combo, 0, 3)
        expires_tab_frame_grid.addWidget(expires_tab_vendor_label, 0, 4)
        expires_tab_frame_grid.addWidget(self.expires_tab_vendor_combo, 0, 5)
        expires_tab_frame_grid.addWidget(expires_tab_feature_labe, 0, 6)
        expires_tab_frame_grid.addWidget(self.expires_tab_feature_line, 0, 7)
        expires_tab_frame_grid.addWidget(expires_tab_filter_button, 0, 8)

        expires_tab_frame_grid.setColumnStretch(1, 1)
        expires_tab_frame_grid.setColumnStretch(3, 1)
        expires_tab_frame_grid.setColumnStretch(5, 1)
        expires_tab_frame_grid.setColumnStretch(7, 1)

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

        if selected_license_server == 'ALL':
            for license_server in self.license_dic.keys():
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if vendor_daemon not in vendor_daemon_list:
                        vendor_daemon_list.append(vendor_daemon)
        else:
            for vendor_daemon in self.license_dic[selected_license_server]['vendor_daemon'].keys():
                if vendor_daemon not in vendor_daemon_list:
                    vendor_daemon_list.append(vendor_daemon)

        # Fill self.expires_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.expires_tab_vendor_combo.addItem(vendor_daemon)

    def update_expires_tab_vendor_combo(self):
        self.set_expires_tab_vendor_combo()
        self.filter_expires_tab_license_feature()

    def check_expires_tab_vendor_combo(self):
        if self.expires_tab_vendor_combo.count() > 2:
            self.filter_expires_tab_license_feature()

    def filter_expires_tab_license_feature(self):
        # Re-generate self.license_dic.
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
        usage_tab_server_label = QLabel('    Server', self.usage_tab_frame)
        usage_tab_server_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_server_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_server_combo()
        self.usage_tab_server_combo.activated.connect(self.usage_tab_server_combo_changed)

        # License vendor daemon
        usage_tab_vendor_label = QLabel('    Vendor', self.usage_tab_frame)
        usage_tab_vendor_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_vendor_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_vendor_combo()
        self.usage_tab_vendor_combo.activated.connect(self.usage_tab_vendor_combo_changed)

        # License Feature
        usage_tab_feature_label = QLabel('    Feature', self.usage_tab_frame)
        usage_tab_feature_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_feature_line = QLineEdit()
        self.usage_tab_feature_line.returnPressed.connect(self.filter_usage_tab_license_feature)

        # Submit Host
        usage_tab_submit_host_label = QLabel('    Submit_Host', self.usage_tab_frame)
        usage_tab_submit_host_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_submit_host_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_submit_host_combo()
        self.usage_tab_submit_host_combo.activated.connect(self.filter_usage_tab_license_feature)

        # Execute Host
        usage_tab_execute_host_label = QLabel('    Execute_Host', self.usage_tab_frame)
        usage_tab_execute_host_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_execute_host_combo = QComboBox(self.usage_tab_frame)
        self.set_usage_tab_execute_host_combo()
        self.usage_tab_execute_host_combo.activated.connect(self.filter_usage_tab_license_feature)

        # User
        usage_tab_user_label = QLabel('    User', self.usage_tab_frame)
        usage_tab_user_label.setStyleSheet('font-weight: bold;')

        self.usage_tab_user_line = QLineEdit()
        self.usage_tab_user_line.returnPressed.connect(self.filter_usage_tab_license_feature)

        # Fileter
        usage_tab_filter_button = QPushButton('Filter', self.usage_tab_frame)
        usage_tab_filter_button.clicked.connect(self.filter_usage_tab_license_feature)

        # Grid
        usage_tab_frame_grid = QGridLayout()

        usage_tab_frame_grid.addWidget(usage_tab_server_label, 0, 0)
        usage_tab_frame_grid.addWidget(self.usage_tab_server_combo, 0, 1)
        usage_tab_frame_grid.addWidget(usage_tab_vendor_label, 0, 2)
        usage_tab_frame_grid.addWidget(self.usage_tab_vendor_combo, 0, 3)
        usage_tab_frame_grid.addWidget(usage_tab_feature_label, 0, 4)
        usage_tab_frame_grid.addWidget(self.usage_tab_feature_line, 0, 5)
        usage_tab_frame_grid.addWidget(usage_tab_submit_host_label, 1, 0)
        usage_tab_frame_grid.addWidget(self.usage_tab_submit_host_combo, 1, 1)
        usage_tab_frame_grid.addWidget(usage_tab_execute_host_label, 1, 2)
        usage_tab_frame_grid.addWidget(self.usage_tab_execute_host_combo, 1, 3)
        usage_tab_frame_grid.addWidget(usage_tab_user_label, 1, 4)
        usage_tab_frame_grid.addWidget(self.usage_tab_user_line, 1, 5)
        usage_tab_frame_grid.addWidget(usage_tab_filter_button, 1, 6)

        usage_tab_frame_grid.setColumnStretch(1, 1)
        usage_tab_frame_grid.setColumnStretch(3, 1)
        usage_tab_frame_grid.setColumnStretch(5, 1)

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
                if (selected_license_server == license_server) or (selected_license_server == 'ALL'):
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
            if (selected_license_server == license_server) or (selected_license_server == 'ALL'):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if (selected_vendor_daemon == vendor_daemon) or (selected_vendor_daemon == 'ALL'):
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
            if (selected_license_server == license_server) or (selected_license_server == 'ALL'):
                for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                    if (selected_vendor_daemon == vendor_daemon) or (selected_vendor_daemon == 'ALL'):
                        for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                            for usage_dic in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']:
                                execute_host = usage_dic['execute_host']

                                if execute_host not in execute_host_list:
                                    execute_host_list.append(execute_host)

        # Fill self.usage_tab_vendor_combo.
        for execute_host in execute_host_list:
            self.usage_tab_execute_host_combo.addItem(execute_host)

    def filter_usage_tab_license_feature(self):
        # Re-generate self.license_dic.
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
                        start_time = common_license.switch_start_time(usage_dic['start_time'])
                        item.setText(start_time)

                        if common_license.check_long_runtime(usage_dic['start_time']):
                            item.setForeground(QBrush(Qt.red))

                        self.usage_tab_table.setItem(row, 8, item)
# For USAGE TAB (end) #

    def close_event(self, QCloseEvent):
        """
        When window close, post-process.
        """
        print('Bye')


class ShowLicenseFeatureUsage(QThread):
    """
    Start tool show_license_feature_usage.py to show license feature usage information.
    """
    def __init__(self, server, feature):
        super(ShowLicenseFeatureUsage, self).__init__()
        self.server = server
        self.feature = feature

    def run(self):
        command = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/tools/show_license_feature_usage.py -s ' + str(self.server) + ' -f ' + str(self.feature)
        os.system(command)


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
