import subprocess
import xlwt
import paramiko
import getpass
import socket


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
                if column_width > 65536:
                    column_width = 65536
                else:
                    worksheet.col(column).width = column_width

    # save excel
    workbook.save(excel_file)


def ssh_client(host_name='', port=22, user_name='', password='', command='', reconnect=False, timeout=10):
    """
    Ssh specified host, execute specified command, get stdout informaiton (return stdout_list).
    """
    stdout_list = []
    client = paramiko.SSHClient()

    try:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host_name, port, user_name, password=password, timeout=timeout)

        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        result = stdout.read().decode()
        stdout_list = str(result).splitlines()

        if exit_status == 1:
            print_error('*Error*: ssh connection is failed.')
    except paramiko.AuthenticationException:
        print_error('*Error*: authentication failed.')
    except paramiko.SSHException as ssh_ex:
        print_error('*Error*: ssh connection error: ' + str(ssh_ex))
    except socket.error as socket_error:
        if not reconnect:
            print_warning('*Warning*: ssh fail.')

            password = getpass.getpass('            Please input password:')
            ssh_client(host_name=host_name, port=22, user_name=user_name, password=password, command=command, reconnect=True)
        else:
            print_error('*Error*: Socket error： ' + str(socket_error))
    except Exception as error:
        print_error('*Error*: Meet below error when ssh ' + str(host_name))
        print_error('         ' + str(error))
    finally:
        client.close()

    return stdout_list
