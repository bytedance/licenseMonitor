# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import getpass
import argparse

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit, QComboBox, QHeaderView
from PyQt5.QtCore import Qt, QThread

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_pyqt5
from config import config

os.environ['PYTHONUNBUFFERED'] = '1'
USER = getpass.getuser()

# Solve some unexpected warning message.
if 'XDG_RUNTIME_DIR' not in os.environ:
    os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-' + str(USER)

    if not os.path.exists(os.environ['XDG_RUNTIME_DIR']):
        os.makedirs(os.environ['XDG_RUNTIME_DIR'])

    os.chmod(os.environ['XDG_RUNTIME_DIR'], 0o777)


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-s", "--server",
                        required=True,
                        help='Required argument, specify license server.')
    parser.add_argument("-v", "--vendor",
                        required=True,
                        help='Required argument, specify vendor daemon.')
    parser.add_argument("-f", "--feature",
                        required=True,
                        help='Required argument, specify license feature.')
    parser.add_argument("-u", "--user",
                        default='',
                        help='Specify user.')
    parser.add_argument("-l", "--lic_files",
                        required=True,
                        nargs='+',
                        default=[],
                        help='Required arguments, specify license files.')

    args = parser.parse_args()

    lic_files = ' '.join(args.lic_files)

    return args.server, args.vendor, args.feature, args.user, lic_files


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
            command = 'ps -aux | grep lmgrd'
            stdout_list = common.ssh_client(host_name=license_server_host, user_name=str(getpass.getuser()), command=command, timeout=1)

            for line in stdout_list:
                if my_match := lic_log_rec.match(line):
                    license_file_info = my_match.group(1)

                    if self.lic_files.find(license_file_info) != -1:
                        license_log = my_match.group(2)

        # Get expected information from license log.
        if not license_log:
            common.bprint('Could not find ' + str(self.vendor) + ' license log file in ' + str(self.server) + ' ...', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
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
            common.bprint('Could not find any infomation when reading license log file ' + str(license_log) + '...', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
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


class MainWindow(QMainWindow):
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
        self.setWindowTitle('Licence Log Info')

        # Set size & position
        self.license_log_widget = QWidget()
        self.setCentralWidget(self.license_log_widget)
        common_pyqt5.auto_resize(self, 800, 525)
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
        """
        Generate self.license_log_frame.
        """
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

        self.license_log_frame_grid.setColumnStretch(1, 1)
        self.license_log_frame_grid.setColumnStretch(2, 1)
        self.license_log_frame_grid.setColumnStretch(3, 1)
        self.license_log_frame_grid.setColumnStretch(4, 1)
        self.license_log_frame_grid.setColumnStretch(5, 1)
        self.license_log_frame_grid.setColumnStretch(6, 1)

        self.license_log_frame.setLayout(self.license_log_frame_grid)

    def get_license_log_info(self, feature='', user='', status='ALL'):
        """
        Get license log content with specified feature/user/status.
        """
        common.bprint('Searching feature info from log, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Searching feature info from log, please wait a moment ...')
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
        """
        Generate self.license_log_table.
        """
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
    (server, vendor, feature, user, lic_files) = read_args()
    app = QApplication(sys.argv)
    mw = MainWindow(server, vendor, feature, user, lic_files)
    mw.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
