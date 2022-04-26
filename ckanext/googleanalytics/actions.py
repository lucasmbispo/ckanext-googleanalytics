from . import dbutil
from ckan.plugins import toolkit
import json

@toolkit.side_effect_free
def resource_stat(context, data_dict):
    '''
    Fetch resource stats
    '''
    resource_id = data_dict['resource_id']
    result = dbutil.get_resource_stat(resource_id)[0]
    return json.dumps(result)

@toolkit.side_effect_free
def package_stat(context, data_dict):
    '''
    Fetch package stats
    '''
    package_id = data_dict['package_id']
    result = dbutil.get_resource_stat(package_id)[0]
    return json.dumps(result)
