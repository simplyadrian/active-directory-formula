'''
A thin wrapper around the AD FS PowerShell cmdlets.
'''
from __future__ import absolute_import

## Import Python libraries
import json
import logging
import inspect
import sys

## Import Salt libraries
import salt.log

log = logging.getLogger(__name__)

def __virtual__():
    '''
    This module works on Windows Server 2008 and newer.
    '''
    if __grains__['os_family'] == 'Windows' and \
       __grains__['osrelease'] in ['2008Server', '2008ServerR2', \
                                   '2012Server', '2012ServerR2']:
        ## Get the list of available cmdlets at runtime.
        cmdlets = _pswrapper('Get-Help ADFS | Where-Object { $_.Category -eq \'Cmdlet\' } | Select Name,Synopsis | Sort Name')

        ## This generates Python functions for each of the AD FS cmdlets
        ## listed above.
        this_module = sys.modules[__name__]
        for cmdlet in cmdlets:
            def f(x):
                def g(**kwargs):
                    return _pswrapper(x, **kwargs)
                return g
            c_name = cmdlet['Name']
            c_docs = cmdlet['Synopsis']
            f_name = c_name.replace('-', '_').lower()
            setattr(this_module, f_name, f(c_name))
            getattr(this_module, f_name).__doc__ = c_docs

        return 'identityserver_sts'
    else:
        return False

def _pscredential(username, password):
    '''
    Generate code that converts a username and a password into a
    PSCredential object.
    '''
    return 'New-Object -TypeName System.Management.Automation.PSCredential ' + \
           '-ArgumentList "{0}", '.format(username) + \
           '(ConvertTo-SecureString -String "{0}" '.format(password) + \
           '-AsPlainText -Force)'

def _pswrapper(cmdlet, **kwargs):
    '''
    Wrap calls to PowerShell cmdlets.

    The results of the cmdlet, if successful, are serialized into a
    JSON document by Powershell and deserialized into the appropriate
    Python object by Salt.
    '''
    cmd = []

    ## On older versions of Windows Server, assume AD FS 2.0.  This
    ## requires manually importing the AD FS PowerShell snapin prior
    ## to executing related cmdlets.
    if __grains__['osrelease'] in ['2008Server', '2008ServerR2']:
        cmd.append('Add-PSSnapin Microsoft.Adfs.PowerShell;')

    cmd.append(cmdlet)

    ## Loop through kwargs, which get translated verbatim into cmdlet
    ## parameters.
    for k, v in kwargs.items():
        if k.find('__pub') >= 0:
            ## filter out special kwargs like '/__pub_fun'
            pass
        elif v == True or v == False:
            cmd.append('-{0}:${1}'.format(k, v))
        elif type(v) is dict and 'username' in v:
            ## assume dicts that contain a 'username' key should get
            ## transformed into PSCredential objects
            cmd.append('-{0} ({1})'.format(k, _pscredential(v.username, v.password)))
        elif type(v) is int:
            cmd.append('-{0} {1}'.format(k, v))
        else:
            cmd.append('-{0} "{1}"'.format(k, v))
    cmd.append('| ConvertTo-Json -Compress -Depth 32')

    ## TODO: replace with cmd.powershell in a future Salt release
    response = __salt__['cmd.run'](
        " ".join(cmd),
        shell='powershell',
        python_shell=True)
    try:
        return json.loads(response)
    except Exception:
        log.error("Error converting PowerShell JSON return", exc_info=True)
        return {}

#### Local Variables:
#### coding: utf-8
#### End:
