# -*-coding:UTF-8 -*
"""
Base Class for AIL Objects
"""

##################################
# Import External packages
##################################
import os
import sys
import time
from abc import ABC

from datetime import datetime
# from flask import url_for

sys.path.append(os.environ['AIL_BIN'])
##################################
# Import Project packages
##################################
from lib.objects.abstract_subtype_object import AbstractSubtypeObject
from lib.ail_core import get_object_all_subtypes, zscan_iter ################
from lib.ConfigLoader import ConfigLoader
from lib.objects import Messages
from packages import Date

# from lib.data_retention_engine import update_obj_date


# LOAD CONFIG
config_loader = ConfigLoader()
r_cache = config_loader.get_redis_conn("Redis_Cache")
r_object = config_loader.get_db_conn("Kvrocks_Objects")
config_loader = None

# # FIXME: SAVE SUBTYPE NAMES ?????

class AbstractChatObject(AbstractSubtypeObject, ABC):
    """
    Abstract Subtype Object
    """

    def __init__(self, obj_type, id, subtype):
        """ Abstract for all the AIL object

        :param obj_type: object type (item, ...)
        :param id: Object ID
        """
        super().__init__(obj_type, id, subtype)

    # get useraccount / username
    # get users ?
    # timeline name ????
    # info
    # created
    # last imported/updated

    # TODO get instance
    # TODO get protocol
    # TODO get network
    # TODO get address

    def get_chat(self):  # require ail object TODO ##
        if self.type != 'chat':
            parent = self.get_parent()
            if parent:
                obj_type, _ = parent.split(':', 1)
                if obj_type == 'chat':
                    return parent

    def get_subchannels(self):
        subchannels = []
        if self.type == 'chat':  # category ???
            for obj_global_id in self.get_childrens():
                obj_type, _ = obj_global_id.split(':', 1)
                if obj_type == 'chat-subchannel':
                    subchannels.append(obj_global_id)
        return subchannels

    def get_nb_subchannels(self):
        nb = 0
        if self.type == 'chat':
            for obj_global_id in self.get_childrens():
                obj_type, _ = obj_global_id.split(':', 1)
                if obj_type == 'chat-subchannel':
                    nb += 1
        return nb

    def get_threads(self):
        threads = []
        for obj_global_id in self.get_childrens():
            obj_type, _ = obj_global_id.split(':', 1)
            if obj_type == 'chat-thread':
                threads.append(obj_global_id)
        return threads

    def get_created_at(self, date=False):
        created_at = self._get_field('created_at')
        if date and created_at:
            created_at = datetime.fromtimestamp(float(created_at))
            created_at = created_at.isoformat(' ')
        return created_at

    def set_created_at(self, timestamp):
        self._set_field('created_at', timestamp)

    def get_name(self):
        name = self._get_field('name')
        if not name:
            name = ''
        return name

    def set_name(self, name):
        self._set_field('name', name)

    def get_icon(self):
        icon = self._get_field('icon')
        if icon:
            return icon.rsplit(':', 1)[1]

    def set_icon(self, icon):
        self._set_field('icon', icon)

    def get_info(self):
        return self._get_field('info')

    def set_info(self, info):
        self._set_field('info', info)

    def get_nb_messages(self):
        return r_object.zcard(f'messages:{self.type}:{self.subtype}:{self.id}')

    def _get_messages(self, nb=-1, page=1):
        if nb < 1:
            return r_object.zrange(f'messages:{self.type}:{self.subtype}:{self.id}', 0, -1, withscores=True)
        else:
            if page > 1:
                start = page - 1 + nb
            else:
                start = 0
            messages = r_object.zrevrange(f'messages:{self.type}:{self.subtype}:{self.id}', start, start+nb-1, withscores=True)
            if messages:
                messages = reversed(messages)
            return messages

    def get_timestamp_first_message(self):
        return r_object.zrange(f'messages:{self.type}:{self.subtype}:{self.id}', 0, 0, withscores=True)

    def get_timestamp_last_message(self):
        return r_object.zrevrange(f'messages:{self.type}:{self.subtype}:{self.id}', 0, 0, withscores=True)

    def get_first_message(self):
        return r_object.zrange(f'messages:{self.type}:{self.subtype}:{self.id}', 0, 0)

    def get_last_message(self):
        return r_object.zrevrange(f'messages:{self.type}:{self.subtype}:{self.id}', 0, 0)

    def get_nb_message_by_hours(self, date_day, nb_day):
        hours = []
        # start=0, end=23
        timestamp = time.mktime(datetime.strptime(date_day, "%Y%m%d").timetuple())
        for i in range(24):
            timestamp_end = timestamp + 3600
            nb_messages = r_object.zcount(f'messages:{self.type}:{self.subtype}:{self.id}', timestamp, timestamp_end)
            timestamp = timestamp_end
            hours.append({'date': f'{date_day[0:4]}-{date_day[4:6]}-{date_day[6:8]}', 'day': nb_day, 'hour': i, 'count': nb_messages})
        return hours

    def get_nb_message_by_week(self, date_day):
        date_day = Date.get_date_week_by_date(date_day)
        week_messages = []
        i = 0
        for date in Date.daterange_add_days(date_day, 6):
            week_messages = week_messages + self.get_nb_message_by_hours(date, i)
            i += 1
        return week_messages

    def get_nb_message_this_week(self):
        week_date = Date.get_current_week_day()
        return self.get_nb_message_by_week(week_date)

    def get_message_meta(self, message, timestamp=None):  # TODO handle file message
        message = Messages.Message(message[9:])
        meta = message.get_meta(options={'content', 'files-names', 'images', 'link', 'parent', 'parent_meta', 'reactions', 'thread', 'user-account'}, timestamp=timestamp)
        return meta

    def get_messages(self, start=0, page=1, nb=500, unread=False):  # threads ???? # TODO ADD last/first message timestamp + return page
        # TODO return message meta
        tags = {}
        messages = {}
        curr_date = None
        for message in self._get_messages(nb=2000, page=1):
            timestamp = message[1]
            date_day = datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d')
            if date_day != curr_date:
                messages[date_day] = []
                curr_date = date_day
            mess_dict = self.get_message_meta(message[0], timestamp=timestamp)
            messages[date_day].append(mess_dict)

            if mess_dict.get('tags'):
                for tag in mess_dict['tags']:
                    if tag not in tags:
                        tags[tag] = 0
                    tags[tag] += 1
        return messages, tags

    # TODO REWRITE ADD OR ADD MESSAGE ????
    # add
    # add message

    def get_obj_by_message_id(self, message_id):
        return r_object.hget(f'messages:ids:{self.type}:{self.subtype}:{self.id}', message_id)

    def add_message_cached_reply(self, reply_id, message_id):
        r_cache.sadd(f'messages:ids:{self.type}:{self.subtype}:{self.id}:{reply_id}', message_id)
        r_cache.expire(f'messages:ids:{self.type}:{self.subtype}:{self.id}:{reply_id}', 600)

    def _get_message_cached_reply(self, message_id):
        return r_cache.smembers(f'messages:ids:{self.type}:{self.subtype}:{self.id}:{message_id}')

    def get_cached_message_reply(self, message_id):
        objs_global_id = []
        for mess_id in self._get_message_cached_reply(message_id):
            obj_global_id = self.get_obj_by_message_id(mess_id)  # TODO CATCH EXCEPTION
            if obj_global_id:
                objs_global_id.append(obj_global_id)
        return objs_global_id

    def add_message(self, obj_global_id, message_id, timestamp, reply_id=None):
        r_object.hset(f'messages:ids:{self.type}:{self.subtype}:{self.id}', message_id, obj_global_id)
        r_object.zadd(f'messages:{self.type}:{self.subtype}:{self.id}', {obj_global_id: float(timestamp)})

        # MESSAGE REPLY
        if reply_id:
            reply_obj = self.get_obj_by_message_id(reply_id)  # TODO CATCH EXCEPTION
            if reply_obj:
                self.add_obj_children(reply_obj, obj_global_id)
            else:
                self.add_message_cached_reply(reply_id, message_id)
        # CACHED REPLIES
        for mess_id in self.get_cached_message_reply(message_id):
            self.add_obj_children(obj_global_id, mess_id)



    # get_messages_meta ????

# TODO move me to abstract subtype
class AbstractChatObjects(ABC):
    def __init__(self, type):
        self.type = type

    def add_subtype(self, subtype):
        r_object.sadd(f'all_{self.type}:subtypes', subtype)

    def get_subtypes(self):
        return r_object.smembers(f'all_{self.type}:subtypes')

    def get_nb_ids_by_subtype(self, subtype):
        return r_object.zcard(f'{self.type}_all:{subtype}')

    def get_ids_by_subtype(self, subtype):
        return r_object.zrange(f'{self.type}_all:{subtype}', 0, -1)

    def get_all_id_iterator_iter(self, subtype):
        return zscan_iter(r_object, f'{self.type}_all:{subtype}')

    def get_ids(self):
        pass

    def search(self):
        pass
