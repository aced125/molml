import unittest
import os
import json
import warnings

import numpy

from molml.utils import get_dict_func_getter
from molml.utils import get_bond_type
from molml.utils import get_connections, get_depth_threshold_mask_connections
from molml.utils import get_graph_distance
from molml.utils import LazyValues, SMOOTHING_FUNCTIONS
from molml.utils import get_coulomb_matrix, get_element_pairs
from molml.utils import deslugify, _get_form_indices, get_index_mapping
from molml.utils import sort_chain, needs_reversal
from molml.utils import load_json


DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
ELEMENTS = ['C', 'H', 'H', 'H', 'H']
NUMBERS = [6, 1, 1, 1, 1]
COORDS = [
    [0.99826008, -0.00246000, -0.00436000],
    [2.09021016, -0.00243000, 0.00414000],
    [0.63379005, 1.02686007, 0.00414000],
    [0.62704006, -0.52773003, 0.87811010],
    [0.64136006, -0.50747003, -0.90540005],
]
CONNECTIONS = {
    0: {1: "1", 2: "1", 3: "1", 4: "1"},
    1: {0: "1"},
    2: {0: "1"},
    3: {0: "1"},
    4: {0: "1"},
}
UNIT_CELL = [
    [2., .1, 0.],
    [0., 1., 0.],
    [0., 0., 1.]
]


class UtilsTest(unittest.TestCase):

    def test_smoothing_functions(self):
        # These are mostly sanity checks for the functions
        expected = {
            "norm_cdf": numpy.array([0., 0.158655, 0.308538, 0.5, 0.691462,
                                     0.841345, 1.]),
            "zero_one": numpy.array([0., 0., 0., 0., 1., 1., 1.]),
            "expit": numpy.array([0., 0.268941, 0.377541, 0.5, 0.622459,
                                  0.731059, 1.]),
            "tanh": numpy.array([0., 0.11920292, 0.26894142, 0.5, 0.73105858,
                                 0.88079708, 1.]),
            "norm": numpy.array([0., 0.241971, 0.352065, 0.398942, 0.352065,
                                 0.241971, 0.]),
            "circ": numpy.array([0.220598, 0.215781, 0.302338, 0.34171,
                                 0.302338, 0.215781, 0.220598]),
            "expit_pdf": numpy.array([0., 0.196612, 0.235004, 0.25, 0.235004,
                                      0.196612, 0.]),
            "spike": numpy.array([0., 0., 1., 1., 1., 0., 0.]),
        }

        values = numpy.array([-1000., -1., -0.5, 0, 0.5, 1., 1000.])
        for key, expected_value in expected.items():
            with numpy.warnings.catch_warnings():
                numpy.warnings.filterwarnings('ignore', 'overflow')
                res = SMOOTHING_FUNCTIONS[key](values, 1.)
            try:
                numpy.testing.assert_array_almost_equal(
                    res,
                    expected_value)
            except AssertionError as e:
                self.fail(e)

    def test_smoothing_lerp(self):
        f = SMOOTHING_FUNCTIONS['lerp']
        # Note: this is slightly different from the others because lerp
        # depends on the spacing between the first two bins
        theta = numpy.linspace(1, 3, 3)
        pairs = [
            (0., numpy.array([0., 0., 0.])),
            (.4, numpy.array([0.4, 0., 0.])),
            (1., numpy.array([1., 0., 0.])),
            (1.3, numpy.array([.7, .3, 0.])),
            (2., numpy.array([0., 1., 0.])),
            (2.5, numpy.array([0., .5, .5])),
            (3., numpy.array([0., 0., 1.])),
            (3.3, numpy.array([0., 0., .7])),
        ]
        for off, expected in pairs:
            try:
                numpy.testing.assert_array_almost_equal(
                    f(theta - off, 1.),
                    expected)
            except AssertionError as e:
                self.fail(e)

    def test_get_dict_func_getter(self):
        f = get_dict_func_getter({'norm': lambda x: x})
        self.assertAlmostEqual(f('norm')(3), 3)

    def test_get_dict_func_getter_fails(self):
        f = get_dict_func_getter({})
        with self.assertRaises(KeyError):
            self.assertAlmostEqual(f('not_real')(3), 0.00)

    def test_get_dict_func_getter_callable(self):
        f = get_dict_func_getter({})
        self.assertAlmostEqual(f(lambda x: x)(3), 3)

    def test_get_coulomb_matrix(self):
        res = get_coulomb_matrix([1, 1], [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        expected_results = numpy.array([
            [0.5, 1.0],
            [1.0, 0.5]])
        try:
            numpy.testing.assert_array_almost_equal(
                res,
                expected_results)
        except AssertionError as e:
            self.fail(e)

    def test_get_coulomb_matrix_alpha(self):
        nums = [1, 1]
        coords = [[0.0, 0.0, 0.0], [0.0, 0.0, .5]]
        res = get_coulomb_matrix(nums, coords, alpha=2)
        expected_results = numpy.array([
            [0.5, 4.],
            [4., 0.5]])
        try:
            numpy.testing.assert_array_almost_equal(
                res,
                expected_results)
        except AssertionError as e:
            self.fail(e)

    def test_get_coulomb_matrix_use_decay(self):
        nums = [1, 1, 1]
        coords = [[0.0, 0.0, 0.0], [0.0, 0.0, .5], [0.0, 0.5, 0.0]]
        res = get_coulomb_matrix(nums, coords, use_decay=True)
        expected_results = numpy.array([
            [0.5, 1., 1.],
            [1., 0.5, 0.585786],
            [1., 0.585786, 0.5]])
        try:
            numpy.testing.assert_array_almost_equal(
                res,
                expected_results)
        except AssertionError as e:
            self.fail(e)

    def test_get_element_pairs(self):
        res = get_element_pairs(ELEMENTS)
        self.assertEqual(set(res), set([('C', 'H'), ('H', 'H')]))

    def test_deslugify(self):
        string = 'Class__int=1__float=1.__str=string'
        expected = ('Class', {'int': 1, 'float': 1., 'str': 'string'})
        self.assertEqual(deslugify(string), expected)

        string = 'ClassM__none=None__true=True__false=False'
        expected = ('ClassM', {'none': None, 'true': True, 'false': False})
        self.assertEqual(deslugify(string), expected)

    def test__get_form_indicies(self):
        data = (
            (  # 1
                (0, ([], False)),
                (1, ([0], False)),
                (2, ([0], False)),
            ),
            (  # 2
                (0, ([], False)),
                (1, ([0], True)),
                (2, ([0, 1], False)),
            ),
            (  # 3
                (0, ([], False)),
                (1, ([1], False)),
                (2, ([0, 2], False)),
                (3, ([0, 1, 2], False)),
            ),
            (  # 4
                (0, ([], False)),
                (1, ([1], True)),
                (2, ([1, 2], False)),
                (3, ([0, 1, 2], True)),
                (4, ([0, 1, 2, 3], False)),
            ),
            (  # 5
                (0, ([], False)),
                (1, ([2], False)),
                (2, ([1, 3], False)),
                (3, ([1, 2, 3], False)),
                (4, ([0, 1, 3, 4], False)),
                (5, ([0, 1, 2, 3, 4], False)),
            ),
            (  # 6
                (0, ([], False)),
                (1, ([2], True)),
                (2, ([2, 3], False)),
                (3, ([1, 2, 3], True)),
                (4, ([1, 2, 3, 4], False)),
                (5, ([0, 1, 2, 3, 4], True)),
                (6, ([0, 1, 2, 3, 4, 5], False)),
            )
        )
        for i, group in enumerate(data):
            values = [list(range(i + 1))]
            for depth, expected in group:
                vals = _get_form_indices(values, depth)
                self.assertEqual(vals, expected)

    def test__get_form_indicies_invalid(self):
        with self.assertRaises(ValueError):
            _get_form_indices([], 1)

    def test_get_index_mapping(self):
        values = [('H', 'H'), ('H', 'C'), ('C', 'C')]
        expected = (
            (0, 1, False, (0, 0, 0)),
            (1, 2, True, (1, 1, 0)),
            (2, 3, False, (2, 1, 0)),
            (3, 3, False, (2, 1, 0)),
        )
        for depth, expected_length, expected_both, idxs in expected:
            f, length, both = get_index_mapping(values, depth, False)
            self.assertEqual(length, expected_length)
            self.assertEqual(both, expected_both)
            self.assertEqual(tuple(f(x) for x in values), idxs)

    def test_get_index_mapping_add_unknown(self):
        values = [('H', 'H'), ('H', 'C'), ('C', 'C')]
        expected = (
            (0, 1, False, (0, 0, 0)),
            (1, 3, True, (1, 1, 0)),
            (2, 4, False, (2, 1, 0)),
            (3, 4, False, (2, 1, 0)),
            (1, 3, True, (1, 1, 0)),
            (2, 4, False, (2, 1, 0)),
        )
        for depth, expected_length, expected_both, idxs in expected:
            f, length, both = get_index_mapping(values, depth, True)
            self.assertEqual(length, expected_length)
            self.assertEqual(both, expected_both)
            self.assertEqual(tuple(f(x) for x in values), idxs)
            if not depth:
                self.assertEqual(f("NEW"), 0)
            else:
                self.assertEqual(f("NEW"), -1)

    def test_sort_chain(self):
        needs_flip = ("O", "H", "C")
        expected = ("C", "H", "O")
        self.assertEqual(sort_chain(needs_flip), expected)

        needs_flip = ("O", "H", "H", "C")
        expected = ("C", "H", "H", "O")
        self.assertEqual(sort_chain(needs_flip), expected)

    def test_needs_reversal(self):
        needs_flip = ("O", "H", "C")
        self.assertTrue(needs_reversal(needs_flip))

        needs_flip = ("O", "H", "H", "C")
        self.assertTrue(needs_reversal(needs_flip))

        no_flip = ("O", "H", "H", "O")
        self.assertFalse(needs_reversal(no_flip))

        no_flip = ("O", "C", "H", "O")
        self.assertFalse(needs_reversal(no_flip))

    def test_load_json(self):
        data = {'parameters': {'n_jobs': 2,
                               'input_type': 'list'},
                'attributes': {'_base_chains': [['H']]},
                'transformer': 'molml.molecule.Connectivity'}
        path = '/tmp/somefile.json'
        with open(path, 'w') as f:
            json.dump(data, f)

        with open(path, 'r') as f:
            for x in (path, f):
                m = load_json(path)
                self.assertEqual(m.__class__.__name__,
                                 data["transformer"].split('.')[-1])
                self.assertEqual(m.n_jobs, data["parameters"]["n_jobs"])
                self.assertEqual(m._base_chains,
                                 data["attributes"]["_base_chains"])

    def test_load_json_nested(self):
        # We will hack on connectivity a sub transformer on its `depth` param.
        data = {
            'parameters': {
                'n_jobs': 2,
                'depth': {
                    'parameters': {
                        'n_jobs': 3,
                        'input_type': 'list'},
                    'attributes': {'_base_chains': [['H']]},
                    'transformer': 'molml.molecule.Connectivity'},
                'input_type': 'list'},
            'attributes': {'_base_chains': [['H']]},
            'transformer': 'molml.molecule.Connectivity'
        }
        path = '/tmp/somefile.json'
        with open(path, 'w') as f:
            json.dump(data, f)

        m = load_json(path)
        self.assertEqual(m.__class__.__name__,
                         data["transformer"].split('.')[-1])
        self.assertEqual(m.n_jobs, data["parameters"]["n_jobs"])
        self.assertEqual(m._base_chains, data["attributes"]["_base_chains"])

        in_data = data["parameters"]["depth"]
        in_m = m.depth
        self.assertEqual(in_m.__class__.__name__,
                         in_data["transformer"].split('.')[-1])
        self.assertEqual(in_m.n_jobs, in_data["parameters"]["n_jobs"])
        self.assertEqual(in_m._base_chains,
                         in_data["attributes"]["_base_chains"])

    def test_get_connections(self):
        res = get_connections(ELEMENTS, COORDS)
        self.assertEqual(res, CONNECTIONS)

    def test_get_graph_distance(self):
        conn = {
            0: {1: '1'},
            1: {0: '1'},
            2: {3: '1'},
            3: {2: '1', 4: '1', 5: '1'},
            4: {3: '1', 5: '1'},
            5: {3: '1', 4: '1'},
        }
        inf = numpy.inf
        expected = numpy.array([
            [0, 1, inf, inf, inf, inf],
            [1, 0, inf, inf, inf, inf],
            [inf, inf, 0, 1, 2, 2],
            [inf, inf, 1, 0, 1, 1],
            [inf, inf, 2, 1, 0, 1],
            [inf, inf, 2, 1, 1, 0],
        ])
        res = get_graph_distance(conn)
        try:
            numpy.testing.assert_equal(res, expected)
        except AssertionError as e:
            self.fail(e)

    def test_get_connections_disjoint(self):
        coords2 = numpy.array(COORDS) + 1
        res = get_connections(ELEMENTS, COORDS, ELEMENTS, coords2)
        expected = {
            0: {4: '1'},
            1: {0: '1', 4: '1'},
            2: {4: '1'},
            3: {},
            4: {}
        }
        self.assertEqual(res, expected)

    def test_get_bond_type_warn(self):
        with warnings.catch_warnings(record=True) as w:
            get_bond_type('Fake', 'H', 1)
            get_bond_type('H', 'Not Real', 1)
            get_bond_type('Fake', 'Not Real', 1)
            self.assertEqual(len(w), 3)

    def test_get_depth_threshold_mask_connections_all(self):
        conn = {
            0: {1: '1'},
            1: {0: '1'},
            2: {3: '1'},
            3: {2: '1'},
        }
        res = get_depth_threshold_mask_connections(conn, max_depth=0)
        try:
            numpy.testing.assert_equal(res,
                                       numpy.ones((len(conn), len(conn))))
        except AssertionError as e:
            self.fail(e)

    def test_get_depth_threshold_mask_connections_disjoint(self):
        conn = {
            0: {1: '1'},
            1: {0: '1'},
            2: {3: '1'},
            3: {2: '1'},
        }
        res = get_depth_threshold_mask_connections(conn, min_depth=numpy.inf)
        expected = numpy.array([
            [False, False, True, True],
            [False, False, True, True],
            [True, True, False, False],
            [True, True, False, False],
        ])
        try:
            numpy.testing.assert_equal(res, expected)
        except AssertionError as e:
            self.fail(e)

    def test_get_depth_threshold_mask_connections_max(self):
        conn = {
            0: {1: '1'},
            1: {0: '1', 2: '1'},
            2: {1: '1', 3: '1'},
            3: {2: '1'},
        }
        res = get_depth_threshold_mask_connections(conn, max_depth=2)
        expected = numpy.array([
            [True, True, True, False],
            [True, True, True, True],
            [True, True, True, True],
            [False, True, True, True],
        ])
        try:
            numpy.testing.assert_equal(res, expected)
        except AssertionError as e:
            self.fail(e)

    def test_get_depth_threshold_mask_connections_min(self):
        conn = {
            0: {1: '1'},
            1: {0: '1', 2: '1'},
            2: {1: '1', 3: '1'},
            3: {2: '1'},
        }
        res = get_depth_threshold_mask_connections(conn, min_depth=2)
        expected = numpy.array([
            [False, False, True, True],
            [False, False, False, True],
            [True, False, False, False],
            [True, True, False, False],
        ])
        try:
            numpy.testing.assert_equal(res, expected)
        except AssertionError as e:
            self.fail(e)

    def test_get_depth_threshold_mask_connections_both(self):
        conn = {
            0: {1: '1'},
            1: {0: '1', 2: '1'},
            2: {1: '1', 3: '1'},
            3: {2: '1', 4: '1'},
            4: {3: '1'},
        }
        res = get_depth_threshold_mask_connections(conn, min_depth=2,
                                                   max_depth=2)
        expected = numpy.array([
            [False, False, True, False, False],
            [False, False, False, True, False],
            [True, False, False, False, True],
            [False, True, False, False, False],
            [False, False, True, False, False],
        ])
        try:
            numpy.testing.assert_equal(res, expected)
        except AssertionError as e:
            self.fail(e)


class LazyValuesTest(unittest.TestCase):

    def test_all(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS,
                       connections=CONNECTIONS, unit_cell=UNIT_CELL)
        self.assertEqual(a.elements.tolist(), ELEMENTS)
        self.assertEqual(a.coords.tolist(), COORDS)
        self.assertEqual(a.numbers.tolist(), NUMBERS)
        self.assertEqual(a.connections, CONNECTIONS)
        self.assertEqual(a.unit_cell.tolist(), UNIT_CELL)

    def test_num_from_ele(self):
        a = LazyValues(elements=ELEMENTS)
        self.assertEqual(a.numbers.tolist(), NUMBERS)

    def test_ele_from_num(self):
        a = LazyValues(numbers=NUMBERS)
        self.assertEqual(a.elements.tolist(), ELEMENTS)

    def test_no_coords(self):
        a = LazyValues(elements=ELEMENTS, numbers=NUMBERS)
        with self.assertRaises(ValueError):
            a.coords

    def test_no_unit_cell(self):
        a = LazyValues(elements=ELEMENTS, numbers=NUMBERS)
        with self.assertRaises(ValueError):
            a.unit_cell

    def test_no_ele_or_num(self):
        a = LazyValues(coords=COORDS)
        with self.assertRaises(ValueError):
            a.elements
        with self.assertRaises(ValueError):
            a.numbers

    def test_connections(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS)
        self.assertEqual(a.connections, CONNECTIONS)

    def test_fill_in_crystal(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS,
                       connections=CONNECTIONS, unit_cell=UNIT_CELL)
        a.fill_in_crystal(radius=1.)
        length = 3
        self.assertEqual(a.elements.tolist(), ELEMENTS * length)
        expected_results = numpy.array([
            [0.99826008, -0.00246000, -1.00436000],
            [2.09021016, -0.00243000, -0.99586000],
            [0.63379005,  1.02686007, -0.99586000],
            [0.62704006, -0.52773003, -0.12188990],
            [0.64136006, -0.50747003, -1.90540005],
            [0.99826008, -0.00246000, -0.00436000],
            [2.09021016, -0.00243000,  0.00414000],
            [0.63379005,  1.02686007,  0.00414000],
            [0.62704006, -0.52773003,  0.87811010],
            [0.64136006, -0.50747003, -0.90540005],
            [0.99826008, -0.00246000,  0.99564000],
            [2.09021016, -0.00243000,  1.00414000],
            [0.63379005,  1.02686007,  1.00414000],
            [0.62704006, -0.52773003,  1.87811010],
            [0.64136006, -0.50747003,  0.09459995],
        ])
        try:
            numpy.testing.assert_array_almost_equal(
                a.coords,
                expected_results)
        except AssertionError as e:
            self.fail(e)
        self.assertEqual(a.numbers.tolist(), NUMBERS * length)

    def test_fill_in_crystal_units(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS,
                       connections=CONNECTIONS, unit_cell=UNIT_CELL)
        a.fill_in_crystal(units=1)
        length = 3 * 3 * 3
        self.assertEqual(a.elements.tolist(), ELEMENTS * length)
        self.assertEqual(a.numbers.tolist(), NUMBERS * length)

    def test_fill_in_crystal_units_list(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS,
                       connections=CONNECTIONS, unit_cell=UNIT_CELL)
        a.fill_in_crystal(units=[1, 2, 3])
        length = 3 * 5 * 7
        self.assertEqual(a.elements.tolist(), ELEMENTS * length)
        self.assertEqual(a.numbers.tolist(), NUMBERS * length)

    def test_fill_in_crystal_units_list_invalid(self):
        a = LazyValues(elements=ELEMENTS, coords=COORDS, numbers=NUMBERS,
                       connections=CONNECTIONS, unit_cell=UNIT_CELL)
        with self.assertRaises(ValueError):
            a.fill_in_crystal(units=[1, 2, 3, 4])

        with self.assertRaises(ValueError):
            a.fill_in_crystal(units=[1, 2])

        with self.assertRaises(ValueError):
            a.fill_in_crystal(units=[1, 2], radius=2)

    def test_fill_in_crystal_conn(self):
        eles = ['H']
        coords = numpy.array([[0.0, 0.0, 0.0]])
        nums = [1]
        connections = {0: {}}
        unit_cell = numpy.array([[1., 0, 0],
                                 [0, 1., 0],
                                 [0, 0, 1.]])
        a = LazyValues(elements=eles, coords=coords, numbers=nums,
                       connections=connections, unit_cell=unit_cell)
        a.fill_in_crystal(radius=1.)
        self.assertEqual(a.elements.tolist(), eles * 7)
        expected = {
            0: {3: '1'},
            1: {3: '1'},
            2: {3: '1'},
            3: {0: '1', 1: '1', 2: '1', 4: '1', 5: '1', 6: '1'},
            4: {3: '1'},
            5: {3: '1'},
            6: {3: '1'},
        }
        self.assertEqual(a.connections, expected)

    def test_fill_in_crystal_null(self):
        a = LazyValues()
        with self.assertRaises(ValueError):
            a.fill_in_crystal(radius=1.)

        a = LazyValues(unit_cell=UNIT_CELL)
        with self.assertRaises(ValueError):
            a.fill_in_crystal(radius=1.)

        length = 3
        a = LazyValues(numbers=NUMBERS, coords=COORDS, unit_cell=UNIT_CELL)
        a.fill_in_crystal(radius=1.)
        self.assertEqual(a.numbers.tolist(), NUMBERS * length)

        a = LazyValues(elements=ELEMENTS, coords=COORDS, unit_cell=UNIT_CELL)
        a.fill_in_crystal(radius=1.)
        self.assertEqual(a.elements.tolist(), ELEMENTS * length)


if __name__ == '__main__':
    unittest.main()
