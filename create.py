#!/usr/bin/env python

from os import getuid, makedirs, errno
from os.path import abspath, join
from sys import exit, argv
from shutil import copy2
from subprocess import check_output, check_call, CalledProcessError

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

def main():
    if len(argv) < 2:
        print_usage()

    check_root()
    check_tools()
    arch = get_arch(argv[1])

    print("chroot architecture is " + arch)

    dest = argv[2] if len(argv) == 3 else 'centos-' + arch

    print("creating in " + dest)

    dest = abspath(dest)

    try:
        makedirs(join(dest, 'var/lib/rpm'))
    except OSError as e:
        if not e.errno == errno.EEXIST:
            raise

    def arch_call(args, okcode=None):
        try:
            check_call(['setarch', arch] + args)
        except CalledProcessError as e:
            if e.returncode != okcode:
                raise

    arch_call(['rpm', '--root', dest, '--initdb'])
    arch_call(['rpm', '-ivh', '--force-debian', '--nodeps', '--root',
               dest, argv[1]], 1)
    check_call(['rm', '-r', '/etc/pki'])
    check_call(['ln', '-s', join(dest, 'etc/pki'), '/etc/pki'])

    arch_call(['yum', '-c', 'yum.conf', '-y', '--installroot', dest,
               'install', 'yum'])

    copy2('/etc/resolv.conf', join(dest, 'etc'))

    with open(join(dest, 'arch'), 'w') as f:
        f.write(arch)

if __name__ == '__main__':
    main()
