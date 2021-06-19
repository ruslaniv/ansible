import re


def read_group_vars():
    vars_dict = {}
    with open('group_vars/all') as file:
        for line in file:
            data = line.strip().replace('"','').split(sep=': ')
            it = iter(data)
            vars_dict.update(dict(zip(it, it)))
    return vars_dict


def read_hosts():
    pattern = re.compile(r'(?!^\[all]\n)([0-9.]+)(?<!\s)')
    with open('hosts') as file:
        data = file.read()
        result = pattern.findall(data)
        return result
