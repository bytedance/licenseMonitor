# -*- coding: utf-8 -*-
import os
import re
import sys
import copy
import datetime
import argparse

sys.path.append(os.environ['LICENSE_MONITOR_INSTALL_PATH'])
from common import common
from common import common_lsf

os.environ['PYTHONUNBUFFERED'] = '1'
CURRENT_TIME = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--project_execute_host_file',
                        default='',
                        help='Specify original project execute host file.')
    parser.add_argument('-o', '--output_file',
                        default='./project_execute_host.' + str(CURRENT_TIME),
                        help='Output file, default is "./project_execute_host.<CURRENT_TIME>".')

    args = parser.parse_args()

    # Check original args.project_execute_host_file exists or not.
    if args.project_execute_host_file and (not os.path.exists(args.project_execute_host_file)):
        common.bprint('"' + str(args.project_execute_host_file) + '": No such file.', level='Error')
        sys.exit(1)

    return args.project_execute_host_file, args.output_file


class UpdateProjectExecuteHostWithLsf():
    """
    On LSF, if the queue name is "<project>" or "<project>_.*", you can get project information from LSF queue.
    Then you can get project-execute_host information from LSF queue-host information.
    """
    def __init__(self, orig_project_execute_host_file, output_file):
        self.orig_project_execute_host_file = orig_project_execute_host_file
        self.output_file = output_file
        self.project_list = self.get_project_list()

    def get_project_list(self):
        """
        Get project list information from config/project/project_list file.
        """
        project_list = []
        project_list_file = str(os.environ['LICENSE_MONITOR_INSTALL_PATH']) + '/config/project/project_list'

        print('>>> Get project list from "' + str(project_list_file) + '"')

        if os.path.exists(project_list_file):
            with open(project_list_file, 'r') as PLF:
                for line in PLF.readlines():
                    line = line.strip()

                    if re.match(r'^\s*#.*$', line) or re.match(r'^\s*$', line):
                        continue
                    else:
                        project_list.append(line)

        return project_list

    def get_queue_project_info(self, queue):
        """
        If the queue is "<project>" or "<project>_.*" or "<project>-.*", then the queue is for project <project>.
        """
        print('    * Get project information for LSF queue "' + str(queue) + '"')

        queue_project_list = []

        for project in self.project_list:
            if project == queue:
                queue_project_list.append(project)
                break
            elif re.match(r'^' + str(project) + '_.*$', queue) or re.match(r'^' + str(project) + '-.*$', queue):
                queue_project_list.append(project)

        if not queue_project_list:
            return ''
        elif len(queue_project_list) == 1:
            return queue_project_list[0]
        else:
            # If catch several posible projects, choice the shortest one.
            return max(queue_project_list, key=len)

    def get_queue_project_relationship(self, queue_list):
        """
        Get queue_project_dic, which save queue-project relationship.
        """
        print('>>> Get project information for LSF queue(s)')

        queue_project_dic = {}

        for queue in queue_list:
            queue_project = self.get_queue_project_info(queue)

            if queue_project:
                queue_project_dic[queue] = queue_project

        return queue_project_dic

    def get_project_execute_host_info(self, queue_project_dic, host_queue_dic):
        """
        Get execute_host-project information from queue-host information.
        """
        print('>>> Get execute_host - project relationship from queue-host information')

        project_execute_host_dic = {}

        for host in host_queue_dic.keys():
            host_project_list = []

            for host_queue in host_queue_dic[host]:
                if host_queue in queue_project_dic:
                    queue_project = queue_project_dic[host_queue]

                    if queue_project not in host_project_list:
                        host_project_list.append(queue_project)

            if host_project_list:
                project_execute_host_dic.setdefault(host, {})

                for i, host_project in enumerate(host_project_list):
                    if i != len(host_project_list) - 1:
                        project_execute_host_dic[host][host_project] = round(1 / len(host_project_list), 3)
                    else:
                        project_execute_host_dic[host][host_project] = round(1 - (len(host_project_list) - 1) * round(1 / len(host_project_list), 3), 3)

        return project_execute_host_dic

    def write_output_file(self, project_execute_host_dic):
        """
        Write project_execute_host_dic into self.output_file with text format.
        """
        # Write output_file with relationship_dic.
        if project_execute_host_dic:
            print('')
            print('>>> Write output file "' + str(self.output_file) + '".')

            with open(self.output_file, 'w', encoding='utf-8') as OF:
                for execute_host in project_execute_host_dic.keys():
                    output_string = str(execute_host) + ' :'

                    for project in project_execute_host_dic[execute_host].keys():
                        if len(project_execute_host_dic[execute_host]) == 1:
                            output_string = str(output_string) + ' ' + str(project)
                        else:
                            output_string = str(output_string) + ' ' + str(project) + '(' + str(project_execute_host_dic[execute_host][project]) + ')'

                    OF.write(str(output_string) + '\n')

            os.chmod(self.output_file, 0o777)

    def run(self):
        """
        Main function if class UpdateProjectExecuteHostWithLsf.
        """
        # Get all LSF queues.
        queue_list = common_lsf.get_queue_list()

        if not queue_list:
            common.bprint('Not find any LSF queue information.', level='Error')
            sys.exit(1)

        # Get queue-project relationship.
        queue_project_dic = self.get_queue_project_relationship(queue_list)

        if not queue_project_dic:
            common.bprint('Not find any valid queue-project relationship.', level='Error')
            sys.exit(1)

        # Get execute_host-project relationship.
        host_queue_dic = common_lsf.get_host_queue_info()

        if not host_queue_dic:
            common.bprint('Not find any valid LSF host-queue relationship.', level='Error')
            sys.exit(1)

        project_execute_host_dic = self.get_project_execute_host_info(queue_project_dic, host_queue_dic)

        if not project_execute_host_dic:
            common.bprint('Not find any valid execute_host-project relationship.', level='Error')
            sys.exit(1)

        # Get origianl execute_host-project relationship.
        orig_project_execute_host_dic = common.parse_project_proportion_file(self.orig_project_execute_host_file)

        # Replace orig_project_execute_host_dic with project_execute_host_dic.
        new_project_execute_host_dic = copy.deepcopy(project_execute_host_dic)

        if orig_project_execute_host_dic:
            new_project_execute_host_dic = copy.deepcopy(orig_project_execute_host_dic)

            for execute_host in project_execute_host_dic.keys():
                new_project_execute_host_dic[execute_host] = project_execute_host_dic[execute_host]

        # Write output file.
        self.write_output_file(new_project_execute_host_dic)


################
# Main Process #
################
def main():
    (project_execute_host_file, output_file) = read_args()
    my_update_project_execute_host_with_lsf = UpdateProjectExecuteHostWithLsf(project_execute_host_file, output_file)
    my_update_project_execute_host_with_lsf.run()


if __name__ == '__main__':
    main()
