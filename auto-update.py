#!/usr/bin/env python3

# Adapted from https://github.com/flathub/org.vim.Vim/blob/master/auto-update.py
#
# See: https://discourse.lathub.org/t/tools-for-automatically-updating-flatpak-packaging/736/

import argparse
import collections
import os
import re
import subprocess
import textwrap

import ruamel.yaml

HERE = os.path.abspath(os.path.dirname(__file__))
VIM_CLONE = os.path.join(HERE, 'purr-data')
MANIFEST = os.path.join(HERE, 'net.purrdata.PurrData.yml')
APPDATA = os.path.join(HERE, 'net.purrdata.PurrData.metainfo.xml')


def run(args, **kwargs):
    print('$', ' '.join(args))
    return subprocess.run(args, check=True, **kwargs)


def dry_run(args, **kwargs):
    print('would run $', ' '.join(args))


def run_and_read(args):
    result = run(args, stdout=subprocess.PIPE)
    return result.stdout.decode('ascii').strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    yaml = ruamel.yaml.YAML()
    with open(MANIFEST, 'r') as f:
        manifest = yaml.load(f)

    if not os.path.isdir(VIM_CLONE):
        run(('git', 'clone', vim_source['url'], VIM_CLONE))

    os.chdir(VIM_CLONE)
    run(('git', 'pull'))
    sha = run_and_read(('git', 'show-ref', '--hash', 'HEAD'))
    tag = run_and_read(('git', 'describe', '--tags', 'HEAD'))
    date = run_and_read(('git', 'log', '-1', '--date=short',
                         '--pretty=format:%cd'))
    os.chdir(HERE)

    # Patch manifest
    old_tag = None
    source = None
    pd_modules = ['purr-data', 'pd-externals', 'pd-abstractions', 'purr-data-integration']
    for module in manifest['modules']:
        if issubclass(type(module), dict) and module['name'] in pd_modules:
            source = module['sources'][0]

            old_tag = source['tag']
            source['tag'] = tag
            source['commit'] = sha
            module['sources'][0] = source

    with open(MANIFEST, 'w') as f:
        yaml.dump(manifest, f)

    # Patch appdata. Sorry, I can't bring myself to use an XML parser.
    with open(APPDATA, 'r') as f:
        xml = f.read()

    xml = re.sub(r'<release version="(.+?)" date="(.+?)">',
                 '<release version="{}" date="{}">'.format(tag, date),
                 xml)
    with open(APPDATA, 'w') as f:
        f.write(xml)

    try:
        run(('git', 'diff-index', '--quiet', 'HEAD', '--'))
    except subprocess.CalledProcessError:
        pass
    else:
        print("Manifest is up-to-date")
        return

    branch = 'update-to-{}'.format(tag)
    f = dry_run if args.dry_run else run
    f(('git', 'checkout', '-b', branch))
    f(('git', 'commit', '-am', 'Update to {}'.format(tag)))
    f(('git', 'push', '-u', args.remote, branch))
    f(('hub', 'pull-request', '--no-edit', '-m', textwrap.dedent('''
       Update to {tag}

       Upstream changes: {url}/compare/{old_tag}...{tag}

       <i>(This pull request was automatically generated.)</i>
       ''').strip().format(
           tag=tag,
           old_tag=old_tag,
           url=vim_source['url'],
       )))


if __name__ == '__main__':
    main()
