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

from spdb.spatialdb.object_indices import ObjectIndices

from bossutils.aws import get_region
import numpy as np
from spdb.c_lib.ndlib import XYZMorton
from spdb.c_lib.ndtype import CUBOIDSIZE
from spdb.project import BossResourceBasic
from spdb.project.test.resource_setup import get_anno_dict
from spdb.spatialdb.object import AWSObjectStore
from spdb.spatialdb import SpatialDB
from spdb.spatialdb.cube import Cube
import unittest
from unittest.mock import patch
import random

from bossutils import configuration

from spdb.project import BossResourceBasic
from spdb.spatialdb.test.setup import SetupTests
from spdb.spatialdb.error import SpdbError


class ObjectIndicesTestMixin(object):
    def setUp(self):
        # Randomize the look-up key so tests don't mess with each other
        self.resource._lookup_key = "1&2&{}".format(random.randint(4, 1000))

    def test_make_ids_strings_ignore_zeros(self):
        zeros = np.zeros(4, dtype='uint64')
        expected = []
        actual = self.obj_ind._make_ids_strings(zeros)
        self.assertEqual(expected, actual)

    def test_make_ids_strings_mix(self):
        arr = np.zeros(4, dtype='uint64')
        arr[0] = 12345
        arr[2] = 9876

        expected = ['12345', '9876']
        actual = self.obj_ind._make_ids_strings(arr)
        self.assertEqual(expected, actual)

    def test_update_id_indices_ignores_zeros(self):
        """
        Never send id 0 to the DynamoDB id index or cuboid index!  Since
        0 is the default value before an id is assigned to a voxel, this
        would blow way past DynamoDB limits.
        """

        resolution = 0
        version = 0
        _id = 300
        id_str_list = ['{}'.format(_id)]
        cube_data = np.zeros(5, dtype='uint64')
        cube_data[2] = _id
        key = 'some_obj_key'

        exp_channel_key = self.obj_ind.generate_channel_id_key(self.resource, resolution, _id)

        with patch.object(self.obj_ind.dynamodb, 'update_item') as mock_update_item:
            mock_update_item.return_value = {
                'ResponseMetadata': { 'HTTPStatusCode': 200 }
            }
            self.obj_ind.update_id_indices(self.resource, resolution, [key], [cube_data], version)

            # Expect only 2 calls because there's only 1 non-zero id.
            self.assertEqual(2, mock_update_item.call_count)

            # First call should update s3 cuboid index.
            kall0 = mock_update_item.mock_calls[0]
            _, _, kwargs0 = kall0
            self.assertEqual(id_str_list, kwargs0['ExpressionAttributeValues'][':ids']['NS'])

            # Second call should update id index.
            kall1 = mock_update_item.mock_calls[1]
            _, _, kwargs1 = kall1
            self.assertEqual(exp_channel_key, kwargs1['Key']['channel-id-key']['S'])

            
    def test_get_loose_bounding_box(self):
        # Only need for the AWSObjectStore's generate_object_key() method, so
        # can provide dummy values to initialize it.
        with patch('spdb.spatialdb.object.get_region') as fake_get_region:
            # Force us-east-1 region for testing.
            fake_get_region.return_value = 'us-east-1'
            obj_store = AWSObjectStore(self.object_store_config)

        resolution = 0
        time_sample = 0

        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]

        pos0 = [4, 4, 4]
        pos1 = [2, 1, 3]
        pos2 = [6, 7, 5]

        mort0 = XYZMorton(pos0)
        mort1 = XYZMorton(pos1)
        mort2 = XYZMorton(pos2)


        key0 = obj_store.generate_object_key(self.resource, resolution, time_sample, mort0)
        key1 = obj_store.generate_object_key(self.resource, resolution, time_sample, mort1)
        key2 = obj_store.generate_object_key(self.resource, resolution, time_sample, mort2)

        id = 2234

        with patch.object(self.obj_ind, 'get_cuboids') as fake_get_cuboids:
            fake_get_cuboids.return_value = [key0, key1, key2]
            actual = self.obj_ind.get_loose_bounding_box(self.resource, resolution, id)
            expected = {
                'x_range': [2*x_cube_dim, (6+1)*x_cube_dim],
                'y_range': [1*y_cube_dim, (7+1)*y_cube_dim],
                'z_range': [3*z_cube_dim, (5+1)*z_cube_dim],
                't_range': [0, 1]
            }
            self.assertEqual(expected, actual)

    def test_get_loose_bounding_box_not_found(self):
        """Make sure None returned if id is not in channel."""
        resolution = 0
        time_sample = 0
        id = 2234

        with patch.object(self.obj_ind, 'get_cuboids') as fake_get_cuboids:
            fake_get_cuboids.return_value = []
            actual = self.obj_ind.get_loose_bounding_box(
                self.resource, resolution, id)
            expected = None
            self.assertEqual(expected, actual)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_x_axis_single_cuboid(self, mock_spdb):
        """Loose bounding box only spans a single cuboid."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][7][128][10] = id
        cube.data[0][7][128][11] = id
        cube.data[0][7][128][12] = id
        mock_spdb.cutout.return_value = cube

        expected = (10, 12)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_x_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(1, mock_spdb.cutout.call_count)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_x_axis_multiple_cuboids(self, mock_spdb):
        """Loose bounding box spans multiple cuboids."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, 2*x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][7][128][10] = id
        cube.data[0][7][128][11] = id
        cube.data[0][7][128][12] = id

        cube2 = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube2.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube2.data[0][7][128][3] = id
        cube2.data[0][7][128][4] = id

        # Return cube on the 1st call to cutout and cube2 on the 2nd call.
        mock_spdb.cutout.side_effect = [cube, cube2]

        expected = (10, 516)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_x_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(2, mock_spdb.cutout.call_count)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_y_axis_single_cuboid(self, mock_spdb):
        """Loose bounding box only spans a single cuboid."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][7][200][10] = id
        cube.data[0][7][201][10] = id
        cube.data[0][7][202][10] = id
        mock_spdb.cutout.return_value = cube

        expected = (200, 202)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_y_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(1, mock_spdb.cutout.call_count)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_y_axis_multiple_cuboids(self, mock_spdb):
        """Loose bounding box spans multiple cuboids."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, 2*y_cube_dim]
        z_rng = [0, z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][7][509][11] = id
        cube.data[0][7][510][11] = id
        cube.data[0][7][511][11] = id

        cube2 = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube2.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube2.data[0][7][0][11] = id
        cube2.data[0][7][1][11] = id

        # Return cube on the 1st call to cutout and cube2 on the 2nd call.
        mock_spdb.cutout.side_effect = [cube, cube2]

        expected = (509, 513)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_y_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(2, mock_spdb.cutout.call_count)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_z_axis_single_cuboid(self, mock_spdb):
        """Loose bounding box only spans a single cuboid."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][12][200][10] = id
        cube.data[0][13][200][10] = id
        cube.data[0][14][200][10] = id
        mock_spdb.cutout.return_value = cube

        expected = (12, 14)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_z_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(1, mock_spdb.cutout.call_count)

    def test_create_id_counter_key(self):
        self.resource._lookup_key = "1&2&3"
        key = self.obj_ind.generate_reserve_id_key(self.resource)
        self.assertEqual(key, '14a343245e1adb6297e43c12e22770ad&1&2&3')

    def test_reserve_id_wrong_type(self):
        img_data = self.setup_helper.get_image8_dict()
        img_resource = BossResourceBasic(img_data)

        with self.assertRaises(SpdbError):
            start_id = self.obj_ind.reserve_ids(img_resource, 10)

    @patch('spdb.spatialdb.SpatialDB', autospec=True)
    def test_tight_bounding_box_z_axis_multiple_cuboids(self, mock_spdb):
        """Loose bounding box spans multiple cuboids."""
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, 2*z_cube_dim]
        t_rng = [0, 1]

        cube = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube.data[0][13][509][11] = id
        cube.data[0][14][509][11] = id
        cube.data[0][15][509][11] = id

        cube2 = Cube.create_cube(
            self.resource, (x_cube_dim, y_cube_dim, z_cube_dim))
        cube2.data = np.zeros((1, z_cube_dim, y_cube_dim, x_cube_dim))
        cube2.data[0][0][509][11] = id
        cube2.data[0][1][509][11] = id

        # Return cube on the 1st call to cutout and cube2 on the 2nd call.
        mock_spdb.cutout.side_effect = [cube, cube2]

        expected = (13, 17)

        # Method under test.
        actual = self.obj_ind._get_tight_bounding_box_z_axis(
            mock_spdb.cutout, self.resource, resolution, id,
            x_rng, y_rng, z_rng, t_rng)

        self.assertEqual(expected, actual)
        self.assertEqual(2, mock_spdb.cutout.call_count)

    def test_get_tight_bounding_box_ranges(self):
        """Ensure that ranges are Python style ranges: [x, y).

        In other words, make sure the max indices are incremented by 1.
        """
        resolution = 0
        [x_cube_dim, y_cube_dim, z_cube_dim] = CUBOIDSIZE[resolution]
        id = 12345
        x_rng = [0, x_cube_dim]
        y_rng = [0, y_cube_dim]
        z_rng = [0, 2*z_cube_dim]
        t_rng = [0, 1]

        # Don't need real one because will provide fake
        # _get_tight_bounding_box_*_axis().
        cutout_fcn = None

        with patch.object(self.obj_ind, '_get_tight_bounding_box_x_axis') as fake_get_x_axis:
            with patch.object(self.obj_ind, '_get_tight_bounding_box_y_axis') as fake_get_y_axis:
                with patch.object(self.obj_ind, '_get_tight_bounding_box_z_axis') as fake_get_z_axis:
                    x_min_max = (35, 40)
                    y_min_max = (100, 105)
                    z_min_max = (22, 26)

                    fake_get_x_axis.return_value = x_min_max
                    fake_get_y_axis.return_value = y_min_max
                    fake_get_z_axis.return_value = z_min_max

                    actual = self.obj_ind.get_tight_bounding_box(
                        cutout_fcn, self.resource, resolution, id,
                        x_rng, y_rng, z_rng, t_rng)

                    self.assertIn('x_range', actual)
                    self.assertIn('y_range', actual)
                    self.assertIn('z_range', actual)
                    self.assertIn('t_range', actual)
                    self.assertEqual(x_min_max[0], actual['x_range'][0])
                    self.assertEqual(1+x_min_max[1], actual['x_range'][1])
                    self.assertEqual(y_min_max[0], actual['y_range'][0])
                    self.assertEqual(1+y_min_max[1], actual['y_range'][1])
                    self.assertEqual(z_min_max[0], actual['z_range'][0])
                    self.assertEqual(1+z_min_max[1], actual['z_range'][1])
                    self.assertEqual(t_rng, actual['t_range'])

class TestObjectIndices(ObjectIndicesTestMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """ Create a diction of configuration values for the test resource. """
        # Create resource
        cls.setup_helper = SetupTests()
        cls.data = cls.setup_helper.get_anno64_dict()
        cls.resource = BossResourceBasic(cls.data)

        # Load config
        cls.config = configuration.BossConfig()
        cls.object_store_config = {"s3_flush_queue": 'https://mytestqueue.com',
                                   "cuboid_bucket": "test_bucket",
                                   "page_in_lambda_function": "page_in.test.boss",
                                   "page_out_lambda_function": "page_out.test.boss",
                                   "s3_index_table": "test_s3_table",
                                   "id_index_table": "test_id_table",
                                   "id_count_table": "test_count_table",
                                   }

        # Create AWS Resources needed for tests while mocking
        cls.setup_helper.start_mocking()
        cls.setup_helper.create_index_table(cls.object_store_config["id_count_table"], cls.setup_helper.ID_COUNT_SCHEMA)

        cls.obj_ind = ObjectIndices(cls.object_store_config["s3_index_table"],
                                    cls.object_store_config["id_index_table"],
                                    cls.object_store_config["id_count_table"],
                                    'us-east-1')

    @classmethod
    def tearDownClass(cls):
        cls.setup_helper.stop_mocking()

if __name__ == '__main__':
    unittest.main()

