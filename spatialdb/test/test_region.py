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

from spdb.spatialdb.region import Region
import unittest

class TestRegion(unittest.TestCase):
    def test_get_cuboid_aligned_sub_region_cuboid_aligned(self):
        """Region already cuboid aligned case."""
        resolution = 0
        corner = (512, 1024, 32)
        extent = (1024, 512, 32)
        expected = Region.Cuboids(
            x_cuboids=range(1, 3),
            y_cuboids=range(2, 3),
            z_cuboids=range(2, 4)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_cuboid_aligned_sub_region_x_not_cuboid_aligned(self):
        """Region not cuboid aligned along x axis."""
        resolution = 0
        corner = (511, 1024, 32)
        extent = (1026, 512, 32)
        expected = Region.Cuboids(
            x_cuboids=range(1, 3),
            y_cuboids=range(2, 3),
            z_cuboids=range(2, 4)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_cuboid_aligned_sub_region_y_not_cuboid_aligned(self):
        """Region not cuboid aligned along y axis."""
        resolution = 0
        corner = (512, 1023, 32)
        extent = (1024, 514, 32)
        expected = Region.Cuboids(
            x_cuboids=range(1, 3),
            y_cuboids=range(2, 3),
            z_cuboids=range(2, 4)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_cuboid_aligned_sub_region_z_not_cuboid_aligned(self):
        """Region not cuboid aligned along z axis."""
        resolution = 0
        corner = (512, 1024, 15)
        extent = (1024, 512, 18)
        expected = Region.Cuboids(
            x_cuboids=range(1, 3),
            y_cuboids=range(2, 3),
            z_cuboids=range(1, 2)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_cuboid_aligned_sub_region_smaller_than_cuboid(self):
        """Requested region smaller than a cuboid."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (100, 50, 12)
        expected = Region.Cuboids(
            x_cuboids=range(1, 1),
            y_cuboids=range(2, 2),
            z_cuboids=range(1, 1)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_cuboid_aligned_sub_region_smaller_than_cuboid_within_first_cuboid(self):
        """Request region within the bounds of the first cuboid."""
        resolution = 0
        corner = (100, 50, 4)
        extent = (20, 20, 4)
        expected = Region.Cuboids(
            x_cuboids=range(0, -1),
            y_cuboids=range(0, -1),
            z_cuboids=range(0, -1)
        )
        actual = Region.get_cuboid_aligned_sub_region(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_near_side_none(self):
        """Near side cuboid aligned along z axis, so z extent is 0."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (1024, 512, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=(1024, 512, 0)
        )
        actual = Region.get_sub_region_x_y_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_near_side(self):
        """Near side non-cuboid aligned along z axis."""
        resolution = 0
        corner = (512, 1024, 14)
        extent = (1024, 512, 18)
        expected = Region.Bounds(
            corner=corner,
            extent=(1024, 512, 2)
        )
        actual = Region.get_sub_region_x_y_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_near_side_small_extents(self):
        """
        Near side non-cuboid aligned along z axis and extents less than a
        cuboid, but a cuboid boundary is crossed.
        """
        resolution = 0
        corner = (512, 490, 14)
        extent = (100, 100, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_x_y_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_near_side_less_than_cuboid(self):
        """Near side non-cuboid aligned along z axis - extents less than a cuboid."""
        resolution = 0
        corner = (512, 1024, 4)
        extent = (1024, 512, 10)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_x_y_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_near_side_less_than_cuboid2(self):
        """Cuboid aligned on near side but extents less than a cuboid."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (1024, 512, 10)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_x_y_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_far_side_none(self):
        """Far side cuboid aligned along z axis, so z extent is 0."""
        resolution = 0
        corner = (512, 1024, 14)
        extent = (1024, 512, 18)
        expected = Region.Bounds(
            corner=(corner[0], corner[1], 32),
            extent=(1024, 512, 0)
        )
        actual = Region.get_sub_region_x_y_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_far_side(self):
        """Far side non-cuboid aligned along z axis."""
        resolution = 0
        corner = (512, 1024, 18)
        extent = (1024, 512, 15)
        expected = Region.Bounds(
            corner=(corner[0], corner[1], 32),
            extent=(1024, 512, 1)
        )
        actual = Region.get_sub_region_x_y_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_y_block_far_side_less_than_cuboid(self):
        """
        Far side non-cuboid aligned along z axis - extents less than a cuboid.

        Expect a 0 width slice in the z dimension.  This case should be covered
        by Region.get_sub_region_x_y_block_near_side().
        """
        resolution = 0
        corner = (512, 1024, 17)
        extent = (1024, 512, 10)
        expected = Region.Bounds(
            corner=(corner[0], corner[1], 16),
            extent=(1024, 512, 0)
        )
        actual = Region.get_sub_region_x_y_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_near_side_none(self):
        """Near side cuboid aligned along y axis, so y extent is 0."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (1024, 512, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=(1024, 0, 16)
        )
        actual = Region.get_sub_region_x_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_near_side(self):
        """Near side non-cuboid aligned along y axis."""
        resolution = 0
        corner = (512, 1022, 16)
        extent = (1024, 514, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=(1024, 2, 16)
        )
        actual = Region.get_sub_region_x_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_near_side_small_extents(self):
        """
        Near side non-cuboid aligned along x axis and extents less than a
        cuboid, but a cuboid boundary is crossed.
        """
        resolution = 0
        corner = (512, 490, 14)
        extent = (100, 100, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_x_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_near_side_less_than_cuboid(self):
        """Near side non-cuboid aligned along y axis - extents less than a cuboid."""
        resolution = 0
        corner = (512, 100, 0)
        extent = (1024, 128, 32)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_x_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_near_side_less_than_cuboid2(self):
        """
        Near side non-cuboid aligned along y axis - extents less than a cuboid.
        This is the same as test_get_sub_region_x_z_block_far_side_less_than_cuboid(),
        but for the near side calculation, there should be non-zero extents.
        """
        resolution = 0
        corner = (512, 1024, 17)
        extent = (1024, 12, 50)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )

        actual = Region.get_sub_region_x_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_far_side_none(self):
        """Far side cuboid aligned along z axis, so z extent is 0."""
        resolution = 0
        corner = (512, 1023, 16)
        extent = (1024, 513, 20)
        expected = Region.Bounds(
            corner=(corner[0], 1536, corner[2]),
            extent=(1024, 0, 20)
        )
        actual = Region.get_sub_region_x_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_far_side(self):
        """Far side non-cuboid aligned along z axis."""
        resolution = 0
        corner = (512, 1024, 18)
        extent = (1024, 514, 16)
        expected = Region.Bounds(
            corner=(corner[0], 1536, corner[2]),
            extent=(1024, 2, 16)
        )
        actual = Region.get_sub_region_x_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_x_z_block_far_side_less_than_cuboid(self):
        """
        Far side non-cuboid aligned along z axis - extents less than a cuboid.

        Expect a 0 width slice in the z dimension.  This case should be covered
        by Region.get_sub_region_x_z_block_near_side().

        See test_get_sub_region_x_z_block_near_side_less_than_cuboid2().
        """
        resolution = 0
        corner = (512, 1024, 17)
        extent = (1024, 12, 50)
        expected = Region.Bounds(
            corner=(corner[0], 1024, corner[2]),
            extent=(1024, 0, 50)
        )
        actual = Region.get_sub_region_x_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_near_side_none(self):
        """Near side cuboid aligned along x axis, so x extent is 0."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (1024, 512, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=(0, 512, 16)
        )
        actual = Region.get_sub_region_y_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_near_side(self):
        """Near side non-cuboid aligned along x axis."""
        resolution = 0
        corner = (509, 1024, 14)
        extent = (1027, 512, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=(3, 512, 16)
        )
        actual = Region.get_sub_region_y_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_near_side_small_extents(self):
        """
        Near side non-cuboid aligned along x axis and extents less than a
        cuboid, but a cuboid boundary is crossed.
        """
        resolution = 0
        corner = (509, 1024, 14)
        extent = (100, 512, 16)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_y_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_near_side_less_than_cuboid(self):
        """Near side non-cuboid aligned along x axis - extents less than a cuboid."""
        resolution = 0
        corner = (400, 1024, 4)
        extent = (80, 512, 10)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_y_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_near_side_less_than_cuboid2(self):
        """Cuboid aligned on near side but extents less than a cuboid."""
        resolution = 0
        corner = (512, 1024, 16)
        extent = (200, 512, 10)
        expected = Region.Bounds(
            corner=corner,
            extent=extent
        )
        actual = Region.get_sub_region_y_z_block_near_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_far_side_none(self):
        """Far side cuboid aligned along x axis, so x extent is 0."""
        resolution = 0
        corner = (512, 1023, 16)
        extent = (1024, 513, 20)
        expected = Region.Bounds(
            corner=(1536, corner[1], corner[2]),
            extent=(0, extent[1], extent[2])
        )
        actual = Region.get_sub_region_y_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_far_side(self):
        """Far side non-cuboid aligned along x axis."""
        resolution = 0
        corner = (512, 1024, 18)
        extent = (1026, 514, 16)
        expected = Region.Bounds(
            corner=(1536, corner[1], corner[2]),
            extent=(2, extent[1], extent[2])
        )
        actual = Region.get_sub_region_y_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

    def test_get_sub_region_y_z_block_far_side_less_than_cuboid(self):
        """
        Far side non-cuboid aligned along x axis - extents less than a cuboid.

        Expect a 0 width slice in the x dimension.  This case should be covered
        by Region.get_sub_region_y_z_block_near_side().

        See test_get_sub_region_y_z_block_near_side_less_than_cuboid2().
        """
        resolution = 0
        corner = (512, 1024, 17)
        extent = (104, 12, 50)
        expected = Region.Bounds(
            corner=corner,
            extent=(0, extent[1], extent[2])
        )
        actual = Region.get_sub_region_y_z_block_far_side(resolution, corner, extent)

        self.assertEqual(expected, actual)

if __name__ == '__main__':
    unittest.main()
