# -*- coding: utf-8 -*-

# Copyright (C) 2012-2014 Geoscience Australia

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=C0103
# Since function names are based on what they are testing,
# and if they are testing classes the function names will have capitals
# C0103: 16:TestCalcs.test_AddTest: Invalid name "test_AddTest"
# (should match [a-z_][a-z0-9_]{2,50}$)
# pylint: disable=R0904
# Disable too many public methods for test cases

"""
Test the workflow module.
"""

import unittest
import tempfile
import os
import numpy

from scipy import allclose, asarray, array

from core_hazimp import workflow
from core_hazimp import misc
from core_hazimp.workflow import (ConfigPipeLineBuilder, Context, EX_LAT,
                                  EX_LONG)
from core_hazimp.calcs.calcs import CALCS
from core_hazimp.jobs.jobs import JOBS, LOADCSVEXPOSURE
from core_hazimp import parallel


class TestWorkFlow(unittest.TestCase):
    """
    Test the workflow module
    """

    def test_ContextAwareBuilder(self):
        a_test = 5
        b_test = 2
        Cab = ConfigPipeLineBuilder()
        calc_list = [CALCS['add_test'], CALCS['multiply_test'],
                     CALCS['constant_test']]
        context = Context()
        context.exposure_att = {'a_test': a_test, 'b_test': b_test}
        pipeline = Cab.build(calc_list)
        config = {'constant_test': {'constant': 5}}
        pipeline.run(context, config)
        self.assertEqual(context.exposure_att['d_test'], 35)

    def test_Job_ContextAwareBuilder(self):

        # Write a file to test
        f = tempfile.NamedTemporaryFile(suffix='.txt',
                                        prefix='test_Job_ContextAwareBuilder',
                                        delete=False)
        f.write('exposure_latitude, exposure_longitude, a_test, b_test\n')
        f.write('1., 2., 3., 30.\n')
        f.write('4., 5., 6., 60.\n')
        f.close()
        f2 = tempfile.NamedTemporaryFile(suffix='.csv',
                                         prefix='test_Job_ContextAwareBuilder',
                                         delete=False)
        f2.close()

        Cab = ConfigPipeLineBuilder()
        calc_list = [JOBS[LOADCSVEXPOSURE], CALCS['add_test']]
        context = Context()

        pipeline = Cab.build(calc_list)
        config = {'constant_test': {'c_test': [5., 2.]},
                  LOADCSVEXPOSURE: {'file_name': f.name}}
        pipeline.run(context, config)
        cont_dict = context.save_exposure_atts(f2.name)
        os.remove(f2.name)
        if parallel.STATE.rank == 0:
            results = cont_dict['c_test']
            actual = asarray([33., 66.])
            self.assertTrue(allclose(actual,
                                     results), 'actual:' + str(actual) +
                            '\n results:' + str(results))
        os.remove(f.name)

    def test_Job_title_fix_ContextAwareBuilder(self):

        # Write a file to test
        f = tempfile.NamedTemporaryFile(suffix='.csv',
                                        prefix='test_Job_title_fix_Co',
                                        delete=False)
        f.write('LAT, LONG, a_test, b_test,BUILDING\n')
        f.write('1., 2., 3., 30.,TAB\n')
        f.write('4., 5., 6., 60.,DSG\n')
        f.close()
        f2 = tempfile.NamedTemporaryFile(suffix='.csv',
                                         prefix='test_Job_title_fix_Co',
                                         delete=False)
        f2.close()

        Cab = ConfigPipeLineBuilder()
        calc_list = [JOBS[LOADCSVEXPOSURE], CALCS['add_test']]
        context = Context()

        pipeline = Cab.build(calc_list)
        config = {'constant_test': {'c_test': [5., 2.]},
                  LOADCSVEXPOSURE: {'file_name': f.name,
                                    workflow.EX_LAT: 'LAT',
                                    workflow.EX_LONG: 'LONG'}}
        pipeline.run(context, config)
        cont_dict = context.save_exposure_atts(f2.name)
        os.remove(f2.name)
        if parallel.STATE.rank == 0:
            self.assertTrue(allclose(cont_dict['c_test'],
                                     asarray([33., 66.])))
            self.assertEqual(cont_dict['BUILDING'].tolist(),
                             ['TAB', 'DSG'])
        os.remove(f.name)

    def test_save_exposure_atts(self):

        # Write a file to test
        f = tempfile.NamedTemporaryFile(suffix='.npz',
                                        prefix='test_save_exposure_atts',
                                        delete=False)
        f.close()

        con = workflow.Context()
        actual = {'shoes': array([10., 11]),
                  'depth': array([[5., 3.], [2., 4]]),
                  misc.INTID: array([0, 1, 2])}
        con.exposure_att = actual
        lat = array([1, 2.])
        con.exposure_lat = lat
        lon = array([10., 20.])
        con.exposure_long = lon
        con.save_exposure_atts(f.name, use_parallel=False)
        exp_dict = numpy.load(f.name)

        actual[EX_LONG] = lon
        actual[EX_LAT] = lat
        for keyish in exp_dict.files:
            self.assertTrue(allclose(exp_dict[keyish],
                                     actual[keyish]))
        os.remove(f.name)

    def test_save_exposure_attsII(self):

        # Write a file to test
        f = tempfile.NamedTemporaryFile(suffix='.csv',
                                        prefix='test_save_exposure_atts',
                                        delete=False)
        f.close()
        con = workflow.Context()
        actual = {'shoes': array([10., 11, 12]),
                  'depth': array([[5., 4., 3.], [3., 2, 1], [30., 20, 10]]),
                  misc.INTID: array([0, 1, 2])}
        con.exposure_att = actual
        lat = array([1, 2., 3])
        con.exposure_lat = lat
        lon = array([10., 20., 30])
        con.exposure_long = lon
        con.save_exposure_atts(f.name, use_parallel=False)
        exp_dict = misc.csv2dict(f.name)

        actual[EX_LONG] = lon
        actual[EX_LAT] = lat
        actual['depth'] = array([4, 2, 20])
        for key in exp_dict:
            self.assertTrue(allclose(exp_dict[key],
                                     actual[key]))
        os.remove(f.name)


#-------------------------------------------------------------
if __name__ == "__main__":
    Suite = unittest.makeSuite(TestWorkFlow, 'test')
    #Suite = unittest.makeSuite(TestWorkFlow, '')
    Runner = unittest.TextTestRunner()
    Runner.run(Suite)
