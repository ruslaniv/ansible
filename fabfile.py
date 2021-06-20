import os

from fabric import Connection, config
import re
import io

import get_vars

root_user = get_vars.read_group_vars().get("root_user")
root_user_pwd = get_vars.read_group_vars().get("root_user_pwd")

remote_user = get_vars.read_group_vars().get("remote_user")
remote_user_group = get_vars.read_group_vars().get("remote_user_group")
remote_user_pwd = get_vars.read_group_vars().get("ansible_sudo_pass")

ssh_key_filename = get_vars.read_group_vars().get("ssh_key_filename")
ssh_port = get_vars.read_group_vars().get("ansible_port")

hosts = get_vars.read_hosts()


def get_ssh_connection(host, passwd, port=22, user='root', hide=True, verbose=False):
    """Establish SSH connection with the remote host

    Parameters
    ----------
    host
    passwd
    port
    user
    hide
    verbose

    Returns
    -------

    """
    if verbose: print(f'Establishing SSH connection under {user} user...')
    return Connection(
        host=host,
        port=port,
        user=user,
        connect_kwargs={
            "password": passwd,
        },
        config=config.Config(overrides={"run": {"hide": hide}}),
    )


def create_ssh_keys(c, verbose=False):
    if verbose: print(f'Getting ready to create SSH keys...')
    local_user_home = c.local('eval echo "~$USER"')
    keys, keys_path = os.path.join(str(local_user_home.stdout).rstrip(), '.ssh', ssh_key_filename), os.path.join(str(local_user_home.stdout).rstrip(), '.ssh')
    if os.path.exists(keys) and os.path.exists(keys + '.pub'):
        if verbose: print(f'Private key file \"{ssh_key_filename}\" and public key file \"{ssh_key_filename}.pub\" exist at \"{keys_path}\"')
        public_key = keys + '.pub'
        return public_key
    else:
        if verbose: print(f'Creating SSH keys...')
        c.local(f'ssh-keygen -t rsa -b 4096 -f {keys} -q -N ""')
        public_key = keys + '.pub'
        return public_key


def update_known_hosts(c, host, new_port=False, verbose=False):
    if verbose: print(f'Getting ready to update known_hosts file...')
    local_user_home = c.local('eval echo "~$USER"')
    known_hosts = os.path.join(str(local_user_home.stdout).rstrip(), '.ssh/known_hosts')
    f = open(f'{known_hosts}')
    data = f.read()
    if not new_port:
        pattern = re.compile(fr'({host}\s)')
        result = pattern.search(data).group() if pattern.search(data) else None
        if result:
            if verbose:
                print(f'Host {host} already in the known_host file:')
                pattern = re.compile(fr'({host}.+)')
                result = pattern.search(data).group()
                print(result[:96])
            return
        else:
            if verbose: print(f'Updating known_hosts file...')
            c.local(f'ssh-keyscan -t rsa {host} >> {known_hosts}')
    else:
        pattern = re.compile(fr'(\[{host}\]:{ssh_port})')
        result = pattern.search(data).group() if pattern.search(data) else None
        if result:
            if verbose:
                print(f'Host [{host}]:{ssh_port} already in the known_host file:')
                pattern = re.compile(fr'(\[{host}\]:{ssh_port}).+')
                result = pattern.search(data).group()
                print(result[:96])
            return
        else:
            if verbose: print(f'Updating known_hosts file...')
            c.local(f'ssh-keyscan -p {ssh_port} -t \'rsa\' {host} >> ~/.ssh/known_hosts')


def create_remote_user(c, verbose=False):
    if verbose: print(f'Getting ready to create remote user and user group...')
    result = c.run(f'getent group {remote_user_group}', warn=True)
    if result.return_code == 0:
        if verbose: print(f'The group "{remote_user_group}" already exists in the system')
    else:
        if verbose: print(f'Creating remote user group...')
        c.run(f'groupadd {remote_user_group}')

    result = c.run(f'id -u {remote_user}', warn=True)
    if result.return_code == 0:
        if verbose: print(f'The user "{remote_user}" already exists in the system')
    else:
        if verbose: print(f'Creating remote user...')
        c.run(f'useradd -m -N -g {remote_user_group} {remote_user}')
        c.run(f'echo {remote_user}:{remote_user_pwd} | chpasswd -c SHA512')
        c.run(f'mkdir /home/{remote_user}/.ssh')
        c.run(f'chown -R {remote_user} /home/{remote_user}/.ssh')
        c.run(f'chgrp -R {remote_user_group} /home/{remote_user}/.ssh')


def check_sudoers_file(c, verbose=False):
    if verbose: print("Checking sudoers file for errors...")
    result = c.run(f'visudo -csf /etc/sudoers')
    if result.stdout.strip() == '/etc/sudoers: parsed OK':
        if verbose: print('Sudoers file successfully changed')
    else:
        c.run(f'cp /etc/sudoers.bak /etc/sudoers')
        print('Something went wrong, sudoers file restored')
    if verbose: print("Checking the owner of sudoers file...")
    result = c.run(f'stat --format="%g%u" /etc/sudoers')
    if result.stdout.strip() == '00':
        if verbose: print('The sudoers file is owned by the "root:root"')
    else:
        if verbose: print('Setting user "root:root" as the owner of sudoers file...')
        c.run(f'chown root /etc/sudoers')
    if verbose: print("Checking sudoers file permissions...")
    result = c.run(f'stat --format="%a" /etc/sudoers')
    if result.stdout.strip() == '440':
        if verbose: print("Sudoers files permissions are OK")
    else:
        if verbose: print("Setting sudoers file permission to 440...")
        c.run(f'chmod 440 /etc/sudoers')


def add_remote_user_group_to_sudoers(c, verbose=False):
    if verbose: print(f'Getting ready to change sudoers file...')
    if verbose: print(f'Backing up sudoers file...')
    c.run(f'cp /etc/sudoers /etc/sudoers.bak')
    result = str(c.run(f'cat /etc/sudoers').stdout)
    if f'%{remote_user_group} ALL=(ALL) NOPASSWD: ALL' in result:
        if verbose: print(f'Group {remote_user_group} already in sudoers file')
        return
    result = result + f'%{remote_user_group} ALL=(ALL) NOPASSWD: ALL'
    f = io.StringIO(result)
    c.put(f, remote='/etc/sudoers')
    check_sudoers_file(c, verbose=verbose)
    #Todo run('dnf upgrade -y')


def upload_ssh_key(c, public_key, verbose=False):
    if verbose: print(f'Getting ready to upload public SSH key to remote host...')
    remote_home = str(c.run('pwd').stdout)
    remote_keys = os.path.join(remote_home.rstrip(), '.ssh/authorized_keys')
    result = c.run(f'cat {remote_keys}', warn=True)
    if result.return_code == 1:
        if verbose: print(f'Uploading SSH public key to remote host...')
        c.run(f'touch {remote_keys}')
        c.put(public_key, remote=remote_keys)
        c.run('chmod 700 ~/.ssh')
        c.run('chmod 600 ~/.ssh/authorized_keys')
    if result.return_code == 0:
        result = c.run(f'cat {remote_keys}')
        f = open(f'{public_key}')
        data = f.read()
        if data in result.stdout:
            if verbose: print('The SSH key is already present in the \"authorized_keys\" file')
        else:
            if verbose: print(f'Adding public SSH key to remote host "authorized_keys" file...')
            c.put(public_key, remote=remote_keys)


def change_ssh_port(c, port, verbose=False):
    if verbose: print(f'Getting ready to change SSH port...')
    sshd_config = str(c.run('find / -xdev -name sshd_config 2>/dev/null').stdout).strip()
    if sshd_config == '':
        print('No file "sshd_config" found')
    else:
        if verbose: print(f'Changing SSH port...')
        result = str(c.run(f'cat {sshd_config}').stdout)
        result = result.replace("#Port 22", f'Port {port}')
        f = io.StringIO(result)
        c.put(f, remote=sshd_config)
        if verbose: print('Restarting SSHD service...')
        c.run('systemctl restart sshd')


def update_firewall_rules(c, verbose=False):
    if verbose: print(f'Getting ready to update firewall rule to allow custom SSH port...')
    install_package(c, 'firewalld')
    c.run(f'firewall-cmd --permanent --zone=public --add-port={ssh_port}/tcp')
    c.run('systemctl restart firewalld')


def install_package(c, package, verbose=False):
    if verbose: print(f'Checking if {package} is installed...')
    result = c.run(f'rpm -qa | grep -i {package}', warn=True)
    if result.return_code == 0 and package in result.stdout:
        if verbose: print(f'Package "{package}" is already installed')
    else:
        if verbose: print(f'Package {package} is not installed, installing...')
        c.run(f'yum install -y {package}')


def initialize():
    public_key = create_ssh_keys(get_ssh_connection(hosts[0], root_user_pwd), verbose=True)
    for host in hosts:
        root_c = get_ssh_connection(host, root_user_pwd, verbose=True)
        update_firewall_rules(root_c, verbose=True)
        update_known_hosts(root_c, host, verbose=True)
        create_remote_user(root_c, verbose=True)
        add_remote_user_group_to_sudoers(root_c, verbose=True)
        user_c = get_ssh_connection(host, remote_user_pwd, 22, remote_user, verbose=True)
        upload_ssh_key(user_c, public_key, verbose=True)
        change_ssh_port(root_c, ssh_port, verbose=True)
        update_known_hosts(root_c, host, new_port=True, verbose=True)


initialize()
