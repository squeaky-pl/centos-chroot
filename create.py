#!/usr/bin/env python

from os import getuid, makedirs, errno
from os.path import abspath, join, dirname, normpath, exists, isabs, basename
from sys import exit, argv
from shutil import copy2
from subprocess import check_output, check_call, CalledProcessError
from xml.etree import ElementTree
from textwrap import dedent


def check_root():
    if getuid() != 0:
        print("You have to be root to run this program.")
        exit(1)


def print_usage():
    print("create.py release-file [chroot-dir]")
    exit(1)


def check_tools():
    for tool in ['setarch', 'rpm', 'yum', 'wget']:
        try:
            check_output(['which', tool])
        except CalledProcessError:
            print("Cannot find needed program '{0}'".format(tool))
            exit(1)


def get_arch(archive):
    output = check_output(['rpm', '-qip', archive])
    for line in output.splitlines():
        if line.startswith("Architecture"):
            arch = line.split()[1]
            if arch == 'i386':
                arch = 'i686'

            return arch


def find_spec():
    current = dirname(abspath(__file__))

    while 1:
        spec = join(current, 'chroot.spec.xml')
        if exists(spec):
            return spec

        if current == '/':
            break

        current = normpath(join(current, '..'))


def parse_spec(spec):
    result = {}

    root = ElementTree.parse(spec).getroot()

    repositories = root.find('repositories')
    if repositories is not None:
        result['repositories'] = repositories.text.split()

    packages = root.find('packages')
    if packages is not None:
        result['packages'] = packages.text.split()

    directories = root.find('directories')
    if directories is not None:
        result['directories'] = directories.text.split()

    files = root.find('files')
    if files is not None:
        files = files.text.strip()
        result['files'] = {}

        for line in files.splitlines():
            src, dest = line.split()
            src = join(dirname(spec), src)

            result['files'][src] = dest

    appends = root.findall('append')
    if appends:
        result['appends'] = {}
        for append in appends:
            path = append.attrib['path']
            result['appends'][path] = dedent(append.text.strip())

    return result


def ensuredirs(dirs):
    try:
        makedirs(dirs)
    except OSError as e:
        if not e.errno == errno.EEXIST:
            raise


def main():
    if len(argv) < 2:
        print_usage()

    check_root()
    check_tools()
    arch = get_arch(argv[1])

    print("chroot architecture is " + arch)

    dest = argv[2] if len(argv) == 3 else 'centos-' + arch

    print("creating in " + dest)

    name = basename(dest)
    dest = abspath(dest)

    ensuredirs(join(dest, 'var/lib/rpm'))

    def arch_call(args, okcode=None):
        try:
            check_call(['setarch', arch] + args)
        except CalledProcessError as e:
            if e.returncode != okcode:
                raise

    def install(package):
        arch_call(['yum', '-c', 'yum.conf', '-y', '--installroot', dest,
                   'install', package])

    arch_call(['rpm', '--root', dest, '--initdb'])
    arch_call(['rpm', '-ivh', '--force-debian', '--nodeps', '--root',
               dest, argv[1]], 1)
    check_call(['rm', '-r', '/etc/pki'])
    check_call(['ln', '-s', join(dest, 'etc/pki'), '/etc/pki'])

    install('yum')

    copy2('/etc/resolv.conf', join(dest, 'etc'))

    with open(join(dest, 'arch'), 'w') as f:
        f.write(arch)

    with open(join(dest, 'root/.bashrc'), 'w') as f:
        f.write('export PS1=({0})$PS1\n'.format(name))

    spec = find_spec()
    if not spec:
        return

    print("Using spec file: " + spec)
    spec = parse_spec(spec)

    for repository in spec.get('repositories', []):
        filename = basename(repository)
        check_call(['wget', '-O', join(dest, 'etc/yum.repos.d', filename),
                    repository])

    for package in spec.get('packages', []):
        install(package)

    for directory in spec.get('directories', []):
        if isabs(directory):
            directory = directory[1:]

        directory = join(dest, directory)
        print("Creating " + directory)
        ensuredirs(directory)

    for src, destination in spec.get('files', {}).items():
        if isabs(destination):
            destination = destination[1:]

        destination = join(dest, destination)
        print("Copying {0} to {1}".format(src, destination))
        copy2(src, destination)

    for path, data in spec.get('appends', {}).items():
        if isabs(path):
            path = path[1:]

        print("Appending to " + path)
        with open(join(dest, path), 'a') as f:
            f.write(data)


if __name__ == '__main__':
    main()
