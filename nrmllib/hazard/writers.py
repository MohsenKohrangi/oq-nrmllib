# Copyright (c) 2010-2012, GEM Foundation.
#
# NRML is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# NRML is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with NRML.  If not, see <http://www.gnu.org/licenses/>.

"""
Classes for serializing various NRML XML artifacts.
"""

from lxml import etree
from collections import OrderedDict

import nrmllib
from nrmllib import utils


SM_TREE_PATH = 'sourceModelTreePath'
GSIM_TREE_PATH = 'gsimTreePath'

#: Maps XML writer constructor keywords to XML attribute names
_ATTR_MAP = OrderedDict([
    ('statistics', 'statistics'),
    ('quantile_value', 'quantileValue'),
    ('smlt_path', 'sourceModelTreePath'),
    ('gsimlt_path', 'gsimTreePath'),
    ('imt', 'IMT'),
    ('investigation_time', 'investigationTime'),
    ('sa_period', 'saPeriod'),
    ('sa_damping', 'saDamping'),
    ('poe', 'poE'),
    ('lon', 'lon'),
    ('lat', 'lat'),
])


def _validate_hazard_metadata(md):
    """
    Validate metadata `dict` of attributes, which are more or less the same for
    hazard curves, hazard maps, and disaggregation histograms.

    :param dict md:
        `dict` which can contain the following keys:

        * statistics
        * gsimlt_path
        * smlt_path
        * imt
        * sa_period
        * sa_damping

    :raises:
        :exc:`ValueError` if the metadata is not valid.
    """
    if (md.get('statistics') is not None
        and (md.get('smlt_path') is not None
             or md.get('gsimlt_path') is not None)):
        raise ValueError('Cannot specify both `statistics` and logic tree '
                         'paths')

    if md.get('statistics') is not None:
        # make sure only valid statistics types are specified
        if md.get('statistics') not in ('mean', 'quantile'):
            raise ValueError('`statistics` must be either `mean` or '
                             '`quantile`')
    else:
        # must specify both logic tree paths
        if md.get('smlt_path') is None or md.get('gsimlt_path') is None:
            raise ValueError('Both logic tree paths are required for '
                             'non-statistical results')

    if md.get('statistics') == 'quantile':
        if md.get('quantile_value') is None:
            raise ValueError('quantile stastics results require a quantile'
                             ' value to be specified')

    if not md.get('statistics') == 'quantile':
        if md.get('quantile_value') is not None:
            raise ValueError('Quantile value must be specified with '
                             'quantile statistics')

    if md.get('imt') == 'SA':
        if md.get('sa_period') is None:
            raise ValueError('`sa_period` is required for IMT == `SA`')
        if md.get('sa_damping') is None:
            raise ValueError('`sa_damping` is required for IMT == `SA`')


def _set_metadata(element, metadata, attr_map, transform=str):
    """
    Set metadata attributes on a given ``element``.

    :param element:
        :class:`lxml.etree._Element` instance
    :param metadata:
        Dictionary of metadata items containing attribute data for ``element``.
    :param attr_map:
        Dictionary mapping of metadata key->attribute name.
    :param transform:
        A function accepting and returning a single value to be applied to each
        attribute value. Defaults to `str`.
    """
    for kw, attr in attr_map.iteritems():
        value = metadata.get(kw)
        if value is not None:
            element.set(attr, transform(value))


class HazardCurveXMLWriter(object):
    """
    :param path:
        File path (including filename) for XML results to be saved to.
    :param metadata:
        The following keyword args are required:

        * investigation_time: Investigation time (in years) defined in the
          calculation which produced these results.
        * imt: Intensity measure type used to compute these hazard curves.
        * imls: Intensity measure levels, which represent the x-axis values of
          each curve.

        The following are more or less optional (combinational rules noted
        below where applicable):

        * statistics: 'mean' or 'quantile'
        * quantile_value: Only required if statistics = 'quantile'.
        * smlt_path: String representing the logic tree path which produced
          these curves. Only required for non-statistical curves.
        * gsimlt_path: String represeting the GSIM logic tree path which
          produced these curves. Only required for non-statisical curves.
        * sa_period: Only used with imt = 'SA'.
        * sa_damping: Only used with imt = 'SA'.
    """

    def __init__(self, path, **metadata):
        self.path = path
        self.metadata = metadata
        _validate_hazard_metadata(metadata)

    def serialize(self, data):
        """
        Write a sequence of hazard curves to the specified file.

        :param data:
            Iterable of hazard curve data. Each datum must be an object with
            the following attributes:

            * poes: A list of probability of exceedence values (floats).
            * location: An object representing the location of the curve; must
              have `x` and `y` to represent lon and lat, respectively.
        """
        gml_ns = nrmllib.SERIALIZE_NS_MAP['gml']

        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)

            hazard_curves = etree.SubElement(root, 'hazardCurves')

            _set_metadata(hazard_curves, self.metadata, _ATTR_MAP)

            imls_elem = etree.SubElement(hazard_curves, 'IMLs')
            imls_elem.text = ' '.join([str(x) for x in self.metadata['imls']])

            for hc in data:
                hc_elem = etree.SubElement(hazard_curves, 'hazardCurve')
                gml_point = etree.SubElement(hc_elem, '{%s}Point' % gml_ns)
                gml_pos = etree.SubElement(gml_point, '{%s}pos' % gml_ns)
                gml_pos.text = '%s %s' % (hc.location.x, hc.location.y)
                poes_elem = etree.SubElement(hc_elem, 'poEs')
                poes_elem.text = ' '.join([str(x) for x in hc.poes])

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))


class EventBasedGMFXMLWriter(object):
    """
    :param str path:
        File path (including filename) for XML results to be saved to.
    :param str sm_lt_path:
        Source model logic tree branch identifier of the logic tree realization
        which produced this collection of ground motion fields.
    :param gsim_lt_path:
        GSIM logic tree branch identifier of the logic tree realization which
        produced this collection of ground motion fields.
    """

    def __init__(self, path, sm_lt_path, gsim_lt_path):
        self.path = path
        self.sm_lt_path = sm_lt_path
        self.gsim_lt_path = gsim_lt_path

    def serialize(self, data):
        """
        Serialize a collection of ground motion fields to XML.

        :param data:
            An iterable of "GMF set" objects.
            Each "GMF set" object should:

            * have an `investigation_time` attribute
            * be iterable, yielding a sequence of "GMF" objects

            Each "GMF" object should:

            * have an `imt` attribute
            * have an `sa_period` attribute (only if `imt` is 'SA')
            * have an `sa_damping` attribute (only if `imt` is 'SA')
            * be iterable, yielding a sequence of "GMF node" objects

            Each "GMF node" object should have:

            * an `iml` attribute (to indicate the ground motion value
            * `lon` and `lat` attributes (to indicate the geographical location
              of the ground motion field
        """
        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)

            if self.sm_lt_path is not None and self.gsim_lt_path is not None:
                # A normal GMF collection
                gmf_container = etree.SubElement(root, 'gmfCollection')
                gmf_container.set(SM_TREE_PATH, self.sm_lt_path)
                gmf_container.set(GSIM_TREE_PATH, self.gsim_lt_path)
            else:
                # A collection of GMFs for a complete logic tree
                # In this case, we should only have a single <gmfSet>,
                # containing all ground motion fields.
                # NOTE: In this case, there is no need for a <gmfCollection>
                # element; instead, we just write the single <gmfSet>
                # underneath the root <nrml> element.
                gmf_container = root

            for gmf_set in data:
                gmf_set_elem = etree.SubElement(gmf_container, 'gmfSet')
                gmf_set_elem.set(
                    'investigationTime', str(gmf_set.investigation_time))

                for gmf in gmf_set:
                    gmf_elem = etree.SubElement(gmf_set_elem, 'gmf')
                    gmf_elem.set('IMT', gmf.imt)
                    if gmf.imt == 'SA':
                        gmf_elem.set('saPeriod', str(gmf.sa_period))
                        gmf_elem.set('saDamping', str(gmf.sa_damping))

                    for gmf_node in gmf:
                        node_elem = etree.SubElement(gmf_elem, 'node')
                        node_elem.set('iml', str(gmf_node.iml))
                        node_elem.set('lon', str(gmf_node.location.x))
                        node_elem.set('lat', str(gmf_node.location.y))

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))


class SESXMLWriter(object):
    """
    :param str path:
        File path (including filename) for XML results to be saved to.
    :param str sm_lt_path:
        Source model logic tree branch identifier of the logic tree realization
        which produced this collection of stochastic event sets.
    :param gsim_lt_path:
        GSIM logic tree branch identifier of the logic tree realization which
        produced this collection of stochastic event sets.
    """

    def __init__(self, path, sm_lt_path, gsim_lt_path):
        self.path = path
        self.sm_lt_path = sm_lt_path
        self.gsim_lt_path = gsim_lt_path

    def serialize(self, data):
        """
        Serialize a collection of stochastic event sets to XML.

        :param data:
            An iterable of "SES" ("Stochastic Event Set") objects.
            Each "SES" object should:

            * have an `investigation_time` attribute
            * be iterable, yielding a sequence of "rupture" objects

            Each "rupture" should have the following attributes:
            * `magnitude`
            * `strike`
            * `dip`
            * `rake`
            * `tectonic_region_type`
            * `is_from_fault_source` (a `bool`)
            * `lons`
            * `lats`
            * `depths`

            If `is_from_fault_source` is `True`, the rupture originated from a
            simple or complex fault sources. In this case, `lons`, `lats`, and
            `depths` should all be 2D arrays (of uniform shape). These
            coordinate triples represent nodes of the rupture mesh.

            If `is_from_fault_source` is `False`, the rupture originated from a
            point or area source. In this case, the rupture is represented by a
            quadrilateral planar surface. This planar surface is defined by 3D
            vertices. In this case, the rupture should have the following
            attributes:

            * `top_left_corner`
            * `top_right_corner`
            * `bottom_right_corner`
            * `bottom_left_corner`

            Each of these should be a triple of `lon`, `lat`, `depth`.
        """
        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)

            if self.sm_lt_path is not None and self.gsim_lt_path is not None:
                # A normal stochastic event set collection
                ses_container = etree.SubElement(
                    root, 'stochasticEventSetCollection')

                ses_container.set(SM_TREE_PATH, self.sm_lt_path)
                ses_container.set(GSIM_TREE_PATH, self.gsim_lt_path)
            else:
                # A stochastic event set collection for the complete logic tree
                # In this case, we should only have a single stochastic event
                # set.
                # NOTE: In this case, there is no need for a
                # `stochasticEventSetCollection` tag.
                # Write the _single_ stochastic event set directly under the
                # root element.
                ses_container = root
                # NOTE: The code below is written to expect 1 or more SESs in
                # `data`. Again, there will only be one in this case.

            for ses in data:
                ses_elem = etree.SubElement(
                    ses_container, 'stochasticEventSet')
                ses_elem.set('investigationTime', str(ses.investigation_time))

                for rupture in ses:
                    rup_elem = etree.SubElement(ses_elem, 'rupture')
                    rup_elem.set('magnitude', str(rupture.magnitude))
                    rup_elem.set('strike', str(rupture.strike))
                    rup_elem.set('dip', str(rupture.dip))
                    rup_elem.set('rake', str(rupture.rake))
                    rup_elem.set(
                        'tectonicRegion', str(rupture.tectonic_region_type))

                    if rupture.is_from_fault_source:
                        # rupture is from a simple or complex fault source
                        # the rupture geometry is represented by a mesh of 3D
                        # points
                        self._create_rupture_mesh(rupture, rup_elem)
                    else:
                        # rupture is from a point or area source
                        # the rupture geometry is represented by four 3D corner
                        # points
                        self._create_planar_surface(rupture, rup_elem)

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))

    @staticmethod
    def _create_rupture_mesh(rupture, rup_elem):
        """
        :param rupture:
            See documentation for :meth:`serialize` for more info.
        :param rup_elem:
            A `rupture` :class:`lxml.etree._Element`.
        """
        mesh_elem = etree.SubElement(rup_elem, 'mesh')

        # we assume the mesh components (lons, lats, depths)
        # are of uniform shape
        for i, row in enumerate(rupture.lons):
            for j, col in enumerate(row):
                node_elem = etree.SubElement(mesh_elem, 'node')
                node_elem.set('row', str(i))
                node_elem.set('col', str(j))
                node_elem.set('lon', str(rupture.lons[i][j]))
                node_elem.set('lat', str(rupture.lats[i][j]))
                node_elem.set(
                    'depth', str(rupture.depths[i][j]))

        try:
            # if we never entered the loop above, it's possible
            # that i and j will be undefined
            mesh_elem.set('rows', str(i + 1))
            mesh_elem.set('cols', str(j + 1))
        except NameError:
            raise ValueError('Invalid rupture mesh')

    @staticmethod
    def _create_planar_surface(rupture, rup_elem):
        """
        :param rupture:
            See documentation for :meth:`serialize` for more info.
        :param rup_elem:
            A `rupture` :class:`lxml.etree._Element`.
        """
        ps_elem = etree.SubElement(
            rup_elem, 'planarSurface')

        # create the corner point elements, in the order of:
        # * top left
        # * top right
        # * bottom right
        # * bottom left
        for el_name, corner in (
            ('topLeft', rupture.top_left_corner),
            ('topRight', rupture.top_right_corner),
            ('bottomRight', rupture.bottom_right_corner),
            ('bottomLeft', rupture.bottom_left_corner)):

            corner_elem = etree.SubElement(ps_elem, el_name)
            corner_elem.set('lon', str(corner[0]))
            corner_elem.set('lat', str(corner[1]))
            corner_elem.set('depth', str(corner[2]))


class HazardMapXMLWriter(object):
    """
    :param path:
        File path (including filename) for XML results to be saved to.
    :param metadata:
        The following keyword args are required:

        * investigation_time: Investigation time (in years) defined in the
          calculation which produced these results.
        * imt: Intensity measure type used to compute these hazard curves.
        * poe: The Probability of Exceedance level for which this hazard map
          was produced.

        The following are more or less optional (combinational rules noted
        below where applicable):

        * statistics: 'mean' or 'quantile'
        * quantile_value: Only required if statistics = 'quantile'.
        * smlt_path: String representing the logic tree path which produced
          these curves. Only required for non-statistical curves.
        * gsimlt_path: String represeting the GSIM logic tree path which
          produced these curves. Only required for non-statisical curves.
        * sa_period: Only used with imt = 'SA'.
        * sa_damping: Only used with imt = 'SA'.
    """

    def __init__(self, path, **metadata):
        self.path = path
        self.metadata = metadata
        _validate_hazard_metadata(metadata)

    def serialize(self, data):
        """
        Write a sequence of hazard map data to the specified file.

        :param data:
            Iterable of hazard map data. Each datum should be a triple of
            (lon, lat, iml) values.
        """

        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)

            hazard_map = etree.SubElement(root, 'hazardMap')

            _set_metadata(hazard_map, self.metadata, _ATTR_MAP)

            for lon, lat, iml in data:
                node = etree.SubElement(hazard_map, 'node')
                node.set('lon', str(lon))
                node.set('lat', str(lat))
                node.set('iml', str(iml))

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))


class DisaggXMLWriter(object):
    """
    :param path:
        File path (including filename) for XML results to be saved to.
    :param metadata:
        The following keyword args are required:

        * investigation_time: Investigation time (in years) defined in the
          calculation which produced these results.
        * imt: Intensity measure type used to compute these matrices.
        * lon, lat: Longitude and latitude associated with these results.

        The following attributes define dimension context for the result
        matrices:

        * mag_bin_edges: List of magnitude bin edges (floats)
        * dist_bin_edges: List of distance bin edges (floats)
        * lon_bin_edges: List of longitude bin edges (floats)
        * lat_bin_edges: List of latitude bin edges (floats)
        * eps_bin_edges: List of epsilon bin edges (floats)
        * tectonic_region_types: List of tectonic region types (strings)
        * smlt_path: String representing the logic tree path which produced
          these results. Only required for non-statistical results.
        * gsimlt_path: String represeting the GSIM logic tree path which
          produced these results. Only required for non-statistical results.

        The following are optional, depending on the `imt`:

        * sa_period: Only used with imt = 'SA'.
        * sa_damping: Only used with imt = 'SA'.
    """

    #: Maps metadata keywords to XML attribute names for bin edge information
    #: passed to the constructor.
    #: The dict here is an `OrderedDict` so as to give consistent ordering of
    #: result attributes.
    BIN_EDGE_ATTR_MAP = OrderedDict([
        ('mag_bin_edges', 'magBinEdges'),
        ('dist_bin_edges', 'distBinEdges'),
        ('lon_bin_edges', 'lonBinEdges'),
        ('lat_bin_edges', 'latBinEdges'),
        ('eps_bin_edges', 'epsBinEdges'),
        ('tectonic_region_types', 'tectonicRegionTypes'),
    ])

    DIM_LABEL_TO_BIN_EDGE_MAP = dict([
        ('Mag', 'mag_bin_edges'),
        ('Dist', 'dist_bin_edges'),
        ('Lon', 'lon_bin_edges'),
        ('Lat', 'lat_bin_edges'),
        ('Eps', 'eps_bin_edges'),
        ('TRT', 'tectonic_region_types'),
    ])

    def __init__(self, path, **metadata):
        self.path = path
        self.metadata = metadata
        _validate_hazard_metadata(self.metadata)

    def serialize(self, data):
        """
        :param data:
            A sequence of data where each datum has the following attributes:

            * matrix: N-dimensional numpy array containing the disaggregation
              histogram.
            * dim_labels: A list of strings which label the dimensions of a
              given histogram. For example, for a Magnitude-Distance-Epsilon
              histogram, we would expect `dim_labels` to be
              ``['Mag', 'Dist', 'Eps']``.
            * poe: The disaggregation Probability of Exceedance level for which
              these results were produced.
            * iml: Intensity measure level, interpolated from the source hazard
              curve at the given ``poe``.
        """

        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)

            diss_matrices = etree.SubElement(root, 'disaggMatrices')

            _set_metadata(diss_matrices, self.metadata, _ATTR_MAP)

            transform = lambda val: ', '.join([str(x) for x in val])
            _set_metadata(diss_matrices, self.metadata, self.BIN_EDGE_ATTR_MAP,
                          transform=transform)

            for result in data:
                diss_matrix = etree.SubElement(diss_matrices, 'disaggMatrix')

                # Check that we have bin edges defined for each dimension label
                # (mag, dist, lon, lat, eps, TRT)
                for label in result.dim_labels:
                    bin_edge_attr = self.DIM_LABEL_TO_BIN_EDGE_MAP.get(label)
                    assert self.metadata.get(bin_edge_attr) is not None, (
                        "Writer is missing '%s' metadata" % bin_edge_attr
                    )

                result_type = ','.join(result.dim_labels)
                diss_matrix.set('type', result_type)

                dims = ','.join([str(x) for x in result.matrix.shape])
                diss_matrix.set('dims', dims)

                diss_matrix.set('poE', str(result.poe))
                diss_matrix.set('iml', str(result.iml))

                for idxs, value in utils.ndenumerate(result.matrix):
                    prob = etree.SubElement(diss_matrix, 'prob')

                    index = ','.join([str(x) for x in idxs])
                    prob.set('index', index)
                    prob.set('value', str(value))

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))


class ScenarioGMFXMLWriter(object):
    """
    :param str path:
        File path (including filename) for XML results to be saved to.
    """

    def __init__(self, path):
        self.path = path

    def serialize(self, data):
        """
        Serialize a collection of ground motion fields to XML.

        :param data:
            An iterable of "GMFScenario" objects.

            Each "GMFScenario" object should:

            * have an `imt` attribute
            * have an `sa_period` attribute (only if `imt` is 'SA')
            * have an `sa_damping` attribute (only if `imt` is 'SA')
            * be iterable, yielding a sequence of "GMF node" objects

            Each "GMF node" object should have:

            * an `iml` attribute (to indicate the ground motion value
            * `lon` and `lat` attributes (to indicate the geographical location
              of the ground motion field
        """
        with open(self.path, 'w') as fh:
            root = etree.Element('nrml',
                                 nsmap=nrmllib.SERIALIZE_NS_MAP)
            gmfset = etree.SubElement(root, 'gmfSet')
            for gmf in data:
                gmf_elem = etree.SubElement(gmfset, 'gmf')
                gmf_elem.set('IMT', gmf.imt)
                if gmf.imt == 'SA':
                    gmf_elem.set('saPeriod', str(gmf.sa_period))
                    gmf_elem.set('saDamping', str(gmf.sa_damping))
                for gmf_node in gmf:
                    node_elem = etree.SubElement(gmf_elem, 'node')
                    node_elem.set('iml', str(gmf_node.iml))
                    node_elem.set('lon', str(gmf_node.location.x))
                    node_elem.set('lat', str(gmf_node.location.y))

            fh.write(etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding='UTF-8'))
