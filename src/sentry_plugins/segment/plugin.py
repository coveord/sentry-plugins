from __future__ import absolute_import

from sentry import http
from sentry.app import ratelimiter
from sentry.plugins.base import Plugin
from sentry.utils.hashlib import md5_text

from sentry_plugins.base import CorePluginMixin


class SegmentPlugin(CorePluginMixin, Plugin):
    title = 'Segment'
    slug = 'segment'
    description = 'Send Sentry events into Segment.'
    conf_key = 'segment'

    endpoint = 'https://api.segment.io/v1/track'

    def get_config(self, project, **kwargs):
        return [{
            'name': 'write_key',
            'label': 'Write Key',
            'type': 'secret',
            'required': True,
        }]

    def post_process(self, event, **kwargs):
        # TODO(dcramer): we currently only support authenticated events, as the
        # value of anonymous errors/crashes/etc is much less meaningful in the
        # context of Segment
        user_interface = event.data.get('sentry.interfaces.User')
        if not user_interface:
            return

        user_id = user_interface.get('id')

        if not user_id:
            return

        write_key = self.get_option('write_key', event.project)
        if not write_key:
            return

        rl_key = 'segment:{}'.format(md5_text(write_key).hexdigest())
        # limit segment to 50 requests/second
        if ratelimiter.is_limited(rl_key, limit=50, window=1):
            return

        payload = {
            'userId': user_id,
            'event': 'Error Captured',
            'properties': {
                'eventId': event.event_id,
            },
            'timestamp': event.datetime.isoformat() + 'Z',
            'integration': {
                'name': 'sentry',
                'version': self.version,
            },
        }
        session = http.build_session()
        session.post(self.endpoint, json=payload, auth=(write_key, ''))
