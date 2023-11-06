# -*- coding: utf-8 -*-
################################
# File Name   : config_product_feature_relationship.py
# Author      : liyanqing
# Created On  : 2022-04-13 00:00:00
# Description :
################################
import os
import sys
import yaml

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox

sys.path.insert(0, os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common_pyqt5
from common import common_license

CWD = os.getcwd()
os.environ['PYTHONUNBUFFERED'] = '1'


class MainWindow(QMainWindow):
    """
    Main window of config_product_feature_relationship.
    Below are some vendor daemon names.
    ['alterad', 'ansysldm', 'armldm', 'cdslmd', 'empyrean', 'imperasd', 'interrad', 'magillem', 'mgcld', 'saltd', 'snpsldm', 'verplex', 'xilinxd', 'xpdldm']
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """
        Main process, draw the main graphic frame.
        """
        # Define main Tab widget
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        # Defaint sub-frames
        self.select_frame = QFrame(self.main_tab)
        self.select_frame.setFrameShadow(QFrame.Raised)
        self.select_frame.setFrameShape(QFrame.Box)

        self.license_table = QTableWidget(self.main_tab)

        self.output_frame = QFrame(self.main_tab)
        self.output_frame.setFrameShadow(QFrame.Raised)
        self.output_frame.setFrameShape(QFrame.Box)

        # Grid
        main_grid = QGridLayout()

        main_grid.addWidget(self.select_frame, 0, 0)
        main_grid.addWidget(self.license_table, 1, 0)
        main_grid.addWidget(self.output_frame, 2, 0)

        main_grid.setRowStretch(0, 2)
        main_grid.setRowStretch(1, 15)
        main_grid.setRowStretch(2, 1)

        self.main_tab.setLayout(main_grid)

        # Generate main_table
        self.gen_select_frame()
        self.gen_output_frame()

        # Show main window
        self.setWindowTitle('Config product-feature relationship')
        self.resize(1000, 520)
        common_pyqt5.center_window(self)

    def gen_select_frame(self):
        # Vendor
        vendor_label = QLabel(self.select_frame)
        vendor_label.setStyleSheet("font-weight: bold;")
        vendor_label.setText('* Vendor Daemon')

        self.vendor_line = QLineEdit()

        # License File
        license_file_label = QLabel(self.select_frame)
        license_file_label.setStyleSheet("font-weight: bold;")
        license_file_label.setText('* License File')

        self.license_file_line = QLineEdit()

        # Yaml File
        yaml_file_label = QLabel(self.select_frame)
        yaml_file_label.setStyleSheet("font-weight: bold;")
        yaml_file_label.setText('Yaml File')

        self.yaml_file_line = QLineEdit()

        # Update Button
        update_button = QPushButton('Update', self.select_frame)
        update_button.setFixedHeight(90)
        update_button.clicked.connect(self.update_license_table)

        # self.select_frame - Grid
        select_frame_grid = QGridLayout()

        select_frame_grid.addWidget(vendor_label, 0, 0)
        select_frame_grid.addWidget(self.vendor_line, 0, 1)
        select_frame_grid.addWidget(license_file_label, 1, 0)
        select_frame_grid.addWidget(self.license_file_line, 1, 1)
        select_frame_grid.addWidget(yaml_file_label, 2, 0)
        select_frame_grid.addWidget(self.yaml_file_line, 2, 1)
        select_frame_grid.addWidget(update_button, 0, 2, 3, 1)

        select_frame_grid.setColumnStretch(0, 1)
        select_frame_grid.setColumnStretch(1, 8)
        select_frame_grid.setColumnStretch(2, 1)

        self.select_frame.setLayout(select_frame_grid)

    def get_license_file_dic(self):
        license_file_dic = {}
        license_file = self.license_file_line.text().strip()

        if license_file:
            if not os.path.exists(license_file):
                warning_message = '*Warning*: "' + str(license_file) + '": No such file.'
                QMessageBox.warning(self, 'Warning', warning_message)
            else:
                print('>>> Parse license file "' + str(license_file) + '".')
                license_file_dic = common_license.parse_license_file(license_file)

        return (license_file_dic)

    def update_license_table(self):
        # Pre-check
        vendor = self.vendor_line.text().strip()

        if not vendor:
            warning_message = '*Warning*: Required argument "Vendor Daemon" is not specified.'
            QMessageBox.warning(self, 'Warning', warning_message)
            return

        license_file = self.license_file_line.text().strip()

        if not license_file:
            warning_message = '*Warning*: Required argument "License File" is not specified.'
            QMessageBox.warning(self, 'Warning', warning_message)
            return
        elif not os.path.exists(license_file):
            warning_message = '*Warning*: "' + str(license_file) + '": No such file.'
            QMessageBox.warning(self, 'Warning', warning_message)
            return

        # Generate self.license_table.
        self.license_table.setShowGrid(True)
        self.license_table.setColumnCount(0)
        self.license_table.setColumnCount(2)
        self.license_table.setHorizontalHeaderLabels(['Feature', 'Product'])

        # Set column width.
        self.license_table.setColumnWidth(0, 250)
        self.license_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # Get licene_file_dic.
        license_file_dic = self.get_license_file_dic()

        # Get feature list.
        feature_list = []

        if license_file_dic:
            for feature_dic in license_file_dic['feature']:
                if feature_dic['feature'] not in feature_list:
                    feature_list.append(feature_dic['feature'])

        feature_list.sort()

        # Get product_feature_relationship_dic.
        product_feature_relationship_dic = {}
        yaml_file = self.yaml_file_line.text().strip()

        if yaml_file and os.path.exists(yaml_file):
            print('>>> Load yaml file "' + str(yaml_file) + '".')

            yaml_dic = yaml.load(open(yaml_file), Loader=yaml.FullLoader)

            if vendor in yaml_dic:
                product_feature_relationship_dic = yaml_dic[vendor]
            else:
                warning_message = '*Warning*: Not find vendor daemon "' + str(vendor) + '" on "' + str(yaml_file) + '".'
                QMessageBox.warning(self, 'Warning', warning_message)

        # Fill self.license_table.
        if feature_list:
            # Set row count
            self.license_table.setRowCount(0)
            self.license_table.setRowCount(len(feature_list))

            # Set item.
            for (row, feature) in enumerate(feature_list):
                # Feature item
                item = QTableWidgetItem()
                item.setText(feature)
                self.license_table.setItem(row, 0, item)

                # Product item.
                if product_feature_relationship_dic and (feature in product_feature_relationship_dic):
                    product = '#'.join(product_feature_relationship_dic[feature])
                    item = QTableWidgetItem()
                    item.setText(product)
                    self.license_table.setItem(row, 1, item)

    def gen_output_frame(self):
        # self.output_frame
        output_label = QLabel(self.output_frame)
        output_label.setStyleSheet("font-weight: bold;")
        output_label.setText('Output : ')

        self.output_line = QLineEdit()
        default_output_file = str(CWD) + '/product_feature.yaml'
        self.output_line.setText(default_output_file)

        gen_button = QPushButton('Gen', self.output_frame)
        gen_button.clicked.connect(self.gen_output_file)

        # self.output_frame - Grid
        output_frame_grid = QGridLayout()

        output_frame_grid.addWidget(output_label, 0, 0)
        output_frame_grid.addWidget(self.output_line, 0, 1)
        output_frame_grid.addWidget(gen_button, 0, 2)

        output_frame_grid.setColumnStretch(0, 1)
        output_frame_grid.setColumnStretch(1, 10)
        output_frame_grid.setColumnStretch(2, 1)

        self.output_frame.setLayout(output_frame_grid)

    def gen_output_file(self):
        # Check output_file directory.
        output_file = self.output_line.text().strip()
        output_dir = os.path.dirname(output_file)

        if not os.path.exists(output_dir):
            error_message = '*Error*: "' + str(output_dir) + '": No such output file directory.'
            QMessageBox.critical(self, 'Error', error_message)
            return

        # Generate product_feature_relationship_dic.
        vendor = self.vendor_line.text().strip()
        product_feature_relationship_dic = {vendor: {}}

        for row in range(self.license_table.rowCount()):
            feature = self.license_table.item(row, 0).text().strip()
            product_list = []

            if self.license_table.item(row, 1):
                orig_product_list = self.license_table.item(row, 1).text().strip().split('#')

                for product in orig_product_list:
                    product = product.strip()

                    if product and (product not in product_list):
                        product_list.append(product)

            if feature:
                if feature not in product_feature_relationship_dic[vendor]:
                    if product_list:
                        product_feature_relationship_dic[vendor][feature] = product_list
                    else:
                        print('*Warning*: "' + str(feature) + '": Not find related product setting.')
                else:
                    print('*Warning*: "' + str(feature) + '": Repeated feature.')

        # Write output_file.
        print('>>> Write output file "' + str(output_file) + '".')

        with open(output_file, 'w', encoding='utf-8') as OF:
            yaml.dump(product_feature_relationship_dic, OF)


################
# Main Process #
################
def main():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
