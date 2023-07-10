import subprocess
import xlwt


def print_error(message):
    """
    Print error message with red color.
    """
    print('\033[1;31m' + str(message) + '\033[0m')


def print_warning(message):
    """
    Print warning message with yellow color.
    """
    print('\033[1;33m' + str(message) + '\033[0m')


def run_command(command, mystdin=subprocess.PIPE, mystdout=subprocess.PIPE, mystderr=subprocess.PIPE):
    """
    Run system command with subprocess.Popen, get returncode/stdout/stderr.
    """
    SP = subprocess.Popen(command, shell=True, stdin=mystdin, stdout=mystdout, stderr=mystderr)
    (stdout, stderr) = SP.communicate()

    return (SP.returncode, stdout, stderr)


def write_excel(excel_file, contents_list, specified_sheet_name='default'):
    """
    Open Excel for write.
    Input contents_list is a 2-dimentional list.

    contents_list = [
                     row_1_list,
                     row_2_list,
                     ...
                    ]
    """
    workbook = xlwt.Workbook(encoding='utf-8')

    # create worksheet
    worksheet = workbook.add_sheet(specified_sheet_name)

    # Set title style
    title_style = xlwt.XFStyle()
    font = xlwt.Font()
    font.bold = True
    title_style.font = font

    # write excel
    for (row, content_list) in enumerate(contents_list):
        for (column, content_string) in enumerate(content_list):
            if row == 0:
                worksheet.write(row, column, content_string, title_style)
            else:
                worksheet.write(row, column, content_string)

            # auto-width
            column_width = len(str(content_string)) * 256

            if column_width > worksheet.col(column).width:
                worksheet.col(column).width = column_width

    # save excel
    workbook.save(excel_file)
