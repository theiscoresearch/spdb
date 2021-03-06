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
    def __init__(self, config):
        """
        A class to implement the Boss cache state database and associated functionality

        Database is a redis instance.

        Args:
            config(dict): Dictionary containing configuration details for the key-value store


        Params in the kv_config dictionary:
            state_client: Optional instance of a redis client that will be used directly
            cache_state_host: If state_client not provided, a string indicating the database host
            cache_state_db: If state_client not provided, an integer indicating the database to use

        """
        self.config = config

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
            # Check if too much time has passed
            if (datetime.now() - start_time).seconds > timeout:
                # Took too long! Something must have crashed
                self.delete_page_in_channel(page_in_channel)
                raise SpdbError('All data failed to page in before timeout elapsed.',
                                ErrorCodes.ASYNC_ERROR)

            # If not, get a message
            msg = self.status_client_listener.get_message()

            # If message is not there, continue
            if not msg:
                continue

            # Verify the message was from the correct channel
            if msg["channel"].decode() != page_in_channel:
                raise SpdbError('Message from incorrect channel received. Read operation aborted.',
                                ErrorCodes.ASYNC_ERROR)

            # If you didn't get a message (e.g. a subscribe) continue
            if msg["type"] != 'message':
                continue

            # Remove the key from the set you are waiting for
            keys_set.remove(msg["data"].decode())

            # Check if you have completed
            if len(keys_set) == 0:
                # Done!
                break

            # Sleep a bit so you don't kill the DB
            time.sleep(0.05)

        # If you get here you got everything! Clean up
        self.delete_page_in_channel(page_in_channel)

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
        if isinstance(key_list, str):
            key_list = [key_list]

        self.status_client.rpush('CACHE-MISS', *key_list)

    def project_locked(self, lookup_key):
        """
        Method to check if a given channel is locked for writing due to an error

        Args:
            lookup_key (str): Lookup key for a channel

        Returns:
            (bool): True if the channel is locked, false if not
        """
        key = "WRITE-LOCK&{}".format(lookup_key)
        return bool(self.status_client.exists(key))

    def set_project_lock(self, lookup_key, locked):
        """
        Method to modify the lock status of a channel

        Args:
            lookup_key (str): Lookup key for a channel
            locked (bool): boolean indicating lock state. True=locked, False=unlocked

        Returns:
            None
        """
        key = "WRITE-LOCK&{}".format(lookup_key)
        if locked:
            self.status_client.set(key, True)
        else:
            self.status_client.delete(key)

    def in_page_out(self, temp_page_out_key, lookup_key, resolution, morton, time_sample):
        """
        Method to check if a cuboid is currently being written to S3 via page out key

        Args:
            temp_page_out_key (str): a temporary set used to check if cubes are in page out
            lookup_key (str): Lookup key for a channel
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid

        Returns:
            (bool): True if the key is in page out
        """
        with self.status_client.pipeline() as pipe:
            try:
                # Create temp set
                pipe.sadd(temp_page_out_key, "{}&{}".format(time_sample, morton))
                pipe.expire(temp_page_out_key, 30)
                pipe.execute()
            except Exception as e:
                raise SpdbError("Failed to check page-out set. {}".format(e),
                                ErrorCodes.REDIS_ERROR)

        # Use set diff to check for key
        result = self.status_client.sdiff(temp_page_out_key, "PAGE-OUT&{}&{}".format(lookup_key, resolution))

        if result:
            return False
        else:
            return True

    def add_to_delayed_write(self, write_cuboid_key, lookup_key, resolution, morton, time_sample, resource_str):
        """
        Method to add a write cuboid key to a delayed write queue

        Args:
            write_cuboid_key (str): write-cuboid key for the cuboid to delay write
            lookup_key (str): Lookup key for a channel
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid
            resource_str (str): a JSON encoded resource for the write-cuboid to be written

        Returns:
            None
        """
        self.status_client.rpush("DELAYED-WRITE&{}&{}&{}&{}".format(lookup_key, resolution, time_sample, morton),
                                 write_cuboid_key)
        self.status_client.set("RESOURCE-DELAYED-WRITE&{}&{}&{}&{}".format(lookup_key, resolution, time_sample, morton),
                               resource_str)

    def get_all_delayed_write_keys(self):
        """
        Method to get all available delayed write key

        Returns:
            list(str): List of available delayed write keys
        """
        delayed_write_keys = self.status_client.keys("DELAYED-WRITE*")
        return [x.decode() for x in delayed_write_keys]

    def write_cuboid_key_to_delayed_write_key(self, write_cuboid_key):
        """
        Method to convert a write-cuboid key to a delayed write key

        Returns:
            str:  delayed write key
        """
        temp_key = write_cuboid_key.split("&", 1)[1]
        temp_key = temp_key.rsplit("&", 1)[0]

        return "DELAYED-WRITE&{}".format(temp_key)

    def get_delayed_writes(self, delayed_write_key):
        """
        Method to get all delayed write-cuboid keys for a single delayed_write_key

        Returns:
            list(str): List of delayed write-cuboid keys
        """
        write_cuboid_key_list = []
        with self.status_client.pipeline() as pipe:
            try:
                # Get all items in the list and cleanup, in a transaction so other procs can't add anything
                pipe.watch(delayed_write_key)
                pipe.multi()

                # Get all items in the list
                pipe.lrange(delayed_write_key, 0, -1)

                # Delete the delayed-write-key as it should be empty now
                pipe.delete(delayed_write_key)

                # Delete its associated resource-delayed-write key that stores the resource string
                pipe.delete("RESOURCE-{}".format(delayed_write_key))

                # Execute.
                write_cuboid_key_list = pipe.execute()

                # If you got here things worked OK. Clean up the result. First entry in list is the LRANGE result
                write_cuboid_key_list = write_cuboid_key_list[0]

                # Keys are encoded
                write_cuboid_key_list = [x.decode() for x in write_cuboid_key_list]

            except redis.WatchError as _:
                # Watch error occurred. Just bail out and let the daemon pick this up later.
                return []

            except Exception as e:
                raise SpdbError("An error occurred while attempting to retrieve delay-write keys: \n {}".format(e),
                                ErrorCodes.REDIS_ERROR)

        return write_cuboid_key_list

    def check_single_delayed_write(self, delayed_write_key):
        """
        Method to get a single delayed write-cuboid key for a single delayed_write_key without popping it off the queue

        Returns:
            list(str): Single delayed write-cuboid keys
        """
        write_cuboid_key = self.status_client.lindex(delayed_write_key, 0)

        if write_cuboid_key:
            return write_cuboid_key.decode()
        else:
            return None

    def get_single_delayed_write(self, delayed_write_key):
        """
        Method to get a single delayed write-cuboid key for a single delayed_write_key without popping it off the queue

        Returns:
            list(str): Single delayed write-cuboid keys
        """
        write_cuboid_key = self.status_client.lpop(delayed_write_key)
        resource = self.status_client.get("RESOURCE-{}".format(delayed_write_key))

        if write_cuboid_key:
            return write_cuboid_key.decode(), resource.decode()
        else:
            return None

    def add_to_page_out(self, temp_page_out_key, lookup_key, resolution, morton, time_sample):
        """
        Method to add a key to the page-out tracking set

        Args:
            lookup_key (str): Lookup key for a channel
            resolution (int): level in the resolution heirarchy
            morton (int): morton id for the cuboid
            time_sample (int): time sample for cuboid

        Returns:
            (bool, bool): Tuple where first value is if the transaction succeeded and the second is if the key is in
            page out already
        """
        page_out_key = "PAGE-OUT&{}&{}".format(lookup_key, resolution)
        in_page_out = True
        cnt = 0
        with self.status_client.pipeline() as pipe:
            while 1:
                try:
                    # Create temp set
                    pipe.watch(page_out_key)
                    pipe.multi()
                    pipe.sadd(temp_page_out_key, "{}&{}".format(time_sample, morton))
                    pipe.expire(temp_page_out_key, 15)
                    pipe.sdiff(temp_page_out_key, page_out_key)
                    pipe.sadd(page_out_key, "{}&{}".format(time_sample, morton))
                    result = pipe.execute()

                    if len(result[2]) > 0:
                        in_page_out = False
                    else:
                        in_page_out = True

                    break
                except redis.WatchError as e:
                    # Watch error occurred, try again!
                    cnt += 1

                    if cnt > 200:
                        raise SpdbError("Failed to add to page out due to timeout. {}".format(e),
                                        ErrorCodes.REDIS_ERROR)
                    continue

                except Exception as e:
                    raise SpdbError("Failed to check page-out set. {}".format(e),
                                    ErrorCodes.REDIS_ERROR)

        return in_page_out

    def remove_from_page_out(self, write_cuboid_key):
        """
        Method to remove a key to from page-out tracking set

        Args:
            write_cuboid_key (str): the write cuboid key you want removed

        Returns:
            None
        """
        _, parts = write_cuboid_key.split("&", 1)
        parts, _ = parts.rsplit("&", 1)
        parts, morton = parts.rsplit("&", 1)
        parts, time_sample = parts.rsplit("&", 1)
        lookup, res = parts.rsplit("&", 1)

        page_out_key = "PAGE-OUT&{}&{}".format(lookup, res)
        self.status_client.srem(page_out_key, "{}&{}".format(time_sample, morton))
