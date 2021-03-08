# !/bin/python3

import os
import subprocess
import yaml
import glob
import csv
import time
from datetime import datetime
from threading import Thread


def load_yaml(path):
    with open(path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


class Iteration:
    
    def __init__(self, trial_name, description=None):
        self.trials_dir_name = "trials"
        self.trials_dir = os.path.join(os.getcwd(), self.trials_dir_name)
        self.trial_name = trial_name
        self.trial_dir = os.path.join(self.trials_dir, trial_name)

        self.name = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        self.dir = os.path.join(self.trial_dir, self.name)

        os.makedirs(self.dir)

        if description:
            desc_file = os.path.join(self.dir, "description.txt")
            with open(desc_file, "w") as text_file:
                print(description, file=text_file)

        latest_dir = os.path.join(self.trial_dir, "latest")
        if os.path.isdir(latest_dir):
            os.unlink(latest_dir)
        elif os.path.islink(latest_dir):    
            #it is a broken sym link, so lets remove it.
            os.remove(latest_dir)
        os.symlink(self.dir, latest_dir, target_is_directory=True)
        print(f'Using iteration directory [{self.dir}]')


class HdrLogMerging:
    
    def __init__(self, properties):
        self.properties = properties        

    # def __log_merging(self, files):

    def merge_logs(self, dir):
        print("------------------ HdrLogMerging -------------------------------------")
        print(dir)
        # todo be careful with merging the merge file.
        files_map = {}

        for hdr_file in glob.iglob(dir + '/*/*.hdr', recursive=True):
            print(hdr_file)
            base = os.path.splitext(os.path.basename(hdr_file))[0]
            files = files_map.get(base)
            if files is None:
                files = []
                files_map[base] = files
            files.append(hdr_file)

        lib_dir=f"{os.environ['SSO']}/lib/"    
        cwd = os.getcwd()
        jvm_path = self.properties['jvm_path']
        for name, files in files_map.items():
            input = ""
            for file in files:
                input = input + " -ifp " + file
            cmd = f'{jvm_path}/bin/java -cp {lib_dir}/processor.jar CommandDispatcherMain union {input} -of {dir}/{name}.hdr'
            print(cmd)
            os.system(cmd)

        print("------------------ HdrLogMerging -------------------------------------")


class HdrLogProcessor:
    
    def __init__(self, properties):
        self.properties = properties

    def process(self, dir):
        print("process " + str(dir))
        for hdr_file in glob.iglob(dir + '/**/*.hdr', recursive=True):
            print(hdr_file)
            self.__process(hdr_file)

    def __process(self, file):
        print("------------------ HdrLogProcessor -------------------------------------")
        filename = os.path.basename(file)
        filename_no_ext = os.path.splitext(filename)[0]
        jvm_path = self.properties['jvm_path']
        old_cwd = os.getcwd()
        new_cwd = os.path.dirname(os.path.realpath(file))
        os.chdir(new_cwd)


        tags = set()
        with open(filename, "r") as hdr_file:
            reader = csv.reader(hdr_file, delimiter=',')
            # Skip headers
            for i in range(5):
                next(reader, None)
            for row in reader:
                first_column = row[0]
                tag = first_column[4:]
                tags.add(tag)

        lib_dir=f"{os.environ['SSO']}/lib/"
        print("lib dir = "+lib_dir)
        for tag in tags:
            os.system(
                f'{jvm_path}/bin/java -cp {lib_dir}/HdrHistogram-2.1.9.jar org.HdrHistogram.HistogramLogProcessor -i {filename} -o {filename_no_ext + "_" + tag} -csv -tag {tag}')

        os.system(
            f'{jvm_path}/bin/java -cp {lib_dir}/processor.jar CommandDispatcherMain summarize -if {filename_no_ext}.hdr >  {filename_no_ext}-summary.txt')

        os.chdir(old_cwd)
        print("------------------ HdrLogProcessor -------------------------------------")


def run_parallel(t, args_list):
    threads = []
    for a in args_list:
        thread = Thread(target=t, args=a)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
   

class Ssh:

    def __init__(self, ip, user, ssh_options, wait_for_connect=True, silent_seconds=30):
        self.ip = ip
        self.user = user
        self.ssh_options = ssh_options
        self.wait_for_connect = wait_for_connect 
        self.silent_seconds = silent_seconds
        self.log_ssh = False

    def __wait_for_connect(self):
        if not self.wait_for_connect:
            return
        
        cmd = f'ssh {self.ssh_options} {self.user}@{self.ip} ls'
        for i in range(1, 300):
            if i > self.silent_seconds:
                print(f"[{i}] Connect to {self.ip}")
                exitcode = subprocess.call(cmd, shell=True)
            else:                
                exitcode = subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
            if exitcode == 0 or exitcode == 1: # todo: we need to deal better with exit code
                self.wait_for_connect = False
                return
            time.sleep(1)

        raise Exception(f"Failed to connect to {self.ip}, exitcode={exitcode}")
    

    def scp_from_remote(self, src, dst):
        cmd = f'scp {self.ssh_options} -q {self.user}@{self.ip}:{src} {dst}'
        self.__scp(cmd)

    def scp_to_remote(self, src, dst):
        cmd = f'scp {self.ssh_options} -q {src} {self.user}@{self.ip}:{dst}'
        self.__scp(cmd)
                
    def __scp(self, cmd):
        self.__wait_for_connect()
        # we need to retry under certain conditions
        #for attempt in range(1, self.max_attempts):
        #    if self.log_ssh or attempt > 1:
        #        print(f'[{attempt}] {cmd}')
        exitcode = subprocess.call(cmd, shell=True)
        #    if exitcode == 0:
        #        return
        #    elif exitcode in [4, 65, 255]:            
        #        # 4 is connection failed
        #        # 65 is host not allowed to connect.
        #        time.sleep(5)
        #        continue
        #    else:
        #        raise Exception(f"Failed to execute {cmd}, exitcode={exitcode}")
        #    
        #raise Exception(f"Failed to execute {cmd} after {self.max_attempts} attempts")
                        
    def run(self, command):
        self.__wait_for_connect()
        
        
        
        cmd = f'ssh {self.ssh_options} {self.user}@{self.ip} \'{command}\''
        
        # we need to retry under certain conditions
        exitcode = subprocess.call(cmd, shell=True)
        if exitcode == 0 or exitcode == 1: # todo: we need to deal better with exit code
            return
        else:
            raise Exception(f"Failed to execute {cmd}, exitcode={exitcode}")
            
    def update(self):
        print(f'    [{self.ip}] Update: started')
        self.run(
            f"""if hash apt-get 2>/dev/null; then
                sudo apt-get -y -qq update
            elif hash yum 2>/dev/null; then
                sudo yum -y -q update
            else
                echo "Cannot update: yum/apt not found"
                exit 1
            fi""")
        print(f'    [{self.ip}] Update: done')

    def install_one(self, package_list):
         self.run(
            f"""set -e
                for package in {" ".join(package_list)} 
                do                
                    echo Trying package [$package]
                    if hash apt-get 2>/dev/null ; then
                        if sudo apt show $package >/dev/null 2>&1; then
                            echo Installing $package
                            sudo apt-get install -y -qq $package
                            exit 0
                        fi    
                     elif hash yum 2>/dev/null; then
                        if sudo yum list --available $package >/dev/null 2>&1; then
                            echo Installing $package
                            sudo yum -y -q install $package
                            exit 0
                        fi                        
                    else
                        echo "Cannot install $package: yum/apt not found"
                        exit 1
                    fi
                    
                    echo Not found $package                       
                done
                echo "Could not find any of the packages from {package_list}"
                exit 1
                """)
         
    def install(self, package):
        print(f'    [{self.ip}] Install: {package}')
        self.run(
            f"""if hash apt-get 2>/dev/null; then
                sudo apt-get install -y -qq {package}
            elif hash yum 2>/dev/null; then
                sudo yum -y -q install {package}
            elif hash dnf 2>/dev/null; then
                sudo dnf -y -q install {package}
            else
                echo "Cannot install {package}: yum/apt not found"
                exit 1
            fi""")


def __collect_ec2_metadata(ip, ssh_user, ssh_options, dir):
    dest_dir = os.path.join(dir, ip)
    os.makedirs(dest_dir, exist_ok=True)
  
    ssh = Ssh(ip, ssh_user, ssh_options)
    ssh.update()
    # https://stackoverflow.com/questions/35824356/how-collect-metadata-os-info-about-ec2-instance-to-file
    ssh.install("curl")
    ssh.run("curl http://169.254.169.254/latest/dynamic/instance-identity/document > metadata.txt")
    ssh.scp_from_remote("metadata.txt", dest_dir)


def collect_ec2_metadata(ips, ssh_user, ssh_options, dir):
    run_parallel(__collect_ec2_metadata, [(ip, ssh_user, ssh_options, dir) for ip in ips])


class DiskExplorer:

    def __init__(self, ips, ssh_user, ssh_options, capture_lsblk = True):
        self.ips = ips
        self.ssh_user = ssh_user
        self.ssh_options = ssh_options
        self.capture_lsblk = capture_lsblk

    def __new_ssh(self, ip):
        return Ssh(ip, self.ssh_user, self.ssh_options)

    def __install(self, ip):
        print(f'    [{ip}] Instaling disk-explorer: started')
        ssh = self.__new_ssh(ip)
        ssh.update()
        ssh.install('git')
        ssh.install('fio')
        ssh.install('python3')
        ssh.install('python3-pip')
        #ssh.install_one(['python3-matplotlib','python-matplotlib'])
        ssh.run("sudo pip3 install -qqq matplotlib")
        ssh.run(f'rm -fr diskplorer')
        ssh.run(f'git clone -q https://github.com/scylladb/diskplorer.git')
        print(f'    [{ip}] Instaling disk-explorer: done')

    def install(self):
        print("============== Disk Explorer Installation: started =================")
        run_parallel(self.__install, [(ip,) for ip in self.ips])
        print("============== Disk Explorer Installation: done =================")

    def __run(self, ip, cmd):
        print(f'    [{ip}] Run: started')
        ssh = self.__new_ssh(ip)
        ssh.run('rm -fr diskplorer/*.svg')
        ssh.run(f'rm -fr diskplorer/fiotest.tmp')
        if self.capture_lsblk:
            ssh.run(f'lsblk > lsblk.out')
        ssh.run(f'cd diskplorer && python3 diskplorer.py {cmd}')
        # the file is 100 GB; so we want to remove it.
        ssh.run(f'rm -fr diskplorer/fiotest.tmp')
        print(f'    [{ip}] Run: done')

    def run(self, command):
        print(f'============== Disk Explorer run: started [{datetime.now().strftime("%H:%M:%S")}]===========================')
        print(f"python3 diskplorer.py {command}")
        run_parallel(self.__run, [(ip, command) for ip in self.ips])
        print(f'============== Disk Explorer run: done [{datetime.now().strftime("%H:%M:%S")}] ===========================')

    def __download(self, ip, dir):
        dest_dir = os.path.join(dir, ip)
        os.makedirs(dest_dir, exist_ok=True)

        print(f'    [{ip}] Downloading to [{dest_dir}]')
        self.__new_ssh(ip).scp_from_remote(f'diskplorer/*.{{svg,csv}}', dest_dir)
        if self.capture_lsblk:
            self.__new_ssh(ip).scp_from_remote(f'lsblk.out', dest_dir)
        print(f'    [{ip}] Downloading to [{dest_dir}] done')

    def download(self, dir):
        print("============== Disk Explorer Download: started ===========================")
        run_parallel(self.__download, [(ip, dir) for ip in self.ips])
        print("============== Disk Explorer Download: done ===========================")


class Fio:

    def __init__(self, ips, ssh_user, ssh_options, capture_lsblk = True):
        self.ips = ips
        self.ssh_user = ssh_user
        self.ssh_options = ssh_options
        self.dir_name = "fio-"+datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        self.capture_lsblk = capture_lsblk
     
    def __new_ssh(self, ip):
        return Ssh(ip, self.ssh_user, self.ssh_options)

    def __upload(self, ip, file):
        self.__new_ssh(ip).scp_to_remote(file, self.dir_name)

    def upload(self, file):
        print("============== Upload: started ===========================")
        run_parallel(self.__upload, [(ip, file) for ip in self.ips])
        print("============== Upload-Stress: done ==============================")

    def __install(self, ip):
        print(f'    [{ip}] Instaling fio: started')
        ssh = self.__new_ssh(ip)
        ssh.update()
        ssh.install('fio')
        print(f'    [{ip}] Instaling fio: done')

    def install(self):
        print("============== fio Installation: started =================")
        run_parallel(self.__install, [(ip,) for ip in self.ips])
        print("============== fio Installation: done =================")

    def __run(self, ip, options):
        print(f'    [{ip}] fio: started')
        ssh = self.__new_ssh(ip)        
        if self.capture_lsblk:
            ssh.run(f'lsblk > lsblk.out')
  
        ssh.run(f'mkdir -p {self.dir_name}')
        ssh.run(f'cd {self.dir_name} && sudo fio {options}')        
        print(f'    [{ip}] fio: done')

    def run(self, options):
        print("============== fio run: started ===========================")
        print(f"sudo fio {options}")
        run_parallel(self.__run, [(ip, options) for ip in self.ips])
        print("============== fio run: done ===========================")

    def __download(self, ip, dir):
        dest_dir = os.path.join(dir, ip)
        os.makedirs(dest_dir, exist_ok=True)

        print(f'    [{ip}] Downloading to [{dest_dir}]')
        ssh = __new_ssh(ip) 
        ssh.scp_from_remote(f'{self.dir_name}/*', dest_dir)
        if self.capture_lsblk:
            self.__new_ssh(ip).scp_from_remote(f'lsblk.out', dest_dir)
  
        print(f'    [{ip}] Downloading to [{dest_dir}] done')

    def download(self, dir):
        print("============== FIO Download: started ===========================")
        run_parallel(self.__download, [(ip, dir) for ip in self.ips])
        print("============== FIO Download: done ===========================")


class CassandraStress:

    def __init__(self, ips, properties):
        self.properties = properties
        self.ips = ips
        self.cassandra_version = properties['cassandra_version']
        self.ssh_user = properties['load_generator_user']

    def new_ssh(self, ip):
        return Ssh(ip, self.ssh_user, self.properties['ssh_options'])

    def __install(self, ip):
        print(f'    [{ip}] Instaling cassandra-stress: started')
        ssh = self.new_ssh(ip)
        ssh.update()
        ssh.install_one(['openjdk-8-jdk','java-1.8.0-openjdk'])
        ssh.install('wget')
        ssh.run(
            f'wget -q -N https://mirrors.netix.net/apache/cassandra/{self.cassandra_version}/apache-cassandra-{self.cassandra_version}-bin.tar.gz')
        ssh.run(f'tar -xzf apache-cassandra-{self.cassandra_version}-bin.tar.gz')
        print(f'    [{ip}] Instaling cassandra-stress: done')

    def install(self):
        print("============== Instaling Cassandra-Stress: started =================")
        run_parallel(self.__install, [(ip,) for ip in self.ips])
        print("============== Instaling Cassandra-Stress: done =================")

    def __stress(self, ip, cmd):
        print(cmd)
        cassandra_stress_dir = f'apache-cassandra-{self.cassandra_version}/tools/bin'
        full_cmd = f'{cassandra_stress_dir}/cassandra-stress {cmd}'
        self.new_ssh(ip).run(full_cmd)

    def stress(self, command):
        print("============== Cassandra-Stress: started ===========================")
        run_parallel(self.__stress, [(ip, command) for ip in self.ips])
        print("============== Cassandra-Stress: done ==============================")

    def __ssh(self, ip, command):
        self.new_ssh(ip).run(command)

    def ssh(self, command):
        run_parallel(self.__ssh, [(ip, command) for ip in self.ips])

    def __upload(self, ip, file):
        self.new_ssh(ip).scp_to_remote(file, "")

    def upload(self, file):
        print("============== Upload: started ===========================")
        run_parallel(self.__upload, [(ip, file) for ip in self.ips])
        print("============== Upload-Stress: done ==============================")

    def __download(self, ip, dir):
        dest_dir = os.path.join(dir, ip)
        os.makedirs(dest_dir, exist_ok=True)
        print(f'    [{ip}] Downloading to [{dest_dir}]')
        self.new_ssh(ip).scp_from_remote(f'*.{{html,hdr}}', dest_dir)
        print(f'    [{ip}] Downloading to [{dest_dir}] done')

    def get_results(self, dir):
        print("============== Getting results: started ===========================")
        run_parallel(self.__download, [(ip, dir) for ip in self.ips])
        HdrLogMerging(self.properties).merge_logs(dir)
        HdrLogProcessor(self.properties).process(dir)
        print("============== Getting results: done ==============================")

    def __prepare(self, ip):
        print(f'    [{ip}] Preparing: started')
        ssh = self.new_ssh(ip)
        ssh.run(f'rm -fr *.html *.hdr')
        # we need to make sure that the no old load generator is still running.
        ssh.run(f'killall -q -9 java')
        print(f'    [{ip}] Preparing: done')

    def prepare(self):
        print('============== Preparing load generator: started ===================')
        run_parallel(self.__prepare, [(ip,) for ip in self.ips])
        print('============== Preparing load generator: done ======================')