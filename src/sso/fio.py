import os
from datetime import datetime
from sso.ssh import SSH
from sso.util import run_parallel


class Fio:

    def __init__(self, ips, ssh_user, ssh_options, capture_lsblk=True):
        self.ips = ips
        self.ssh_user = ssh_user
        self.ssh_options = ssh_options
        self.dir_name = "fio-" + datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        self.capture_lsblk = capture_lsblk

    def __new_ssh(self, ip):
        return SSH(ip, self.ssh_user, self.ssh_options)

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
            ssh.exec(f'lsblk > lsblk.out')

        ssh.exec(f'mkdir -p {self.dir_name}')
        ssh.exec(f'cd {self.dir_name} && sudo fio {options}')
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
        ssh = self.__new_ssh(ip)
        ssh.scp_from_remote(f'{self.dir_name}/*', dest_dir)
        if self.capture_lsblk:
            self.__new_ssh(ip).scp_from_remote(f'lsblk.out', dest_dir)

        print(f'    [{ip}] Downloading to [{dest_dir}] done')

    def download(self, dir):
        print("============== FIO Download: started ===========================")
        run_parallel(self.__download, [(ip, dir) for ip in self.ips])
        print("============== FIO Download: done ===========================")

