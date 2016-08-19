# Copyright 2016 The Johns Hopkins University Applied Physics Laboratory
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from .resource import BossResource, Collection, CoordinateFrame, Experiment, Channel, Layer


class BossResourceDjango(BossResource):
    """
    Resource class for when using SPDB within a Django app.  It takes a BossRequest as an input to the constructor,
    and from this is able to populate all values as needed.

     Args:
      boss_request (BossRequest): BossRequest instance that has already validated a request

    Attributes:
      boss_request (BossRequest): BossRequest instance that has already validated a request
    """
    def __init__(self, boss_request):
        super().__init__()

        self.boss_request = boss_request

    def to_dict(self):
        """
        Method to convert a resource to a dictionary
        Returns:
            (dict): a dict of all the parameters
        """
        # Populate everything
        self.populate_collection()
        self.populate_coord_frame()
        self.populate_experiment()
        self.populate_channel_or_layer()
        self.populate_boss_key()
        self.populate_lookup_key()

        # Collect Data
        data = {"collection": self._collection.__dict__,
                "coord_frame": self._coord_frame.__dict__,
                "experiment": self._experiment.__dict__,
                "boss_key": self._boss_key,
                "lookup_key": self._lookup_key,
                }

        if self._channel:
            data['channel_layer'] = self._channel.__dict__
            data['channel_layer']['is_channel'] = True
        else:
            data['channel_layer'] = self._layer.__dict__
            data['channel_layer']['is_channel'] = False
            data['channel_layer']['parent_channels'] = [x for x in self._layer.parent_channels.all()]

        # Serialize and return
        return data

    # Methods to populate class properties
    def populate_collection(self):
        """
        Method to create a Collection instance and set self._collection.
        """
        self._collection = Collection(self.boss_request.collection.name,
                                      self.boss_request.collection.description)

    def populate_coord_frame(self):
        """
        Method to create a CoordinateFrame instance and set self._coord_frame.
        """
        self._coord_frame = CoordinateFrame(self.boss_request.coord_frame.name,
                                            self.boss_request.coord_frame.description,
                                            self.boss_request.coord_frame.x_start,
                                            self.boss_request.coord_frame.x_stop,
                                            self.boss_request.coord_frame.y_start,
                                            self.boss_request.coord_frame.y_stop,
                                            self.boss_request.coord_frame.z_start,
                                            self.boss_request.coord_frame.z_stop,
                                            self.boss_request.coord_frame.x_voxel_size,
                                            self.boss_request.coord_frame.y_voxel_size,
                                            self.boss_request.coord_frame.z_voxel_size,
                                            self.boss_request.coord_frame.voxel_unit,
                                            self.boss_request.coord_frame.time_step,
                                            self.boss_request.coord_frame.time_step_unit)

    def populate_experiment(self):
        """
        Method to create a Experiment instance and set self._experiment.
        """
        self._experiment = Experiment(self.boss_request.experiment.name,
                                      self.boss_request.experiment.description,
                                      self.boss_request.experiment.num_hierarchy_levels,
                                      self.boss_request.experiment.hierarchy_method,
                                      self.boss_request.experiment.max_time_sample)

    def populate_channel_or_layer(self):
        """
        Method to create a Channel or Layer instance and set self._channel or self._layer.
        """
        if self.boss_request.channel_layer.is_channel:
            # You have a channel request
            self._channel = Channel(self.boss_request.channel_layer.name,
                                    self.boss_request.channel_layer.description,
                                    self.boss_request.channel_layer.datatype)
        else:
            # You have a layer request
            if self.boss_request.channel_layer.linked_channel_layers:
                linked_channels = self.boss_request.channel_layer.linked_channel_layers
            else:
                linked_channels = None
            self._layer = Layer(self.boss_request.channel_layer.name,
                                self.boss_request.channel_layer.description,
                                self.boss_request.channel_layer.datatype,
                                self.boss_request.channel_layer.base_resolution,
                                linked_channels)

    def populate_boss_key(self):
        """
        Method to set self._boss_key.
        """
        self._boss_key = self.boss_request.get_boss_key()

    def populate_lookup_key(self):
        """
        Method to set self._lookup_key.  Should be overridden.
        """
        self._lookup_key = self.boss_request.get_lookup_key()

    # Methods to delete the entry from the data model tables
    def delete_collection_model(self):
        pass

    def delete_experiment_model(self):
        pass

    def delete_coord_frame_model(self):
        pass

    def delete_channel_layer_model(self):
        pass

