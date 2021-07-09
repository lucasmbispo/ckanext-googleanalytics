from __future__ import absolute_import

import logging
import ckan.model as model
from . import extract_table_names
from ckan.lib.base import BaseController, c, render, request
from . import dbutil

import ckan.logic as logic
import hashlib
from . import plugin
from pylons import config

from paste.util.multidict import MultiDict

from ckan.controllers.api import ApiController

from ckan.exceptions import CkanVersionException
import ckan.plugins.toolkit as tk
try:
    tk.requires_ckan_version("2.9")
except CkanVersionException:
    pass
else:
    from builtins import str


log = logging.getLogger("ckanext.googleanalytics")


class GAController(BaseController):
    def view(self):
        # get package objects corresponding to popular GA content
        c.top_resources = dbutil.get_top_resources(limit=10)
        return render("summary.html")


class GAApiController(ApiController):
    # intercept API calls to record via google analytics
    def _post_analytics(
        self, user, request_obj_type, request_function, ids
    ):
        if config.get("googleanalytics.id"):
            id = ids[0] if isinstance(ids, list) else ids
            id = id if id else ""
            data_dict = {
                "v": 1,
                "tid": config.get("googleanalytics.id"),
                "cid": hashlib.md5(user).hexdigest(),
                # customer id should be obfuscated
                "t": "event",
                "dh": c.environ["HTTP_HOST"],
                "dp": c.environ["PATH_INFO"],
                "dr": c.environ.get("HTTP_REFERER", ""),
                "ec": "Regular CKAN API Request",
                "ea": request_obj_type + request_function,
                "el": id,
            }
             
            '''
              Many other internal service also using CKAN APIs eg. frontend-v2, data-subscription, dataexplorer.
              so, filtering internal request by user-agent and headers to avoid tracking. 
            '''
            is_it_internal_request = (request.headers.get("Request-Source", '') in ["data-explorer", "ckan-internal"]) or \
                                      request.headers.get("User-Agent", '').startswith(("frontend-v2/latest", "data-explorer/next-gen", \
                                      "ckan-datapusher/latest", "ckan-others/latest", "data-subscription/latest")) 

            blacklisted_actions = ["status_show", "datapusher_hook"]

            if not is_it_internal_request and request_obj_type not in blacklisted_actions:  
                params_dict = self._ga_prepare_parameter(
                    request_obj_type, request_function, ids)
                data_dict.update(params_dict)
                plugin.GoogleAnalyticsPlugin.analytics_queue.put(data_dict)

    def _ga_prepare_parameter(self, request_obj_type, request_function, ids):
        '''
          Send GA custom dimension parameter to generate better report.
              "cd1" : Organization Name
              "cd2" : Package Name
              "cd3" : Resource Name
        '''
        data_dict = {}
        context = {'model': model, 'session': model.Session, 'user': c.user,
                   'api_version': None, 'auth_user_obj': c.userobj}

        id = ids[0]
        resource_id = ids[1]
        package_id = ids[2]

        package_level_action = ['package_show', 'package_create', 'package_patch',
                                'package_update', 'datastore_create']

        resource_level_action = ['resource_create', 'resource_show', 'resource_patch', 'resource_update',
                                 'datastore_search',  'datastore_create', 'datastore_upsert',
                                 'datastore_search_sql', 'datastore_delete']

        if(request_obj_type in package_level_action and not resource_id):
            if id:
                request_id = id
            else:
                request_id = package_id

            pkg = logic.get_action("package_show")(
                dict(context, return_type="dict"), {"id": request_id})

            data_dict.update({
                "cd1": pkg["organization"]["name"],
                "cd2": pkg["name"]
            })


        if(request_obj_type in resource_level_action):
            if id:
                request_id = id
            else:
                request_id = resource_id

            if request_obj_type == "datastore_search_sql":
                # extract resource_id from sql statement
                tables = extract_table_names.extract_tables(id)
                request_id = tables[0]

            resource = logic.get_action('resource_show')(
                dict(context, return_type='dict'), {"id": request_id})

            pkg = logic.get_action('package_show')(
                dict(context, return_type='dict'), {'id': resource['package_id']})

            data_dict.update({
                "cd1": pkg["organization"]["name"],
                "cd2": pkg["name"],
                "cd3": resource["name"]
            })

        return data_dict

    def action(self, logic_function, ver=None):
        try:
            function = logic.get_action(logic_function)
            side_effect_free = getattr(function, "side_effect_free", False)
            request_data = self._get_request_data(
                try_url_params=side_effect_free
            )
            if isinstance(request_data, dict):
                id = request_data.get("id", False)
                resource_id = request_data.get("resource_id", False)
                package_id = request_data.get("resource", {}).get("package_id", False)
                package_id = request_data.get("package_id", package_id)

                if "q" in request_data:
                    id = request_data["q"]
                if "sql" in request_data:
                    id = request_data["sql"]
                if "query" in request_data:
                    id = request_data["query"]
                self._post_analytics(c.user, logic_function, "", [
                                     id, resource_id, package_id])
        except Exception as e:
            log.debug(e)
            pass
        return ApiController.action(self, logic_function, ver)

    def list(self, ver=None, register=None, subregister=None, id=None):
        self._post_analytics(
            c.user,
            register + ("_" + str(subregister) if subregister else ""),
            "list",
            id,
        )
        return ApiController.list(self, ver, register, subregister, id)

    def show(
        self, ver=None, register=None, subregister=None, id=None, id2=None
    ):
        self._post_analytics(
            c.user,
            register + ("_" + str(subregister) if subregister else ""),
            "show",
            id,
        )
        return ApiController.show(self, ver, register, subregister, id, id2)

    def update(
        self, ver=None, register=None, subregister=None, id=None, id2=None
    ):
        self._post_analytics(
            c.user,
            register + ("_" + str(subregister) if subregister else ""),
            "update",
            id,
        )
        return ApiController.update(self, ver, register, subregister, id, id2)

    def delete(
        self, ver=None, register=None, subregister=None, id=None, id2=None
    ):
        self._post_analytics(
            c.user,
            register + ("_" + str(subregister) if subregister else ""),
            "delete",
            id,
        )
        return ApiController.delete(self, ver, register, subregister, id, id2)

    def search(self, ver=None, register=None):
        id = None
        try:
            params = MultiDict(self._get_search_params(request.params))
            if "q" in list(params.keys()):
                id = params["q"]
            if "query" in list(params.keys()):
                id = params["query"]
        except ValueError as e:
            log.debug(str(e))
            pass
        self._post_analytics(c.user, register, "search", id)

        return ApiController.search(self, ver, register)
