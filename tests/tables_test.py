import unittest
from openquake.nrmllib import InvalidFile
from openquake.nrmllib.tables import MemTable, FileObject


class FakeTable(MemTable):
    def __init__(self, container, name):
        self.container = container
        self.name = name


class TableTestCase(unittest.TestCase):
    def test_getitem(self):
        tbl = MemTable.create('tbl', '<gmfSet/>', '''\
lon,lat,gmv
1.0,2.0,0.1
1.0,2.1,0.1
1.0,2.2,0.2
1.0,2.3,0.2
''')
        # test that a Table object support the bracket notation
        self.assertEqual(tbl[0],
                         {'lon': '1.0', 'lat': '2.0', 'gmv': '0.1'})
        self.assertEqual(tbl[1],
                         {'lon': '1.0', 'lat': '2.1', 'gmv': '0.1'})
        self.assertEqual(tbl[2:4],
                         [{'lon': '1.0', 'lat': '2.2', 'gmv': '0.2'},
                          {'lon': '1.0', 'lat': '2.3', 'gmv': '0.2'}])

    def test_get_all(self):
        # test the logic of the table generator, in particular the
        # `<groupname>__` convention in the name of the files to specify
        # files belonging to the same group
        # also test the lexicographic ordering of the tables
        fnames = ['a.csv', 'a.mdata',  # group of one pair
                  'x__1.mdata', 'x__1.csv', 'x__0.mdata', 'x__0.csv',  # group
                  'y.csv',  # unpaired file
                  'x__2.mdata',  # another unpaired file
                  'x__2.cs',  # ignored extension
                  ]
        got = []
        for groupname, tables in FakeTable.get_all(None, fnames):
            got.append((groupname, ' '.join(r.name for r in tables)))
        self.assertEqual(got, [('a', 'a'), ('x', 'x__0 x__1')])

    def test_get_all_invalid(self):
        # test the case when one of the files is invalid
        container = {
            'a.csv': FileObject('a.csv', ''),
            'a.mdata': FileObject('a.mdata', '')
        }
        self.assertEqual(list(MemTable.get_all(container)), [])
        # will print a UserWarning: a.mdata:Document is empty, line 1, column 1

    def test_could_not_extract_fieldnames(self):
        bad_metadata = '''\
<?xml version="1.0" encoding="utf-8"?>
<vulnerabilityModel>
    <discreteVulnerabilitySet
    assetCategory="population"
    lossCategory="fatalities"
    vulnerabilitySetID="NPAGER"
    >
        <IML IMT="MMI"/>
        <discreteVulnerability
        probabilisticDistribution="LN"
        vulnerabilityFunctionID="AA"
        >
            <lossRatio />
        </discreteVulnerability>
    </discreteVulnerabilitySet>
</vulnerabilityModel>
'''  # there is no coefficientsVariation node
        with self.assertRaises(InvalidFile) as e:
            MemTable.create('bad', bad_metadata, '')
            assert isinstance(e, ValueError), e