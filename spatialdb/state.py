# Copyright 2016 The Johns Hopkins University Applied Physics Laboratory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import redis
import uuid
import time
from datetime import datetime
from .error import SpdbError, ErrorCodes


class CacheStateDB(object):
    def __init__(self, kv_conf):
        """
        A class to implement the Boss cache state database and associated functionality

        Args:
            kv_conf(dict): Dictionary containing configuration details for the key-value store



        Params in the kv_config dictionary:
            state_client: Optional instance of a redis client that will be used directly
            cache_state_host: If cache_client not provided, a string indicating the database host
            cache_state_db: If cache_client not provided, an integer indicating the database to use
        """
        self.config = kv_conf

        # Create client
        if "state_client" in self.config:
            self.status_client = self.config["state_client"]
        else:
            self.status_client = redis.StrictRedis(host=self.config["cache_state_host"], port=6379,
                                                   db=self.config["cache_state_db"])

        self.status_client_listener = None

    def create_page_in_channel(self):
        """
        Create a page in channel for monitoring a page-in operation

        Returns:
            (str): the page in channel name
        """
        channel_name = "PAGE-IN-CHANNEL&{}".format(uuid.uuid4().hex)
        self.status_client_listener = self.status_client.pubsub()
        self.status_client_listener.subscribe(channel_name)
        return channel_name

    def delete_page_in_channel(self, page_in_channel):
        """
        Method to remove a page in channel (after use) and close the pubsub connection
        Args:
            page_in_channel (str): Name of the subscription

        Returns:
            None
        """
        self.status_client_listener.punsubscribe(page_in_channel)
        self.status_client_listener.close()

    def wait_for_page_in(self, keys, page_in_channel, timeout):
        """
        Method to monitor page in operation and wait for all operations to complete

        Args:
            keys (list(str)): List of object keys to wait for
            page_in_channel (str): Name of the subscription
            timeout (int): Max # of seconds page in should take before an exception is raised.

        Returns:
            None
        """
        start_time = datetime.now()

        keys_set = set(keys)

        while True:
            msg = self.status_client_listener.get_message()

            # Parse message
            if msg["channel"] != page_in_channel:
                raise SpdbError('Message from incorrect channel received. Read operation aborted.',
                                ErrorCodes.ASYNC_ERROR)

            keys_set.remove(msg["data"])

            # Check if you have completed
            if len(keys_set) == 0:
                # Done!
                break

            # Check if too much time has passed
            if (start_time - datetime.now()).seconds > timeout:
                # Took too long! Something must have crashed
                self.delete_page_in_channel(page_in_channel)
                raise SpdbError('All data failed to page in before timeout elapsed.',
                                ErrorCodes.ASYNC_ERROR)

            # Sleep a bit
            time.sleep(0.05)

    def notify_page_in_complete(self, page_in_channel, key):
        """
        Method to notify main API process that the async page-in operation for a given cuboid is complete
        Args:
            page_in_channel (str): Name of the subscription
            key (str): cached-cuboid key for the cuboid that has been successfully paged in

        Returns:
            None

        """
        self.status_client.publish(page_in_channel, key)

    def add_cache_misses(self, key_list):
        """
        Method to add cached-cuboid keys to the cache-miss list

        Args:
            key_list (list(str)): List of object keys to wait for

        Returns:
            None

        """
        self.status_client.rpush('CACHE-MISS', *key_list)

    def project_locked(self, lookup_key):
        """
        Method to check if a given channel/layer is locked for writing due to an error

        Args:
            lookup_key (str): Lookup key for a channel/layer

        Returns:
            (bool): True if the channel/layer is locked, false if not
        """
        key = "WRITE-LOCK&{}".format(lookup_key)
        return bool(self.status_client.exists(key))

    def in_page_out(self, temp_page_out_key, lookup_key, resolution, morton, time_sample):
        """
        Method to check if a cuboid is currently being written to S3 via page out key

        Args:
            temp_page_out_key (str): a temporary set used to check if cubes are in page out
            lookup_key (str): Lookup key for a channel/layer
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid

        Returns:
            (bool): True if the key is in page out
        """
        try:
            # Create temp set
            pipe = self.status_client.pipeline()
            pipe.sadd(temp_page_out_key, "{}&{}".format(morton, time_sample))
            pipe.expire(temp_page_out_key, 30)
            result = pipe.execute()
        except Exception as e:
            raise SpdbError("Failed to check page-out set. {}".format(e),
                            ErrorCodes.REDIS_ERROR)

        # Use set diff to check for key
        result = self.status_client.sdiff(temp_page_out_key, "PAGE-OUT&{}&{}".format(lookup_key, resolution))

        #TODO: double check output from sdiff
        if result:
            return False
        else:
            return True

    def add_to_delayed_write(self, write_cuboid_key, lookup_key, resolution, morton, time_sample):
        """
        Method to add a write cuboid key to a delayed write queue

        Args:
            write_cuboid_key (str): write-cuboid key for the cuboid to delay write
            lookup_key (str): Lookup key for a channel/layer
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid

        Returns:
            None
        """
        self.status_client.rpush("DELAYED-WRITE&{}&{}&{}&{}".format(lookup_key, resolution, time_sample, morton),
                                 write_cuboid_key)

    def get_delayed_write_keys(self):
        """
        Method to get delayed write-cuboid keys for processing

        Returns:
            list((str, str)): List of tuples where the first item is the delayed-write key and the second is the
                                write-cuboid key
        """
        # TODO: Double check if key doesn't exist lpop returns nil
        delayed_write_keys = self.status_client.get("DELAYED-WRITE*")
        output = []
        for key in delayed_write_keys:
            write_cuboid_key = self.status_client.lpop(key)
            if write_cuboid_key != "nil":
                output.append((key, write_cuboid_key))

        return output

    def add_to_page_out(self, temp_page_out_key, lookup_key, resolution, morton, time_sample):
        """
        Method to add a key to the page-out tracking set

        Args:
            lookup_key (str): Lookup key for a channel/layer
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid

        Returns:
            (bool, bool): Tuple where first value is if the transaction succeeded and the second is if the key is in
            page out already
        """
        # TODO: Validate output from pipe
        page_out_key = "PAGE-OUT&{}&{}".format(lookup_key, resolution)
        success = True
        in_page_out = True
        try:
            # Create temp set
            pipe = self.status_client.pipeline()
            pipe.multi()
            pipe.watch(page_out_key)
            self.status_client.sdiff(temp_page_out_key, page_out_key)
            self.status_client.sadd(page_out_key, "{}&{}".format(morton, time_sample))
            result = pipe.execute()

            if result[1]:
                in_page_out = False
            else:
                in_page_out = True

        except redis.WatchError:
            # Watch error occurred
            success = False

        except Exception as e:
            raise SpdbError("Failed to check page-out set. {}".format(e),
                            ErrorCodes.REDIS_ERROR)

        return success, in_page_out