# -*- coding: utf-8 -*-
import os
import re
import sys
import argparse
import yaml

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
from PyQt5.QtCore import Qt

sys.path.insert(0, os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--input_file',
                        default='',
                        help='Specify input product_feature relationship yaml file.')

    args = parser.parse_args()

    if args.input_file:
        if not os.path.exists(args.input_file):
            common.bprint(str(args.input_file) + '" No such file.', level='Error')
            sys.exit(1)
    else:
        args.input_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/others/product_feature.yaml'

        if not os.path.exists(args.input_file):
            args.input_file = ''

    return args.input_file


class MainWindow(QMainWindow):
    def __init__(self, input_file):
        self.input_file = input_file
        (self.feature_product_dic, self.product_feature_dic) = self.get_product_feature_info()

        super().__init__()
        self.init_ui()

    def get_product_feature_info(self):
        """
        Get product_feature information from self.input_file.
        """
        feature_product_dic = {}
        product_feature_dic = {}

        if self.input_file:
            with open(self.input_file, 'r') as IF:
                feature_product_dic = yaml.load(IF, Loader=yaml.FullLoader)

                # Get product_feature_dic based on feature_product_dic.
                for vendor_daemon in feature_product_dic.keys():
                    product_feature_dic.setdefault(vendor_daemon, {})

                    for feature in feature_product_dic[vendor_daemon].keys():
                        for product in feature_product_dic[vendor_daemon][feature]:
                            product_feature_dic[vendor_daemon].setdefault(product, [])
                            product_feature_dic[vendor_daemon][product].append(feature)

        return feature_product_dic, product_feature_dic

    def init_ui(self):
        """
        Main process, draw the main graphic frame.
        """
        # Define main Tab widget.
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        # Define sub-frames
        self.product_feature_frame = QFrame(self.main_tab)
        self.product_feature_frame.setFrameShadow(QFrame.Raised)
        self.product_feature_frame.setFrameShape(QFrame.Box)

        self.product_feature_table = QTableWidget(self.main_tab)

        # Grid
        main_grid = QGridLayout()

        main_grid.addWidget(self.product_feature_frame, 0, 0)
        main_grid.addWidget(self.product_feature_table, 1, 0)

        main_grid.setRowStretch(0, 1)
        main_grid.setRowStretch(1, 10)

        self.main_tab.setLayout(main_grid)

        # Generate sub-frames
        self.gen_product_feature_frame()
        self.gen_product_feature_table()

        # Show main window
        self.setWindowTitle('View product-feature relationship')
        self.resize(1000, 520)
        common_pyqt5.center_window(self)

    def gen_product_feature_frame(self):
        """
        Gnerate self.product_feature_frame.
        """
        # Product-Feature File
        file_label = QLabel('File', self.product_feature_frame)
        file_label.setStyleSheet('font-weight: bold;')
        file_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.product_feature_file_line = QLineEdit()

        if self.input_file:
            self.product_feature_file_line.setText(self.input_file)

        # Vendor
        vendor_label = QLabel('Vendor', self.product_feature_frame)
        vendor_label.setStyleSheet('font-weight: bold;')
        vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.vendor_combo = QComboBox(self.product_feature_frame)
        self.set_vendor_combo()
        self.vendor_combo.activated.connect(self.gen_product_feature_table)

        # Product
        product_label = QLabel('Product', self.product_feature_frame)
        product_label.setStyleSheet('font-weight: bold;')
        product_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.product_line = QLineEdit()
        self.product_line.returnPressed.connect(self.gen_product_feature_table)

        # Feature
        feature_label = QLabel('Feature', self.product_feature_frame)
        feature_label.setStyleSheet('font-weight: bold;')
        feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.feature_line = QLineEdit()
        self.feature_line.returnPressed.connect(self.gen_product_feature_table)

        # Check
        check_button = QPushButton('Check', self.product_feature_frame)
        check_button.clicked.connect(self.gen_product_feature_table)

        # self.product_feature_frame - Grid
        product_feature_frame_grid = QGridLayout()

        product_feature_frame_grid.addWidget(file_label, 0, 0)
        product_feature_frame_grid.addWidget(self.product_feature_file_line, 0, 1, 1, 6)
        product_feature_frame_grid.addWidget(vendor_label, 1, 0)
        product_feature_frame_grid.addWidget(self.vendor_combo, 1, 1)
        product_feature_frame_grid.addWidget(product_label, 1, 2)
        product_feature_frame_grid.addWidget(self.product_line, 1, 3)
        product_feature_frame_grid.addWidget(feature_label, 1, 4)
        product_feature_frame_grid.addWidget(self.feature_line, 1, 5)
        product_feature_frame_grid.addWidget(check_button, 1, 6)

        product_feature_frame_grid.setColumnStretch(1, 1)
        product_feature_frame_grid.setColumnStretch(2, 1)
        product_feature_frame_grid.setColumnStretch(3, 1)
        product_feature_frame_grid.setColumnStretch(4, 1)
        product_feature_frame_grid.setColumnStretch(5, 1)
        product_feature_frame_grid.setColumnStretch(6, 1)

        self.product_feature_frame.setLayout(product_feature_frame_grid)

    def set_vendor_combo(self):
        """
        Set (initilize) self.vendor_combo.
        """
        self.vendor_combo.clear()
        self.vendor_combo.addItem('ALL')

        for vendor in self.product_feature_dic.keys():
            self.vendor_combo.addItem(vendor)

    def gen_product_feature_table(self):
        """
        Gnerate self.product_feature_table.
        """
        # Get filtered_product_feature_relationship_dic.
        (filtered_product_feature_relationship_dic, row_count) = self.filter_product_feature_relationship()

        # Generate self.product_feature_table.
        self.product_feature_table.setShowGrid(True)
        self.product_feature_table.setSortingEnabled(True)
        self.product_feature_table.setColumnCount(3)
        self.product_feature_table_title_list = ['Vendor', 'product', 'feature']
        self.product_feature_table.setHorizontalHeaderLabels(self.product_feature_table_title_list)

        self.product_feature_table.setColumnWidth(0, 120)
        self.product_feature_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.product_feature_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        # File self.product_feature_table.
        self.product_feature_table.setRowCount(row_count)

        row = -1

        for vendor in filtered_product_feature_relationship_dic.keys():
            for product in filtered_product_feature_relationship_dic[vendor].keys():
                for feature in filtered_product_feature_relationship_dic[vendor][product]:
                    row += 1

                    # For vendor
                    item = QTableWidgetItem()
                    item.setText(vendor)
                    self.product_feature_table.setItem(row, 0, item)

                    # For product
                    item = QTableWidgetItem()
                    item.setText(product)
                    self.product_feature_table.setItem(row, 1, item)

                    # For feature
                    item = QTableWidgetItem()
                    item.setText(feature)
                    self.product_feature_table.setItem(row, 2, item)

    def filter_product_feature_relationship(self):
        """
        Filter self.product_feature_dic with specified vendor/product/feature.
        """
        specified_vendor = self.vendor_combo.currentText().strip()
        specified_product = self.product_line.text().strip()
        specified_feature = self.feature_line.text().strip()
        filtered_product_feature_relationship_dic = {}
        row_count = 0

        # Cannot specify product and feature the same time, will empty product if feature is specified.
        if specified_product and specified_feature:
            specified_product = ''

        # Get full product/feature list.
        full_product_list = []
        full_feature_list = []

        for vendor in self.product_feature_dic.keys():
            if (specified_vendor == 'ALL') or (vendor == specified_vendor):
                for product in self.product_feature_dic[vendor].keys():
                    if product not in full_product_list:
                        full_product_list.append(product)

                    for feature in self.product_feature_dic[vendor][product]:
                        if feature not in full_feature_list:
                            full_feature_list.append(feature)

                        # Get all product/feature information without specified_product and specified_feature.
                        if (not specified_product) and (not specified_feature):
                            filtered_product_feature_relationship_dic.setdefault(vendor, {})
                            filtered_product_feature_relationship_dic[vendor].setdefault(product, [])
                            filtered_product_feature_relationship_dic[vendor][product].append(feature)
                            row_count += 1

        if specified_product or specified_feature:
            filtered_product_feature_relationship_dic = {}
            row_count = 0

            # Get fuzzy_mode for product/feature.
            product_fuzzy = True
            feature_fuzzy = True

            if specified_product and (specified_product in full_product_list):
                product_fuzzy = False

            if specified_feature and (specified_feature in full_feature_list):
                feature_fuzzy = False

            # Filter with product/feature.
            for vendor in self.product_feature_dic.keys():
                if (specified_vendor == 'ALL') or (vendor == specified_vendor):
                    for product in self.product_feature_dic[vendor].keys():
                        if (not specified_product) or ((product_fuzzy and re.search(specified_product.lower(), product.lower())) or ((not product_fuzzy) and (product == specified_product))):
                            for feature in self.product_feature_dic[vendor][product]:
                                if (not specified_feature) or ((feature_fuzzy and re.search(specified_feature.lower(), feature.lower())) or ((not feature_fuzzy) and (feature == specified_feature))):
                                    filtered_product_feature_relationship_dic.setdefault(vendor, {})
                                    filtered_product_feature_relationship_dic[vendor].setdefault(product, [])
                                    filtered_product_feature_relationship_dic[vendor][product].append(feature)
                                    row_count += 1

        return (filtered_product_feature_relationship_dic, row_count)


################
# Main Process #
################
def main():
    (input_file) = read_args()
    app = QApplication(sys.argv)
    mw = MainWindow(input_file)
    mw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
