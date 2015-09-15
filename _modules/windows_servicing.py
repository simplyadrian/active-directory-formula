from __future__ import absolute_import
import logging
import re

import salt.utils

log = logging.getLogger(__name__)

def __virtual__():
    '''
    This works only on Windows Vista/Windows Server 2008 and newer.
    '''
    if __grains__['kernel'] == 'Windows' and int(__grains__['osversion'].split('.')[0]) >= 6:
        return 'windows_servicing'
    else:
        return False

def _dism(action,
          image=None,
          sources=[]):
    '''
    Run a DISM servicing command on the given image.
    '''
    command='dism {0} {1} {2}'.format(
        '/Image:{0}'.format(image) if image else '/Online',
        ' '.join(['/Source:{0}'.format(source) for source in sources]),
        action
    )
    return __salt__['cmd.run'](command, ignore_retcode=True)

def get_packages(image=None):
    '''
    Return information about all packages in the image (relative to
    the minion on which this command is run).  If no image is
    specified, this will target the minion itself.

    CLI Example:

    .. code-block:: bash

        salt -G os:Windows windows_servicing.get_packages
    '''
    output = _dism('/Get-Packages', image)
    if not re.search('The operation completed successfully.', output):
        return {}

    return {p: {'State': s, 'Release Type': r, 'Install Time': t}
            for p, s, r, t
            in re.findall('Package Identity : ([^\r\n]+)\r?\nState : ([^\r\n]+)\r?\nRelease Type : ([^\r\n]+)\r?\nInstall Time : ([^\r?\n]+)\r?\n',
                          output, re.MULTILINE)}

def get_features(package=None, image=None):
    '''
    Return information about all features found in a specific package
    within a specific image.  If you do not specify a package name or
    path, all features in the image will be listed.  If you do not
    specify an image, this will target the minion itself.

    CLI Example:

    .. code-block:: bash

        salt -G os:Windows windows_servicing.get_features
    '''
    if package:
        output = _dism('/Get-Features /PackageName:{0}'.format(package), image)
    else:
        output = _dism('/Get-Features', image)
    if not re.search('The operation completed successfully.', output):
        return {}

    return {f: {'State': s}
            for f, s
            in re.findall('Feature Name : ([^\r\n]+)\r?\nState : ([^\r\n]+)\r?\n',
                          output, re.MULTILINE)}

def enable_feature(name,
                   package=None,
                   image=None,
                   sources=[]):
    '''Enable the specified Windows feature.

    name
        The name of the feature (case-sensitive).

        CLI Example:

        .. code-block:: bash

            salt -G osrelease:2008ServerR2 windows_servicing.enable_feature TelnetClient

    package
        Enable the feature from the specified package.  If no package
        name is specified, the Windows Foundation package is assumed.

        CLI Example:

        .. code-block:: bash

            salt -G osrelease:2008ServerR2 windows_servicing.enable_feature Calc package=Microsoft.Windows.Calc.Demo~6595b6144ccf1df~x86~en~1.0.0.0

    image
        Enable the feature in the specified offline image.  If no
        image is specified, the feature will be enabled in the running
        Windows installation.  Note that the path to the offline image
        is relative to the minion, not the master.

        CLI Example:

        .. code-block:: bash

            salt-call windows_servicing.enable_feature TelnetClient image='C:\test\offline'

    sources
        Specify a list of one or more sources to search for the
        required files needed to enable the feature.  If you do not
        specify a source, this will look in the default location
        specified by Group Policy
        (https://technet.microsoft.com/en-us/library/hh825020.aspx).

        CLI Example:

        .. code-block:: bash

            salt-call windows_servicing.enable_feature TelnetClient sources="['d:\sources\sxs']"
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': '',
           'pending': False,
           'dism': ''}
    features = get_features(package, image)
    if name not in features:
        ret['result'] = False
        ret['comment'] = 'Feature {0} not found'.format(name)
        return ret
    elif features[name]['State'] == 'Enabled':
        ret['comment'] = 'Feature {0} already installed'.format(name)
        return ret
    elif features[name]['State'] == 'Enable Pending':
        ret['pending'] = True
        ret['comment'] = 'Feature {0} already installed (pending a reboot)'.format(name)
        return ret

    if package:
        output = _dism('/Enable-Feature /FeatureName:{0} /PackageName:{1} /NoRestart'.format(name, package), image, sources)
    else:
        output = _dism('/Enable-Feature /FeatureName:{0} /NoRestart'.format(name), image, sources)
    if not re.search('The operation completed successfully.', output):
        ret['result'] = False
        ret['comment'] = 'Feature {0} installation failed'.format(name)
        ret['dism'] = output
        return ret

    ret['changes'] = {'windows_servicing': 'Installed feature {0}'.format(name)}
    features = get_features(package, image)
    if features[name]['State'] == 'Enable Pending':
        ret['pending'] = True
        ret['comment'] = 'Reboot to complete feature {0} installation'.format(name)
    return ret