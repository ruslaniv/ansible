# Ansible
Using [Ansible](https://www.ansible.com/) to configure remote CentOS server.

## Fabric
Ansible is not very convenient to perform initial server configuration, specifically I have found it hard to perform the following tasks:
1. Transfer an SHH public key to the remote server right after server initialization.
2. Programmatically add server SSH fingerprint to local "known_hosts" file
3. Programmatically change SSH port.

[Fabric](https://www.fabfile.org/) can easily automate these tasks.
Fabric is a high level imperative style shell command execution library written in python.  
I found it very useful to perform initial configuration of a remote server, having only root username and password provided by the cloud operator when you buy a VM instance.
All you need to do is:
```python
pip install fabric
```
And then Fabric scripts can be run as a regular python scripts.
Since Fabric is imperative it is somewhat cumbersome to achieve idempotency, and a lot of `if` statements have to be used to check for various conditions. In this regard, Ansible abstracts away a lot of such complexities.
So as soon as initial server configuration is completed, you can switch to Ansible to perform the rest of configuration tasks.