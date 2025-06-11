#
# Copyright 2015 Reliance Jio Infocomm Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from collections import namedtuple

#from awsauth import S3Auth
from requests_aws4auth import AWS4Auth
import datetime
import requests
import json

from urllib import parse as urlparse

from ceilometer.i18n import _


class RGWAdminAPIFailed(Exception):
    pass


class RGWAdminClient(object):
    Bucket = namedtuple('Bucket', 'name, num_objects, size')

    def __init__(self, endpoint, access_key, secret_key, implicit_tenants):
        self.access_key = access_key
        self.secret = secret_key
        self.endpoint = endpoint
        self.hostname = urlparse.urlparse(endpoint).hostname
        self.implicit_tenants = implicit_tenants

    def _make_request(self, path, req_params):
        uri = "{0}/{1}".format(self.endpoint, path)
        headers = {
          "host": self.hostname,
          "x-amz-date": datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        }
        r = requests.get(uri, params=req_params, headers=headers,
                         auth=AWS4Auth(self.access_key, self.secret,
                                       self.hostname,'s3')
                         )

        if r.status_code != 200:
            raise RGWAdminAPIFailed(
                _('RGW AdminOps API returned %(status)s %(reason)s') %
                {'status': r.status_code, 'reason': r.reason})
        len1 = r.headers.get('content-length', 0)
        len2 = r.headers.get('Content-Length', 0)
        if int(len1) == 0 and int(len2) == 0:
           return json.dumps({})

        return r.json()

    def get_bucket(self, tenant_id):
        if self.implicit_tenants:
            rgw_uid = tenant_id + "$" + tenant_id
        else:
            rgw_uid = tenant_id
        path = "bucket"
        req_params = {"uid": rgw_uid, "stats": "true"}
        json_data = self._make_request(path, req_params)
        stats = {'num_buckets': 0, 'buckets': [], 'size': 0, 'num_objects': 0}
        stats['num_buckets'] = len(json_data)
        if stats['num_buckets'] == 0:
            return stats
        for it in json_data:
            if not isinstance(it, dict):
                continue
            for v in it["usage"].values():
                stats['num_objects'] += v["num_objects"]
                stats['size'] += v["size_kb"]
                stats['buckets'].append(self.Bucket(it["bucket"],
                                                    v["num_objects"],
                                                    v["size_kb"]))
        return stats

    def get_usage(self, tenant_id):
        if self.implicit_tenants:
            rgw_uid = tenant_id + "$" + tenant_id
        else:
            rgw_uid = tenant_id
        path = "usage"
        req_params = {"uid": rgw_uid}
        json_data = self._make_request(path, req_params)
        usage_data = json_data["summary"]
        return sum((it["total"]["ops"] for it in usage_data))
